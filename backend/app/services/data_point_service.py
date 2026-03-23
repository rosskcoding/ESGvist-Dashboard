from app.core.access import (
    assignment_matches_data_point,
    get_data_point_for_ctx,
    get_project_for_ctx,
    get_user_assignments,
)
from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.policies.auth_policy import AuthPolicy
from app.repositories.audit_repo import AuditRepository
from app.repositories.data_point_repo import DataPointRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.data_points import DataPointCreate, DataPointListOut, DataPointOut


class DataPointService:
    def __init__(
        self,
        repo: DataPointRepository,
        project_repo: ProjectRepository,
        audit_repo: AuditRepository | None = None,
    ):
        self.repo = repo
        self.project_repo = project_repo
        self.audit_repo = audit_repo

    async def create(
        self, project_id: int, payload: DataPointCreate, ctx: RequestContext
    ) -> DataPointOut:
        AuthPolicy.require_collector_or_manager(ctx)
        await get_project_for_ctx(self.repo.session, project_id, ctx)
        if ctx.role == "collector":
            assignments = await get_user_assignments(
                self.repo.session, project_id, ctx.user_id, "collector"
            )
            if not any(
                assignment.shared_element_id == payload.shared_element_id
                and (assignment.entity_id is None or assignment.entity_id == payload.entity_id)
                and (assignment.facility_id is None or assignment.facility_id == payload.facility_id)
                for assignment in assignments
            ):
                raise AppError("FORBIDDEN", 403, "Collectors can only create assigned data points")

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
                performed_by_platform_admin=ctx.is_platform_admin,
        )

        return DataPointOut.model_validate(dp)

    async def list_by_project(
        self, project_id: int, ctx: RequestContext, page: int = 1, page_size: int = 50
    ) -> DataPointListOut:
        await get_project_for_ctx(self.repo.session, project_id, ctx)

        if ctx.role in ("collector", "reviewer"):
            assignments = await get_user_assignments(
                self.repo.session, project_id, ctx.user_id, ctx.role
            )
            shared_element_ids = list({assignment.shared_element_id for assignment in assignments})
            data_points = await self.repo.list_all_by_project(project_id, shared_element_ids)
            items = [
                data_point
                for data_point in data_points
                if (
                    ctx.role == "collector" and data_point.created_by == ctx.user_id
                ) or any(
                    assignment_matches_data_point(assignment, data_point)
                    for assignment in assignments
                )
            ]
            total = len(items)
            start = (page - 1) * page_size
            items = items[start:start + page_size]
        else:
            items, total = await self.repo.list_by_project(project_id, page, page_size)

        return DataPointListOut(
            items=[DataPointOut.model_validate(dp) for dp in items],
            total=total,
        )

    async def get(self, dp_id: int, ctx: RequestContext) -> DataPointOut:
        dp, _, _ = await get_data_point_for_ctx(self.repo.session, dp_id, ctx)
        return DataPointOut.model_validate(dp)
