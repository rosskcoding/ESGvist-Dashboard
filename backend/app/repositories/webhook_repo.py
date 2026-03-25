from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.db.models.webhook import WebhookDelivery, WebhookEndpoint


class WebhookRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_endpoint(self, **kwargs) -> WebhookEndpoint:
        endpoint = WebhookEndpoint(**kwargs)
        self.session.add(endpoint)
        await self.session.flush()
        return endpoint

    async def get_endpoint(self, endpoint_id: int) -> WebhookEndpoint | None:
        result = await self.session.execute(select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id))
        return result.scalar_one_or_none()

    async def get_endpoint_or_raise(self, endpoint_id: int) -> WebhookEndpoint:
        endpoint = await self.get_endpoint(endpoint_id)
        if not endpoint:
            raise AppError("NOT_FOUND", 404, f"Webhook endpoint {endpoint_id} not found")
        return endpoint

    async def list_endpoints(self, organization_id: int) -> list[WebhookEndpoint]:
        result = await self.session.execute(
            select(WebhookEndpoint)
            .where(WebhookEndpoint.organization_id == organization_id)
            .order_by(WebhookEndpoint.id.desc())
        )
        return list(result.scalars().all())

    async def delete_endpoint(self, endpoint: WebhookEndpoint) -> None:
        await self.session.delete(endpoint)
        await self.session.flush()

    async def create_delivery(self, **kwargs) -> WebhookDelivery:
        delivery = WebhookDelivery(**kwargs)
        self.session.add(delivery)
        await self.session.flush()
        return delivery

    async def get_delivery_or_raise(self, delivery_id: int) -> WebhookDelivery:
        result = await self.session.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
        delivery = result.scalar_one_or_none()
        if not delivery:
            raise AppError("NOT_FOUND", 404, f"Webhook delivery {delivery_id} not found")
        return delivery

    async def list_deliveries(
        self,
        endpoint_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WebhookDelivery], int]:
        total = (
            await self.session.execute(
                select(func.count()).select_from(WebhookDelivery).where(
                    WebhookDelivery.webhook_endpoint_id == endpoint_id
                )
            )
        ).scalar_one()
        result = await self.session.execute(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_endpoint_id == endpoint_id)
            .order_by(WebhookDelivery.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def list_due_retry_deliveries(
        self,
        now: datetime,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        """Atomically claim due webhook retries.

        Uses FOR UPDATE SKIP LOCKED on PostgreSQL. Transitions claimed
        deliveries to 'retrying' so other workers skip them.
        """
        q = (
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status == "failed",
                WebhookDelivery.next_retry_at.is_not(None),
                WebhookDelivery.next_retry_at <= now,
            )
            .order_by(WebhookDelivery.next_retry_at, WebhookDelivery.id)
            .limit(limit)
        )
        dialect = self.session.bind.dialect.name if self.session.bind else ""
        if "postgres" in dialect:
            q = q.with_for_update(skip_locked=True)
        result = await self.session.execute(q)
        deliveries = list(result.scalars().all())

        for d in deliveries:
            d.status = "retrying"
        if deliveries:
            await self.session.flush()
        return deliveries

    async def count_delivery_statuses(self) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(WebhookDelivery.status, func.count())
                .group_by(WebhookDelivery.status)
            )
        ).all()
        return {status: count for status, count in rows}

    async def count_due_retries(self, now: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(WebhookDelivery).where(
                WebhookDelivery.status == "failed",
                WebhookDelivery.next_retry_at.is_not(None),
                WebhookDelivery.next_retry_at <= now,
            )
        )
        return result.scalar_one()
