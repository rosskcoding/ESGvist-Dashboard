"""
Integration tests for Release Build API endpoints.

Focus: idempotency for POST /api/v1/releases
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duplicate_build_returns_existing(auth_client: AsyncClient, test_report_id: str):
    """
    Creating the same build twice should return the same build_id (idempotency).
    """
    payload = {
        "report_id": test_report_id,
        "build_type": "draft",
        "locales": ["ru"],
        # Use defaults for package/scope/theme where possible
    }

    resp1 = await auth_client.post("/api/v1/releases", json=payload)
    assert resp1.status_code == 201, resp1.text
    build_id_1 = resp1.json()["build_id"]

    resp2 = await auth_client.post("/api/v1/releases", json=payload)
    assert resp2.status_code == 201, resp2.text
    build_id_2 = resp2.json()["build_id"]

    assert build_id_1 == build_id_2  # Idempotency



