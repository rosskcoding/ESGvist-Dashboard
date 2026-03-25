import httpx
import pytest

from app.api.routes.health import _check_database
from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.core.metrics import HEALTH_CHECK_RESULTS, NON_BLOCKING_FAILURES
from app.db.models.user import User
from app.db.models.webhook import WebhookDelivery, WebhookEndpoint
from app.events.bus import DataPointSubmitted, EventBus
from app.schemas.ai import AIResponse, AskRequest
from app.services.ai_service import AIAssistantService
from app.services.notification_service import NotificationService
from app.services.webhook_service import WebhookService


class _FakeLogger:
    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []

    def warning(self, event: str, **kwargs):
        self.calls.append(("warning", event, kwargs))

    def error(self, event: str, **kwargs):
        self.calls.append(("error", event, kwargs))


class _FailingEmailSender:
    provider_name = "test-failing"

    async def send(self, **kwargs):
        raise RuntimeError("smtp unavailable")


class _BrokenSession:
    async def execute(self, *args, **kwargs):
        raise RuntimeError("db unavailable")


class _FlushOnlySession:
    async def flush(self):
        return None


class _WebhookRepoStub:
    def __init__(self):
        self.session = _FlushOnlySession()


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
    assert fake_logger.calls[0][2]["provider"] == "test-failing"
    assert fake_logger.calls[0][2]["failure_reason"] == "RuntimeError"
    assert fake_logger.calls[0][2]["exception_type"] == "RuntimeError"
    assert fake_logger.calls[0][2]["fail_silently"] is True


@pytest.mark.asyncio
async def test_ai_service_logs_and_counts_provider_timeout_fallback(monkeypatch):
    from app.services import ai_service as ai_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="ai_service",
        operation="provider_timeout",
    )._value.get()
    monkeypatch.setattr(ai_module, "logger", fake_logger)

    class _TimeoutProvider:
        provider_name = "timeout-provider"
        model_name = "timeout-v1"

        async def ask(self, question: str, context: dict) -> AIResponse:
            raise TimeoutError("provider timed out")

    service = AIAssistantService(session=None)
    service.primary_provider = _TimeoutProvider()

    response, model_name, used_fallback = await service._invoke_provider("ask", "What next?", {})

    after = NON_BLOCKING_FAILURES.labels(
        component="ai_service",
        operation="provider_timeout",
    )._value.get()
    assert used_fallback is True
    assert model_name == service.fallback_provider.model_name
    assert response.provider == "static"
    assert after == before + 1
    assert fake_logger.calls[0][1] == "ai_provider_call_failed"
    assert fake_logger.calls[0][2]["provider"] == "timeout-provider"
    assert fake_logger.calls[0][2]["failure_reason"] == "TimeoutError"


@pytest.mark.asyncio
async def test_ai_service_logs_and_counts_stream_timeout_fallback(monkeypatch):
    from app.services import ai_service as ai_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="ai_service",
        operation="stream_timeout",
    )._value.get()
    monkeypatch.setattr(ai_module, "logger", fake_logger)

    class _BrokenLLMClient:
        model = "broken-stream-v1"

        async def generate_stream(self, system_prompt: str, user_message: str):
            raise TimeoutError("stream timed out")
            yield  # pragma: no cover

    monkeypatch.setattr("app.infrastructure.llm_client.build_llm_client", lambda: _BrokenLLMClient())

    service = AIAssistantService(session=None)
    async def _noop_log(**kwargs):
        return None

    service._log = _noop_log  # type: ignore[method-assign]

    prepared = {
        "safe_context": {"organization_id": 9},
        "clean_question": "What changed?",
        "started": 0.0,
    }
    payload = AskRequest(question="What changed?", screen="dashboard", context={})
    ctx = RequestContext(
        user_id=12,
        email="ai@example.com",
        organization_id=9,
        role="admin",
    )

    events = []
    async for event in service.ask_stream_generate(prepared, payload, ctx):
        events.append(event)

    after = NON_BLOCKING_FAILURES.labels(
        component="ai_service",
        operation="stream_timeout",
    )._value.get()
    assert after == before + 1
    assert fake_logger.calls[0][1] == "ai_stream_provider_failed"
    assert fake_logger.calls[0][2]["model"] == "broken-stream-v1"
    assert fake_logger.calls[0][2]["failure_reason"] == "TimeoutError"
    assert events[-1][0] == "done"
    assert isinstance(events[-1][1], AIResponse)


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
    assert fake_logger.calls[0][2]["delivery"] == "non_blocking"


