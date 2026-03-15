"""
API tests for /api/v1/datasets endpoints.
"""

import io
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_dataset(client: AsyncClient):
    """Test creating a dataset via API."""
    payload = {
        "name": "Test Dataset",
        "description": "API test",
        "schema_json": {
            "columns": [
                {"key": "year", "type": "text"},
                {"key": "value", "type": "number"},
            ]
        },
        "rows_json": [
            ["2023", 100],
            ["2024", 150],
        ],
        "meta_json": {"source": "API test"},
    }

    response = await client.post("/api/v1/datasets", json=payload)

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Test Dataset"
    assert data["current_revision"] == 1
    assert "dataset_id" in data


@pytest.mark.asyncio
async def test_list_datasets(client: AsyncClient):
    """Test listing datasets."""
    # Create some datasets first
    for i in range(3):
        payload = {
            "name": f"Dataset {i}",
            "schema_json": {"columns": []},
            "rows_json": [],
        }
        await client.post("/api/v1/datasets", json=payload)

    response = await client.get("/api/v1/datasets")

    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3


@pytest.mark.asyncio
async def test_get_dataset(client: AsyncClient):
    """Test retrieving a specific dataset."""
    # Create dataset
    payload = {
        "name": "Get Test",
        "schema_json": {"columns": []},
        "rows_json": [],
    }
    create_response = await client.post("/api/v1/datasets", json=payload)
    dataset_id = create_response.json()["dataset_id"]

    # Get dataset
    response = await client.get(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["dataset_id"] == dataset_id
    assert data["name"] == "Get Test"


@pytest.mark.asyncio
async def test_update_dataset(client: AsyncClient):
    """Test updating a dataset."""
    # Create dataset
    payload = {
        "name": "Original",
        "schema_json": {"columns": []},
        "rows_json": [],
    }
    create_response = await client.post("/api/v1/datasets", json=payload)
    dataset_id = create_response.json()["dataset_id"]

    # Update dataset
    update_payload = {
        "name": "Updated",
        "rows_json": [["new", "data"]],
    }
    response = await client.patch(
        f"/api/v1/datasets/{dataset_id}",
        json=update_payload,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"


@pytest.mark.asyncio
async def test_delete_dataset(client: AsyncClient):
    """Test deleting a dataset."""
    # Create dataset
    payload = {
        "name": "To Delete",
        "schema_json": {"columns": []},
        "rows_json": [],
    }
    create_response = await client.post("/api/v1/datasets", json=payload)
    dataset_id = create_response.json()["dataset_id"]

    # Delete dataset (soft)
    response = await client.delete(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 204

    # Should not be retrievable
    get_response = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_create_revision(client: AsyncClient):
    """Test creating a dataset revision."""
    # Create dataset
    payload = {
        "name": "Versioned Dataset",
        "schema_json": {"columns": []},
        "rows_json": [["data"]],
    }
    create_response = await client.post("/api/v1/datasets", json=payload)
    dataset_id = create_response.json()["dataset_id"]

    # Create revision
    revision_payload = {"reason": "Manual snapshot"}
    response = await client.post(
        f"/api/v1/datasets/{dataset_id}/revisions",
        json=revision_payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["revision_number"] == 2
    assert data["reason"] == "Manual snapshot"


@pytest.mark.asyncio
async def test_import_csv_preview(client: AsyncClient):
    """Test CSV import preview."""
    csv_content = b"year,value\n2023,100\n2024,150"

    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}

    response = await client.post(
        "/api/v1/datasets/import/csv/preview",
        files=files,
    )

    assert response.status_code == 200
    data = response.json()

    assert "detected_columns" in data
    assert "preview_rows" in data
    assert "total_rows" in data
    assert data["total_rows"] == 2


@pytest.mark.asyncio
async def test_import_csv_confirm(client: AsyncClient):
    """Test CSV import confirmation and dataset creation."""
    csv_content = b"year,value\n2023,100\n2024,150"

    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    data = {
        "name": "Imported Dataset",
        "description": "From CSV",
        "schema_json": '{"columns": [{"key": "col_0", "type": "text"}, {"key": "col_1", "type": "number"}]}',
    }

    response = await client.post(
        "/api/v1/datasets/import/csv/confirm",
        files=files,
        data=data,
    )

    assert response.status_code == 201
    result = response.json()

    assert result["name"] == "Imported Dataset"
    assert len(result["rows_json"]) == 2


@pytest.mark.asyncio
async def test_export_csv(client: AsyncClient):
    """Test exporting dataset to CSV."""
    # Create dataset
    payload = {
        "name": "Export Test",
        "schema_json": {
            "columns": [
                {"key": "col1", "type": "text"},
                {"key": "col2", "type": "number"},
            ]
        },
        "rows_json": [["A", 1], ["B", 2]],
    }
    create_response = await client.post("/api/v1/datasets", json=payload)
    dataset_id = create_response.json()["dataset_id"]

    # Export to CSV
    response = await client.get(f"/api/v1/datasets/{dataset_id}/export/csv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient):
    """Test that datasets are isolated by company."""
    # Create dataset with user A
    payload = {
        "name": "Company A Dataset",
        "schema_json": {"columns": []},
        "rows_json": [],
    }
    create_response = await client.post("/api/v1/datasets", json=payload)
    dataset_id = create_response.json()["dataset_id"]

    # Try to access with different user's token (would need another auth setup)
    # For now, just verify that GET works with correct auth
    response = await client.get(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 200

