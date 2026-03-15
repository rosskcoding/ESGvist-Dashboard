"""
API tests for /api/v1/esg metric owner assignment endpoints.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User


@pytest.mark.asyncio
async def test_metric_owner_upsert_list_and_clear(client: AsyncClient, current_user: User):
    create = await client.post(
        "/api/v1/esg/metrics",
        json={"code": "OWN_TEST_1", "name": "Owner metric", "value_type": "number", "unit": "t"},
    )
    assert create.status_code == 201, create.text
    metric_id = create.json()["metric_id"]

    owners0 = await client.get("/api/v1/esg/metric-owners")
    assert owners0.status_code == 200, owners0.text
    assert owners0.json() == []

    upsert = await client.put(
        f"/api/v1/esg/metrics/{metric_id}/owner",
        json={"owner_user_id": str(current_user.user_id)},
    )
    assert upsert.status_code == 200, upsert.text
    payload = upsert.json()
    assert payload["metric_id"] == metric_id
    assert payload["owner_user_id"] == str(current_user.user_id)
    assert payload["owner_user_email"] == current_user.email
    assert payload["updated_at_utc"] is not None

    owners1 = await client.get("/api/v1/esg/metric-owners")
    assert owners1.status_code == 200, owners1.text
    data = owners1.json()
    assert len(data) == 1
    assert data[0]["metric_id"] == metric_id
    assert data[0]["owner_user_id"] == str(current_user.user_id)

    cleared = await client.put(f"/api/v1/esg/metrics/{metric_id}/owner", json={"owner_user_id": None})
    assert cleared.status_code == 200, cleared.text
    cleared_payload = cleared.json()
    assert cleared_payload["metric_id"] == metric_id
    assert cleared_payload["owner_user_id"] is None

    owners2 = await client.get("/api/v1/esg/metric-owners")
    assert owners2.status_code == 200, owners2.text
    assert owners2.json() == []


@pytest.mark.asyncio
async def test_list_metric_owners_filters_by_metric_ids(client: AsyncClient, current_user: User):
    m1 = await client.post(
        "/api/v1/esg/metrics",
        json={"code": "OWN_TEST_2A", "name": "Owner metric A", "value_type": "number"},
    )
    assert m1.status_code == 201, m1.text
    m1_id = m1.json()["metric_id"]

    m2 = await client.post(
        "/api/v1/esg/metrics",
        json={"code": "OWN_TEST_2B", "name": "Owner metric B", "value_type": "number"},
    )
    assert m2.status_code == 201, m2.text
    m2_id = m2.json()["metric_id"]

    upsert = await client.put(
        f"/api/v1/esg/metrics/{m1_id}/owner",
        json={"owner_user_id": str(current_user.user_id)},
    )
    assert upsert.status_code == 200, upsert.text

    only_m2 = await client.get("/api/v1/esg/metric-owners", params={"metric_ids": [m2_id]})
    assert only_m2.status_code == 200, only_m2.text
    assert only_m2.json() == []

    both = await client.get("/api/v1/esg/metric-owners", params={"metric_ids": [m1_id, m2_id]})
    assert both.status_code == 200, both.text
    data = both.json()
    assert len(data) == 1
    assert data[0]["metric_id"] == m1_id


@pytest.mark.asyncio
async def test_upsert_metric_owner_requires_active_company_membership(client: AsyncClient, db_session: AsyncSession):
    create = await client.post(
        "/api/v1/esg/metrics",
        json={"code": "OWN_TEST_3", "name": "Owner metric", "value_type": "number"},
    )
    assert create.status_code == 201, create.text
    metric_id = create.json()["metric_id"]

    outsider = User(
        user_id=uuid4(),
        email="outsider@example.com",
        password_hash="not-used",
        full_name="Outsider",
        is_active=True,
        is_superuser=False,
        locale_scopes=None,
    )
    db_session.add(outsider)
    await db_session.flush()

    resp = await client.put(
        f"/api/v1/esg/metrics/{metric_id}/owner",
        json={"owner_user_id": str(outsider.user_id)},
    )
    assert resp.status_code == 422, resp.text

