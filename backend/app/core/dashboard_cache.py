from __future__ import annotations

from collections.abc import Iterable

from app.core.config import settings
from app.core.dependencies import RequestContext
from app.core.runtime_cache import TTLCache

_dashboard_progress_cache: TTLCache[dict] = TTLCache(
    ttl_seconds=settings.dashboard_progress_cache_ttl_seconds
)


def _viewer_scope(ctx: RequestContext) -> str:
    # Manager/admin/auditor/platform_admin views are shared per role.
    # Collector/reviewer access may be assignment-scoped, so keep those user-specific.
    if ctx.role in {"collector", "reviewer"}:
        return str(ctx.user_id)
    return ctx.role or "unknown"


def _project_prefix(project_id: int) -> str:
    return f"project:{project_id}:"


def build_dashboard_progress_cache_key(project_id: int, ctx: RequestContext) -> str:
    return (
        f"{_project_prefix(project_id)}"
        f"org:{ctx.organization_id or 0}:"
        f"role:{ctx.role or 'unknown'}:"
        f"viewer:{_viewer_scope(ctx)}:"
        f"support:{int(ctx.support_mode)}"
    )


async def get_or_compute_dashboard_progress(
    project_id: int,
    ctx: RequestContext,
    factory,
) -> dict:
    return await _dashboard_progress_cache.get_or_set(
        build_dashboard_progress_cache_key(project_id, ctx),
        factory,
    )


async def invalidate_dashboard_project(project_id: int) -> None:
    prefix = _project_prefix(project_id)
    await _dashboard_progress_cache.invalidate_where(lambda key: key.startswith(prefix))


async def invalidate_dashboard_projects(project_ids: Iterable[int]) -> None:
    unique_ids = {project_id for project_id in project_ids}
    if not unique_ids:
        return
    await _dashboard_progress_cache.invalidate_where(
        lambda key: any(key.startswith(_project_prefix(project_id)) for project_id in unique_ids)
    )
