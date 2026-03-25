import pytest
from httpx import AsyncClient

from app.core.exceptions import AppError
from app.repositories.form_config_repo import FormConfigRepository
from tests.conftest import TestSessionLocal


async def _setup_project_context(client: AsyncClient, *, email: str = "forms@test.com") -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Forms Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Forms Org", "country": "GB"},
        headers=headers,
    )
    assert org.status_code == 201
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    project = await client.post(
        "/api/projects",
        json={"name": "Forms Project"},
        headers=headers,
    )
    assert project.status_code == 201

    return {
        "headers": headers,
        "project_id": project.json()["id"],
        "organization_id": org.json()["organization_id"],
        "boundary_id": org.json()["boundary_id"],
        "root_entity_id": org.json()["root_entity_id"],
    }


async def _create_standard_item(
    client: AsyncClient,
    headers: dict,
    *,
    standard_code: str,
    disclosure_code: str,
    item_code: str,
    item_name: str,
) -> dict:
    standard = await client.post(
        "/api/standards",
        json={"code": standard_code, "name": standard_code},
        headers=headers,
    )
    assert standard.status_code == 201

    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": disclosure_code,
            "title": disclosure_code,
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    assert disclosure.status_code == 201

    item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "item_code": item_code,
            "name": item_name,
            "item_type": "metric",
            "value_type": "number",
            "is_required": True,
        },
        headers=headers,
    )
    assert item.status_code == 201
    return {
        "standard_id": standard.json()["id"],
        "item_id": item.json()["id"],
    }


async def _prepare_row_aware_project(
    client: AsyncClient,
    *,
    email: str,
    entity_names: list[str],
) -> dict:
    ctx = await _setup_project_context(client, email=email)

    item = await _create_standard_item(
        client,
        ctx["headers"],
        standard_code="GRI",
        disclosure_code="305-1",
        item_code="GRI-305-1",
        item_name="Gross direct GHG emissions",
    )

    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_SCOPE_1", "name": "Scope 1 emissions"},
        headers=ctx["headers"],
    )
    assert shared_element.status_code == 201

    mapping = await client.post(
        "/api/mappings",
        json={
            "requirement_item_id": item["item_id"],
            "shared_element_id": shared_element.json()["id"],
        },
        headers=ctx["headers"],
    )
    assert mapping.status_code == 201

    attached = await client.post(
        f"/api/projects/{ctx['project_id']}/standards",
        json={"standard_id": item["standard_id"], "is_base_standard": True},
        headers=ctx["headers"],
    )
    assert attached.status_code == 200

    entities: list[dict] = []
    assignments: list[dict] = []
    for entity_name in entity_names:
        entity = await client.post(
            "/api/entities",
            json={"name": entity_name, "entity_type": "facility", "country": "GB"},
            headers=ctx["headers"],
        )
        assert entity.status_code == 201
        entities.append(entity.json())

        assignment = await client.post(
            f"/api/projects/{ctx['project_id']}/assignments",
            json={
                "shared_element_id": shared_element.json()["id"],
                "entity_id": entity.json()["id"],
            },
            headers=ctx["headers"],
        )
        assert assignment.status_code == 201
        assignments.append(assignment.json())

    generated = await client.post(
        f"/api/form-configs/projects/{ctx['project_id']}/generate",
        headers=ctx["headers"],
    )
    assert generated.status_code == 200

    return {
        **ctx,
        "item": item,
        "shared_element": shared_element.json(),
        "entities": entities,
        "assignments": assignments,
        "generated": generated.json(),
    }


@pytest.mark.asyncio
async def test_active_form_config_falls_back_to_org_default_and_prefers_project_specific(
    client: AsyncClient,
):
    ctx = await _setup_project_context(client)

    org_default = await client.post(
        "/api/form-configs",
        json={
            "project_id": None,
            "name": "Org Default",
            "description": "Fallback collection config",
            "config": {
                "steps": [
                    {
                        "id": "step-1",
                        "title": "General",
                        "fields": [{"shared_element_id": 101, "visible": True, "required": True, "order": 1}],
                    }
                ]
            },
            "is_active": True,
        },
        headers=ctx["headers"],
    )
    assert org_default.status_code == 201

    active_from_default = await client.get(
        f"/api/form-configs/projects/{ctx['project_id']}/active",
        headers=ctx["headers"],
    )
    assert active_from_default.status_code == 200
    assert active_from_default.json()["id"] == org_default.json()["id"]

    project_specific = await client.post(
        "/api/form-configs",
        json={
            "project_id": ctx["project_id"],
            "name": "Project Specific",
            "description": "Project-scoped wizard",
            "config": {
                "steps": [
                    {
                        "id": "step-1",
                        "title": "Specific",
                        "fields": [{"shared_element_id": 202, "visible": True, "required": True, "order": 1}],
                    }
                ]
            },
            "is_active": True,
        },
        headers=ctx["headers"],
    )
    assert project_specific.status_code == 201

    active_project = await client.get(
        f"/api/form-configs/projects/{ctx['project_id']}/active",
        headers=ctx["headers"],
    )
    assert active_project.status_code == 200
    assert active_project.json()["id"] == project_specific.json()["id"]


