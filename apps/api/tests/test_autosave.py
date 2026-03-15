"""
Tests for block autosave endpoint.

Tests cover:
- Unified autosave (data_json + fields_json)
- Optimistic locking (version conflicts)
- Validation
- HTML sanitization
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def test_block(
    client: AsyncClient,
    auth_headers: dict,
    test_report_id: str,
    test_section_id: str,
) -> dict:
    """Create a test block for autosave tests."""
    response = await client.post(
        "/api/v1/blocks",
        headers=auth_headers,
        json={
            "report_id": test_report_id,
            "section_id": test_section_id,
            "type": "text",
            "variant": "default",
            "order_index": 0,
            "data_json": {"test": "data"},
            "i18n": [
                {
                    "locale": "ru",
                    "fields_json": {"title": "Test Title"},
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_autosave_data_json_only(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave with only data_json update."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "ru",
        "expected_version": test_block["version"],
        "data_json": {"new_field": "new_value"},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == test_block["version"] + 1
    assert data["data_json"]["new_field"] == "new_value"


@pytest.mark.asyncio
async def test_autosave_fields_json_only(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave with only fields_json update."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "ru",
        "expected_version": test_block["version"],
        "fields_json": {"title": "New Title"},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == test_block["version"] + 1

    # Check i18n was updated
    ru_i18n = next((i for i in data["i18n"] if i["locale"] == "ru"), None)
    assert ru_i18n is not None
    assert ru_i18n["fields_json"]["title"] == "New Title"


@pytest.mark.asyncio
async def test_autosave_both_data_and_fields(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave with both data_json and fields_json."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "ru",
        "expected_version": test_block["version"],
        "data_json": {"layout": "grid"},
        "fields_json": {"title": "Updated Title"},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == test_block["version"] + 1
    assert data["data_json"]["layout"] == "grid"

    ru_i18n = next((i for i in data["i18n"] if i["locale"] == "ru"), None)
    assert ru_i18n["fields_json"]["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_autosave_version_conflict(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave returns 409 on version conflict."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "ru",
        "expected_version": test_block["version"] + 100,  # Wrong version (too high)
        "fields_json": {"title": "Should Fail"},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 409
    assert "Version conflict" in response.json()["detail"]


@pytest.mark.asyncio
async def test_autosave_creates_i18n_if_missing(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave creates i18n entry if it doesn't exist."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    # Update for locale that doesn't exist yet
    payload = {
        "locale": "en",
        "expected_version": test_block["version"],
        "fields_json": {"title": "English Title"},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    en_i18n = next((i for i in data["i18n"] if i["locale"] == "en"), None)
    assert en_i18n is not None
    assert en_i18n["fields_json"]["title"] == "English Title"
    assert en_i18n["status"] == "draft"


@pytest.mark.asyncio
async def test_autosave_sanitizes_html(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave sanitizes HTML fields."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "ru",
        "expected_version": test_block["version"],
        "fields_json": {
            "content_html": '<p>Safe</p><script>alert("XSS")</script>',
        },
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    ru_i18n = next((i for i in data["i18n"] if i["locale"] == "ru"), None)
    # Script tag should be removed
    assert "<script>" not in ru_i18n["fields_json"]["content_html"]
    assert "<p>Safe</p>" in ru_i18n["fields_json"]["content_html"]


@pytest.mark.asyncio
async def test_autosave_invalid_locale(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave rejects invalid locale."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "fr",  # Not supported
        "expected_version": test_block["version"],
        "fields_json": {"title": "French"},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 422
    # Pydantic v2 returns array of errors
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any("Invalid locale" in str(err) for err in detail)


@pytest.mark.asyncio
async def test_autosave_requires_at_least_one_field(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave requires at least one of data_json or fields_json."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    payload = {
        "locale": "ru",
        "expected_version": test_block["version"],
        # Neither data_json nor fields_json provided
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_autosave_increments_version_only_if_changed(
    client: AsyncClient,
    auth_headers: dict,
    test_block: dict,
):
    """Test autosave increments version when content changes."""
    url = f"/api/v1/blocks/{test_block['block_id']}/autosave"

    original_version = test_block["version"]

    payload = {
        "locale": "ru",
        "expected_version": original_version,
        "data_json": {"updated": True},
    }

    response = await client.patch(url, json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["version"] == original_version + 1

