import pytest
from httpx import AsyncClient


@pytest.fixture
async def admin_headers(client: AsyncClient) -> dict:
    """Create the first user (platform_admin) and return auth headers."""
    await client.post(
        "/api/auth/register",
        json={"email": "admin@test.com", "password": "password123", "full_name": "Admin"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --- Standards CRUD ---
@pytest.mark.asyncio
async def test_create_standard(client: AsyncClient, admin_headers: dict):
    resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI Standards 2021", "version": "2021"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "GRI"
    assert data["name"] == "GRI Standards 2021"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_list_standards(client: AsyncClient, admin_headers: dict):
    await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI 2021"},
        headers=admin_headers,
    )
    resp = await client.get("/api/standards", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_duplicate_code_returns_409(client: AsyncClient, admin_headers: dict):
    await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI 1"},
        headers=admin_headers,
    )
    resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI 2"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_deactivate_standard(client: AsyncClient, admin_headers: dict):
    create_resp = await client.post(
        "/api/standards",
        json={"code": "OLD", "name": "Old Standard"},
        headers=admin_headers,
    )
    sid = create_resp.json()["id"]

    resp = await client.post(f"/api/standards/{sid}/deactivate", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_standard(client: AsyncClient, admin_headers: dict):
    create_resp = await client.post(
        "/api/standards",
        json={"code": "UPD", "name": "Original"},
        headers=admin_headers,
    )
    sid = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/standards/{sid}",
        json={"name": "Updated Name"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, admin_headers: dict):
    for i in range(5):
        await client.post(
            "/api/standards",
            json={"code": f"STD{i}", "name": f"Standard {i}"},
            headers=admin_headers,
        )

    resp = await client.get("/api/standards?page=1&page_size=2", headers=admin_headers)
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


# --- Sections ---
@pytest.mark.asyncio
async def test_create_section_tree(client: AsyncClient, admin_headers: dict):
    std_resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=admin_headers,
    )
    sid = std_resp.json()["id"]

    # Root section
    r1 = await client.post(
        f"/api/standards/{sid}/sections",
        json={"title": "Environmental", "code": "300", "sort_order": 1},
        headers=admin_headers,
    )
    assert r1.status_code == 201
    parent_id = r1.json()["id"]

    # Child section
    r2 = await client.post(
        f"/api/standards/{sid}/sections",
        json={
            "title": "Emissions",
            "code": "305",
            "parent_section_id": parent_id,
            "sort_order": 1,
        },
        headers=admin_headers,
    )
    assert r2.status_code == 201

    # List as tree
    resp = await client.get(f"/api/standards/{sid}/sections", headers=admin_headers)
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) == 1  # one root
    assert tree[0]["title"] == "Environmental"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["title"] == "Emissions"


# --- Disclosures ---
@pytest.mark.asyncio
async def test_create_disclosure(client: AsyncClient, admin_headers: dict):
    std_resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=admin_headers,
    )
    sid = std_resp.json()["id"]

    resp = await client.post(
        f"/api/standards/{sid}/disclosures",
        json={
            "code": "305-1",
            "title": "Direct GHG emissions",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "305-1"
    assert data["mandatory_level"] == "mandatory"


@pytest.mark.asyncio
async def test_duplicate_disclosure_code_returns_409(client: AsyncClient, admin_headers: dict):
    std_resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=admin_headers,
    )
    sid = std_resp.json()["id"]

    await client.post(
        f"/api/standards/{sid}/disclosures",
        json={
            "code": "305-1",
            "title": "D1",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    resp = await client.post(
        f"/api/standards/{sid}/disclosures",
        json={
            "code": "305-1",
            "title": "D2",
            "requirement_type": "quantitative",
            "mandatory_level": "mandatory",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_disclosure_applicability_rule(client: AsyncClient, admin_headers: dict):
    std_resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=admin_headers,
    )
    sid = std_resp.json()["id"]

    resp = await client.post(
        f"/api/standards/{sid}/disclosures",
        json={
            "code": "305-3",
            "title": "Scope 3",
            "requirement_type": "quantitative",
            "mandatory_level": "conditional",
            "applicability_rule": {"if_material": True, "if_sector": "oil_gas"},
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["applicability_rule"]["if_material"] is True


@pytest.mark.asyncio
async def test_list_disclosures(client: AsyncClient, admin_headers: dict):
    std_resp = await client.post(
        "/api/standards",
        json={"code": "GRI", "name": "GRI"},
        headers=admin_headers,
    )
    sid = std_resp.json()["id"]

    for i in range(3):
        await client.post(
            f"/api/standards/{sid}/disclosures",
            json={
                "code": f"305-{i + 1}",
                "title": f"D{i + 1}",
                "requirement_type": "quantitative",
                "mandatory_level": "mandatory",
            },
            headers=admin_headers,
        )

    resp = await client.get(f"/api/standards/{sid}/disclosures", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


# --- Permissions ---
@pytest.mark.asyncio
async def test_non_admin_cannot_create_standard(client: AsyncClient):
    # Register first user as platform_admin and create a real tenant context.
    await client.post(
        "/api/auth/register",
        json={
            "email": "admin@test.com",
            "password": "password123",
            "full_name": "Admin",
        },
    )
    admin_login_resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@test.com", "password": "password123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login_resp.json()['access_token']}"}
    org_resp = await client.post(
        "/api/organizations/setup",
        json={"name": "Standards Org", "country": "GB"},
        headers=admin_headers,
    )
    org_id = org_resp.json()["organization_id"]
    admin_headers["X-Organization-Id"] = str(org_id)

    # Register second user (no role bindings to any org)
    await client.post(
        "/api/auth/register",
        json={"email": "user@test.com", "password": "password123", "full_name": "User"},
    )
    invite_resp = await client.post(
        "/api/auth/invitations",
        json={"email": "user@test.com", "role": "collector"},
        headers=admin_headers,
    )
    assert invite_resp.status_code == 201
    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "user@test.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    accept_resp = await client.post(
        f"/api/invitations/accept/{invite_resp.json()['token']}",
        headers=headers,
    )
    assert accept_resp.status_code == 200
    headers["X-Organization-Id"] = str(org_id)

    resp = await client.post(
        "/api/standards",
        json={"code": "HACK", "name": "Hack"},
        headers=headers,
    )
    assert resp.status_code == 403
