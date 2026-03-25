"""Tests for full ТЗ coverage: comments, invitations, impact, entity tree, references, SLA."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.comment import Comment
from app.db.models.completeness import RequirementItemStatus
from app.db.models.user import User
from tests.conftest import TestSessionLocal


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "a@t.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Co"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {
        "headers": headers,
        "org_id": org.json()["organization_id"],
        "root_id": org.json()["root_entity_id"],
    }


async def _create_data_point(client: AsyncClient, headers: dict) -> int:
    project = await client.post("/api/projects", json={"name": "Comment Project"}, headers=headers)
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "COMMENT_SE", "name": "Comment Element"},
        headers=headers,
    )
    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={"shared_element_id": shared_element.json()["id"], "numeric_value": 10},
        headers=headers,
    )
    return data_point.json()["id"]


async def _create_requirement_item(client: AsyncClient, headers: dict) -> int:
    standard = await client.post(
        "/api/standards",
        json={"code": "COMMENT-STD", "name": "Comment Standard"},
        headers=headers,
    )
    assert standard.status_code == 201
    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "COMMENT-DISC",
            "title": "Comment Disclosure",
            "requirement_type": "qualitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    assert disclosure.status_code == 201
    item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "item_code": "COMMENT-ITEM",
            "name": "Comment Item",
            "item_type": "narrative",
            "value_type": "text",
            "is_required": True,
        },
        headers=headers,
    )
    assert item.status_code == 201, item.text
    return item.json()["id"]


# === COMMENTS (threaded) ===

@pytest.mark.asyncio
async def test_create_comment(client: AsyncClient, ctx: dict):
    data_point_id = await _create_data_point(client, ctx["headers"])
    resp = await client.post(
        "/api/comments",
        json={
            "body": "Please check this value",
            "comment_type": "question",
            "data_point_id": data_point_id,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["comment_type"] == "question"


@pytest.mark.asyncio
async def test_threaded_comments(client: AsyncClient, ctx: dict):
    data_point_id = await _create_data_point(client, ctx["headers"])
    # Create parent
    parent = await client.post(
        "/api/comments",
        json={"body": "Parent comment", "data_point_id": data_point_id},
        headers=ctx["headers"],
    )
    # Create reply
    reply = await client.post(
        "/api/comments",
        json={
            "body": "Reply",
            "data_point_id": data_point_id,
            "parent_comment_id": parent.json()["id"],
        },
        headers=ctx["headers"],
    )
    assert reply.status_code == 201

    # List threaded
    resp = await client.get(f"/api/comments/data-point/{data_point_id}", headers=ctx["headers"])
    assert resp.status_code == 200
    threads = resp.json()
    assert len(threads) == 1  # one root
    assert len(threads[0]["replies"]) == 1


@pytest.mark.asyncio
async def test_resolve_comment(client: AsyncClient, ctx: dict):
    data_point_id = await _create_data_point(client, ctx["headers"])
    c = await client.post(
        "/api/comments",
        json={"body": "Issue", "comment_type": "issue", "data_point_id": data_point_id},
        headers=ctx["headers"],
    )
    resp = await client.patch(
        f"/api/comments/{c.json()['id']}/resolve",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["is_resolved"] is True


@pytest.mark.asyncio
async def test_requirement_item_only_comment_is_rejected(client: AsyncClient, ctx: dict):
    requirement_item_id = await _create_requirement_item(client, ctx["headers"])
    resp = await client.post(
        "/api/comments",
        json={"body": "Unscoped requirement item note", "requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "COMMENT_SCOPE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_comment_requirement_item_must_match_data_point_context(
    client: AsyncClient,
    ctx: dict,
):
    data_point_id = await _create_data_point(client, ctx["headers"])
    requirement_item_id = await _create_requirement_item(client, ctx["headers"])

    resp = await client.post(
        "/api/comments",
        json={
            "body": "This item should not attach to an unrelated data point",
            "data_point_id": data_point_id,
            "requirement_item_id": requirement_item_id,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUIREMENT_ITEM_CONTEXT"


@pytest.mark.asyncio
async def test_legacy_requirement_item_only_comment_can_be_resolved_by_admin(
    client: AsyncClient,
    ctx: dict,
):
    requirement_item_id = await _create_requirement_item(client, ctx["headers"])
    project = await client.post(
        "/api/projects",
        json={"name": "Legacy Comment Project"},
        headers=ctx["headers"],
    )
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        user_id = (
            await session.execute(select(User.id).where(User.email == "a@t.com"))
        ).scalars().one()
        session.add(
            RequirementItemStatus(
                reporting_project_id=project.json()["id"],
                requirement_item_id=requirement_item_id,
                status="missing",
            )
        )
        comment = Comment(
            user_id=user_id,
            body="Legacy requirement item-only note",
            requirement_item_id=requirement_item_id,
            comment_type="issue",
        )
        session.add(comment)
        await session.flush()
        comment_id = comment.id
        await session.commit()

    resp = await client.patch(
        f"/api/comments/{comment_id}/resolve",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["is_resolved"] is True


# === INVITATIONS ===

@pytest.mark.asyncio
async def test_create_invitation(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/invitations",
        json={"email": "new@co.com", "role": "collector"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_accept_invitation(client: AsyncClient, ctx: dict):
    # Create invitation
    inv = await client.post(
        "/api/invitations",
        json={"email": "joiner@co.com", "role": "reviewer"},
        headers=ctx["headers"],
    )
    token = inv.json()["token"]

    # Register new user
    await client.post(
        "/api/auth/register",
        json={"email": "joiner@co.com", "password": "password123", "full_name": "Joiner"},
    )
    login = await client.post(
        "/api/auth/login", json={"email": "joiner@co.com", "password": "password123"}
    )
    joiner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Accept
    resp = await client.post(f"/api/invitations/accept/{token}", headers=joiner_headers)
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True
    assert resp.json()["role"] == "reviewer"


@pytest.mark.asyncio
async def test_list_pending_invitations(client: AsyncClient, ctx: dict):
    await client.post(
        "/api/invitations",
        json={"email": "x@co.com", "role": "collector"},
        headers=ctx["headers"],
    )
    resp = await client.get("/api/invitations", headers=ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# === IMPACT ANALYSIS ===

@pytest.mark.asyncio
async def test_impact_requirement_change(client: AsyncClient, ctx: dict):
    std = await client.post(
        "/api/standards",
        json={"code": "G", "name": "G"},
        headers=ctx["headers"],
    )
    disc = await client.post(
        f"/api/standards/{std.json()['id']}/disclosures",
        json={
            "code": "D1",
            "title": "D1",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=ctx["headers"],
    )
    item = await client.post(
        f"/api/disclosures/{disc.json()['id']}/items",
        json={"name": "I1", "item_type": "metric", "value_type": "number"},
        headers=ctx["headers"],
    )

    resp = await client.get(
        f"/api/impact/requirement-item/{item.json()['id']}",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "affected_standards" in resp.json()


@pytest.mark.asyncio
async def test_impact_boundary_preview(client: AsyncClient, ctx: dict):
    b = await client.post(
        "/api/boundaries",
        json={"name": "B1", "boundary_type": "operational_control"},
        headers=ctx["headers"],
    )
    proj = await client.post("/api/projects", json={"name": "P"}, headers=ctx["headers"])

    resp = await client.get(
        f"/api/impact/boundary/preview?project_id={proj.json()['id']}&new_boundary_id={b.json()['id']}",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert "added_count" in resp.json()
    assert "removed_count" in resp.json()


# === ENTITY TREE ===

@pytest.mark.asyncio
async def test_entity_tree(client: AsyncClient, ctx: dict):
    # Create child entities
    for name in ["Sub A", "Sub B"]:
        await client.post(
            "/api/entities",
            json={"name": name, "entity_type": "legal_entity", "parent_entity_id": ctx["root_id"]},
            headers=ctx["headers"],
        )

    resp = await client.get("/api/entities/tree", headers=ctx["headers"])
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1  # root
    assert len(tree[0]["children"]) == 2


@pytest.mark.asyncio
async def test_effective_ownership(client: AsyncClient, ctx: dict):
    child = await client.post(
        "/api/entities",
        json={"name": "Child", "entity_type": "legal_entity"},
        headers=ctx["headers"],
    )
    child_id = child.json()["id"]

    await client.post(
        "/api/ownership-links",
        json={
            "parent_entity_id": ctx["root_id"],
            "child_entity_id": child_id,
            "ownership_percent": 75,
        },
        headers=ctx["headers"],
    )

    resp = await client.get(
        f"/api/entities/{child_id}/effective-ownership", headers=ctx["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["effective_ownership_percent"] == 75.0


# === REFERENCES (справочники) ===

@pytest.mark.asyncio
async def test_units_crud(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/references/units",
        json={"code": "tCO2e", "name": "Tonnes CO2 equivalent", "category": "emissions"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 201

    resp = await client.get("/api/references/units", headers=ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_methodologies_crud(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/references/methodologies",
        json={"code": "GHG_PROTOCOL", "name": "GHG Protocol"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 201

    resp = await client.get("/api/references/methodologies", headers=ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_boundary_approaches_crud(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/references/boundary-approaches",
        json={"code": "OPERATIONAL_CONTROL", "name": "Operational Control"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 201

    resp = await client.get("/api/references/boundary-approaches", headers=ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# === EVENT BUS WIRING ===

@pytest.mark.asyncio
async def test_event_handlers_registered():
    from app.events.handlers.audit_handler import AuditEventHandler
    from app.events.handlers.notification_handler import NotificationEventHandler
    # Verify classes exist and have methods
    assert hasattr(NotificationEventHandler, "on_data_point_submitted")
    assert hasattr(NotificationEventHandler, "on_data_point_rejected")
    assert hasattr(AuditEventHandler, "on_data_point_submitted")
    assert hasattr(AuditEventHandler, "on_boundary_applied")


# === SLA SERVICE ===

@pytest.mark.asyncio
async def test_sla_service_exists():
    from app.services.sla_service import SLAService
    assert hasattr(SLAService, "check_sla_breaches")
