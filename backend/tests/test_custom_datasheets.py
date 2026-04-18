import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.db.models.custom_datasheet import CustomDatasheetItem
from app.db.models.project import MetricAssignment
from app.db.models.role_binding import RoleBinding
from app.db.models.shared_element import SharedElement
from app.domain.catalog import prepare_shared_element_defaults
from tests.conftest import TestSessionLocal


async def _setup_datasheet_context(client: AsyncClient, *, email: str = "datasheets@test.com") -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "full_name": "Datasheet Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/auth/me", headers=headers)

    org = await client.post(
        "/api/organizations/setup",
        json={"name": "Datasheet Org", "country": "GB"},
        headers=headers,
    )
    assert org.status_code == 201
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    project = await client.post(
        "/api/projects",
        json={"name": "Datasheet Project"},
        headers=headers,
    )
    assert project.status_code == 201

    second_project = await client.post(
        "/api/projects",
        json={"name": "Other Datasheet Project"},
        headers=headers,
    )
    assert second_project.status_code == 201

    framework_metric = await client.post(
        "/api/shared-elements",
        json={
            "code": "SE-DATASHEET-FRAMEWORK",
            "name": "Framework datasheet metric",
            "concept_domain": "emissions",
        },
        headers=headers,
    )
    assert framework_metric.status_code == 201

    assignment = await client.post(
        f"/api/projects/{project.json()['id']}/assignments",
        json={"shared_element_id": framework_metric.json()["id"]},
        headers=headers,
    )
    assert assignment.status_code == 201

    return {
        "headers": headers,
        "user_id": me.json()["id"],
        "org_id": org.json()["organization_id"],
        "root_entity_id": org.json()["root_entity_id"],
        "project_id": project.json()["id"],
        "other_project_id": second_project.json()["id"],
        "framework_metric_id": framework_metric.json()["id"],
        "assignment_id": assignment.json()["id"],
    }


async def _attach_requirement_to_framework_metric(client: AsyncClient, ctx: dict) -> dict:
    standard = await client.post(
        "/api/standards",
        json={"code": "GRI-DATASHEET", "name": "GRI Datasheet"},
        headers=ctx["headers"],
    )
    assert standard.status_code == 201

    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "305-1",
            "title": "Direct emissions",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=ctx["headers"],
    )
    assert disclosure.status_code == 201

    item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "item_code": "GRI-305-1-C",
            "name": "Biogenic CO2 emissions",
            "item_type": "metric",
            "value_type": "number",
        },
        headers=ctx["headers"],
    )
    assert item.status_code == 201

    mapping = await client.post(
        "/api/mappings",
        json={
            "requirement_item_id": item.json()["id"],
            "shared_element_id": ctx["framework_metric_id"],
        },
        headers=ctx["headers"],
    )
    assert mapping.status_code == 201

    attached = await client.post(
        f"/api/projects/{ctx['project_id']}/standards",
        json={"standard_id": standard.json()["id"], "is_base_standard": True},
        headers=ctx["headers"],
    )
    assert attached.status_code == 200

    return {
        "standard_id": standard.json()["id"],
        "standard_code": standard.json()["code"],
        "disclosure_id": disclosure.json()["id"],
        "disclosure_code": disclosure.json()["code"],
        "item_id": item.json()["id"],
        "item_code": item.json()["item_code"],
    }


