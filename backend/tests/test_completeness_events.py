import socket

import pytest
from sqlalchemy import update

from app.db.models.data_point import DataPoint
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


async def _setup_org_admin(client) -> dict:
    await client.post(
        "/api/auth/register",
        json={
            "email": "admin+compl@org.com",
            "password": "password123",
            "full_name": "Completeness Admin",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin+compl@org.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Completeness Org", "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {
        "headers": headers,
        "org_id": org.json()["organization_id"],
    }


async def _invite_and_accept(
    client,
    *,
    admin_headers: dict,
    org_id: int,
    email: str,
    role: str,
    full_name: str,
):
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
    base_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    accepted = await client.post(
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=base_headers,
    )
    assert accepted.status_code == 200
    return {"headers": {**base_headers, "X-Organization-Id": str(org_id)}}


@pytest.mark.asyncio
async def test_completeness_change_publishes_webhook_and_manager_notification(monkeypatch, client):
    captured = []

    async def fake_sender(
        url: str,
        payload: dict,
        headers: dict[str, str],
        timeout_seconds: int,
    ):
        captured.append(payload)
        return 200, "ok"

    monkeypatch.setattr("app.services.webhook_service.send_webhook_request", fake_sender)

    org = await _setup_org_admin(client)
    manager = await _invite_and_accept(
        client,
        admin_headers=org["headers"],
        org_id=org["org_id"],
        email="manager+compl@org.com",
        role="esg_manager",
        full_name="Completeness Manager",
    )

    std = await client.post(
        "/api/standards",
        json={"code": "CMP", "name": "Completeness"},
        headers=org["headers"],
    )
    disc = await client.post(
        f"/api/standards/{std.json()['id']}/disclosures",
        json={
            "code": "CMP-1",
            "title": "Completeness",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=org["headers"],
    )
    item = await client.post(
        f"/api/disclosures/{disc.json()['id']}/items",
        json={
            "name": "Metric",
            "item_type": "metric",
            "value_type": "number",
            "is_required": True,
        },
        headers=org["headers"],
    )
    shared = await client.post(
        "/api/shared-elements",
        json={"code": "CMP_METRIC", "name": "Completeness Metric"},
        headers=org["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Completeness Project"},
        headers=org["headers"],
    )
    await client.post(
        f"/api/projects/{project.json()['id']}/standards",
        json={"standard_id": std.json()["id"], "is_base_standard": True},
        headers=org["headers"],
    )
    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={"shared_element_id": shared.json()["id"], "numeric_value": 12},
        headers=org["headers"],
    )
    await client.post(
        "/api/webhooks",
        json={
            "url": "https://example.com/hooks/completeness",
            "events": ["completeness.updated"],
        },
        headers=org["headers"],
    )
    await client.post(
        f"/api/projects/{project.json()['id']}/bindings",
        json={
            "requirement_item_id": item.json()["id"],
            "data_point_id": data_point.json()["id"],
        },
        headers=org["headers"],
    )

    first = await client.get(
        f"/api/projects/{project.json()['id']}/completeness",
        headers=org["headers"],
    )
    assert first.status_code == 200
    assert first.json()["overall_status"] == "partial"

    manager_notifications = await client.get(
        "/api/notifications",
        headers=manager["headers"],
    )
    assert any(
        item["type"] == "completeness_recalculated"
        for item in manager_notifications.json()["items"]
    )
    assert captured[-1]["event"] == "completeness.updated"
    assert captured[-1]["data"]["overallStatus"] == "partial"

    async with TestSessionLocal() as session:
        await session.execute(
            update(DataPoint)
            .where(DataPoint.id == data_point.json()["id"])
            .values(status="approved")
        )
        await session.commit()

    second = await client.get(
        f"/api/projects/{project.json()['id']}/completeness",
        headers=org["headers"],
    )
    assert second.status_code == 200
    assert second.json()["overall_status"] == "complete"
    assert second.json()["overall_percent"] == 100.0

    manager_notifications = await client.get(
        "/api/notifications",
        headers=manager["headers"],
    )
    assert any(
        item["type"] == "completeness_100_percent" for item in manager_notifications.json()["items"]
    )
    assert captured[-1]["data"]["overallStatus"] == "complete"
    assert captured[-1]["data"]["overallPercent"] == 100.0
