from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.audit_repo import AuditRepository
from app.repositories.project_repo import ProjectRepository
from app.schemas.projects import (
    AssignmentCreate,
    AssignmentOut,
    BoundaryDefCreate,
    BoundaryDefOut,
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectStandardAdd,
)


class ProjectService:
    def __init__(self, repo: ProjectRepository, audit_repo: AuditRepository | None = None):
        self.repo = repo
        self.audit_repo = audit_repo

    async def _audit(self, entity_type: str, action: str, ctx: RequestContext,
                     entity_id: int | None = None, changes: dict | None = None):
        if self.audit_repo:
            await self.audit_repo.log(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user_id=ctx.user_id,
                organization_id=ctx.organization_id,
                changes=changes,
            )

    def _require_manager(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "esg_manager", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin/esg_manager can manage projects")

    # --- Projects ---
    async def create_project(self, payload: ProjectCreate, ctx: RequestContext) -> ProjectOut:
        self._require_manager(ctx)
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        p = await self.repo.create_project(ctx.organization_id, **payload.model_dump())
        return ProjectOut.model_validate(p)

    async def list_projects(self, ctx: RequestContext, page: int = 1, page_size: int = 20) -> ProjectListOut:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items, total = await self.repo.list_projects(ctx.organization_id, page, page_size)
        return ProjectListOut(
            items=[ProjectOut.model_validate(p) for p in items],
            total=total,
        )

    async def get_project(self, project_id: int) -> ProjectOut:
        p = await self.repo.get_or_raise(project_id)
        return ProjectOut.model_validate(p)

    async def add_standard(self, project_id: int, payload: ProjectStandardAdd, ctx: RequestContext):
        self._require_manager(ctx)
        await self.repo.get_or_raise(project_id)
        ps = await self.repo.add_standard(project_id, payload.standard_id, payload.is_base_standard)
        return {"project_id": project_id, "standard_id": payload.standard_id}

    # --- Assignments ---
    async def create_assignment(
        self, project_id: int, payload: AssignmentCreate, ctx: RequestContext
    ) -> AssignmentOut:
        self._require_manager(ctx)

        if payload.collector_id and payload.reviewer_id and payload.collector_id == payload.reviewer_id:
            raise AppError(
                "ASSIGNMENT_ROLE_CONFLICT", 409,
                "Collector and reviewer cannot be the same person"
            )

        a = await self.repo.create_assignment(project_id, **payload.model_dump())
        await self._audit("MetricAssignment", "assignment_created", ctx, entity_id=a.id,
                          changes=payload.model_dump())
        return AssignmentOut.model_validate(a)

    async def list_assignments(self, project_id: int) -> list[AssignmentOut]:
        items = await self.repo.list_assignments(project_id)
        return [AssignmentOut.model_validate(a) for a in items]

    # --- Boundaries ---
    async def create_boundary(self, payload: BoundaryDefCreate, ctx: RequestContext) -> BoundaryDefOut:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can create boundaries")
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        b = await self.repo.create_boundary(ctx.organization_id, **payload.model_dump())
        await self._audit("BoundaryDefinition", "create_boundary", ctx, entity_id=b.id,
                          changes=payload.model_dump())
        return BoundaryDefOut.model_validate(b)

    async def list_boundaries(self, ctx: RequestContext) -> list[BoundaryDefOut]:
        if not ctx.organization_id:
            raise AppError("ORG_HEADER_REQUIRED", 400, "Organization context required")
        items = await self.repo.list_boundaries(ctx.organization_id)
        return [BoundaryDefOut.model_validate(b) for b in items]

    async def apply_boundary(self, project_id: int, boundary_id: int, ctx: RequestContext) -> ProjectOut:
        self._require_manager(ctx)
        p = await self.repo.get_or_raise(project_id)
        if p.status == "published":
            raise AppError("PROJECT_LOCKED", 422, "Cannot change boundary for published project")
        p = await self.repo.update_project(project_id, boundary_definition_id=boundary_id)
        await self._audit("ReportingProject", "apply_boundary_to_project", ctx, entity_id=project_id,
                          changes={"boundary_id": boundary_id})
        return ProjectOut.model_validate(p)
