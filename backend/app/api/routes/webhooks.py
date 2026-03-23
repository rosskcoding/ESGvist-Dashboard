from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import RequestContext, get_current_context
from app.db.session import get_session
from app.repositories.audit_repo import AuditRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.webhook_repo import WebhookRepository
from app.schemas.webhooks import (
    WebhookDeliveryListOut,
    WebhookEndpointCreate,
    WebhookEndpointCreateOut,
    WebhookEndpointOut,
    WebhookEndpointUpdate,
    WebhookListOut,
    WebhookTestOut,
)
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


def _get_service(session: AsyncSession) -> WebhookService:
    return WebhookService(
        repo=WebhookRepository(session),
        audit_repo=AuditRepository(session),
        notification_repo=NotificationRepository(session),
    )


@router.get("", response_model=WebhookListOut)
async def list_webhooks(
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_endpoints(ctx)


@router.post("", response_model=WebhookEndpointCreateOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: WebhookEndpointCreate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).create_endpoint(payload, ctx)


@router.patch("/{endpoint_id}", response_model=WebhookEndpointOut)
async def update_webhook(
    endpoint_id: int,
    payload: WebhookEndpointUpdate,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).update_endpoint(endpoint_id, payload, ctx)


@router.delete("/{endpoint_id}")
async def delete_webhook(
    endpoint_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).delete_endpoint(endpoint_id, ctx)


@router.get("/{endpoint_id}/deliveries", response_model=WebhookDeliveryListOut)
async def list_webhook_deliveries(
    endpoint_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).list_deliveries(endpoint_id, ctx, page, page_size)


@router.post("/{endpoint_id}/test", response_model=WebhookTestOut)
async def test_webhook(
    endpoint_id: int,
    ctx: RequestContext = Depends(get_current_context),
    session: AsyncSession = Depends(get_session),
):
    return await _get_service(session).trigger_test(endpoint_id, ctx)
