"""
API tests for company context inference in ESG endpoints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Company, CompanyMembership, User
from app.domain.models.enums import CompanyStatus


@pytest.mark.asyncio
async def test_esg_requires_company_id_when_multiple_active_memberships(
    client: AsyncClient, db_session: AsyncSession, current_user: User
):
    # Add a second active company membership for the same user.
    company2 = Company(
        company_id=uuid4(),
        name=f"Second Company {uuid4()}",
        status=CompanyStatus.ACTIVE,
        created_by=current_user.user_id,
    )
    db_session.add(company2)
    await db_session.flush()

    membership2 = CompanyMembership(
        company=company2,
        user=current_user,
        is_active=True,
        created_by=current_user.user_id,
    )
    db_session.add(membership2)
    await db_session.flush()

    # No company_id -> ambiguous -> structured 409.
    resp = await client.get("/api/v1/esg/metrics")
    assert resp.status_code == 409, resp.text
    data = resp.json()
    assert data["error"] == "company_context_required"
    assert data["message"] == "Provide company_id"
    assert "company_id" in data["hint"]
    assert isinstance(data["companies"], list)
    assert len(data["companies"]) >= 2

    # With company_id -> ok.
    resp2 = await client.get("/api/v1/esg/metrics", params={"company_id": str(company2.company_id)})
    assert resp2.status_code == 200, resp2.text