@pytest.mark.asyncio
async def test_custom_datasheet_crud_and_detail_counts(client: AsyncClient):
    ctx = await _setup_datasheet_context(client)

    created = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={
            "name": "BP ESG Datasheet",
            "description": "Curated reporting sheet for the BP pilot.",
            "status": "draft",
        },
        headers=ctx["headers"],
    )
    assert created.status_code == 201
    datasheet_id = created.json()["id"]

    listed = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        headers=ctx["headers"],
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["item_count"] == 0

    async with TestSessionLocal() as session:
        custom_metric = SharedElement(
            code="CUST-DATASHEET-BOARD-DIVERSITY",
            name="Board diversity custom metric",
            **prepare_shared_element_defaults(
                code="CUST-DATASHEET-BOARD-DIVERSITY",
                owner_layer="tenant_catalog",
                organization_id=ctx["org_id"],
            ),
        )
        session.add(custom_metric)
        await session.flush()

        session.add_all(
            [
                CustomDatasheetItem(
                    custom_datasheet_id=datasheet_id,
                    reporting_project_id=ctx["project_id"],
                    shared_element_id=ctx["framework_metric_id"],
                    assignment_id=ctx["assignment_id"],
                    source_type="framework",
                    category="environmental",
                    display_group="Emissions",
                    collection_scope="project",
                    is_required=True,
                    sort_order=10,
                    created_by=ctx["user_id"],
                ),
                CustomDatasheetItem(
                    custom_datasheet_id=datasheet_id,
                    reporting_project_id=ctx["project_id"],
                    shared_element_id=custom_metric.id,
                    source_type="new_custom",
                    category="governance",
                    display_group="Board composition",
                    label_override="Female representation on board",
                    collection_scope="entity",
                    entity_id=ctx["root_entity_id"],
                    is_required=True,
                    sort_order=20,
                    created_by=ctx["user_id"],
                ),
            ]
        )
        await session.commit()

    detailed = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}",
        headers=ctx["headers"],
    )
    assert detailed.status_code == 200
    payload = detailed.json()
    assert payload["item_count"] == 2
    assert payload["framework_item_count"] == 1
    assert payload["custom_item_count"] == 1
    assert len(payload["items"]) == 2

    environmental_item = next(item for item in payload["items"] if item["category"] == "environmental")
    assert environmental_item["shared_element_code"] == "SE-DATASHEET-FRAMEWORK"
    assert environmental_item["owner_layer"] == "internal_catalog"
    assert environmental_item["assignment_id"] == ctx["assignment_id"]

    governance_item = next(item for item in payload["items"] if item["category"] == "governance")
    assert governance_item["shared_element_code"] == "CUST-DATASHEET-BOARD-DIVERSITY"
    assert governance_item["owner_layer"] == "tenant_catalog"
    assert governance_item["entity_id"] == ctx["root_entity_id"]
    assert governance_item["entity_name"]

    relisted = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        headers=ctx["headers"],
    )
    assert relisted.status_code == 200
    assert relisted.json()["items"][0]["item_count"] == 2
    assert relisted.json()["items"][0]["custom_item_count"] == 1

    updated = await client.patch(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}",
        json={"name": "BP ESG Datasheet v2", "status": "active"},
        headers=ctx["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "BP ESG Datasheet v2"
    assert updated.json()["status"] == "active"

    archived = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/archive",
        headers=ctx["headers"],
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_framework_item_search_and_add_reuses_existing_assignment(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-framework@test.com")
    requirement = await _attach_requirement_to_framework_metric(client, ctx)

    datasheet = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Framework Datasheet"},
        headers=ctx["headers"],
    )
    assert datasheet.status_code == 201
    datasheet_id = datasheet.json()["id"]

    search = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/item-options",
        params={"source": "framework", "q": "biogenic"},
        headers=ctx["headers"],
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    option = payload["items"][0]
    assert option["shared_element_id"] == ctx["framework_metric_id"]
    assert option["standard_code"] == requirement["standard_code"]
    assert option["disclosure_code"] == requirement["disclosure_code"]
    assert option["requirement_item_code"] == requirement["item_code"]
    assert option["suggested_category"] == "environmental"

    added = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items",
        json={
            "shared_element_id": ctx["framework_metric_id"],
            "source_type": "framework",
            "category": "environmental",
            "collection_scope": "project",
            "display_group": "Emissions",
        },
        headers=ctx["headers"],
    )
    assert added.status_code == 201
    added_item = added.json()
    assert added_item["assignment_id"] == ctx["assignment_id"]
    assert added_item["owner_layer"] == "internal_catalog"

    duplicate = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items",
        json={
            "shared_element_id": ctx["framework_metric_id"],
            "source_type": "framework",
            "category": "environmental",
            "collection_scope": "project",
        },
        headers=ctx["headers"],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_existing_custom_item_add_creates_assignment_and_archive_hides_it(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-custom-item@test.com")

    datasheet = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Custom Item Datasheet"},
        headers=ctx["headers"],
    )
    assert datasheet.status_code == 201
    datasheet_id = datasheet.json()["id"]

    async with TestSessionLocal() as session:
        custom_metric = SharedElement(
            code="CUST-BOARD-DIVERSITY-RATIO",
            name="Board diversity ratio",
            concept_domain="governance",
            **prepare_shared_element_defaults(
                code="CUST-BOARD-DIVERSITY-RATIO",
                owner_layer="tenant_catalog",
                organization_id=ctx["org_id"],
            ),
        )
        session.add(custom_metric)
        await session.commit()
        custom_metric_id = custom_metric.id

    search = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/item-options",
        params={"source": "existing_custom", "q": "board diversity"},
        headers=ctx["headers"],
    )
    assert search.status_code == 200
    payload = search.json()
    assert payload["total"] == 1
    option = payload["items"][0]
    assert option["shared_element_id"] == custom_metric_id
    assert option["owner_layer"] == "tenant_catalog"
    assert option["suggested_category"] == "governance"

    added = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items",
        json={
            "shared_element_id": custom_metric_id,
            "source_type": "existing_custom",
            "category": "governance",
            "collection_scope": "entity",
            "entity_id": ctx["root_entity_id"],
            "display_group": "Board composition",
            "label_override": "Female representation on board",
        },
        headers=ctx["headers"],
    )
    assert added.status_code == 201
    added_item = added.json()
    assert added_item["owner_layer"] == "tenant_catalog"
    assert added_item["entity_id"] == ctx["root_entity_id"]
    assert added_item["assignment_id"] is not None

    async with TestSessionLocal() as session:
        assignment = await session.get(MetricAssignment, added_item["assignment_id"])
        assert assignment is not None
        assert assignment.reporting_project_id == ctx["project_id"]
        assert assignment.shared_element_id == custom_metric_id
        assert assignment.entity_id == ctx["root_entity_id"]

    updated = await client.patch(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items/{added_item['id']}",
        json={
            "category": "business_operations",
            "display_group": "Board metrics",
            "help_text": "Backfilled from BP datasheet",
        },
        headers=ctx["headers"],
    )
    assert updated.status_code == 200
    assert updated.json()["category"] == "business_operations"
    assert updated.json()["display_group"] == "Board metrics"

    archived = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items/{added_item['id']}/archive",
        headers=ctx["headers"],
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    detail = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}",
        headers=ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["item_count"] == 0
    assert detail.json()["items"] == []