@pytest.mark.asyncio
async def test_form_config_repo_rejects_non_editable_fields(client: AsyncClient):
    ctx = await _setup_project_context(client, email="forms-invalid-update@test.com")
    created = await client.post(
        "/api/form-configs",
        json={
            "project_id": None,
            "name": "Locked Config",
            "description": "Cannot re-scope via generic update",
            "config": {"steps": []},
            "is_active": True,
        },
        headers=ctx["headers"],
    )
    assert created.status_code == 201

    async with TestSessionLocal() as session:
        repo = FormConfigRepository(session)
        with pytest.raises(AppError) as exc_info:
            await repo.update(created.json()["id"], organization_id=ctx["organization_id"] + 1)

    assert exc_info.value.code == "FORM_CONFIG_FIELD_NOT_EDITABLE"


@pytest.mark.asyncio
async def test_generate_default_deduplicates_shared_elements_and_keeps_requirement_metadata(
    client: AsyncClient,
):
    ctx = await _setup_project_context(client, email="forms-generate@test.com")

    first_item = await _create_standard_item(
        client,
        ctx["headers"],
        standard_code="GRI",
        disclosure_code="302-1",
        item_code="GRI-302-1A",
        item_name="Energy consumed inside the organization",
    )
    second_item = await _create_standard_item(
        client,
        ctx["headers"],
        standard_code="IFRS_S2",
        disclosure_code="S2-ENERGY",
        item_code="IFRS-S2-ENERGY",
        item_name="Energy consumption for climate disclosure",
    )

    shared_element = await client.post(
        "/api/shared-elements",
        json={"code": "ENERGY_TOTAL", "name": "Total Energy Consumption"},
        headers=ctx["headers"],
    )
    assert shared_element.status_code == 201

    for item_id in (first_item["item_id"], second_item["item_id"]):
        mapping = await client.post(
            "/api/mappings",
            json={"requirement_item_id": item_id, "shared_element_id": shared_element.json()["id"]},
            headers=ctx["headers"],
        )
        assert mapping.status_code == 201

    for standard_id in (first_item["standard_id"], second_item["standard_id"]):
        attached = await client.post(
            f"/api/projects/{ctx['project_id']}/standards",
            json={"standard_id": standard_id, "is_base_standard": standard_id == first_item['standard_id']},
            headers=ctx["headers"],
        )
        assert attached.status_code == 200

    generated = await client.post(
        f"/api/form-configs/projects/{ctx['project_id']}/generate",
        headers=ctx["headers"],
    )
    assert generated.status_code == 200

    steps = generated.json()["config"]["steps"]
    assert len(steps) == 1
    assert steps[0]["title"] == "Metric"
    assert len(steps[0]["fields"]) == 1

    field = steps[0]["fields"][0]
    assert field["shared_element_id"] == shared_element.json()["id"]
    assert field["requirement_item_id"] in {first_item["item_id"], second_item["item_id"]}
    assert "GRI-302-1A" in field["help_text"]
    assert "IFRS-S2-ENERGY" in field["help_text"]
    assert field["tooltip"] == "ENERGY_TOTAL: Total Energy Consumption"


@pytest.mark.asyncio
async def test_generate_default_expands_multi_context_assignments_with_assignment_ids(
    client: AsyncClient,
):
    ctx = await _prepare_row_aware_project(
        client,
        email="forms-assignments@test.com",
        entity_names=["Plant North", "Plant South"],
    )

    steps = ctx["generated"]["config"]["steps"]
    assert len(steps) == 1

    fields = steps[0]["fields"]
    assert len(fields) == 2
    assert {field["assignment_id"] for field in fields} == {
        assignment["id"] for assignment in ctx["assignments"]
    }
    assert {field["entity_id"] for field in fields} == {
        entity["id"] for entity in ctx["entities"]
    }
    assert all(field["shared_element_id"] == ctx["shared_element"]["id"] for field in fields)


