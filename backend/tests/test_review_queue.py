import pytest
from httpx import AsyncClient


async def _setup_org_admin(client: AsyncClient) -> dict:
    return await _setup_named_org_admin(
        client,
        email="admin+review@org.com",
        org_name="Review Org",
    )


async def _setup_named_org_admin(
    client: AsyncClient,
    *,
    email: str,
    org_name: str,
) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Review Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    org = await client.post(
        "/api/organizations/setup",
        json={"name": org_name, "country": "GB"},
        headers=headers,
    )
    headers["X-Organization-Id"] = str(org.json()["organization_id"])
    return {
        "headers": headers,
        "org_id": org.json()["organization_id"],
        "root_entity_id": org.json()["root_entity_id"],
    }


async def _invite_and_accept(
    client: AsyncClient,
    admin_headers: dict,
    *,
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
    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Organization-Id": admin_headers["X-Organization-Id"],
    }
    accept = await client.post(
        "/api/invitations/accept",
        json={"token": invitation.json()["token"]},
        headers=headers,
    )
    assert accept.status_code == 200

    me = await client.get("/api/auth/me", headers=headers)
    return {"id": me.json()["id"], "headers": headers}


@pytest.fixture
async def review_ctx(client: AsyncClient) -> dict:
    org = await _setup_org_admin(client)
    collector = await _invite_and_accept(
        client,
        org["headers"],
        email="collector+review@org.com",
        role="collector",
        full_name="Collector Review",
    )
    reviewer = await _invite_and_accept(
        client,
        org["headers"],
        email="reviewer+review@org.com",
        role="reviewer",
        full_name="Reviewer Review",
    )
    auditor = await _invite_and_accept(
        client,
        org["headers"],
        email="auditor+review@org.com",
        role="auditor",
        full_name="Auditor Review",
    )

    entity = await client.post(
        "/api/entities",
        json={
            "name": "Review Subsidiary",
            "entity_type": "legal_entity",
            "parent_entity_id": org["root_entity_id"],
        },
        headers=org["headers"],
    )
    assert entity.status_code == 201

    project = await client.post(
        "/api/projects",
        json={"name": "Review Project"},
        headers=org["headers"],
    )
    assert project.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "RV-1",
            "shared_element_name": "Review Metric",
            "entity_id": entity.json()["id"],
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
        },
        headers=org["headers"],
    )
    assert assignment.status_code == 201

    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={
            "shared_element_id": assignment.json()["shared_element_id"],
            "entity_id": entity.json()["id"],
            "numeric_value": 42.5,
            "unit_code": "MWH",
        },
        headers=collector["headers"],
    )
    assert data_point.status_code == 201

    submit = await client.post(
        f"/api/data-points/{data_point.json()['id']}/submit",
        headers=collector["headers"],
    )
    assert submit.status_code == 200
    assert submit.json()["status"] == "in_review"

    return {
        "admin": org,
        "collector": collector,
        "reviewer": reviewer,
        "auditor": auditor,
        "project_id": project.json()["id"],
        "data_point_id": data_point.json()["id"],
        "shared_element_id": assignment.json()["shared_element_id"],
        "entity_id": entity.json()["id"],
    }