@pytest.mark.asyncio
async def test_create_custom_metric_and_add_item_creates_tenant_metric_and_assignment(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-create-custom@test.com")

    datasheet = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Create Custom Datasheet"},
        headers=ctx["headers"],
    )
    assert datasheet.status_code == 201
    datasheet_id = datasheet.json()["id"]

    created = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items/create-custom",
        json={
            "code": "CUST-BP-BOARD-DIVERSITY",
            "name": "BP board diversity",
            "description": "Narrative collected from the BP ESG datasheet.",
            "concept_domain": "governance",
            "default_value_type": "text",
            "category": "governance",
            "display_group": "Board composition",
            "label_override": "Female representation on board",
            "collection_scope": "entity",
            "entity_id": ctx["root_entity_id"],
        },
        headers=ctx["headers"],
    )
    assert created.status_code == 201
    item = created.json()
    assert item["source_type"] == "new_custom"
    assert item["owner_layer"] == "tenant_catalog"
    assert item["shared_element_code"] == "CUST-BP-BOARD-DIVERSITY"
    assert item["assignment_id"] is not None

    async with TestSessionLocal() as session:
        shared_element = await session.get(SharedElement, item["shared_element_id"])
        assert shared_element is not None
        assert shared_element.owner_layer == "tenant_catalog"
        assert shared_element.organization_id == ctx["org_id"]
        assert shared_element.is_custom is True
        assert shared_element.default_value_type == "text"
        assert shared_element.element_key == f"tenant:{ctx['org_id']}:cust-bp-board-diversity"

        assignment = await session.get(MetricAssignment, item["assignment_id"])
        assert assignment is not None
        assert assignment.reporting_project_id == ctx["project_id"]
        assert assignment.shared_element_id == shared_element.id
        assert assignment.entity_id == ctx["root_entity_id"]


@pytest.mark.asyncio
async def test_create_custom_metric_and_add_item_rejects_duplicate_code(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-create-custom-dup@test.com")

    datasheet = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Duplicate Custom Datasheet"},
        headers=ctx["headers"],
    )
    assert datasheet.status_code == 201
    datasheet_id = datasheet.json()["id"]

    first = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items/create-custom",
        json={
            "code": "CUST-DUPLICATE-METRIC",
            "name": "Duplicate metric",
            "category": "other",
            "collection_scope": "project",
        },
        headers=ctx["headers"],
    )
    assert first.status_code == 201

    duplicate = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets/{datasheet_id}/items/create-custom",
        json={
            "code": "CUST-DUPLICATE-METRIC",
            "name": "Duplicate metric again",
            "category": "other",
            "collection_scope": "project",
        },
        headers=ctx["headers"],
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_custom_datasheet_blocks_cross_project_access(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-scope@test.com")

    created = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Scoped datasheet"},
        headers=ctx["headers"],
    )
    assert created.status_code == 201

    wrong_project = await client.get(
        f"/api/projects/{ctx['other_project_id']}/custom-datasheets/{created.json()['id']}",
        headers=ctx["headers"],
    )
    assert wrong_project.status_code == 403
    assert wrong_project.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_auditor_can_read_but_cannot_write_custom_datasheets(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-auditor@test.com")

    created = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Existing datasheet"},
        headers=ctx["headers"],
    )
    assert created.status_code == 201

    async with TestSessionLocal() as session:
        await session.execute(
            update(RoleBinding)
            .where(
                RoleBinding.user_id == ctx["user_id"],
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == ctx["org_id"],
            )
            .values(role="auditor")
        )
        await session.commit()

    listed = await client.get(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        headers=ctx["headers"],
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    write_attempt = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Should fail"},
        headers=ctx["headers"],
    )
    assert write_attempt.status_code == 403
    assert write_attempt.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_esg_manager_can_manage_custom_datasheets(client: AsyncClient):
    ctx = await _setup_datasheet_context(client, email="datasheets-manager@test.com")

    async with TestSessionLocal() as session:
        await session.execute(
            update(RoleBinding)
            .where(
                RoleBinding.user_id == ctx["user_id"],
                RoleBinding.scope_type == "organization",
                RoleBinding.scope_id == ctx["org_id"],
            )
            .values(role="esg_manager")
        )
        await session.commit()

    created = await client.post(
        f"/api/projects/{ctx['project_id']}/custom-datasheets",
        json={"name": "Manager datasheet", "status": "active"},
        headers=ctx["headers"],
    )
    assert created.status_code == 201
    assert created.json()["status"] == "active"
