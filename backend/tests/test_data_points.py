import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.data_point import DataPointDimension
from tests.conftest import TestSessionLocal


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    """Full setup: register, org, project, shared element."""
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    org = await client.post(
        "/api/organizations/setup", json={"name": "Co"}, headers=headers
    )
    org_id = org.json()["organization_id"]
    headers["X-Organization-Id"] = str(org_id)

    proj = await client.post(
        "/api/projects", json={"name": "Report 2025"}, headers=headers
    )
    proj_id = proj.json()["id"]

    el = await client.post(
        "/api/shared-elements",
        json={"code": "GHG_S1", "name": "Scope 1"},
        headers=headers,
    )

    return {
        "headers": headers,
        "project_id": proj_id,
        "element_id": el.json()["id"],
        "org_id": org_id,
        "root_entity_id": org.json()["root_entity_id"],
        "default_boundary_id": org.json()["boundary_id"],
    }


async def _create_requirement_item(
    client: AsyncClient,
    *,
    headers: dict,
    project_id: int,
    attach_to_project: bool,
) -> int:
    suffix = f"{project_id}-{'attached' if attach_to_project else 'detached'}"
    standard = await client.post(
        "/api/standards",
        json={"code": f"GRI-{suffix}", "name": f"GRI {suffix}"},
        headers=headers,
    )
    assert standard.status_code == 201

    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": f"305-1-{suffix}",
            "title": f"Gross direct GHG emissions {suffix}",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=headers,
    )
    assert disclosure.status_code == 201

    item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "name": f"Scope 1 total {suffix}",
            "item_type": "metric",
            "value_type": "number",
            "unit_code": "tCO2e",
            "item_code": f"305-1.a-{suffix}",
        },
        headers=headers,
    )
    assert item.status_code == 201

    if attach_to_project:
        linked = await client.post(
            f"/api/projects/{project_id}/standards",
            json={"standard_id": standard.json()["id"], "is_base_standard": True},
            headers=headers,
        )
        assert linked.status_code == 200

    return item.json()["id"]


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


@pytest.mark.asyncio
async def test_create_data_point(client: AsyncClient, ctx: dict):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 1240.5,
            "unit_code": "tCO2e",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["numeric_value"] == 1240.5
    assert data["unit_code"] == "tCO2e"


@pytest.mark.asyncio
async def test_create_data_point_rejects_entity_from_another_organization(
    client: AsyncClient,
    ctx: dict,
):
    await client.post(
        "/api/auth/register",
        json={
            "email": "other-admin@test.com",
            "password": "password123",
            "full_name": "Other Admin",
        },
    )
    other_login = await client.post(
        "/api/auth/login",
        json={"email": "other-admin@test.com", "password": "password123"},
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    other_org = await client.post(
        "/api/organizations/setup",
        json={"name": "Other Co"},
        headers=other_headers,
    )
    other_headers["X-Organization-Id"] = str(other_org.json()["organization_id"])

    foreign_entity = await client.post(
        "/api/entities",
        json={
            "name": "Foreign Entity",
            "entity_type": "legal_entity",
            "parent_entity_id": other_org.json()["root_entity_id"],
        },
        headers=other_headers,
    )
    assert foreign_entity.status_code == 201

    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "entity_id": foreign_entity.json()["id"],
            "numeric_value": 1,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_create_data_point_with_dimensions(client: AsyncClient, ctx: dict):
    await client.post(
        f"/api/shared-elements/{ctx['element_id']}/dimensions",
        json={"dimension_type": "scope", "is_required": True},
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/shared-elements/{ctx['element_id']}/dimensions",
        json={"dimension_type": "gas", "is_required": False},
        headers=ctx["headers"],
    )

    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 100,
            "dimensions": [
                {"dimension_type": "scope", "dimension_value": "Scope 1"},
                {"dimension_type": "gas", "dimension_value": "CO2"},
            ],
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201

    dp_id = resp.json()["id"]
    async with TestSessionLocal() as session:
        dimensions = (
            await session.execute(
                select(DataPointDimension)
                .where(DataPointDimension.data_point_id == dp_id)
                .order_by(DataPointDimension.dimension_type)
            )
        ).scalars().all()

    assert [(dimension.dimension_type, dimension.dimension_value) for dimension in dimensions] == [
        ("gas_type", "CO2"),
        ("scope", "Scope 1"),
    ]


@pytest.mark.asyncio
async def test_create_data_point_rejects_dimensions_not_configured_for_shared_element(
    client: AsyncClient, ctx: dict
):
    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 100,
            "dimensions": [{"dimension_type": "scope", "dimension_value": "Scope 1"}],
        },
        headers=ctx["headers"],
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_DIMENSION_TYPE"


