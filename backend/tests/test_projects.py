import pytest
from httpx import AsyncClient

from app.core.exceptions import AppError
from app.repositories.project_repo import ProjectRepository
from tests.conftest import TestSessionLocal


@pytest.fixture
async def org_ctx(client: AsyncClient) -> dict:
    """Register admin, setup org, return headers with org context."""
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    org = await client.post(
        "/api/organizations/setup",
        json={"name": "TestCo", "country": "KZ"},
        headers=headers,
    )
    org_id = org.json()["organization_id"]
    headers["X-Organization-Id"] = str(org_id)
    return {
        "headers": headers,
        "org_id": org_id,
        "root_entity_id": org.json()["root_entity_id"],
        "default_boundary_id": org.json()["boundary_id"],
    }


async def _setup_standard_launch_fixture(client: AsyncClient, headers: dict) -> dict:
    standard = await client.post(
        "/api/standards",
        json={"code": "GRI-LAUNCH", "name": "GRI Launch"},
        headers=headers,
    )
    assert standard.status_code == 201
    standard_id = standard.json()["id"]

    energy_disclosure = await client.post(
        f"/api/standards/{standard_id}/disclosures",
        json={
            "code": "GRI 302-1",
            "title": "Energy consumption",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    climate_disclosure = await client.post(
        f"/api/standards/{standard_id}/disclosures",
        json={
            "code": "GRI 305-1",
            "title": "Scope 1 emissions",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    assert energy_disclosure.status_code == 201
    assert climate_disclosure.status_code == 201

    energy_item = await client.post(
        f"/api/disclosures/{energy_disclosure.json()['id']}/items",
        json={
            "item_code": "ENERGY_TOTAL",
            "name": "Total energy consumption",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "MWh",
        },
        headers=headers,
    )
    intensity_item = await client.post(
        f"/api/disclosures/{climate_disclosure.json()['id']}/items",
        json={
            "item_code": "ENERGY_INTENSITY",
            "name": "Energy intensity input",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "MWh",
        },
        headers=headers,
    )
    scope1_item = await client.post(
        f"/api/disclosures/{climate_disclosure.json()['id']}/items",
        json={
            "item_code": "SCOPE1_TOTAL",
            "name": "Scope 1 total emissions",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "tCO2e",
        },
        headers=headers,
    )
    assert energy_item.status_code == 201
    assert intensity_item.status_code == 201
    assert scope1_item.status_code == 201

    energy_element = await client.post(
        "/api/shared-elements",
        json={"code": "SE-ENERGY-TOTAL", "name": "Total energy", "default_unit_code": "MWh"},
        headers=headers,
    )
    emissions_element = await client.post(
        "/api/shared-elements",
        json={"code": "SE-GHG-SCOPE1", "name": "Scope 1 emissions", "default_unit_code": "tCO2e"},
        headers=headers,
    )
    assert energy_element.status_code == 201
    assert emissions_element.status_code == 201

    for item_id, element_id, mapping_type in (
        (energy_item.json()["id"], energy_element.json()["id"], "full"),
        (intensity_item.json()["id"], energy_element.json()["id"], "partial"),
        (scope1_item.json()["id"], emissions_element.json()["id"], "full"),
    ):
        mapping = await client.post(
            "/api/mappings",
            json={
                "requirement_item_id": item_id,
                "shared_element_id": element_id,
                "mapping_type": mapping_type,
            },
            headers=headers,
        )
        assert mapping.status_code == 201

    project = await client.post(
        "/api/projects",
        json={"name": "Launch Project"},
        headers=headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    attached = await client.post(
        f"/api/projects/{project_id}/standards",
        json={"standard_id": standard_id, "is_base_standard": True},
        headers=headers,
    )
    assert attached.status_code == 200

    return {
        "project_id": project_id,
        "standard_id": standard_id,
        "energy_element_id": energy_element.json()["id"],
        "emissions_element_id": emissions_element.json()["id"],
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
        f"/api/invitations/accept/{invitation.json()['token']}",
        headers=headers,
    )
    assert accept.status_code == 200

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    return {"id": me.json()["id"], "headers": headers}


# --- Projects ---
@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, org_ctx: dict):
    resp = await client.post(
        "/api/projects",
        json={"name": "ESG Report 2025", "reporting_year": 2025},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "ESG Report 2025"
    assert resp.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_create_project_inherits_org_defaults(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={"email": "defaults-project@test.com", "password": "password123", "full_name": "Defaults Project"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "defaults-project@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for payload in (
        {"code": "GRI", "name": "GRI"},
        {"code": "IFRS_S2", "name": "IFRS S2"},
    ):
        standard = await client.post("/api/standards", json=payload, headers=headers)
        assert standard.status_code == 201

    org = await client.post(
        "/api/organizations/setup",
        json={
            "name": "Defaults Project Org",
            "country": "DE",
            "reporting_year": 2028,
            "standards": ["GRI", "IFRS_S2"],
        },
        headers=headers,
    )
    assert org.status_code == 201
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    project = await client.post(
        "/api/projects",
        json={"name": "Inherited Defaults Project"},
        headers=headers,
    )
    assert project.status_code == 201
    assert project.json()["reporting_year"] == 2028
    assert project.json()["boundary_definition_id"] == org.json()["boundary_id"]
    assert project.json()["standard_codes"] == ["GRI", "IFRS_S2"]


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, org_ctx: dict):
    await client.post(
        "/api/projects",
        json={"name": "P1"},
        headers=org_ctx["headers"],
    )
    await client.post(
        "/api/projects",
        json={"name": "P2"},
        headers=org_ctx["headers"],
    )

    resp = await client.get("/api/projects", headers=org_ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_project_standard_attach_preview_counts_reuse_and_new_metrics(
    client: AsyncClient, org_ctx: dict
):
    fixture = await _setup_standard_launch_fixture(client, org_ctx["headers"])

    existing_assignment = await client.post(
        f"/api/projects/{fixture['project_id']}/assignments",
        json={
            "shared_element_id": fixture["energy_element_id"],
            "entity_id": org_ctx["root_entity_id"],
        },
        headers=org_ctx["headers"],
    )
    assert existing_assignment.status_code == 201

    standard = await client.post(
        "/api/standards",
        json={"code": "IFRS-PREVIEW", "name": "IFRS Preview"},
        headers=org_ctx["headers"],
    )
    assert standard.status_code == 201
    preview_standard_id = standard.json()["id"]

    disclosure = await client.post(
        f"/api/standards/{preview_standard_id}/disclosures",
        json={
            "code": "IFRS S2.1",
            "title": "Preview disclosure",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=org_ctx["headers"],
    )
    assert disclosure.status_code == 201

    full_item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "item_code": "PREVIEW_FULL",
            "name": "Preview full reuse",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "MWh",
        },
        headers=org_ctx["headers"],
    )
    partial_item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "item_code": "PREVIEW_PARTIAL",
            "name": "Preview partial reuse",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "tCO2e",
        },
        headers=org_ctx["headers"],
    )
    new_item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "item_code": "PREVIEW_NEW",
            "name": "Preview new metric",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "m3",
        },
        headers=org_ctx["headers"],
    )
    assert full_item.status_code == 201
    assert partial_item.status_code == 201
    assert new_item.status_code == 201

    new_element = await client.post(
        "/api/shared-elements",
        json={"code": "SE-WATER-PREVIEW", "name": "Water preview", "default_unit_code": "m3"},
        headers=org_ctx["headers"],
    )
    assert new_element.status_code == 201

    for item_id, element_id, mapping_type in (
        (full_item.json()["id"], fixture["energy_element_id"], "full"),
        (partial_item.json()["id"], fixture["emissions_element_id"], "partial"),
        (new_item.json()["id"], new_element.json()["id"], "full"),
    ):
        mapping = await client.post(
            "/api/mappings",
            json={
                "requirement_item_id": item_id,
                "shared_element_id": element_id,
                "mapping_type": mapping_type,
            },
            headers=org_ctx["headers"],
        )
        assert mapping.status_code == 201

    preview = await client.get(
        f"/api/projects/{fixture['project_id']}/standards/{preview_standard_id}/attach-preview",
        headers=org_ctx["headers"],
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["total_mapped_elements"] == 3
    assert body["auto_reuse_count"] == 1
    assert body["needs_review_count"] == 1
    assert body["new_metric_count"] == 1
    assert body["already_in_collection_count"] == 1


@pytest.mark.asyncio
async def test_project_repo_rejects_non_editable_fields(client: AsyncClient, org_ctx: dict):
    project = await client.post(
        "/api/projects",
        json={"name": "Repo Guard"},
        headers=org_ctx["headers"],
    )
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        repo = ProjectRepository(session)
        with pytest.raises(AppError) as exc_info:
            await repo.update_project(project.json()["id"], organization_id=org_ctx["org_id"] + 1)

    assert exc_info.value.code == "PROJECT_FIELD_NOT_EDITABLE"


@pytest.mark.asyncio
async def test_add_standard_to_project(client: AsyncClient, org_ctx: dict):
    # Create standard
    std = await client.post(
        "/api/standards",
        json={"code": "GRI 302", "name": "GRI 302: Energy"},
        headers=org_ctx["headers"],
    )
    std_id = std.json()["id"]

    # Create project
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )
    proj_id = proj.json()["id"]

    # Add standard
    resp = await client.post(
        f"/api/projects/{proj_id}/standards",
        json={"standard_id": std_id, "is_base_standard": True},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_project_standard_launch_options_group_mapped_indicators(client: AsyncClient, org_ctx: dict):
    fixture = await _setup_standard_launch_fixture(client, org_ctx["headers"])

    resp = await client.get(
        f"/api/projects/{fixture['project_id']}/standards/{fixture['standard_id']}/launch-options",
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["standard_code"] == "GRI-LAUNCH"
    assert data["option_count"] == 2

    options_by_id = {item["shared_element_id"]: item for item in data["options"]}
    energy_option = options_by_id[fixture["energy_element_id"]]
    assert energy_option["shared_element_code"] == "SE-ENERGY-TOTAL"
    assert energy_option["existing_assignment_count"] == 0
    assert energy_option["assigned_entity_ids"] == []
    assert len(energy_option["linked_requirements"]) == 2
    assert {item["disclosure_code"] for item in energy_option["linked_requirements"]} == {
        "GRI 302-1",
        "GRI 305-1",
    }


@pytest.mark.asyncio
async def test_launch_project_standard_indicators_creates_assignments_and_skips_duplicates(
    client: AsyncClient,
    org_ctx: dict,
):
    fixture = await _setup_standard_launch_fixture(client, org_ctx["headers"])

    launch = await client.post(
        f"/api/projects/{fixture['project_id']}/standards/{fixture['standard_id']}/launch",
        json={
            "shared_element_ids": [
                fixture["energy_element_id"],
                fixture["emissions_element_id"],
            ],
            "entity_id": org_ctx["root_entity_id"],
            "deadline": "2026-12-31",
        },
        headers=org_ctx["headers"],
    )
    assert launch.status_code == 201
    launch_data = launch.json()
    assert launch_data["created_count"] == 2
    assert launch_data["skipped_count"] == 0

    assignments = await client.get(
        f"/api/projects/{fixture['project_id']}/assignments",
        headers=org_ctx["headers"],
    )
    assert assignments.status_code == 200
    assignment_rows = assignments.json()["assignments"]
    assert len(assignment_rows) == 2
    assert {
        item["shared_element_id"] for item in assignment_rows
    } == {fixture["energy_element_id"], fixture["emissions_element_id"]}

    launch_again = await client.post(
        f"/api/projects/{fixture['project_id']}/standards/{fixture['standard_id']}/launch",
        json={
            "shared_element_ids": [
                fixture["energy_element_id"],
                fixture["emissions_element_id"],
            ],
            "entity_id": org_ctx["root_entity_id"],
        },
        headers=org_ctx["headers"],
    )
    assert launch_again.status_code == 201
    second_data = launch_again.json()
    assert second_data["created_count"] == 0
    assert second_data["skipped_count"] == 2

    options = await client.get(
        f"/api/projects/{fixture['project_id']}/standards/{fixture['standard_id']}/launch-options",
        headers=org_ctx["headers"],
    )
    assert options.status_code == 200
    options_by_id = {item["shared_element_id"]: item for item in options.json()["options"]}
    assert options_by_id[fixture["energy_element_id"]]["assigned_entity_ids"] == [org_ctx["root_entity_id"]]


# --- Assignments ---
@pytest.mark.asyncio
async def test_create_assignment(client: AsyncClient, org_ctx: dict):
    # Create shared element
    el = await client.post(
        "/api/shared-elements",
        json={"code": "S1", "name": "Scope 1"},
        headers=org_ctx["headers"],
    )

    # Create project
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )

    resp = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={"shared_element_id": el.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "assigned"


@pytest.mark.asyncio
async def test_create_assignment_rejects_duplicate_metric_scope(client: AsyncClient, org_ctx: dict):
    el = await client.post(
        "/api/shared-elements",
        json={"code": "S1-DUP", "name": "Scope 1 duplicate"},
        headers=org_ctx["headers"],
    )
    assert el.status_code == 201

    proj = await client.post(
        "/api/projects",
        json={"name": "Duplicate Assignment Report"},
        headers=org_ctx["headers"],
    )
    assert proj.status_code == 201

    first = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={"shared_element_id": el.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert first.status_code == 201

    duplicate = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={"shared_element_id": el.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ASSIGNMENT_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_assignment_creates_custom_shared_element_by_code(client: AsyncClient, org_ctx: dict):
    proj = await client.post(
        "/api/projects",
        json={"name": "Custom Metric Project"},
        headers=org_ctx["headers"],
    )
    assert proj.status_code == 201

    resp = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={
            "shared_element_code": "CUST-BP-BOARD-DIVERSITY",
            "shared_element_name": "BP board diversity narrative",
            "entity_id": org_ctx["root_entity_id"],
        },
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201

    assignments = await client.get(
        f"/api/projects/{proj.json()['id']}/assignments",
        headers=org_ctx["headers"],
    )
    assert assignments.status_code == 200
    created = assignments.json()["assignments"][0]
    assert created["shared_element_code"] == "CUST-BP-BOARD-DIVERSITY"
    assert created["shared_element_name"] == "BP board diversity narrative"


@pytest.mark.asyncio
async def test_evidence_detail_includes_framework_context_for_linked_data_point(
    client: AsyncClient,
    org_ctx: dict,
):
    fixture = await _setup_standard_launch_fixture(client, org_ctx["headers"])
    launch = await client.post(
        f"/api/projects/{fixture['project_id']}/standards/{fixture['standard_id']}/launch",
        json={
            "shared_element_ids": [fixture["energy_element_id"]],
            "entity_id": org_ctx["root_entity_id"],
        },
        headers=org_ctx["headers"],
    )
    assert launch.status_code == 201

    data_point = await client.post(
        f"/api/projects/{fixture['project_id']}/data-points",
        json={
            "shared_element_id": fixture["energy_element_id"],
            "entity_id": org_ctx["root_entity_id"],
            "numeric_value": 125.5,
            "unit_code": "MWh",
        },
        headers=org_ctx["headers"],
    )
    assert data_point.status_code == 201

    evidence = await client.post(
        "/api/evidences",
        json={
            "type": "link",
            "title": "Framework evidence",
            "description": "Support document for launched framework metric",
            "url": "https://example.com/framework-evidence",
        },
        headers=org_ctx["headers"],
    )
    assert evidence.status_code == 201

    link = await client.post(
        f"/api/data-points/{data_point.json()['id']}/evidences",
        json={"evidence_id": evidence.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert link.status_code == 200

    detail = await client.get(
        f"/api/evidences/{evidence.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert detail.status_code == 200
    linked = detail.json()["linked_data_points"][0]
    assert linked["project_id"] == fixture["project_id"]
    assert linked["project_name"] == "Launch Project"
    assert linked["owner_layer"] == "internal_catalog"
    assert linked["is_custom"] is False
    assert linked["requirement_contexts"][0]["standard_code"] == "GRI-LAUNCH"
    assert linked["requirement_contexts"][0]["disclosure_code"] == "GRI 302-1"


@pytest.mark.asyncio
async def test_evidence_detail_marks_custom_metric_links(client: AsyncClient, org_ctx: dict):
    project = await client.post(
        "/api/projects",
        json={"name": "Custom Evidence Project"},
        headers=org_ctx["headers"],
    )
    assert project.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_code": "CUST-EVIDENCE-NARRATIVE",
            "shared_element_name": "Custom evidence narrative",
            "entity_id": org_ctx["root_entity_id"],
        },
        headers=org_ctx["headers"],
    )
    assert assignment.status_code == 201

    data_point = await client.post(
        f"/api/projects/{project.json()['id']}/data-points",
        json={
            "shared_element_id": assignment.json()["shared_element_id"],
            "entity_id": org_ctx["root_entity_id"],
            "text_value": "Narrative value",
        },
        headers=org_ctx["headers"],
    )
    assert data_point.status_code == 201

    evidence = await client.post(
        "/api/evidences",
        json={
            "type": "link",
            "title": "Custom metric evidence",
            "description": "Support document for a tenant custom metric",
            "url": "https://example.com/custom-evidence",
        },
        headers=org_ctx["headers"],
    )
    assert evidence.status_code == 201

    link = await client.post(
        f"/api/data-points/{data_point.json()['id']}/evidences",
        json={"evidence_id": evidence.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert link.status_code == 200

    detail = await client.get(
        f"/api/evidences/{evidence.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert detail.status_code == 200
    linked = detail.json()["linked_data_points"][0]
    assert linked["owner_layer"] == "tenant_catalog"
    assert linked["is_custom"] is True
    assert linked["project_name"] == "Custom Evidence Project"
    assert linked["requirement_contexts"] == []


@pytest.mark.asyncio
async def test_assignment_collector_reviewer_conflict(client: AsyncClient, org_ctx: dict):
    el = await client.post(
        "/api/shared-elements",
        json={"code": "S1", "name": "Scope 1"},
        headers=org_ctx["headers"],
    )
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )

    # Same user as collector and reviewer
    resp = await client.post(
        f"/api/projects/{proj.json()['id']}/assignments",
        json={"shared_element_id": el.json()["id"], "collector_id": 1, "reviewer_id": 1},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "ASSIGNMENT_ROLE_CONFLICT"


@pytest.mark.asyncio
async def test_auto_assign_handles_reviewer_only_gaps(client: AsyncClient, org_ctx: dict):
    collector = await _invite_and_accept(
        client,
        org_ctx["headers"],
        email="collector+auto-projects@test.com",
        role="collector",
        full_name="Collector Auto",
    )
    reviewer = await _invite_and_accept(
        client,
        org_ctx["headers"],
        email="reviewer+auto-projects@test.com",
        role="reviewer",
        full_name="Reviewer Auto",
    )

    updated_entity = await client.patch(
        f"/api/entities/{org_ctx['root_entity_id']}",
        json={
            "default_collector_user_id": collector["id"],
            "default_reviewer_user_id": reviewer["id"],
        },
        headers=org_ctx["headers"],
    )
    assert updated_entity.status_code == 200
    assert updated_entity.json()["default_collector_user_id"] == collector["id"]
    assert updated_entity.json()["default_reviewer_user_id"] == reviewer["id"]

    project = await client.post(
        "/api/projects",
        json={"name": "Auto Assign Reviewer Gap"},
        headers=org_ctx["headers"],
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    assignment = await client.post(
        f"/api/projects/{project_id}/assignments",
        json={
            "shared_element_code": "AUTO-REVIEW-GAP",
            "shared_element_name": "Auto review gap metric",
            "entity_id": org_ctx["root_entity_id"],
            "collector_id": collector["id"],
        },
        headers=org_ctx["headers"],
    )
    assert assignment.status_code == 201

    preview = await client.get(
        f"/api/projects/{project_id}/auto-assign/preview",
        headers=org_ctx["headers"],
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["covered_count"] == 1
    assert preview_payload["skipped_count"] == 0
    assert len(preview_payload["items"]) == 1
    assert preview_payload["items"][0]["proposed_collector_id"] is None
    assert preview_payload["items"][0]["proposed_reviewer_id"] == reviewer["id"]

    applied = await client.post(
        f"/api/projects/{project_id}/auto-assign",
        json={"dry_run": False},
        headers=org_ctx["headers"],
    )
    assert applied.status_code == 200
    assert applied.json()["updated_count"] == 1
    assert applied.json()["skipped_count"] == 0

    assignments = await client.get(
        f"/api/projects/{project_id}/assignments",
        headers=org_ctx["headers"],
    )
    assert assignments.status_code == 200
    row = assignments.json()["assignments"][0]
    assert row["collector_id"] == collector["id"]
    assert row["reviewer_id"] == reviewer["id"]
    assert row["reviewer_name"] == "Reviewer Auto"


@pytest.mark.asyncio
async def test_project_setup_health_counts_collector_and_reviewer(client: AsyncClient, org_ctx: dict):
    collector = await _invite_and_accept(
        client,
        org_ctx["headers"],
        email="collector+team-size@test.com",
        role="collector",
        full_name="Collector Team Size",
    )
    reviewer = await _invite_and_accept(
        client,
        org_ctx["headers"],
        email="reviewer+team-size@test.com",
        role="reviewer",
        full_name="Reviewer Team Size",
    )

    project = await client.post(
        "/api/projects",
        json={"name": "Setup Health Team Size"},
        headers=org_ctx["headers"],
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    assignment = await client.post(
        f"/api/projects/{project_id}/assignments",
        json={
            "shared_element_code": "SETUP-HEALTH-TEAM",
            "shared_element_name": "Setup health team metric",
            "collector_id": collector["id"],
            "reviewer_id": reviewer["id"],
        },
        headers=org_ctx["headers"],
    )
    assert assignment.status_code == 201

    detail = await client.get(
        f"/api/projects/{project_id}",
        headers=org_ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["setup_health"]["team_size"] == 2


# --- Boundaries ---
@pytest.mark.asyncio
async def test_create_boundary(client: AsyncClient, org_ctx: dict):
    resp = await client.post(
        "/api/boundaries",
        json={"name": "Financial Default", "boundary_type": "financial_reporting_default", "is_default": True},
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["boundary_type"] == "financial_reporting_default"
    assert resp.json()["is_default"] is True

    boundaries = await client.get("/api/boundaries", headers=org_ctx["headers"])
    assert boundaries.status_code == 200
    defaults = [item for item in boundaries.json() if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == resp.json()["id"]


@pytest.mark.asyncio
async def test_update_boundary_promotes_single_default(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Operational Boundary", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201

    promoted = await client.patch(
        f"/api/boundaries/{boundary.json()['id']}",
        json={"is_default": True},
        headers=org_ctx["headers"],
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_default"] is True

    boundaries = await client.get("/api/boundaries", headers=org_ctx["headers"])
    assert boundaries.status_code == 200
    defaults = [item for item in boundaries.json() if item["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == boundary.json()["id"]


@pytest.mark.asyncio
async def test_list_boundaries(client: AsyncClient, org_ctx: dict):
    await client.post(
        "/api/boundaries",
        json={"name": "B1", "boundary_type": "financial_reporting_default"},
        headers=org_ctx["headers"],
    )
    await client.post(
        "/api/boundaries",
        json={"name": "B2", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )

    resp = await client.get("/api/boundaries", headers=org_ctx["headers"])
    assert resp.status_code == 200
    assert len(resp.json()) >= 2  # includes default boundary from org setup


@pytest.mark.asyncio
async def test_apply_boundary_to_project(client: AsyncClient, org_ctx: dict):
    boundary = await client.post(
        "/api/boundaries",
        json={"name": "OpControl", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    proj = await client.post(
        "/api/projects",
        json={"name": "Report"},
        headers=org_ctx["headers"],
    )

    resp = await client.put(
        f"/api/projects/{proj.json()['id']}/boundary?boundary_id={boundary.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["boundary_definition_id"] == boundary.json()["id"]


@pytest.mark.asyncio
async def test_apply_boundary_invalidates_existing_snapshot(client: AsyncClient, org_ctx: dict):
    boundary_a = await client.post(
        "/api/boundaries",
        json={"name": "Boundary A", "boundary_type": "financial_control"},
        headers=org_ctx["headers"],
    )
    boundary_b = await client.post(
        "/api/boundaries",
        json={"name": "Boundary B", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Snapshot Project"},
        headers=org_ctx["headers"],
    )

    apply_a = await client.put(
        f"/api/projects/{project.json()['id']}/boundary?boundary_id={boundary_a.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert apply_a.status_code == 200

    snapshot = await client.post(
        f"/api/projects/{project.json()['id']}/boundary/snapshot",
        headers=org_ctx["headers"],
    )
    assert snapshot.status_code == 200

    apply_b = await client.put(
        f"/api/projects/{project.json()['id']}/boundary?boundary_id={boundary_b.json()['id']}",
        headers=org_ctx["headers"],
    )
    assert apply_b.status_code == 200

    snapshot_after_change = await client.get(
        f"/api/projects/{project.json()['id']}/boundary/snapshot",
        headers=org_ctx["headers"],
    )
    assert snapshot_after_change.status_code == 404


@pytest.mark.asyncio
async def test_create_assignment_rejects_entity_outside_active_boundary(client: AsyncClient, org_ctx: dict):
    from app.db.models.boundary import BoundaryMembership

    boundary = await client.post(
        "/api/boundaries",
        json={"name": "Operational", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    entity_in = await client.post(
        "/api/entities",
        json={"name": "Entity In", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    entity_out = await client.post(
        "/api/entities",
        json={"name": "Entity Out", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Boundary Guard Project"},
        headers=org_ctx["headers"],
    )
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "BG1", "name": "Boundary Guard Metric"},
        headers=org_ctx["headers"],
    )
    assert boundary.status_code == 201
    assert entity_in.status_code == 201
    assert entity_out.status_code == 201
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        session.add(
            BoundaryMembership(
                boundary_definition_id=boundary.json()["id"],
                entity_id=entity_in.json()["id"],
                included=True,
                inclusion_source="manual",
                consolidation_method="full",
            )
        )
        await session.commit()

    applied = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert applied.status_code == 200

    resp = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "entity_id": entity_out.json()["id"],
        },
        headers=org_ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ASSIGNMENT_ENTITY_MISMATCH"


@pytest.mark.asyncio
async def test_boundary_assignments_preview_returns_added_and_removed_assignments(client: AsyncClient, org_ctx: dict):
    from app.db.models.boundary import BoundaryMembership

    boundary_a = await client.post(
        "/api/boundaries",
        json={"name": "Boundary A", "boundary_type": "financial_control"},
        headers=org_ctx["headers"],
    )
    boundary_b = await client.post(
        "/api/boundaries",
        json={"name": "Boundary B", "boundary_type": "operational_control"},
        headers=org_ctx["headers"],
    )
    entity_a = await client.post(
        "/api/entities",
        json={"name": "Entity A", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    entity_b = await client.post(
        "/api/entities",
        json={"name": "Entity B", "entity_type": "legal_entity", "parent_entity_id": org_ctx["root_entity_id"]},
        headers=org_ctx["headers"],
    )
    project = await client.post(
        "/api/projects",
        json={"name": "Boundary Preview Project"},
        headers=org_ctx["headers"],
    )
    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "BP1", "name": "Boundary Preview Metric"},
        headers=org_ctx["headers"],
    )
    assert boundary_a.status_code == 201
    assert boundary_b.status_code == 201
    assert entity_a.status_code == 201
    assert entity_b.status_code == 201
    assert project.status_code == 201

    async with TestSessionLocal() as session:
        session.add_all(
            [
                BoundaryMembership(
                    boundary_definition_id=boundary_a.json()["id"],
                    entity_id=entity_a.json()["id"],
                    included=True,
                    inclusion_source="manual",
                    consolidation_method="full",
                ),
                BoundaryMembership(
                    boundary_definition_id=boundary_b.json()["id"],
                    entity_id=entity_b.json()["id"],
                    included=True,
                    inclusion_source="manual",
                    consolidation_method="full",
                ),
            ]
        )
        await session.commit()

    applied = await client.put(
        f"/api/projects/{project.json()['id']}/boundary",
        params={"boundary_id": boundary_a.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert applied.status_code == 200

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={
            "shared_element_id": shared_element.json()["id"],
            "entity_id": entity_a.json()["id"],
        },
        headers=org_ctx["headers"],
    )
    assert assignment.status_code == 201

    preview = await client.get(
        f"/api/projects/{project.json()['id']}/boundary/assignments-preview",
        params={"boundary_id": boundary_b.json()["id"]},
        headers=org_ctx["headers"],
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["added_entity_ids"] == [entity_b.json()["id"]]
    assert data["removed_entity_ids"] == [entity_a.json()["id"]]
    assert data["assignment_changes"]["removed_count"] == 1
    assert data["assignment_changes"]["added_count"] == 1
    assert data["assignment_changes"]["added"][0]["entity_id"] == entity_b.json()["id"]
    assert data["assignment_changes"]["removed"][0]["entity_id"] == entity_a.json()["id"]
