import socket
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models.notification import Notification
from app.db.models.organization import Organization
from app.db.models.role_binding import RoleBinding
from app.db.models.user import User
from app.db.models.webhook import WebhookDelivery, WebhookEndpoint
from app.db.models.worker_lease import WorkerLease
from app.repositories.worker_lease_repo import WorkerLeaseRepository
from app.workers.job_runner import JobRunner
from tests.conftest import TestSessionLocal


@pytest.fixture(autouse=True)
def stub_public_webhook_dns(monkeypatch):
    def fake_getaddrinfo(host: str, port: int, type: int = 0):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", port),
            )
        ]

    monkeypatch.setattr("app.services.webhook_service.socket.getaddrinfo", fake_getaddrinfo)


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
            next_retry_at=datetime.now(UTC) - timedelta(seconds=1),
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
        user = User(
            email="admin+runner-all@org.com",
            password_hash="hash",
            full_name="Runner Admin All",
        )
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
            next_retry_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session.add(delivery)
        await session.commit()

    async def failing_sender(
        url: str, payload: dict, headers: dict[str, str], timeout_seconds: int
    ):
        return 500, "still failing"

    runner = JobRunner(session_factory=TestSessionLocal, webhook_sender=failing_sender)
    result = await runner.run_all()

    assert result["webhook_retries"]["dead_letter"] == 1
    assert "sla_check" in result
    assert "project_deadlines" in result

    async with TestSessionLocal() as session:
        delivery = await session.get(WebhookDelivery, 1)
        assert delivery.status == "dead_letter"
        notifications = (
            await session.execute(
                Notification.__table__.select().where(Notification.type == "webhook_dead_letter")
            )
        ).all()
        assert notifications


@pytest.mark.asyncio
async def test_job_runner_cycle_skips_when_lease_is_held():
    async with TestSessionLocal() as session:
        await WorkerLeaseRepository(session).acquire_or_renew(
            name="worker-primary",
            owner_id="other-runner",
            ttl_seconds=60,
        )
        await session.commit()

    runner = JobRunner(
        session_factory=TestSessionLocal,
        owner_id="this-runner",
        lease_name="worker-primary",
        lease_ttl_seconds=60,
    )
    result = await runner.run_cycle("all")

    assert result["skipped"] is True
    assert result["lease_owner"] == "other-runner"


@pytest.mark.asyncio
async def test_job_runner_cycle_records_worker_lease_state():
    runner = JobRunner(
        session_factory=TestSessionLocal,
        owner_id="worker-status-runner",
        lease_name="status-worker",
        lease_ttl_seconds=60,
    )
    result = await runner.run_cycle("all")

    assert result["skipped"] is False
    assert result["job"] == "all"

    async with TestSessionLocal() as session:
        lease = await session.get(WorkerLease, "status-worker")
        assert lease is not None
        assert lease.owner_id == "worker-status-runner"
        assert lease.last_status == "completed"
        assert lease.last_result is not None


@pytest.mark.asyncio
async def test_job_runner_collect_status_reports_queue_depths():
    async with TestSessionLocal() as session:
        user = User(email="status+runner@org.com", password_hash="hash", full_name="Runner Status")
        session.add(user)
        await session.flush()

        org = Organization(name="Runner Status Org", status="active", setup_completed=True)
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
            url="https://example.com/hooks/status",
            secret="status-secret",
            events=["project.published"],
            is_active=True,
        )
        session.add(endpoint)
        await session.flush()

        session.add(
            WebhookDelivery(
                webhook_endpoint_id=endpoint.id,
                event_type="project.published",
                payload={"event": "project.published", "data": {"projectId": 3}},
                status="failed",
                http_status=500,
                response_body="status failure",
                attempt=1,
                max_attempts=5,
                next_retry_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        await WorkerLeaseRepository(session).acquire_or_renew(
            name="status-active",
            owner_id="runner-status",
            ttl_seconds=60,
        )
        await session.commit()

    status = await JobRunner(
        session_factory=TestSessionLocal, lease_name="status-active"
    ).collect_status()

    assert status["queues"]["webhooks"]["due_retries"] == 1
    assert status["queues"]["webhooks"]["queue_depth"] == 1
    assert any(lease["name"] == "status-active" for lease in status["worker"]["active_leases"])
