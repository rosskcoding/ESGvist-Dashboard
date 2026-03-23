from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings


@dataclass
class EmailDeliveryResult:
    sent: bool
    sent_at: datetime | None = None
    provider: str = "disabled"
    error: str | None = None


class BaseEmailSender:
    provider_name = "base"

    async def send(self, *, to_email: str, subject: str, body: str) -> EmailDeliveryResult:
        raise NotImplementedError


class ConsoleEmailSender(BaseEmailSender):
    provider_name = "console"

    async def send(self, *, to_email: str, subject: str, body: str) -> EmailDeliveryResult:
        return EmailDeliveryResult(
            sent=True,
            sent_at=datetime.now(timezone.utc),
            provider=self.provider_name,
        )


class DisabledEmailSender(BaseEmailSender):
    provider_name = "disabled"

    async def send(self, *, to_email: str, subject: str, body: str) -> EmailDeliveryResult:
        return EmailDeliveryResult(
            sent=False,
            sent_at=None,
            provider=self.provider_name,
            error="email_disabled",
        )


class FailingEmailSender(BaseEmailSender):
    provider_name = "failing"

    async def send(self, *, to_email: str, subject: str, body: str) -> EmailDeliveryResult:
        raise RuntimeError("Email provider failed")


def get_email_sender() -> BaseEmailSender:
    if not settings.email_enabled:
        return DisabledEmailSender()

    provider = (settings.email_provider or "console").lower()
    if provider == "disabled":
        return DisabledEmailSender()
    if provider == "failing":
        return FailingEmailSender()
    return ConsoleEmailSender()
