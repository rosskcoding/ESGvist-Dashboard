from datetime import datetime, timedelta, timezone

import pytest

from app.db.models.notification import Notification
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.db.models.webhook import WebhookDelivery, WebhookEndpoint
from app.workers.job_runner import JobRunner
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_job_runner_retries_due_webhook_deliveries():
    async with TestSessionLocal() as session:
        user = User(email="admin+runner@org.com", password_hash="hash", full_name="Runner Admin")
        session.add(user)
        await session.flush()

        org = Organization(name="Runner Org", status="active", setup_completed=True)
        session.add(org)
        await session.flush()

        session.add(
            RoleBinding(
                user_id=user.id,
                role="admin",
                scope_type="organization",
                scope_id=org.id,
                created_by=user.id,
            )
        )
        endpoint = WebhookEndpoint(
            organization_id=org.id,
            url="https://example.com/hooks/retry",
            secret="retry-secret",
            events=["project.published"],
            is_active=True,
        )
        session.add(endpoint)
        await session.flush()

        delivery = WebhookDelivery(
            webhook_endpoint_id=endpoint.id,
            event_type="project.published",
            payload={"event": "project.published", "data": {"projectId": 1}},
            status="failed",
            http_status=500,
            response_body="temporary failure",
            attempt=1,
            max_attempts=5,
            next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(delivery)
        await session.commit()

    async def fake_sender(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int):
        return 202, "accepted"

    runner = JobRunner(session_factory=TestSessionLocal, webhook_sender=fake_sender)
    result = await runner.run_webhook_retries()

    assert result == {
        "checked": 1,
        "retried": 1,
        "succeeded": 1,
        "failed": 0,
        "dead_letter": 0,
    }

    async with TestSessionLocal() as session:
        refreshed = await session.get(WebhookDelivery, 1)
        assert refreshed.status == "success"
        assert refreshed.attempt == 2
        assert refreshed.delivered_at is not None


@pytest.mark.asyncio
async def test_job_runner_all_includes_dead_letter_notifications():
    async with TestSessionLocal() as session:
        user = User(email="admin+runner-all@org.com", password_hash="hash", full_name="Runner Admin All")
        session.add(user)
        await session.flush()

        org = Organization(name="Runner Org All", status="active", setup_completed=True)
        session.add(org)
        await session.flush()

        session.add(
            RoleBinding(
                user_id=user.id,
                role="admin",
                scope_type="organization",
                scope_id=org.id,
                created_by=user.id,
            )
        )
        endpoint = WebhookEndpoint(
            organization_id=org.id,
            url="https://example.com/hooks/dead-letter",
            secret="dead-letter-secret",
            events=["project.published"],
            is_active=True,
        )
        session.add(endpoint)
        await session.flush()

        delivery = WebhookDelivery(
            webhook_endpoint_id=endpoint.id,
            event_type="project.published",
            payload={"event": "project.published", "data": {"projectId": 2}},
            status="failed",
            http_status=500,
            response_body="still failing",
            attempt=4,
            max_attempts=5,
            next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        session.add(delivery)
        await session.commit()

    async def failing_sender(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int):
        return 500, "still failing"

    runner = JobRunner(session_factory=TestSessionLocal, webhook_sender=failing_sender)
    result = await runner.run_all()

    assert result["webhook_retries"]["dead_letter"] == 1
    assert "sla_check" in result
    assert "project_deadlines" in result

    async with TestSessionLocal() as session:
        delivery = await session.get(WebhookDelivery, 1)
        assert delivery.status == "dead_letter"
        notifications = (await session.execute(
            Notification.__table__.select().where(Notification.type == "webhook_dead_letter")
        )).all()
        assert notifications