@pytest.mark.asyncio
async def test_create_data_point_rejects_duplicate_dimension_types(
    client: AsyncClient, ctx: dict
):
    await client.post(
        f"/api/shared-elements/{ctx['element_id']}/dimensions",
        json={"dimension_type": "gas", "is_required": False},
        headers=ctx["headers"],
    )

    resp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 100,
            "dimensions": [
                {"dimension_type": "gas", "dimension_value": "CO2"},
                {"dimension_type": "gas_type", "dimension_value": "CH4"},
            ],
        },
        headers=ctx["headers"],
    )

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "DUPLICATE_DIMENSION_TYPE"


@pytest.mark.asyncio
async def test_list_data_points(client: AsyncClient, ctx: dict):
    for i in range(3):
        await client.post(
            f"/api/projects/{ctx['project_id']}/data-points",
            json={"shared_element_id": ctx["element_id"], "numeric_value": i * 10},
            headers=ctx["headers"],
        )

    resp = await client.get(
        f"/api/projects/{ctx['project_id']}/data-points",
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


@pytest.mark.asyncio
async def test_get_data_point(client: AsyncClient, ctx: dict):
    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 42},
        headers=ctx["headers"],
    )
    dp_id = create.json()["id"]

    resp = await client.get(f"/api/data-points/{dp_id}", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["numeric_value"] == 42


@pytest.mark.asyncio
async def test_get_data_point_ignores_historical_mappings_in_related_standards(
    client: AsyncClient,
    ctx: dict,
):
    from datetime import date

    from app.db.models.mapping import RequirementItemSharedElement
    from app.db.models.requirement_item import RequirementItem
    from tests.conftest import TestSessionLocal

    current_standard = await client.post(
        "/api/standards",
        json={"code": "CUR-MAP", "name": "Current Mapping"},
        headers=ctx["headers"],
    )
    current_disclosure = await client.post(
        f"/api/standards/{current_standard.json()['id']}/disclosures",
        json={
            "code": "CUR-1",
            "title": "Current disclosure",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=ctx["headers"],
    )
    current_item = await client.post(
        f"/api/disclosures/{current_disclosure.json()['id']}/items",
        json={
            "name": "Current mapped item",
            "item_type": "metric",
            "value_type": "number",
            "is_required": True,
        },
        headers=ctx["headers"],
    )
    attached_current = await client.post(
        f"/api/projects/{ctx['project_id']}/standards",
        json={"standard_id": current_standard.json()["id"], "is_base_standard": True},
        headers=ctx["headers"],
    )
    assert attached_current.status_code == 200

    historical_standard = await client.post(
        "/api/standards",
        json={"code": "OLD-MAP", "name": "Historical Mapping"},
        headers=ctx["headers"],
    )
    historical_disclosure = await client.post(
        f"/api/standards/{historical_standard.json()['id']}/disclosures",
        json={
            "code": "OLD-1",
            "title": "Old disclosure",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=ctx["headers"],
    )
    historical_item = await client.post(
        f"/api/disclosures/{historical_disclosure.json()['id']}/items",
        json={
            "name": "Historical mapped item",
            "item_type": "metric",
            "value_type": "number",
            "is_required": True,
        },
        headers=ctx["headers"],
    )
    attached_historical = await client.post(
        f"/api/projects/{ctx['project_id']}/standards",
        json={"standard_id": historical_standard.json()["id"], "is_base_standard": False},
        headers=ctx["headers"],
    )
    assert attached_historical.status_code == 200

    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 42},
        headers=ctx["headers"],
    )
    assert create.status_code == 201

    async with TestSessionLocal() as session:
        session.add_all(
            [
                RequirementItemSharedElement(
                    requirement_item_id=current_item.json()["id"],
                    shared_element_id=ctx["element_id"],
                    mapping_type="full",
                    version=1,
                    is_current=True,
                ),
                RequirementItemSharedElement(
                    requirement_item_id=historical_item.json()["id"],
                    shared_element_id=ctx["element_id"],
                    mapping_type="full",
                    version=1,
                    is_current=False,
                    valid_to=date.today(),
                ),
            ]
        )
        historical_item_row = await session.get(RequirementItem, historical_item.json()["id"])
        if historical_item_row is not None:
            historical_item_row.is_current = False
        await session.commit()

    detail = await client.get(
        f"/api/data-points/{create.json()['id']}",
        headers=ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["standards"] == ["CUR-MAP"]


@pytest.mark.asyncio
async def test_get_data_point_includes_dimension_values_for_existing_dimensions(
    client: AsyncClient,
    ctx: dict,
):
    await client.post(
        f"/api/shared-elements/{ctx['element_id']}/dimensions",
        json={"dimension_type": "scope", "is_required": True},
        headers=ctx["headers"],
    )
    await client.post(
        f"/api/shared-elements/{ctx['element_id']}/dimensions",
        json={"dimension_type": "gas", "is_required": False},
        headers=ctx["headers"],
    )

    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 42,
            "dimensions": [
                {"dimension_type": "scope", "dimension_value": "Scope 1"},
                {"dimension_type": "gas_type", "dimension_value": "CO2"},
            ],
        },
        headers=ctx["headers"],
    )
    assert create.status_code == 201

    detail = await client.get(
        f"/api/data-points/{create.json()['id']}",
        headers=ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["dimensions"] == {
        "scope": True,
        "gas_type": True,
        "category": False,
    }
    assert detail.json()["dimension_values"] == {
        "scope": "Scope 1",
        "gas_type": "CO2",
        "category": None,
    }


@pytest.mark.asyncio
async def test_update_data_point_saves_draft_without_internal_error(client: AsyncClient, ctx: dict):
    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 42,
            "unit_code": "tCO2e",
        },
        headers=ctx["headers"],
    )
    assert create.status_code == 201
    dp_id = create.json()["id"]

    resp = await client.patch(
        f"/api/data-points/{dp_id}",
        json={"numeric_value": 67, "unit_code": "kt"},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert data["numeric_value"] == 67
    assert data["unit_code"] == "kt"


@pytest.mark.asyncio
async def test_project_level_data_point_stays_included_with_active_boundary(
    client: AsyncClient,
    ctx: dict,
):
    applied = await client.put(
        f"/api/projects/{ctx['project_id']}/boundary",
        params={"boundary_id": ctx["default_boundary_id"]},
        headers=ctx["headers"],
    )
    assert applied.status_code == 200

    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 55},
        headers=ctx["headers"],
    )
    assert create.status_code == 201
    assert create.json()["boundary_status"] == "included"


