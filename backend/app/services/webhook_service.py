import asyncio
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import httpx
import structlog
from sqlalchemy import select

from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.metrics import record_non_blocking_failure
from app.db.models.role_binding import RoleBinding
from app.db.models.webhook import WebhookDelivery, WebhookEndpoint
from app.repositories.audit_repo import AuditRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.webhook_repo import WebhookRepository
from app.schemas.webhooks import (
    WebhookDeliveryListOut,
    WebhookDeliveryOut,
    WebhookEndpointCreate,
    WebhookEndpointCreateOut,
    WebhookEndpointOut,
    WebhookEndpointUpdate,
    WebhookListOut,
    WebhookTestOut,
)
from app.services.notification_service import NotificationService

SUPPORTED_WEBHOOK_EVENTS = {
    "data_point.submitted",
    "data_point.approved",
    "data_point.rejected",
    "data_point.needs_revision",
    "data_point.rolled_back",
    "project.started",
    "project.in_review",
    "project.published",
    "evidence.created",
    "boundary.changed",
    "completeness.updated",
}
RETRY_DELAYS_SECONDS = [1, 2, 4, 8, 16]
logger = structlog.get_logger("app.webhooks")


async def send_webhook_request(
    url: str,
    payload: dict,
    headers: dict[str, str],
    timeout_seconds: int,
) -> tuple[int, str]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload, headers=headers)
    return response.status_code, response.text


