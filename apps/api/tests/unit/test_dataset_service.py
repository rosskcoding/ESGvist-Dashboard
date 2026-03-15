"""
Unit tests for DatasetService.
"""

from uuid import uuid4

import pytest

from app.domain.schemas.dataset import DatasetCreate, DatasetRevisionCreate, DatasetUpdate
from app.services.dataset_service import DatasetService


@pytest.mark.asyncio
async def test_create_dataset(db_session, test_company, test_user):
    """Test creating a dataset."""
    service = DatasetService(db_session)

    data = DatasetCreate(
        name="Test Dataset",
        description="Test description",
        schema_json={"columns": [{"key": "col1", "type": "text"}]},
        rows_json=[["value1"], ["value2"]],
        meta_json={"source": "test"},
    )

    dataset = await service.create_dataset(
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=data,
    )

    assert dataset.dataset_id is not None
    assert dataset.name == "Test Dataset"
    assert dataset.current_revision == 1
    assert len(dataset.rows_json) == 2

    # Check initial revision was created
    revisions = await service.list_revisions(dataset.dataset_id, test_company.company_id)
    assert len(revisions) == 1
    assert revisions[0].revision_number == 1


@pytest.mark.asyncio
async def test_get_dataset(db_session, test_company, test_user):
    """Test retrieving a dataset."""
    service = DatasetService(db_session)

    data = DatasetCreate(
        name="Test Dataset",
        schema_json={"columns": []},
        rows_json=[],
    )

    created = await service.create_dataset(
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=data,
    )

    retrieved = await service.get_dataset(created.dataset_id, test_company.company_id)

    assert retrieved is not None
    assert retrieved.dataset_id == created.dataset_id
    assert retrieved.name == "Test Dataset"


@pytest.mark.asyncio
async def test_list_datasets(db_session, test_company, test_user):
    """Test listing datasets."""
    service = DatasetService(db_session)

    # Create multiple datasets
    for i in range(3):
        data = DatasetCreate(
            name=f"Dataset {i}",
            schema_json={"columns": []},
            rows_json=[],
        )
        await service.create_dataset(
            company_id=test_company.company_id,
            user_id=test_user.user_id,
            data=data,
        )

    datasets, total = await service.list_datasets(
        company_id=test_company.company_id,
        skip=0,
        limit=10,
    )

    assert len(datasets) == 3
    assert total == 3


@pytest.mark.asyncio
async def test_update_dataset(db_session, test_company, test_user):
    """Test updating a dataset."""
    service = DatasetService(db_session)

    data = DatasetCreate(
        name="Original Name",
        schema_json={"columns": []},
        rows_json=[],
    )

    dataset = await service.create_dataset(
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=data,
    )

    update_data = DatasetUpdate(
        name="Updated Name",
        rows_json=[["new", "data"]],
    )

    updated = await service.update_dataset(
        dataset_id=dataset.dataset_id,
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=update_data,
        create_revision=True,
    )

    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.current_revision == 2

    # Check revision was created
    revisions = await service.list_revisions(dataset.dataset_id, test_company.company_id)
    assert len(revisions) == 2


@pytest.mark.asyncio
async def test_delete_dataset_soft(db_session, test_company, test_user):
    """Test soft deleting a dataset."""
    service = DatasetService(db_session)

    data = DatasetCreate(
        name="To Delete",
        schema_json={"columns": []},
        rows_json=[],
    )

    dataset = await service.create_dataset(
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=data,
    )

    deleted = await service.delete_dataset(
        dataset_id=dataset.dataset_id,
        company_id=test_company.company_id,
        hard_delete=False,
    )

    assert deleted is True

    # Should not be retrievable without include_deleted
    retrieved = await service.get_dataset(dataset.dataset_id, test_company.company_id)
    assert retrieved is None

    # But should exist with include_deleted
    retrieved = await service.get_dataset(
        dataset.dataset_id,
        test_company.company_id,
        include_deleted=True,
    )
    assert retrieved is not None
    assert retrieved.is_deleted is True


@pytest.mark.asyncio
async def test_create_revision(db_session, test_company, test_user):
    """Test creating a manual revision."""
    service = DatasetService(db_session)

    data = DatasetCreate(
        name="Test Dataset",
        schema_json={"columns": []},
        rows_json=[["data"]],
    )

    dataset = await service.create_dataset(
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=data,
    )

    revision_data = DatasetRevisionCreate(reason="Manual snapshot for testing")

    revision = await service.create_revision(
        dataset_id=dataset.dataset_id,
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=revision_data,
    )

    assert revision is not None
    assert revision.revision_number == 2
    assert revision.reason == "Manual snapshot for testing"
    assert revision.rows_json == [["data"]]


@pytest.mark.asyncio
async def test_tenant_isolation(db_session, test_company, test_user):
    """Test that datasets are isolated by company."""
    service = DatasetService(db_session)

    # Create dataset for company A
    data = DatasetCreate(
        name="Company A Dataset",
        schema_json={"columns": []},
        rows_json=[],
    )

    dataset = await service.create_dataset(
        company_id=test_company.company_id,
        user_id=test_user.user_id,
        data=data,
    )

    # Try to access with different company_id
    wrong_company_id = uuid4()

    retrieved = await service.get_dataset(dataset.dataset_id, wrong_company_id)
    assert retrieved is None

