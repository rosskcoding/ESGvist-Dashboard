import pytest

from app.api.routes.health import _check_database
from app.core.config import settings
from app.core.metrics import HEALTH_CHECK_RESULTS, NON_BLOCKING_FAILURES
from app.db.models.user import User
from app.events.bus import DataPointSubmitted, EventBus
from app.services.notification_service import NotificationService


class _FakeLogger:
    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def warning(self, event: str, **kwargs):
        self.calls.append(("warning", event, kwargs))

    def error(self, event: str, **kwargs):
        self.calls.append(("error", event, kwargs))


class _FailingEmailSender:
    async def send(self, **kwargs):
        raise RuntimeError("smtp unavailable")


class _BrokenSession:
    async def execute(self, *args, **kwargs):
        raise RuntimeError("db unavailable")


@pytest.mark.asyncio
async def test_notification_service_logs_and_counts_silent_email_failure(monkeypatch):
    from app.services import notification_service as notification_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="notification_service",
        operation="email_delivery",
    )._value.get()
    monkeypatch.setattr(notification_module, "logger", fake_logger)
    monkeypatch.setattr(settings, "email_fail_silently", True)

    service = NotificationService(repo=object(), email_sender=_FailingEmailSender())
    user = User(
        id=101,
        email="collector@example.com",
        password_hash="hash",
        full_name="Collector",
        is_active=True,
    )

    sent, sent_at = await service._deliver_email(
        user=user,
        channel="both",
        title="Assignment created",
        message="Check the new assignment",
    )

    after = NON_BLOCKING_FAILURES.labels(
        component="notification_service",
        operation="email_delivery",
    )._value.get()
    assert sent is False
    assert sent_at is None
    assert after == before + 1
    assert fake_logger.calls[0][1] == "notification_email_delivery_failed"
    assert fake_logger.calls[0][2]["user_id"] == 101
    assert fake_logger.calls[0][2]["fail_silently"] is True


@pytest.mark.asyncio
async def test_event_bus_logs_and_counts_handler_failure(monkeypatch):
    from app.events import bus as event_bus_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="event_bus",
        operation="handler",
    )._value.get()
    monkeypatch.setattr(event_bus_module, "logger", fake_logger)

    bus = EventBus()

    async def failing_handler(event):
        raise RuntimeError(f"failed for {event.data_point_id}")

    bus.subscribe(DataPointSubmitted, failing_handler)
    await bus.publish(DataPointSubmitted(data_point_id=77, submitted_by=12, organization_id=9))

    after = NON_BLOCKING_FAILURES.labels(
        component="event_bus",
        operation="handler",
    )._value.get()
    assert after == before + 1
    assert fake_logger.calls[0][0] == "error"
    assert fake_logger.calls[0][1] == "event_handler_failed"
    assert fake_logger.calls[0][2]["event_type"] == "DataPointSubmitted"
    assert fake_logger.calls[0][2]["handler"] == "failing_handler"


@pytest.mark.asyncio
async def test_health_check_logs_and_counts_database_failure(monkeypatch):
    from app.api.routes import health as health_module

    fake_logger = _FakeLogger()
    before = HEALTH_CHECK_RESULTS.labels(
        dependency="database",
        status="error",
    )._value.get()
    monkeypatch.setattr(health_module, "logger", fake_logger)

    status = await _check_database(_BrokenSession())

    after = HEALTH_CHECK_RESULTS.labels(
        dependency="database",
        status="error",
    )._value.get()
    assert status == "error"
    assert after == before + 1
    assert fake_logger.calls[0][1] == "health_check_failed"
    assert fake_logger.calls[0][2]["dependency"] == "database"