@pytest.mark.asyncio
async def test_active_form_config_reports_assignment_drift_as_stale(client: AsyncClient):
    ctx = await _prepare_row_aware_project(
        client,
        email="forms-stale-assignment@test.com",
        entity_names=["Plant North"],
    )

    entity_two = await client.post(
        "/api/entities",
        json={"name": "Plant South", "entity_type": "facility", "country": "GB"},
        headers=ctx["headers"],
    )
    assert entity_two.status_code == 201

    assignment_two = await client.post(
        f"/api/projects/{ctx['project_id']}/assignments",
        json={
            "shared_element_id": ctx["shared_element"]["id"],
            "entity_id": entity_two.json()["id"],
        },
        headers=ctx["headers"],
    )
    assert assignment_two.status_code == 201

    active = await client.get(
        f"/api/form-configs/projects/{ctx['project_id']}/active",
        headers=ctx["headers"],
    )
    assert active.status_code == 200
    health = active.json()["health"]

    assert health["is_stale"] is True
    assert health["status"] == "stale"
    issue_counts = {issue["code"]: issue["affected_fields"] for issue in health["issues"]}
    assert issue_counts["UNCONFIGURED_ASSIGNMENT"] == 1


@pytest.mark.asyncio
async def test_active_form_config_reports_boundary_drift_as_stale(client: AsyncClient):
    ctx = await _prepare_row_aware_project(
        client,
        email="forms-stale-boundary@test.com",
        entity_names=["Plant North"],
    )

    memberships = await client.get(
        f"/api/boundaries/{ctx['boundary_id']}/memberships",
        headers=ctx["headers"],
    )
    assert memberships.status_code == 200

    boundary_update = await client.put(
        f"/api/boundaries/{ctx['boundary_id']}/memberships",
        json={
            "memberships": [
                {
                    "entity_id": membership["entity_id"],
                    "included": membership["entity_id"] != ctx["entities"][0]["id"],
                    "inclusion_source": membership["inclusion_source"] or "manual",
                    "consolidation_method": membership["consolidation_method"],
                    "inclusion_reason": membership["inclusion_reason"],
                }
                for membership in memberships.json()["memberships"]
            ]
        },
        headers=ctx["headers"],
    )
    assert boundary_update.status_code == 200

    active = await client.get(
        f"/api/form-configs/projects/{ctx['project_id']}/active",
        headers=ctx["headers"],
    )
    assert active.status_code == 200
    health = active.json()["health"]

    assert health["is_stale"] is True
    issue_counts = {issue["code"]: issue["affected_fields"] for issue in health["issues"]}
    assert issue_counts["OUTSIDE_BOUNDARY"] == 1


@pytest.mark.asyncio
async def test_resync_project_config_creates_fresh_active_version(client: AsyncClient):
    ctx = await _prepare_row_aware_project(
        client,
        email="forms-resync@test.com",
        entity_names=["Plant North"],
    )
    original_config_id = ctx["generated"]["id"]

    entity_two = await client.post(
        "/api/entities",
        json={"name": "Plant South", "entity_type": "facility", "country": "GB"},
        headers=ctx["headers"],
    )
    assert entity_two.status_code == 201

    assignment_two = await client.post(
        f"/api/projects/{ctx['project_id']}/assignments",
        json={
            "shared_element_id": ctx["shared_element"]["id"],
            "entity_id": entity_two.json()["id"],
        },
        headers=ctx["headers"],
    )
    assert assignment_two.status_code == 201

    resynced = await client.post(
        f"/api/form-configs/projects/{ctx['project_id']}/resync",
        headers=ctx["headers"],
    )
    assert resynced.status_code == 200
    resynced_data = resynced.json()

    assert resynced_data["id"] != original_config_id
    assert resynced_data["is_active"] is True
    assert resynced_data["health"]["is_stale"] is False
    assert len(resynced_data["config"]["steps"][0]["fields"]) == 2

    original = await client.get(
        f"/api/form-configs/{original_config_id}",
        headers=ctx["headers"],
    )
    assert original.status_code == 200
    assert original.json()["is_active"] is False

    active = await client.get(
        f"/api/form-configs/projects/{ctx['project_id']}/active",
        headers=ctx["headers"],
    )
    assert active.status_code == 200
    assert active.json()["id"] == resynced_data["id"]
