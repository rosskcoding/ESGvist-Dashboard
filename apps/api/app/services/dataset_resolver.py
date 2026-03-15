"""
Dataset resolver for charts and tables.

Async helper to load dataset data for block rendering.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Block, Dataset
from app.services.dataset_service import DatasetService


async def resolve_dataset_for_block(
    block: Block,
    db: AsyncSession,
    company_id: UUID,
) -> dict | None:
    """
    Resolve dataset data for a block.

    If block references a dataset (dataset_id in data_json or root level),
    loads the dataset and returns it as inline_data format for rendering.

    Args:
        block: Block instance
        db: Database session
        company_id: Company UUID for tenant isolation

    Returns:
        Inline data dict {columns: [...], rows: [[...]]} or None
    """
    # Check if block has dataset reference
    dataset_id = getattr(block, 'dataset_id', None)

    # Also check data_source.dataset_id for charts/tables
    if not dataset_id and block.data_json:
        data_source = block.data_json.get('data_source')
        if data_source:
            dataset_id = data_source.get('dataset_id')

    if not dataset_id:
        return None

    # Load dataset
    service = DatasetService(db)
    dataset = await service.get_dataset(
        dataset_id=UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id,
        company_id=company_id,
    )

    if not dataset:
        return None

    # Convert to inline format
    columns = dataset.schema_json.get('columns', [])
    column_keys = [col.get('key', f'col_{i}') for i, col in enumerate(columns)]

    return {
        'columns': column_keys,
        'rows': dataset.rows_json or [],
    }


async def resolve_dataset_by_id(
    dataset_id: UUID,
    db: AsyncSession,
    company_id: UUID,
    revision_id: UUID | None = None,
) -> Dataset | None:
    """
    Load dataset or specific revision.

    Args:
        dataset_id: Dataset UUID
        db: Database session
        company_id: Company UUID
        revision_id: Optional revision UUID (None = current)

    Returns:
        Dataset or DatasetRevision instance
    """
    service = DatasetService(db)

    if revision_id:
        return await service.get_revision(
            revision_id=revision_id,
            company_id=company_id,
        )
    else:
        return await service.get_dataset(
            dataset_id=dataset_id,
            company_id=company_id,
        )


