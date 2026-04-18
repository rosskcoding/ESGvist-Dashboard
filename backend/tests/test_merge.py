import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.db.models.role_binding import RoleBinding
from tests.conftest import TestSessionLocal

async def _setup_two_standards(client, headers):
    """Create GRI + IFRS standards with items and shared element mapped to both."""
    # Shared element
    el = await client.post(
        "/api/shared-elements", json={"code": "GHG_S1", "name": "Scope 1", "concept_domain": "emissions"},
        headers=headers,
    )
    el_id = el.json()["id"]

    # GRI
    gri = await client.post("/api/standards", json={"code": "GRI", "name": "GRI 2021"}, headers=headers)
    gri_disc = await client.post(
        f"/api/standards/{gri.json()['id']}/disclosures",
        json={"code": "305-1", "title": "Emissions", "requirement_type": "quantitative", "mandatory_level": "mandatory"},
        headers=headers,
    )
    gri_item = await client.post(
        f"/api/disclosures/{gri_disc.json()['id']}/items",
        json={"name": "GRI Scope 1", "item_type": "metric", "value_type": "number"},
        headers=headers,
    )

    # IFRS
    ifrs = await client.post("/api/standards", json={"code": "IFRS_S2", "name": "IFRS S2"}, headers=headers)
    ifrs_disc = await client.post(
        f"/api/standards/{ifrs.json()['id']}/disclosures",
        json={"code": "S2.29", "title": "Climate", "requirement_type": "quantitative", "mandatory_level": "mandatory"},
        headers=headers,
    )
    ifrs_item = await client.post(
        f"/api/disclosures/{ifrs_disc.json()['id']}/items",
        json={"name": "IFRS Scope 1", "item_type": "metric", "value_type": "number"},
        headers=headers,
    )

    # Orphan item (no mapping)
    orphan_item = await client.post(
        f"/api/disclosures/{ifrs_disc.json()['id']}/items",
        json={"name": "Financial Impact", "item_type": "narrative", "value_type": "text"},
        headers=headers,
    )

    # Map both to same shared element
    await client.post(
        "/api/mappings",
        json={"requirement_item_id": gri_item.json()["id"], "shared_element_id": el_id},
        headers=headers,
    )
    await client.post(
        "/api/mappings",
        json={"requirement_item_id": ifrs_item.json()["id"], "shared_element_id": el_id},
        headers=headers,
    )

    return {
        "gri_id": gri.json()["id"],
        "ifrs_id": ifrs.json()["id"],
        "element_id": el_id,
    }


@pytest.fixture
async def ctx(client: AsyncClient) -> dict:
    await client.post(
        "/api/auth/register",
        json={"email": "a@t.com", "password": "password123", "full_name": "A"},
    )
    login = await client.post("/api/auth/login", json={"email": "a@t.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await client.get("/api/auth/me", headers=headers)

    org = await client.post("/api/organizations/setup", json={"name": "Co"}, headers=headers)
    headers["X-Organization-Id"] = str(org.json()["organization_id"])

    stds = await _setup_two_standards(client, headers)

    proj = await client.post("/api/projects", json={"name": "Multi"}, headers=headers)
    proj_id = proj.json()["id"]

    # Add both standards to project
    await client.post(
        f"/api/projects/{proj_id}/standards",
        json={"standard_id": stds["gri_id"], "is_base_standard": True},
        headers=headers,
    )
    await client.post(
        f"/api/projects/{proj_id}/standards",
        json={"standard_id": stds["ifrs_id"]},
        headers=headers,
    )

    return {
        "headers": headers,
        "project_id": proj_id,
        "org_id": org.json()["organization_id"],
        "user_id": me.json()["id"],
        **stds,
    }


@pytest.mark.asyncio
async def test_merged_view_common_elements(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/projects/{ctx['project_id']}/merge", headers=ctx["headers"])
    assert resp.status_code == 200
    data = resp.json()

    # Should have common element (GHG_S1 in both GRI + IFRS)
    common = [e for e in data["elements"] if e["is_common"]]
    assert len(common) == 1
    assert set(common[0]["required_by"]) == {"GRI", "IFRS_S2"}


@pytest.mark.asyncio
async def test_merged_view_orphans(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/projects/{ctx['project_id']}/merge", headers=ctx["headers"])
    data = resp.json()

    # Financial Impact has no shared element mapping → orphan
    assert len(data["orphans"]) == 1
    assert data["orphans"][0]["name"] == "Financial Impact"


@pytest.mark.asyncio
async def test_merged_view_summary(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/projects/{ctx['project_id']}/merge", headers=ctx["headers"])
    summary = resp.json()["summary"]

    assert summary["common"] == 1
    assert summary["orphans"] == 1
    assert set(summary["standards"]) == {"GRI", "IFRS_S2"}


@pytest.mark.asyncio
async def test_esg_manager_can_read_merge_views(client: AsyncClient, ctx: dict):
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

    merged = await client.get(f"/api/projects/{ctx['project_id']}/merge", headers=ctx["headers"])
    assert merged.status_code == 200
    merged_payload = merged.json()
    assert "summary" in merged_payload
    assert "elements" in merged_payload

    coverage = await client.get(f"/api/projects/{ctx['project_id']}/merge/coverage", headers=ctx["headers"])
    assert coverage.status_code == 200
    assert "coverage" in coverage.json()


@pytest.mark.asyncio
async def test_coverage(client: AsyncClient, ctx: dict):
    resp = await client.get(f"/api/projects/{ctx['project_id']}/merge/coverage", headers=ctx["headers"])
    assert resp.status_code == 200
    coverage = resp.json()["coverage"]
    assert "GRI" in coverage
    assert "IFRS_S2" in coverage
    assert coverage["GRI"]["total_items"] == 1
    assert coverage["GRI"]["complete_items"] == 0
    assert coverage["GRI"]["missing_items"] == 1
    assert coverage["GRI"]["completion_percent"] == 0.0
    assert coverage["IFRS_S2"]["total_items"] == 2
    assert coverage["IFRS_S2"]["missing_items"] == 2
    assert coverage["IFRS_S2"]["completion_percent"] == 0.0


@pytest.mark.asyncio
async def test_merged_view_no_standards(client: AsyncClient, ctx: dict):
    # New project without standards
    proj = await client.post("/api/projects", json={"name": "Empty"}, headers=ctx["headers"])
    resp = await client.get(f"/api/projects/{proj.json()['id']}/merge", headers=ctx["headers"])
    assert resp.status_code == 200
    assert resp.json()["summary"]["total"] == 0
