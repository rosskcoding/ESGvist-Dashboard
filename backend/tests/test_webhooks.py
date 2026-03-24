import socket

import pytest
from httpx import AsyncClient


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


async def _setup_org_admin(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "admin+webhooks@org.com", "password": "password123", "full_name": "Webhook Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin+webhooks@org.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Webhook Org", "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {"headers": headers, "org_id": org.json()["organization_id"]}


async def _invite_and_accept(
    client: AsyncClient,
    *,
    admin_headers: dict,
    org_id: int,
    email: str,
    role: str,
    full_name: str,
) -> dict:
    invitation = await client.post(
        "/api/auth/invitations",
        json={"email": email, "role": role},
        headers=admin_headers,
    )
    assert invitation.status_code == 201

    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": full_name},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    accept = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=headers,
    )
    assert accept.status_code == 200

    me = await client.get("/api/auth/me", headers=headers)
    return {
        "id": me.json()["id"],
        "headers": {**headers, "X-Organization-Id": str(org_id)},
    }


@pytest.mark.asyncio
async def test_webhook_crud_and_test_delivery(monkeypatch, client: AsyncClient):
    captured: list[dict] = []

    async def fake_sender(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int):
        captured.append(
            {
                "url": url,
                "payload": payload,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
            }
        )
        return 200, "ok"

    monkeypatch.setattr("app.services.webhook_service.send_webhook_request", fake_sender)

    org = await _setup_org_admin(client)
    created = await client.post(
        "/api/webhooks",
        json={
            "url": "https://example.com/hooks/esg",
            "events": ["data_point.submitted", "project.published"],
        },
        headers=org["headers"],
    )
    assert created.status_code == 201
    endpoint = created.json()
    assert endpoint["secret"]
    assert endpoint["secret_last4"] == endpoint["secret"][-4:]

    listed = await client.get("/api/webhooks", headers=org["headers"])
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = await client.patch(
        f"/api/webhooks/{endpoint['id']}",
        json={
            "url": "https://example.com/hooks/esg/v2",
            "events": ["project.published"],
            "is_active": True,
        },
        headers=org["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["url"] == "https://example.com/hooks/esg/v2"
    assert updated.json()["events"] == ["project.published"]

    tested = await client.post(
        f"/api/webhooks/{endpoint['id']}/test",
        headers=org["headers"],
    )
    assert tested.status_code == 200
    assert tested.json()["delivery"]["status"] == "success"
    assert tested.json()["delivery"]["attempt"] == 1
    assert captured[0]["payload"]["event"] == "webhook.test"
    assert captured[0]["headers"]["X-Webhook-Signature"]
    assert captured[0]["headers"]["X-Webhook-Timestamp"]

    deliveries = await client.get(
        f"/api/webhooks/{endpoint['id']}/deliveries",
        headers=org["headers"],
    )
    assert deliveries.status_code == 200
    assert deliveries.json()["total"] == 1
    assert deliveries.json()["items"][0]["status"] == "success"

    deleted = await client.delete(f"/api/webhooks/{endpoint['id']}", headers=org["headers"])
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_webhook_failed_delivery_becomes_dead_letter_and_notifies_admin(
    monkeypatch,
    client: AsyncClient,
):
    async def failing_sender(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int):
        return 500, "upstream error"

    monkeypatch.setattr("app.services.webhook_service.send_webhook_request", failing_sender)

    org = await _setup_org_admin(client)
    created = await client.post(
        "/api/webhooks",
        json={"url": "https://example.com/hooks/fail", "events": ["project.published"]},
        headers=org["headers"],
    )
    assert created.status_code == 201
    endpoint_id = created.json()["id"]

    tested = await client.post(f"/api/webhooks/{endpoint_id}/test", headers=org["headers"])
    assert tested.status_code == 200
    assert tested.json()["delivery"]["status"] == "dead_letter"
    assert tested.json()["delivery"]["attempt"] == 5
    assert tested.json()["delivery"]["http_status"] == 500

    deliveries = await client.get(
        f"/api/webhooks/{endpoint_id}/deliveries",
        headers=org["headers"],
    )
    assert deliveries.status_code == 200
    assert deliveries.json()["items"][0]["status"] == "dead_letter"

    notifications = await client.get("/api/notifications", headers=org["headers"])
    assert notifications.status_code == 200
    assert any(item["type"] == "webhook_dead_letter" for item in notifications.json()["items"])


@pytest.mark.asyncio
async def test_webhook_rejects_localhost_targets(client: AsyncClient):
    org = await _setup_org_admin(client)

    created = await client.post(
        "/api/webhooks",
        json={"url": "http://localhost:8080/hooks/internal", "events": ["project.published"]},
        headers=org["headers"],
    )
    assert created.status_code == 422
    assert created.json()["error"]["code"] == "WEBHOOK_URL_FORBIDDEN"


@pytest.mark.asyncio
async def test_webhook_blocks_private_dns_resolution(monkeypatch, client: AsyncClient):
    captured: list[str] = []

    async def fake_sender(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int):
        captured.append(url)
        return 200, "ok"

    def fake_getaddrinfo(host: str, port: int, type: int = 0):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", port),
            )
        ]

    monkeypatch.setattr("app.services.webhook_service.send_webhook_request", fake_sender)
    monkeypatch.setattr("app.services.webhook_service.socket.getaddrinfo", fake_getaddrinfo)

    org = await _setup_org_admin(client)
    created = await client.post(
        "/api/webhooks",
        json={"url": "https://ssrf-check.example/hooks/events", "events": ["project.published"]},
        headers=org["headers"],
    )
    assert created.status_code == 201

    tested = await client.post(
        f"/api/webhooks/{created.json()['id']}/test",
        headers=org["headers"],
    )
    assert tested.status_code == 200
    assert tested.json()["delivery"]["status"] == "dead_letter"
    assert tested.json()["delivery"]["attempt"] == 5
    assert captured == []


