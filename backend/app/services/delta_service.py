from app.core.dependencies import RequestContext
from app.core.exceptions import AppError
from app.repositories.delta_repo import DeltaRepository


class DeltaService:
    def __init__(self, repo: DeltaRepository):
        self.repo = repo

    def _require_admin(self, ctx: RequestContext) -> None:
        if ctx.role not in ("admin", "platform_admin"):
            raise AppError("FORBIDDEN", 403, "Only admin can manage deltas")

    async def create(self, payload: dict, ctx: RequestContext):
        self._require_admin(ctx)
        return await self.repo.create(**payload)

    async def list(self, *, standard_id: int | None = None):
        return await self.repo.list(standard_id=standard_id)