@pytest.mark.asyncio
async def test_partial_patch_preserves_omitted_unit_code(client: AsyncClient, ctx: dict):
    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 42,
            "unit_code": "tCO2e",
        },
        headers=ctx["headers"],
    )
    assert create.status_code == 201
    dp_id = create.json()["id"]

    resp = await client.patch(
        f"/api/data-points/{dp_id}",
        json={"numeric_value": 67},
        headers=ctx["headers"],
    )

    assert resp.status_code == 200
    assert resp.json()["numeric_value"] == 67
    assert resp.json()["unit_code"] == "tCO2e"


@pytest.mark.asyncio
async def test_partial_patch_allows_explicit_unit_code_clear(client: AsyncClient, ctx: dict):
    create = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 42,
            "unit_code": "tCO2e",
        },
        headers=ctx["headers"],
    )
    assert create.status_code == 201
    dp_id = create.json()["id"]

    resp = await client.patch(
        f"/api/data-points/{dp_id}",
        json={"unit_code": None},
        headers=ctx["headers"],
    )

    assert resp.status_code == 200
    assert resp.json()["unit_code"] is None


# --- Evidence ---
@pytest.mark.asyncio
async def test_create_evidence_file(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Emissions Report",
            "file_name": "report.pdf",
            "file_uri": "s3://bucket/report.pdf",
            "mime_type": "application/pdf",
            "file_size": 2400000,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "file"
    assert resp.json()["title"] == "Emissions Report"


@pytest.mark.asyncio
async def test_create_evidence_file_accepts_json_mime(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Service Account JSON",
            "file_name": "service-account.json",
            "file_uri": "s3://bucket/service-account.json",
            "mime_type": "application/json",
            "file_size": 4096,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "file"
    assert resp.json()["title"] == "Service Account JSON"


@pytest.mark.asyncio
async def test_download_evidence_file_returns_attachment(client: AsyncClient, ctx: dict):
    file_body = b"metric,value\nscope1,42\n"
    upload = await client.post(
        "/api/evidences/upload",
        files={"file": ("report.csv", file_body, "text/csv")},
        data={"title": "Uploaded CSV", "description": ""},
        headers=ctx["headers"],
    )
    assert upload.status_code == 201

    evidence_id = upload.json()["id"]
    response = await client.get(
        f"/api/evidences/{evidence_id}/download",
        headers=ctx["headers"],
    )

    assert response.status_code == 200
    assert response.content == file_body
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment;" in response.headers["content-disposition"]
    assert "report.csv" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_create_evidence_file_requires_non_empty_file_uri(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Broken Upload",
            "file_name": "broken.pdf",
            "file_uri": "   ",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_INPUT"
    assert "file_uri" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_create_evidence_link(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "link",
            "title": "Company Policy",
            "url": "https://company.com/policy",
            "label": "ESG Policy Page",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 201
    assert resp.json()["type"] == "link"


@pytest.mark.asyncio
async def test_create_evidence_link_requires_url(client: AsyncClient, ctx: dict):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "link",
            "title": "Missing URL",
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_evidence_rejects_oversized_file_message_matches_limit(
    client: AsyncClient,
    ctx: dict,
):
    resp = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Too Large",
            "file_name": "large.pdf",
            "file_uri": "s3://bucket/large.pdf",
            "mime_type": "application/pdf",
            "file_size": 10 * 1024 * 1024 + 1,
        },
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert "10MB" in resp.json()["error"]["message"]
    assert "50MB" not in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_list_evidences(client: AsyncClient, ctx: dict):
    await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Doc 1", "file_name": "a.pdf", "file_uri": "s3://a"},
        headers=ctx["headers"],
    )
    await client.post(
        "/api/evidences",
        json={"type": "link", "title": "Link 1", "url": "https://x.com"},
        headers=ctx["headers"],
    )

    resp = await client.get("/api/evidences", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_update_evidence_rejects_empty_title(client: AsyncClient, ctx: dict):
    evidence = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Doc 1", "file_name": "a.pdf", "file_uri": "s3://a"},
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    resp = await client.put(
        f"/api/evidences/{evidence.json()['id']}",
        json={"title": ""},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_collector_cannot_access_other_collectors_evidence_by_id(
    client: AsyncClient,
    ctx: dict,
):
    collector_one = await _invite_and_accept(
        client,
        ctx["headers"],
        email="collector-one-evidence@test.com",
        role="collector",
        full_name="Collector One",
    )
    collector_two = await _invite_and_accept(
        client,
        ctx["headers"],
        email="collector-two-evidence@test.com",
        role="collector",
        full_name="Collector Two",
    )

    upload = await client.post(
        "/api/evidences/upload",
        files={"file": ("locked.csv", b"metric,value\nscope1,42\n", "text/csv")},
        data={"title": "Locked Evidence", "description": ""},
        headers=collector_two["headers"],
    )
    assert upload.status_code == 201
    evidence_id = upload.json()["id"]

    detail = await client.get(
        f"/api/evidences/{evidence_id}",
        headers=collector_one["headers"],
    )
    assert detail.status_code == 403
    assert detail.json()["error"]["code"] == "FORBIDDEN"

    suggestions = await client.get(
        f"/api/evidences/{evidence_id}/suggestions",
        headers=collector_one["headers"],
    )
    assert suggestions.status_code == 403
    assert suggestions.json()["error"]["code"] == "FORBIDDEN"

    download = await client.get(
        f"/api/evidences/{evidence_id}/download",
        headers=collector_one["headers"],
    )
    assert download.status_code == 403
    assert download.json()["error"]["code"] == "FORBIDDEN"

    update = await client.put(
        f"/api/evidences/{evidence_id}",
        json={"title": "Renamed"},
        headers=collector_one["headers"],
    )
    assert update.status_code == 403
    assert update.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_collector_can_read_evidence_linked_to_assigned_data_point(
    client: AsyncClient,
    ctx: dict,
):
    collector_one = await _invite_and_accept(
        client,
        ctx["headers"],
        email="collector-assigned-read@test.com",
        role="collector",
        full_name="Collector Assigned",
    )
    collector_two = await _invite_and_accept(
        client,
        ctx["headers"],
        email="collector-owner-read@test.com",
        role="collector",
        full_name="Collector Owner",
    )

    assignment = await client.post(
        f"/api/projects/{ctx['project_id']}/assignments",
        json={
            "shared_element_id": ctx["element_id"],
            "collector_id": collector_one["id"],
        },
        headers=ctx["headers"],
    )
    assert assignment.status_code == 201

    data_point = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={
            "shared_element_id": ctx["element_id"],
            "numeric_value": 12,
        },
        headers=collector_one["headers"],
    )
    assert data_point.status_code == 201

    file_body = b"metric,value\nscope1,12\n"
    upload = await client.post(
        "/api/evidences/upload",
        files={"file": ("assigned.csv", file_body, "text/csv")},
        data={"title": "Assigned Evidence", "description": ""},
        headers=collector_two["headers"],
    )
    assert upload.status_code == 201

    link = await client.post(
        f"/api/data-points/{data_point.json()['id']}/evidences",
        json={"evidence_id": upload.json()["id"]},
        headers=ctx["headers"],
    )
    assert link.status_code == 200

    detail = await client.get(
        f"/api/evidences/{upload.json()['id']}",
        headers=collector_one["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["linked_data_points"][0]["data_point_id"] == data_point.json()["id"]

    download = await client.get(
        f"/api/evidences/{upload.json()['id']}/download",
        headers=collector_one["headers"],
    )
    assert download.status_code == 200
    assert download.content == file_body


@pytest.mark.asyncio
async def test_link_evidence_to_data_point(client: AsyncClient, ctx: dict):
    # Create data point
    dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 100},
        headers=ctx["headers"],
    )
    # Create evidence
    ev = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "p.pdf", "file_uri": "s3://p"},
        headers=ctx["headers"],
    )
    # Link
    resp = await client.post(
        f"/api/data-points/{dp.json()['id']}/evidences",
        json={"evidence_id": ev.json()["id"]},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["linked"] is True


@pytest.mark.asyncio
async def test_bind_requirement_rejects_item_outside_active_reporting_context(
    client: AsyncClient,
    ctx: dict,
):
    evidence = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "proof.pdf", "file_uri": "s3://proof"},
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    requirement_item_id = await _create_requirement_item(
        client,
        headers=ctx["headers"],
        project_id=ctx["project_id"],
        attach_to_project=False,
    )

    resp = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUIREMENT_ITEM_CONTEXT"


@pytest.mark.asyncio
async def test_bind_requirement_allows_item_active_in_org_project_context(
    client: AsyncClient,
    ctx: dict,
):
    evidence = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "proof.pdf", "file_uri": "s3://proof"},
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    requirement_item_id = await _create_requirement_item(
        client,
        headers=ctx["headers"],
        project_id=ctx["project_id"],
        attach_to_project=True,
    )

    resp = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["linked"] is True
    assert resp.json()["requirement_item_id"] == requirement_item_id
    assert resp.json()["project_id"] == ctx["project_id"]

    detail = await client.get(
        f"/api/evidences/{evidence.json()['id']}",
        headers=ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["linked_requirement_items"][0]["project_id"] == ctx["project_id"]
    assert detail.json()["linked_requirement_items"][0]["project_name"] == "Report 2025"


@pytest.mark.asyncio
async def test_bind_requirement_rejects_item_active_only_in_other_project_context(
    client: AsyncClient,
    ctx: dict,
):
    second_project = await client.post(
        "/api/projects",
        json={"name": "Report 2026"},
        headers=ctx["headers"],
    )
    assert second_project.status_code == 201

    dp = await client.post(
        f"/api/projects/{ctx['project_id']}/data-points",
        json={"shared_element_id": ctx["element_id"], "numeric_value": 100},
        headers=ctx["headers"],
    )
    assert dp.status_code == 201

    evidence = await client.post(
        "/api/evidences",
        json={
            "type": "file",
            "title": "Proof",
            "file_name": "proof.pdf",
            "file_uri": "s3://proof",
        },
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    linked = await client.post(
        f"/api/data-points/{dp.json()['id']}/evidences",
        json={"evidence_id": evidence.json()["id"]},
        headers=ctx["headers"],
    )
    assert linked.status_code == 200

    requirement_item_id = await _create_requirement_item(
        client,
        headers=ctx["headers"],
        project_id=second_project.json()["id"],
        attach_to_project=True,
    )

    resp = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": requirement_item_id},
        headers=ctx["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REQUIREMENT_ITEM_CONTEXT"
    assert "linked to this evidence" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_bind_requirement_requires_explicit_project_when_item_active_in_multiple_projects(
    client: AsyncClient,
    ctx: dict,
):
    standard = await client.post(
        "/api/standards",
        json={"code": "MULTI-CTX", "name": "Multi Context"},
        headers=ctx["headers"],
    )
    disclosure = await client.post(
        f"/api/standards/{standard.json()['id']}/disclosures",
        json={
            "code": "MC-1",
            "title": "Multi context disclosure",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=ctx["headers"],
    )
    item = await client.post(
        f"/api/disclosures/{disclosure.json()['id']}/items",
        json={
            "name": "Multi context item",
            "item_type": "metric",
            "value_type": "number",
            "is_required": True,
        },
        headers=ctx["headers"],
    )
    first_attach = await client.post(
        f"/api/projects/{ctx['project_id']}/standards",
        json={"standard_id": standard.json()["id"], "is_base_standard": False},
        headers=ctx["headers"],
    )
    assert first_attach.status_code == 200

    second_project = await client.post(
        "/api/projects",
        json={"name": "Report 2026"},
        headers=ctx["headers"],
    )
    assert second_project.status_code == 201
    second_attach = await client.post(
        f"/api/projects/{second_project.json()['id']}/standards",
        json={"standard_id": standard.json()["id"], "is_base_standard": True},
        headers=ctx["headers"],
    )
    assert second_attach.status_code == 200

    evidence = await client.post(
        "/api/evidences",
        json={"type": "file", "title": "Proof", "file_name": "proof.pdf", "file_uri": "s3://proof"},
        headers=ctx["headers"],
    )
    assert evidence.status_code == 201

    ambiguous = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": item.json()["id"]},
        headers=ctx["headers"],
    )
    assert ambiguous.status_code == 422
    assert ambiguous.json()["error"]["code"] == "AMBIGUOUS_PROJECT_CONTEXT"

    resolved = await client.post(
        f"/api/evidence/{evidence.json()['id']}/bind-requirement",
        json={"requirement_item_id": item.json()["id"], "project_id": ctx["project_id"]},
        headers=ctx["headers"],
    )
    assert resolved.status_code == 200
    assert resolved.json()["project_id"] == ctx["project_id"]

    detail = await client.get(
        f"/api/evidences/{evidence.json()['id']}",
        headers=ctx["headers"],
    )
    assert detail.status_code == 200
    assert detail.json()["linked_requirement_items"] == [
        {
            "project_id": ctx["project_id"],
            "project_name": "Report 2025",
            "requirement_item_id": item.json()["id"],
            "code": f"ITEM-{item.json()['id']}",
            "description": "Multi context item",
        }
    ]