@pytest.mark.asyncio
async def test_domain_events_trigger_webhook_deliveries(monkeypatch, client: AsyncClient):
    captured_events: list[str] = []

    async def fake_sender(url: str, payload: dict, headers: dict[str, str], timeout_seconds: int):
        captured_events.append(payload["event"])
        return 200, "accepted"

    monkeypatch.setattr("app.services.webhook_service.send_webhook_request", fake_sender)

    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        admin_headers=org["headers"],
        org_id=org["org_id"],
        email="collector+webhook@org.com",
        role="collector",
        full_name="Collector Webhook",
    )
    reviewer = await _invite_and_accept(
        client,
        admin_headers=org["headers"],
        org_id=org["org_id"],
        email="reviewer+webhook@org.com",
        role="reviewer",
        full_name="Reviewer Webhook",
    )

    endpoint = await client.post(
        "/api/webhooks",
        json={
            "url": "https://example.com/hooks/events",
            "events": ["data_point.submitted", "evidence.created"],
        },
        headers=org["headers"],
    )
    assert endpoint.status_code == 201
    endpoint_id = endpoint.json()["id"]

    project = await client.post("/api/projects", json={"name": "Webhook Project"}, headers=org["headers"])
    assert project.status_code == 201

    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "WH1", "name": "Webhook Metric"},
        headers=org["headers"],
    )
    assert shared_element.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
        },
        headers=org["headers"],
    )
    assert assignment.status_code == 201

    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={"shared_element_id": shared_element.json()["id"], "numeric_value": 10},
        headers=collector["headers"],
    )
    assert data_point.status_code == 201

    submitted = await client.post(
        f"/api/data-points/{data_point.json()['id']}/submit",
        headers=collector["headers"],
    )
    assert submitted.status_code == 200

    evidence = await client.post(
        "/api/evidences",
        json={
            "type": "link",
            "title": "Source",
            "description": "Evidence link",
            "source_type": "external",
            "url": "https://example.com/source",
            "label": "Source Link",
        },
        headers=collector["headers"],
    )
    assert evidence.status_code == 201

    assert "data_point.submitted" in captured_events
    assert "evidence.created" in captured_events

    deliveries = await client.get(
        f"/api/webhooks/{endpoint_id}/deliveries",
        headers=org["headers"],
    )
    assert deliveries.status_code == 200
    assert deliveries.json()["total"] == 2


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_webhooks(client: AsyncClient):
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        admin_headers=org["headers"],
        org_id=org["org_id"],
        email="collector+forbidden-webhook@org.com",
        role="collector",
        full_name="Collector Forbidden",
    )
    resp = await client.get("/api/webhooks", headers=collector["headers"])
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
