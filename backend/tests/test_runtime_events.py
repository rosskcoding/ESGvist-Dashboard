import pytest
from httpx import AsyncClient

from app.core.metrics import CLIENT_RUNTIME_EVENTS


@pytest.mark.asyncio
async def test_client_runtime_event_is_accepted_and_counted(client: AsyncClient):
    before = CLIENT_RUNTIME_EVENTS.labels(
        event_type="api_error",
        level="error",
    )._value.get()

    response = await client.post(
        "/api/runtime/client-events",
        json={
            "event_type": "api_error",
            "level": "error",
            "message": "Request failed",
            "path": "/collection",
            "status": 500,
            "code": "SERVER_ERROR",
            "request_id": "req_123",
            "details": {"retryable": False},
        },
    )

    after = CLIENT_RUNTIME_EVENTS.labels(
        event_type="api_error",
        level="error",
    )._value.get()

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert after == before + 1