@pytest.mark.asyncio
async def test_review_queue_lists_assigned_items_for_reviewer(
    client: AsyncClient,
    review_ctx: dict,
):
    response = await client.get(
        "/api/review/items",
        params={"project_id": review_ctx["project_id"]},
        headers=review_ctx["reviewer"]["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["id"] == review_ctx["data_point_id"]
    assert item["status"] == "in_review"
    assert item["submitter_name"] == "Collector Review"
    assert item["element_code"] == "RV-1"
    assert item["standard_code"] == "CUSTOM"
    assert item["boundary_context"]["entity_name"] == "Review Subsidiary"


@pytest.mark.asyncio
async def test_review_queue_is_readable_for_auditor_but_forbidden_for_collector(
    client: AsyncClient,
    review_ctx: dict,
):
    auditor_response = await client.get(
        "/api/review/items",
        params={"project_id": review_ctx["project_id"]},
        headers=review_ctx["auditor"]["headers"],
    )
    assert auditor_response.status_code == 200
    assert auditor_response.json()["total"] == 1

    collector_response = await client.get(
        "/api/review/items",
        params={"project_id": review_ctx["project_id"]},
        headers=review_ctx["collector"]["headers"],
    )
    assert collector_response.status_code == 403
    assert collector_response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_comment_list_includes_author_name_and_alias_fields(
    client: AsyncClient,
    review_ctx: dict,
):
    created = await client.post(
        "/api/comments",
        json={
            "body": "Please confirm methodology.",
            "comment_type": "question",
            "data_point_id": review_ctx["data_point_id"],
        },
        headers=review_ctx["reviewer"]["headers"],
    )
    assert created.status_code == 201

    listed = await client.get(
        f"/api/comments/data-point/{review_ctx['data_point_id']}",
        headers=review_ctx["reviewer"]["headers"],
    )
    assert listed.status_code == 200
    comments = listed.json()
    assert len(comments) == 1
    assert comments[0]["author_name"] == "Reviewer Review"
    assert comments[0]["content"] == "Please confirm methodology."
    assert comments[0]["type"] == "question"


@pytest.mark.asyncio
async def test_reviewer_can_resolve_collector_comment_within_review_scope(
    client: AsyncClient, review_ctx: dict
):
    created = await client.post(
        "/api/comments",
        json={
            "body": "Collector needs clarification.",
            "comment_type": "issue",
            "data_point_id": review_ctx["data_point_id"],
        },
        headers=review_ctx["collector"]["headers"],
    )
    assert created.status_code == 201

    resolved = await client.patch(
        f"/api/comments/{created.json()['id']}/resolve",
        headers=review_ctx["reviewer"]["headers"],
    )
    assert resolved.status_code == 200
    assert resolved.json()["is_resolved"] is True


@pytest.mark.asyncio
async def test_review_queue_without_project_id_stays_within_current_organization(
    client: AsyncClient,
    review_ctx: dict,
):
    second_org = await _setup_named_org_admin(
        client,
        email="admin+review-2@org.com",
        org_name="Review Org B",
    )
    second_collector = await _invite_and_accept(
        client,
        second_org["headers"],
        email="collector+review-b@org.com",
        role="collector",
        full_name="Collector Review B",
    )

    invitation = await client.post(
        "/api/auth/invitations",
        json={"email": "reviewer+review@org.com", "role": "reviewer"},
        headers=second_org["headers"],
    )
    assert invitation.status_code == 201

    accept = await client.post(
        "/api/invitations/accept",
        json={"token": invitation.json()["token"]},
        headers={"Authorization": review_ctx["reviewer"]["headers"]["Authorization"]},
    )
    assert accept.status_code == 200

    entity = await client.post(
        "/api/entities",
        json={
            "name": "Review Subsidiary B",
            "entity_type": "legal_entity",
            "parent_entity_id": second_org["root_entity_id"],
        },
        headers=second_org["headers"],
    )
    assert entity.status_code == 201

    project = await client.post(
        "/api/projects",
        json={"name": "Review Project B"},
        headers=second_org["headers"],
    )
    assert project.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "RV-2",
            "shared_element_name": "Review Metric B",
            "entity_id": entity.json()["id"],
            "collector_id": second_collector["id"],
            "reviewer_id": review_ctx["reviewer"]["id"],
        },
        headers=second_org["headers"],
    )
    assert assignment.status_code == 201

    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={
            "shared_element_id": assignment.json()["shared_element_id"],
            "entity_id": entity.json()["id"],
            "numeric_value": 84.0,
            "unit_code": "MWH",
        },
        headers=second_collector["headers"],
    )
    assert data_point.status_code == 201

    submit = await client.post(
        f"/api/data-points/{data_point.json()['id']}/submit",
        headers=second_collector["headers"],
    )
    assert submit.status_code == 200

    response = await client.get(
        "/api/review/items",
        headers=review_ctx["reviewer"]["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [review_ctx["data_point_id"]]


@pytest.mark.asyncio
async def test_entity_scoped_assignment_does_not_grant_project_level_data_point_access(
    client: AsyncClient,
    review_ctx: dict,
):
    project_level_data_point = await client.post(
        f"/api/projects/{review_ctx['project_id']}/data-points",
        json={
            "shared_element_id": review_ctx["shared_element_id"],
            "numeric_value": 13.0,
            "unit_code": "MWH",
        },
        headers=review_ctx["admin"]["headers"],
    )
    assert project_level_data_point.status_code == 201

    reviewer_get = await client.get(
        f"/api/data-points/{project_level_data_point.json()['id']}",
        headers=review_ctx["reviewer"]["headers"],
    )
    assert reviewer_get.status_code == 403
    assert reviewer_get.json()["error"]["code"] == "FORBIDDEN"