class WebhookService:
    def __init__(
        self,
        repo: WebhookRepository,
        audit_repo: AuditRepository | None = None,
        notification_repo: NotificationRepository | None = None,
        sender: Callable[[str, dict, dict[str, str], int], Awaitable[tuple[int, str]]]
        | None = None,
    ):
        self.repo = repo
        self.audit_repo = audit_repo
        self.notification_service = (
            NotificationService(notification_repo) if notification_repo else None
        )
        self.sender = sender or send_webhook_request

    @staticmethod
    def _is_forbidden_ip(address: str) -> bool:
        ip = ipaddress.ip_address(address)
        return any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            )
        )

    @classmethod
    async def _resolve_host_addresses(cls, hostname: str, port: int | None) -> set[str]:
        lookup_port = port or 443
        infos = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            lookup_port,
            type=socket.SOCK_STREAM,
        )
        addresses: set[str] = set()
        for family, _socktype, _proto, _canonname, sockaddr in infos:
            if family == socket.AF_INET:
                addresses.add(sockaddr[0])
            elif family == socket.AF_INET6:
                addresses.add(sockaddr[0])
        return addresses

    @classmethod
    async def _validate_outbound_url(cls, url: str, *, resolve_hostname: bool) -> str:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if not hostname:
            raise AppError("INVALID_WEBHOOK_URL", 422, "Webhook URL hostname is required")
        normalized_host = hostname.strip().lower()
        if normalized_host == "localhost" or normalized_host.endswith(".localhost"):
            raise AppError(
                "WEBHOOK_URL_FORBIDDEN",
                422,
                "Webhook URL cannot target localhost",
            )

        try:
            if cls._is_forbidden_ip(normalized_host):
                raise AppError(
                    "WEBHOOK_URL_FORBIDDEN",
                    422,
                    "Webhook URL cannot target private or local network addresses",
                )
            return url
        except ValueError:
            pass

        if not resolve_hostname:
            return url

        try:
            resolved_addresses = await cls._resolve_host_addresses(normalized_host, parsed.port)
        except socket.gaierror as exc:
            raise AppError(
                "WEBHOOK_URL_RESOLUTION_FAILED",
                422,
                f"Webhook hostname '{normalized_host}' could not be resolved",
            ) from exc

        if not resolved_addresses:
            raise AppError(
                "WEBHOOK_URL_RESOLUTION_FAILED",
                422,
                f"Webhook hostname '{normalized_host}' did not resolve to any address",
            )

        blocked = sorted(address for address in resolved_addresses if cls._is_forbidden_ip(address))
        if blocked:
            raise AppError(
                "WEBHOOK_URL_FORBIDDEN",
                422,
                "Webhook URL resolved to private or local network addresses",
            )

        return url

    @staticmethod
    def _classify_delivery_exception(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, AppError):
            return "delivery_policy_rejected", getattr(exc, "code", "APP_ERROR")
        if isinstance(exc, httpx.TimeoutException):
            return "delivery_timeout", type(exc).__name__
        if isinstance(exc, httpx.NetworkError):
            return "delivery_network_error", type(exc).__name__
        if isinstance(exc, httpx.HTTPError):
            return "delivery_http_client_error", type(exc).__name__
        return "delivery_unexpected_error", type(exc).__name__

    @staticmethod
    def _require_admin(ctx: RequestContext) -> int:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can manage webhook endpoints")
        if ctx.organization_id is None:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        return ctx.organization_id

    @staticmethod
    def _normalize_events(events: list[str]) -> list[str]:
        normalized = sorted({event.strip() for event in events if event and event.strip()})
        if not normalized:
            raise AppError("WEBHOOK_EVENTS_REQUIRED", 422, "At least one webhook event is required")
        invalid = [event for event in normalized if event not in SUPPORTED_WEBHOOK_EVENTS]
        if invalid:
            raise AppError(
                "UNSUPPORTED_WEBHOOK_EVENT",
                422,
                f"Unsupported webhook events: {', '.join(invalid)}",
            )
        return normalized

    @staticmethod
    def _serialize_endpoint(
        endpoint: WebhookEndpoint, *, include_secret: bool = False
    ) -> WebhookEndpointOut | WebhookEndpointCreateOut:
        base = {
            "id": endpoint.id,
            "url": endpoint.url,
            "events": endpoint.events or [],
            "is_active": endpoint.is_active,
            "secret_last4": endpoint.secret[-4:],
            "created_at": endpoint.created_at,
            "updated_at": endpoint.updated_at,
        }
        if include_secret:
            return WebhookEndpointCreateOut(**base, secret=endpoint.secret)
        return WebhookEndpointOut(**base)

    @staticmethod
    def _serialize_delivery(delivery: WebhookDelivery) -> WebhookDeliveryOut:
        return WebhookDeliveryOut(
            id=delivery.id,
            event_type=delivery.event_type,
            payload=delivery.payload,
            status=delivery.status,
            http_status=delivery.http_status,
            response_body=delivery.response_body,
            attempt=delivery.attempt,
            max_attempts=delivery.max_attempts,
            next_retry_at=delivery.next_retry_at,
            created_at=delivery.created_at,
            delivered_at=delivery.delivered_at,
        )

    async def _audit(
        self,
        *,
        ctx: RequestContext | None,
        action: str,
        entity_id: int | None,
        organization_id: int,
        changes: dict | None = None,
    ) -> None:
        if not self.audit_repo or ctx is None:
            return
        await self.audit_repo.log(
            entity_type="WebhookEndpoint",
            entity_id=entity_id,
            action=action,
            user_id=ctx.user_id,
            organization_id=organization_id,
            changes=changes,
            performed_by_platform_admin=ctx.is_platform_admin,
        )

    async def _get_endpoint_for_ctx(self, endpoint_id: int, ctx: RequestContext) -> WebhookEndpoint:
        endpoint = await self.repo.get_endpoint_or_raise(endpoint_id)
        org_id = self._require_admin(ctx)
        if endpoint.organization_id != org_id and not ctx.is_platform_admin:
            raise AppError("FORBIDDEN", 403, "Webhook endpoint belongs to another organization")
        return endpoint

    async def list_endpoints(self, ctx: RequestContext) -> WebhookListOut:
        org_id = self._require_admin(ctx)
        items = await self.repo.list_endpoints(org_id)
        return WebhookListOut(
            items=[self._serialize_endpoint(item) for item in items], total=len(items)
        )

    async def create_endpoint(
        self, payload: WebhookEndpointCreate, ctx: RequestContext
    ) -> WebhookEndpointCreateOut:
        org_id = self._require_admin(ctx)
        url = await self._validate_outbound_url(str(payload.url), resolve_hostname=True)
        endpoint = await self.repo.create_endpoint(
            organization_id=org_id,
            url=url,
            secret=payload.secret or secrets.token_hex(16),
            events=self._normalize_events(payload.events),
            is_active=payload.is_active,
        )
        await self.repo.session.refresh(endpoint)
        await self._audit(
            ctx=ctx,
            action="webhook_endpoint_created",
            entity_id=endpoint.id,
            organization_id=org_id,
            changes={
                "url": endpoint.url,
                "events": endpoint.events,
                "is_active": endpoint.is_active,
            },
        )
        return self._serialize_endpoint(endpoint, include_secret=True)

    async def update_endpoint(
        self,
        endpoint_id: int,
        payload: WebhookEndpointUpdate,
        ctx: RequestContext,
    ) -> WebhookEndpointOut:
        endpoint = await self._get_endpoint_for_ctx(endpoint_id, ctx)
        changes = payload.model_dump(exclude_unset=True)
        if "url" in changes:
            endpoint.url = await self._validate_outbound_url(
                str(payload.url),
                resolve_hostname=True,
            )
            changes["url"] = endpoint.url
        if "events" in changes and payload.events is not None:
            endpoint.events = self._normalize_events(payload.events)
            changes["events"] = endpoint.events
        if "secret" in changes and payload.secret is not None:
            endpoint.secret = payload.secret
            changes["secret_rotated"] = True
            changes.pop("secret", None)
        if "is_active" in changes:
            endpoint.is_active = payload.is_active
        await self.repo.session.flush()
        await self.repo.session.refresh(endpoint)
        await self._audit(
            ctx=ctx,
            action="webhook_endpoint_updated",
            entity_id=endpoint.id,
            organization_id=endpoint.organization_id,
            changes=changes,
        )
        return self._serialize_endpoint(endpoint)

    async def delete_endpoint(self, endpoint_id: int, ctx: RequestContext) -> dict:
        endpoint = await self._get_endpoint_for_ctx(endpoint_id, ctx)
        org_id = endpoint.organization_id
        await self.repo.delete_endpoint(endpoint)
        await self._audit(
            ctx=ctx,
            action="webhook_endpoint_deleted",
            entity_id=endpoint_id,
            organization_id=org_id,
        )
        return {"id": endpoint_id, "deleted": True}

    async def list_deliveries(
        self,
        endpoint_id: int,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20,
    ) -> WebhookDeliveryListOut:
        endpoint = await self._get_endpoint_for_ctx(endpoint_id, ctx)
        items, total = await self.repo.list_deliveries(endpoint.id, page, page_size)
        return WebhookDeliveryListOut(
            items=[self._serialize_delivery(item) for item in items],
            total=total,
        )

    @staticmethod
    def _build_signature(secret: str, timestamp: str, payload: dict) -> str:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        digest = hmac.new(
            secret.encode("utf-8"), f"{timestamp}.{body}".encode(), hashlib.sha256
        )
        return digest.hexdigest()

    async def _notify_dead_letter(
        self, endpoint: WebhookEndpoint, delivery: WebhookDelivery
    ) -> None:
        if not self.notification_service:
            return
        result = await self.repo.session.execute(
            select(RoleBinding.user_id).where(
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == endpoint.organization_id,
                RoleBinding.role == "admin",
            )
        )
        admin_ids = sorted({row[0] for row in result.all()})
        for user_id in admin_ids:
            await self.notification_service.notify(
                user_id=user_id,
                org_id=endpoint.organization_id,
                type="webhook_dead_letter",
                title="Webhook delivery failed",
                message=(
                    f"Webhook endpoint #{endpoint.id} failed for event '{delivery.event_type}' "
                    f"after {delivery.attempt} attempts."
                ),
                entity_type="WebhookEndpoint",
                entity_id=endpoint.id,
                severity="critical",
                channel="both",
            )

    async def _perform_delivery_attempt(
        self,
        endpoint: WebhookEndpoint,
        delivery: WebhookDelivery,
    ) -> WebhookDelivery:
        attempt_index = delivery.attempt + 1
        timestamp = datetime.now(UTC).isoformat()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ESGvist-Webhooks/1.0",
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": self._build_signature(
                endpoint.secret, timestamp, delivery.payload
            ),
        }
        try:
            await self._validate_outbound_url(endpoint.url, resolve_hostname=True)
            http_status, response_body = await self.sender(
                endpoint.url, delivery.payload, headers, 10
            )
            response_preview = response_body[:2000] if response_body else None
            if 200 <= http_status < 300:
                delivery.status = "success"
                delivery.http_status = http_status
                delivery.response_body = response_preview
                delivery.attempt = attempt_index
                delivery.next_retry_at = None
                delivery.delivered_at = datetime.now(UTC)
                await self.repo.session.flush()
                return delivery
        except Exception as exc:
            failure_operation, failure_reason = self._classify_delivery_exception(exc)
            record_non_blocking_failure("webhook_service", failure_operation)
            logger.warning(
                f"webhook_{failure_operation}",
                webhook_endpoint_id=endpoint.id,
                organization_id=endpoint.organization_id,
                delivery_id=delivery.id,
                event_type=delivery.event_type,
                attempt=attempt_index,
                failure_reason=failure_reason,
                exception_type=type(exc).__name__,
                exc_info=True,
            )
            http_status = None
            response_preview = str(exc)[:2000]

        delivery.http_status = http_status
        delivery.response_body = response_preview
        delivery.attempt = attempt_index
        if attempt_index >= delivery.max_attempts:
            delivery.status = "dead_letter"
            delivery.next_retry_at = None
            await self.repo.session.flush()
            await self._notify_dead_letter(endpoint, delivery)
            return delivery

        delivery.status = "failed"
        delivery.next_retry_at = datetime.now(UTC) + timedelta(
            seconds=RETRY_DELAYS_SECONDS[attempt_index - 1]
        )
        await self.repo.session.flush()
        return delivery

    async def _deliver_to_endpoint(
        self,
        endpoint: WebhookEndpoint,
        *,
        event_type: str,
        payload: dict,
        inline_retry: bool,
    ) -> WebhookDelivery:
        delivery = await self.repo.create_delivery(
            webhook_endpoint_id=endpoint.id,
            event_type=event_type,
            payload=payload,
            status="pending",
            max_attempts=len(RETRY_DELAYS_SECONDS),
        )
        delivery = await self._perform_delivery_attempt(endpoint, delivery)
        if inline_retry:
            while delivery.status == "failed":
                delivery = await self._perform_delivery_attempt(endpoint, delivery)
        return delivery

    async def trigger_test(self, endpoint_id: int, ctx: RequestContext) -> WebhookTestOut:
        endpoint = await self._get_endpoint_for_ctx(endpoint_id, ctx)
        payload = {
            "event": "webhook.test",
            "timestamp": datetime.now(UTC).isoformat(),
            "data": {
                "organizationId": endpoint.organization_id,
                "triggeredBy": ctx.user_id,
                "endpointId": endpoint.id,
            },
        }
        delivery = await self._deliver_to_endpoint(
            endpoint,
            event_type="webhook.test",
            payload=payload,
            inline_retry=True,
        )
        await self._audit(
            ctx=ctx,
            action="webhook_test_triggered",
            entity_id=endpoint.id,
            organization_id=endpoint.organization_id,
            changes={"delivery_id": delivery.id, "status": delivery.status},
        )
        return WebhookTestOut(delivery=self._serialize_delivery(delivery))

    async def deliver_event(
        self, organization_id: int, event_type: str, payload: dict
    ) -> list[WebhookDeliveryOut]:
        endpoints = [
            endpoint
            for endpoint in await self.repo.list_endpoints(organization_id)
            if endpoint.is_active and event_type in (endpoint.events or [])
        ]
        deliveries = []
        for endpoint in endpoints:
            delivery = await self._deliver_to_endpoint(
                endpoint,
                event_type=event_type,
                payload=payload,
                inline_retry=False,
            )
            deliveries.append(self._serialize_delivery(delivery))
        return deliveries

    async def retry_due_deliveries(self, limit: int = 100) -> dict:
        now = datetime.now(UTC)
        deliveries = await self.repo.list_due_retry_deliveries(now, limit)
        retried = 0
        succeeded = 0
        dead_letters = 0
        failed = 0

        for delivery in deliveries:
            endpoint = await self.repo.get_endpoint_or_raise(delivery.webhook_endpoint_id)
            updated = await self._perform_delivery_attempt(endpoint, delivery)
            retried += 1
            if updated.status == "success":
                succeeded += 1
            elif updated.status == "dead_letter":
                dead_letters += 1
            else:
                failed += 1

        return {
            "checked": len(deliveries),
            "retried": retried,
            "succeeded": succeeded,
            "failed": failed,
            "dead_letter": dead_letters,
        }
