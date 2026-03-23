from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.schemas.data_points import DataPointCreate, DataPointListOut, DataPointOut


class DataPointService:
    def __init__(self, repo: DataPointRepository, audit_repo: AuditRepository | None = None):
        self.repo = repo
        self.audit_repo = audit_repo

    async def create(
        self, project_id: int, payload: DataPointCreate, ctx: RequestContext
    ) -> DataPointOut:
        dp = await self.repo.create(
            project_id=project_id,
            shared_element_id=payload.shared_element_id,
            entity_id=payload.entity_id,
            facility_id=getattr(payload, "facility_id", None),
            numeric_value=payload.numeric_value,
            text_value=payload.text_value,
            unit_code=payload.unit_code,
            created_by=ctx.user_id,
            status="draft",
        )

        for dim in payload.dimensions:
            await self.repo.add_dimension(dp.id, dim.dimension_type, dim.dimension_value)

        # Audit: data point created
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type="DataPoint",
                entity_id=dp.id,
                action="data_point_created",
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes={"project_id": project_id, "shared_element_id": payload.shared_element_id},
            )

        return DataPointOut.model_validate(dp)

    async def list_by_project(
        self, project_id: int, page: int = 1, page_size: int = 50
    ) -> DataPointListOut:
        items, total = await self.repo.list_by_project(project_id, page, page_size)
        return DataPointListOut(
            items=[DataPointOut.model_validate(dp) for dp in items],
            total=total,
        )

    async def get(self, dp_id: int) -> DataPointOut:
        dp = await self.repo.get_or_raise(dp_id)
        return DataPointOut.model_validate(dp)
