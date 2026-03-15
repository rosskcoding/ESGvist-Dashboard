"""
Dataset CRUD service.

Handles dataset creation, updates, revisions, and data operations.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Dataset, DatasetRevision
from app.domain.schemas.dataset import (
    DatasetCreate,
    DatasetListItem,
    DatasetResponse,
    DatasetRevisionCreate,
    DatasetRevisionResponse,
    DatasetUpdate,
)


class DatasetService:
    """Service for Dataset CRUD operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_dataset(
        self,
        company_id: UUID,
        user_id: UUID,
        data: DatasetCreate,
    ) -> Dataset:
        """
        Create a new dataset.

        Args:
            company_id: Company UUID
            user_id: Creator user UUID
            data: Dataset creation data

        Returns:
            Created Dataset instance
        """
        dataset = Dataset(
            company_id=company_id,
            name=data.name,
            description=data.description,
            schema_json=data.schema_json,
            rows_json=data.rows_json,
            meta_json=data.meta_json,
            current_revision=1,
            created_by=user_id,
            updated_by=user_id,
            is_deleted=False,
        )

        self.db.add(dataset)
        await self.db.flush()

        # Create initial revision
        initial_revision = DatasetRevision(
            dataset_id=dataset.dataset_id,
            revision_number=1,
            schema_json=dataset.schema_json,
            rows_json=dataset.rows_json,
            meta_json=dataset.meta_json,
            created_by=user_id,
            reason="Initial version",
        )

        self.db.add(initial_revision)
        await self.db.commit()
        await self.db.refresh(dataset)

        return dataset

    async def get_dataset(
        self,
        dataset_id: UUID,
        company_id: UUID,
        include_deleted: bool = False,
    ) -> Dataset | None:
        """
        Get dataset by ID.

        Args:
            dataset_id: Dataset UUID
            company_id: Company UUID (for tenant isolation)
            include_deleted: Include soft-deleted datasets

        Returns:
            Dataset or None if not found
        """
        conditions = [
            Dataset.dataset_id == dataset_id,
            Dataset.company_id == company_id,
        ]

        if not include_deleted:
            conditions.append(Dataset.is_deleted == False)  # noqa: E712

        stmt = select(Dataset).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_datasets(
        self,
        company_id: UUID,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Dataset], int]:
        """
        List datasets for a company.

        Args:
            company_id: Company UUID
            include_deleted: Include soft-deleted datasets
            skip: Offset for pagination
            limit: Max items to return

        Returns:
            Tuple of (datasets, total_count)
        """
        conditions = [Dataset.company_id == company_id]

        if not include_deleted:
            conditions.append(Dataset.is_deleted == False)  # noqa: E712

        # Get total count
        count_stmt = select(Dataset).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total = len(count_result.scalars().all())

        # Get paginated results
        stmt = (
            select(Dataset)
            .where(and_(*conditions))
            .order_by(desc(Dataset.updated_at_utc))
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        datasets = result.scalars().all()

        return list(datasets), total

    async def update_dataset(
        self,
        dataset_id: UUID,
        company_id: UUID,
        user_id: UUID,
        data: DatasetUpdate,
        create_revision: bool = False,
    ) -> Dataset | None:
        """
        Update dataset.

        Args:
            dataset_id: Dataset UUID
            company_id: Company UUID
            user_id: User making the update
            data: Update data
            create_revision: Whether to create a new revision snapshot

        Returns:
            Updated Dataset or None if not found
        """
        dataset = await self.get_dataset(dataset_id, company_id)
        if not dataset:
            return None

        # Track if data changed (for revision creation)
        data_changed = False

        # Update fields
        if data.name is not None:
            dataset.name = data.name
        if data.description is not None:
            dataset.description = data.description
        if data.schema_json is not None:
            dataset.schema_json = data.schema_json
            data_changed = True
        if data.rows_json is not None:
            dataset.rows_json = data.rows_json
            data_changed = True
        if data.meta_json is not None:
            dataset.meta_json = data.meta_json

        dataset.updated_by = user_id
        dataset.updated_at_utc = datetime.now(UTC)

        # Create revision if requested or if data changed
        if create_revision and data_changed:
            dataset.current_revision += 1

            revision = DatasetRevision(
                dataset_id=dataset.dataset_id,
                revision_number=dataset.current_revision,
                schema_json=dataset.schema_json,
                rows_json=dataset.rows_json,
                meta_json=dataset.meta_json,
                created_by=user_id,
                reason=f"Update at {datetime.now(UTC).isoformat()}",
            )

            self.db.add(revision)

        await self.db.commit()
        await self.db.refresh(dataset)

        return dataset

    async def delete_dataset(
        self,
        dataset_id: UUID,
        company_id: UUID,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete dataset (soft or hard).

        Args:
            dataset_id: Dataset UUID
            company_id: Company UUID
            hard_delete: If True, permanently delete; if False, soft delete

        Returns:
            True if deleted, False if not found
        """
        dataset = await self.get_dataset(dataset_id, company_id)
        if not dataset:
            return False

        if hard_delete:
            await self.db.delete(dataset)
        else:
            dataset.is_deleted = True
            dataset.updated_at_utc = datetime.now(UTC)

        await self.db.commit()
        return True

    # === Revision Operations ===

    async def create_revision(
        self,
        dataset_id: UUID,
        company_id: UUID,
        user_id: UUID,
        data: DatasetRevisionCreate,
    ) -> DatasetRevision | None:
        """
        Create a new revision snapshot of the current dataset state.

        Args:
            dataset_id: Dataset UUID
            company_id: Company UUID
            user_id: User creating the revision
            data: Revision creation data

        Returns:
            Created DatasetRevision or None if dataset not found
        """
        dataset = await self.get_dataset(dataset_id, company_id)
        if not dataset:
            return None

        # Increment revision number
        dataset.current_revision += 1
        dataset.updated_at_utc = datetime.now(UTC)

        # Create revision snapshot
        revision = DatasetRevision(
            dataset_id=dataset.dataset_id,
            revision_number=dataset.current_revision,
            schema_json=dataset.schema_json,
            rows_json=dataset.rows_json,
            meta_json=dataset.meta_json,
            created_by=user_id,
            reason=data.reason,
        )

        self.db.add(revision)
        await self.db.commit()
        await self.db.refresh(revision)

        return revision

    async def get_revision(
        self,
        revision_id: UUID,
        company_id: UUID,
    ) -> DatasetRevision | None:
        """
        Get a specific revision by ID.

        Args:
            revision_id: Revision UUID
            company_id: Company UUID (for tenant isolation)

        Returns:
            DatasetRevision or None if not found
        """
        stmt = (
            select(DatasetRevision)
            .join(Dataset, DatasetRevision.dataset_id == Dataset.dataset_id)
            .where(
                and_(
                    DatasetRevision.revision_id == revision_id,
                    Dataset.company_id == company_id,
                )
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_revisions(
        self,
        dataset_id: UUID,
        company_id: UUID,
    ) -> list[DatasetRevision]:
        """
        List all revisions for a dataset.

        Args:
            dataset_id: Dataset UUID
            company_id: Company UUID

        Returns:
            List of DatasetRevision ordered by revision number (newest first)
        """
        # Verify dataset exists and belongs to company
        dataset = await self.get_dataset(dataset_id, company_id)
        if not dataset:
            return []

        stmt = (
            select(DatasetRevision)
            .where(DatasetRevision.dataset_id == dataset_id)
            .order_by(desc(DatasetRevision.revision_number))
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # === Helper Methods ===

    def to_response(self, dataset: Dataset) -> DatasetResponse:
        """Convert Dataset model to response schema."""
        return DatasetResponse.model_validate(dataset)

    def to_list_item(self, dataset: Dataset) -> DatasetListItem:
        """Convert Dataset model to list item schema."""
        row_count = len(dataset.rows_json) if dataset.rows_json else 0
        columns = dataset.schema_json.get("columns", [])
        column_count = len(columns) if columns else 0

        return DatasetListItem(
            dataset_id=dataset.dataset_id,
            company_id=dataset.company_id,
            name=dataset.name,
            description=dataset.description,
            current_revision=dataset.current_revision,
            row_count=row_count,
            column_count=column_count,
            created_at_utc=dataset.created_at_utc,
            updated_at_utc=dataset.updated_at_utc,
        )

    def to_revision_response(self, revision: DatasetRevision) -> DatasetRevisionResponse:
        """Convert DatasetRevision model to response schema."""
        return DatasetRevisionResponse.model_validate(revision)