@pytest.mark.asyncio
async def test_event_bus_required_handler_failure_propagates(monkeypatch):
    from app.events import bus as event_bus_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="event_bus",
        operation="handler",
    )._value.get()
    monkeypatch.setattr(event_bus_module, "logger", fake_logger)

    bus = EventBus()
    handled: list[str] = []

    async def required_handler(event):
        handled.append("required")
        raise RuntimeError(f"required failed for {event.data_point_id}")

    async def secondary_handler(event):
        handled.append("secondary")

    bus.subscribe(DataPointSubmitted, required_handler, required=True)
    bus.subscribe(DataPointSubmitted, secondary_handler)

    with pytest.raises(RuntimeError, match="required failed"):
        await bus.publish(DataPointSubmitted(data_point_id=78, submitted_by=12, organization_id=9))

    after = NON_BLOCKING_FAILURES.labels(
        component="event_bus",
        operation="handler",
    )._value.get()
    assert after == before
    assert handled == ["required"]
    assert fake_logger.calls[0][0] == "error"
    assert fake_logger.calls[0][1] == "event_required_handler_failed"
    assert fake_logger.calls[0][2]["delivery"] == "required"


@pytest.mark.asyncio
async def test_webhook_service_logs_and_counts_timeout_failure(monkeypatch):
    from app.services import webhook_service as webhook_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="webhook_service",
        operation="delivery_timeout",
    )._value.get()
    monkeypatch.setattr(webhook_module, "logger", fake_logger)

    async def timeout_sender(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    service = WebhookService(repo=_WebhookRepoStub(), sender=timeout_sender)

    async def allow_url(url: str, *, resolve_hostname: bool) -> str:
        return url

    monkeypatch.setattr(service, "_validate_outbound_url", allow_url)

    endpoint = WebhookEndpoint(
        id=11,
        organization_id=9,
        url="https://example.com/hooks/timeouts",
        secret="secret",
        events=["project.published"],
        is_active=True,
    )
    delivery = WebhookDelivery(
        id=21,
        webhook_endpoint_id=11,
        event_type="project.published",
        payload={"event": "project.published"},
        status="pending",
        attempt=0,
        max_attempts=5,
    )

    updated = await service._perform_delivery_attempt(endpoint, delivery)

    after = NON_BLOCKING_FAILURES.labels(
        component="webhook_service",
        operation="delivery_timeout",
    )._value.get()
    assert updated.status == "failed"
    assert updated.http_status is None
    assert updated.response_body == "timed out"
    assert after == before + 1
    assert fake_logger.calls[0][1] == "webhook_delivery_timeout"
    assert fake_logger.calls[0][2]["failure_reason"] == "ReadTimeout"


@pytest.mark.asyncio
async def test_webhook_service_logs_and_counts_policy_rejection(monkeypatch):
    from app.services import webhook_service as webhook_module

    fake_logger = _FakeLogger()
    before = NON_BLOCKING_FAILURES.labels(
        component="webhook_service",
        operation="delivery_policy_rejected",
    )._value.get()
    monkeypatch.setattr(webhook_module, "logger", fake_logger)

    async def sender(*args, **kwargs):
        raise AssertionError("sender should not be called")

    service = WebhookService(repo=_WebhookRepoStub(), sender=sender)

    async def reject_url(url: str, *, resolve_hostname: bool) -> str:
        raise AppError(
            "WEBHOOK_URL_FORBIDDEN",
            422,
            "Webhook URL resolved to private or local network addresses",
        )

    monkeypatch.setattr(service, "_validate_outbound_url", reject_url)

    endpoint = WebhookEndpoint(
        id=12,
        organization_id=9,
        url="https://example.com/hooks/policy",
        secret="secret",
        events=["project.published"],
        is_active=True,
    )
    delivery = WebhookDelivery(
        id=22,
        webhook_endpoint_id=12,
        event_type="project.published",
        payload={"event": "project.published"},
        status="pending",
        attempt=0,
        max_attempts=5,
    )

    updated = await service._perform_delivery_attempt(endpoint, delivery)

    after = NON_BLOCKING_FAILURES.labels(
        component="webhook_service",
        operation="delivery_policy_rejected",
    )._value.get()
    assert updated.status == "failed"
    assert updated.http_status is None
    assert "private or local network addresses" in (updated.response_body or "")
    assert after == before + 1
    assert fake_logger.calls[0][1] == "webhook_delivery_policy_rejected"
    assert fake_logger.calls[0][2]["failure_reason"] == "WEBHOOK_URL_FORBIDDEN"


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
