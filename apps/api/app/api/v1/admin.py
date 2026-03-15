"""
Admin API endpoints — Platform operations for superusers.

Safe by default:
- All endpoints require is_superuser = true
- Read-only by default, except safe recovery actions (retry, cancel, cleanup)
- No access to customer content (reports, blocks)
- Cross-tenant observability without impersonation

Phase 1 endpoints:
- GET /admin/overview — platform stats
- GET /admin/attention-inbox — incidents requiring action
- GET /admin/builds — all builds with filters
- GET /admin/artifacts — all artifacts with filters
- GET /admin/translations — all translation jobs with filters
- GET /admin/audit-events — cross-tenant audit log
- POST /admin/incidents/help — AI advisory for incidents
- POST /admin/builds/{id}/retry — retry failed build
- POST /admin/builds/{id}/cancel — cancel queued/running build
- POST /admin/builds/cleanup — cleanup old DRAFT builds (retention policy)
- POST /admin/builds/cleanup-orphaned — cleanup orphaned files (no DB record)
"""

import csv
import io
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user_required
from app.domain.models import (
    AIUsageEvent,
    ArtifactStatus,
    AuditEvent,
    BuildStatus,
    Company,
    CompanyStatus,
    JobStatus,
    OpenAIKeyStatus,
    PlatformAISettings,
    ReleaseBuild,
    ReleaseBuildArtifact,
    Report,
    TranslationJob,
    User,
)
from app.infra.database import get_session
from app.infra.redis import get_redis
from app.services.secret_encryption import decrypt_secret, encrypt_secret

# Type alias for current user
CurrentUser = Annotated[User, Depends(get_current_user_required)]


# =============================================================================
# Superuser Guard
# =============================================================================


async def require_superuser(user: CurrentUser) -> User:
    """
    Dependency that ensures current user is a superuser.

    Raises:
        HTTPException 403: If user is not a superuser

    Returns:
        User: The superuser
    """
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to platform administrators (superusers)",
        )
    return user


# Type alias for superuser dependency
Superuser = Annotated[User, Depends(require_superuser)]


# =============================================================================
# Router
# =============================================================================

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_superuser)],  # All routes require superuser
)


# =============================================================================
# Schemas
# =============================================================================


class PlatformOverviewResponse(BaseModel):
    """Platform overview stats for superuser dashboard."""

    companies: dict[str, int]
    users: dict[str, int]
    reports: dict[str, int]
    builds_last_24h: dict[str, int]
    health: dict[str, str]


class AttentionInboxItem(BaseModel):
    """Single incident item in attention inbox."""

    type: str  # "build_failed", "artifact_failed", "translation_failed", "job_stuck", "company_disabled"
    entity_id: str  # ID of the entity (build_id, artifact_id, job_id, company_id)
    company_id: str | None  # Company scope
    company_slug: str | None  # For quick navigation
    status: str  # Current status
    error_code: str | None  # Error code if available
    error_message: str | None  # Human-readable error
    occurred_at: str  # ISO timestamp


class AttentionInboxResponse(BaseModel):
    """List of incidents requiring attention."""

    items: list[AttentionInboxItem]


class BuildListItem(BaseModel):
    """Build item for admin list."""

    build_id: str
    report_id: str
    company_id: str
    company_slug: str
    build_type: str
    status: str
    error_message: str | None
    created_at: str
    finished_at: str | None


class BuildListResponse(BaseModel):
    """Paginated list of builds."""

    items: list[BuildListItem]
    total: int
    page: int
    page_size: int


class ArtifactListItem(BaseModel):
    """Artifact item for admin list."""

    artifact_id: str
    build_id: str
    company_id: str
    company_slug: str
    format: str
    locale: str | None
    profile: str | None
    status: str
    error_code: str | None
    error_message: str | None
    created_at: str


class ArtifactListResponse(BaseModel):
    """Paginated list of artifacts."""

    items: list[ArtifactListItem]
    total: int
    page: int
    page_size: int


class TranslationJobListItem(BaseModel):
    """Translation job item for admin list."""

    job_id: str
    report_id: str
    company_id: str
    company_slug: str
    source_locale: str
    target_locales: list[str]
    status: str
    error_log: dict | None
    created_at: str
    finished_at: str | None


class TranslationJobListResponse(BaseModel):
    """Paginated list of translation jobs."""

    items: list[TranslationJobListItem]
    total: int
    page: int
    page_size: int


class AuditEventListItem(BaseModel):
    """Audit event item for admin list."""

    event_id: str
    timestamp_utc: str
    actor_type: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    company_id: str | None
    company_slug: str | None
    metadata_json: dict | None
    ip_address: str | None


class AuditEventListResponse(BaseModel):
    """Paginated list of audit events."""

    items: list[AuditEventListItem]
    total: int
    page: int
    page_size: int


class IncidentHelpRequest(BaseModel):
    """Request for AI incident help."""

    incident_type: str  # "build_failed", "artifact_failed", etc.
    error_code: str | None = None
    job_type: str | None = None  # "release_build", "translation", etc.
    status: str | None = None
    metadata: dict | None = None


class IncidentHelpResponse(BaseModel):
    """Structured AI response for incident help."""

    meaning: str
    possible_causes: list[str]
    recommended_checks: list[str]
    safe_actions: list[str]


class CompanyOpenAIKeyRequest(BaseModel):
    """Request to set company OpenAI key."""

    api_key: str  # Will be encrypted


class CompanyOpenAIKeyResponse(BaseModel):
    """Response for OpenAI key operations."""

    success: bool
    message: str
    status: str  # "active", "invalid", "disabled"
    last_validated_at: str | None = None


class PlatformOpenAISettingsResponse(BaseModel):
    """Platform-wide OpenAI settings (key is never returned)."""

    has_key: bool
    key_status: str  # active|invalid|disabled
    key_last_validated_at: str | None = None
    key_last4: str | None = None
    model: str


class PlatformOpenAIKeyRequest(BaseModel):
    """Set/replace platform OpenAI key (stored encrypted)."""

    api_key: str


class PlatformOpenAIModelRequest(BaseModel):
    """Set platform OpenAI model."""

    model: str


class TranslationPromptsResponse(BaseModel):
    """Translation prompt templates (current values)."""

    reporting_prompt: str
    marketing_prompt: str
    reporting_is_custom: bool
    marketing_is_custom: bool


class TranslationPromptsUpdateRequest(BaseModel):
    """Update translation prompt templates."""

    reporting_prompt: str | None = None  # NULL = reset to default
    marketing_prompt: str | None = None  # NULL = reset to default


# Allowed models for Phase 1 (UI dropdown)
ALLOWED_OPENAI_MODELS: set[str] = {
    "gpt-4.1",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4o-mini",
}


# Default prompts (hardcoded in translation service)
DEFAULT_PROMPT_REPORTING = """You are a professional translator specializing in ESG (Environmental, Social, Governance) corporate reports.

Translate the following text from {source_lang} to {target_lang}.

Important guidelines:
1. Maintain formal, professional tone suitable for annual reports
2. Preserve all formatting, HTML tags, and structure
3. Keep placeholders exactly as they are (e.g., __PH_0__, __PH_1__)
4. Use precise financial and ESG terminology
5. Numbers and units should follow {target_lang} conventions
{glossary_section}

Text to translate:
{text}

Provide ONLY the translation, no explanations."""

DEFAULT_PROMPT_MARKETING = """You are a professional translator for corporate communications.

Translate the following text from {source_lang} to {target_lang}.

Important guidelines:
1. Maintain engaging, professional tone
2. Preserve all formatting, HTML tags, and structure
3. Keep placeholders exactly as they are (e.g., __PH_0__, __PH_1__)
4. Adapt idioms and expressions naturally for {target_lang} audience
{glossary_section}

Text to translate:
{text}

Provide ONLY the translation, no explanations."""


# =============================================================================
# Platform Overview
# =============================================================================


@router.get("/overview", response_model=PlatformOverviewResponse)
async def get_platform_overview(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlatformOverviewResponse:
    """
    Get platform overview stats.

    Returns:
        - Company counts (total, active, disabled)
        - User counts (total, superusers)
        - Report counts (draft, locked, released)
        - Build counts (last 24h, success/failed)
        - Health status (database, redis)
    """
    # Companies
    companies_total = await session.scalar(select(func.count(Company.company_id)))
    # Note: Company.status is VARCHAR in DB, not ENUM (despite model definition)
    # Use text() to bypass SQLAlchemy's automatic ENUM casting
    from sqlalchemy import text
    companies_active = await session.scalar(
        text("SELECT count(*) FROM companies WHERE status = 'active'")
    )
    companies_disabled = await session.scalar(
        text("SELECT count(*) FROM companies WHERE status = 'disabled'")
    )

    # Users
    users_total = await session.scalar(select(func.count(User.user_id)))
    users_superusers = await session.scalar(
        select(func.count(User.user_id)).where(User.is_superuser == True)  # noqa: E712
    )

    # Reports (count by status - we don't have report-level status, so count all)
    # NOTE: For now, we'll just count total reports. In future, we can add report-level status.
    reports_total = await session.scalar(select(func.count(Report.report_id)))

    # Builds (last 24h)
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(hours=24)

    builds_success_24h = await session.scalar(
        select(func.count(ReleaseBuild.build_id)).where(
            ReleaseBuild.created_at_utc >= cutoff,
            ReleaseBuild.status == BuildStatus.SUCCESS,
        )
    )
    builds_failed_24h = await session.scalar(
        select(func.count(ReleaseBuild.build_id)).where(
            ReleaseBuild.created_at_utc >= cutoff,
            ReleaseBuild.status == BuildStatus.FAILED,
        )
    )

    # Health checks
    db_health = "ok"  # If we got here, DB is ok

    redis_health = "ok"
    try:
        redis = get_redis()
        await redis.ping()
    except Exception:
        redis_health = "error"

    return PlatformOverviewResponse(
        companies={
            "total": companies_total or 0,
            "active": companies_active or 0,
            "disabled": companies_disabled or 0,
        },
        users={
            "total": users_total or 0,
            "superusers": users_superusers or 0,
        },
        reports={
            "total": reports_total or 0,
        },
        builds_last_24h={
            "success": builds_success_24h or 0,
            "failed": builds_failed_24h or 0,
        },
        health={
            "database": db_health,
            "redis": redis_health,
        },
    )


# =============================================================================
# Attention Inbox (incidents requiring action)
# =============================================================================


@router.get("/attention-inbox", response_model=AttentionInboxResponse)
async def get_attention_inbox(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AttentionInboxResponse:
    """
    Get list of incidents requiring attention.

    Returns:
        - Failed builds
        - Failed artifacts
        - Failed translation jobs
        - Stuck jobs (queued/running > 1 hour)
        - Disabled companies

    Sorted by occurred_at DESC (most recent first).
    """
    from datetime import UTC, datetime, timedelta

    items: list[AttentionInboxItem] = []

    # 1. Failed builds
    failed_builds = await session.execute(
        select(ReleaseBuild, Company.slug, Report.company_id)
        .join(Report, ReleaseBuild.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
        .where(ReleaseBuild.status == BuildStatus.FAILED)
        .order_by(ReleaseBuild.created_at_utc.desc())
        .limit(50)
    )

    for build, company_slug, report_company_id in failed_builds:
        items.append(
            AttentionInboxItem(
                type="build_failed",
                entity_id=str(build.build_id),
                company_id=str(report_company_id) if report_company_id else None,
                company_slug=company_slug,
                status=build.status.value,
                error_code=None,
                error_message=build.error_message,
                occurred_at=build.created_at_utc.isoformat() if build.created_at_utc else "",
            )
        )

    # 2. Failed artifacts
    failed_artifacts = await session.execute(
        select(ReleaseBuildArtifact, Company.slug, Report.company_id)
        .join(ReleaseBuild, ReleaseBuildArtifact.build_id == ReleaseBuild.build_id)
        .join(Report, ReleaseBuild.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
        .where(ReleaseBuildArtifact.status == ArtifactStatus.FAILED)
        .order_by(ReleaseBuildArtifact.created_at_utc.desc())
        .limit(50)
    )

    for artifact, company_slug, report_company_id in failed_artifacts:
        items.append(
            AttentionInboxItem(
                type="artifact_failed",
                entity_id=str(artifact.artifact_id),
                company_id=str(report_company_id) if report_company_id else None,
                company_slug=company_slug,
                status=artifact.status.value,
                error_code=artifact.error_code.value if artifact.error_code else None,
                error_message=artifact.error_message,
                occurred_at=artifact.created_at_utc.isoformat() if artifact.created_at_utc else "",
            )
        )

    # 3. Failed translation jobs
    failed_translations = await session.execute(
        select(TranslationJob, Company.slug, Report.company_id)
        .join(Report, TranslationJob.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
        .where(TranslationJob.status == JobStatus.FAILED)
        .order_by(TranslationJob.created_at_utc.desc())
        .limit(50)
    )

    for job, company_slug, report_company_id in failed_translations:
        error_msg = None
        if job.error_log:
            error_msg = str(job.error_log.get("message", "Translation failed"))

        items.append(
            AttentionInboxItem(
                type="translation_failed",
                entity_id=str(job.job_id),
                company_id=str(report_company_id) if report_company_id else None,
                company_slug=company_slug,
                status=job.status.value,
                error_code=None,
                error_message=error_msg,
                occurred_at=job.created_at_utc.isoformat() if job.created_at_utc else "",
            )
        )

    # 4. Stuck jobs (queued/running > 1 hour)
    stuck_threshold = datetime.now(UTC) - timedelta(hours=1)

    stuck_builds = await session.execute(
        select(ReleaseBuild, Company.slug, Report.company_id)
        .join(Report, ReleaseBuild.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
        .where(
            ReleaseBuild.status.in_([BuildStatus.QUEUED, BuildStatus.RUNNING]),
            ReleaseBuild.created_at_utc < stuck_threshold,
        )
        .order_by(ReleaseBuild.created_at_utc.desc())
        .limit(20)
    )

    for build, company_slug, report_company_id in stuck_builds:
        items.append(
            AttentionInboxItem(
                type="job_stuck",
                entity_id=str(build.build_id),
                company_id=str(report_company_id) if report_company_id else None,
                company_slug=company_slug,
                status=build.status.value,
                error_code=None,
                error_message=f"Build stuck in {build.status.value} for > 1 hour",
                occurred_at=build.created_at_utc.isoformat() if build.created_at_utc else "",
            )
        )

    # 5. Disabled companies
    # NOTE: Company.status column is VARCHAR in DB (not ENUM), so use raw SQL to avoid type casting issues
    from sqlalchemy import text as sql_text
    disabled_companies_result = await session.execute(
        sql_text("""
            SELECT company_id, slug, status, updated_at_utc
            FROM companies
            WHERE status = 'disabled'
            ORDER BY updated_at_utc DESC
            LIMIT 20
        """)
    )

    for row in disabled_companies_result:
        items.append(
            AttentionInboxItem(
                type="company_disabled",
                entity_id=str(row.company_id),
                company_id=str(row.company_id),
                company_slug=row.slug,
                status=row.status,
                error_code=None,
                error_message=None,
                occurred_at=row.updated_at_utc.isoformat() if row.updated_at_utc else "",
            )
        )

    # Sort all items by occurred_at DESC
    items.sort(key=lambda x: x.occurred_at, reverse=True)

    return AttentionInboxResponse(items=items)


class ClearAttentionInboxRequest(BaseModel):
    """Request to clear attention inbox items."""

    types: list[str] | None = None  # Filter by types, None = all


class ClearAttentionInboxResponse(BaseModel):
    """Result of clearing attention inbox."""

    cleared_builds: int
    cleared_artifacts: int
    cleared_translations: int
    total_cleared: int


@router.delete("/attention-inbox/clear", response_model=ClearAttentionInboxResponse)
async def clear_attention_inbox(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
    types: str | None = Query(default=None, description="Comma-separated types to clear: build_failed,artifact_failed,translation_failed. Empty = all"),
) -> ClearAttentionInboxResponse:
    """
    Clear (delete) failed items from attention inbox.

    Safe action:
    - Deletes FAILED builds, artifacts, and translation jobs
    - Does NOT affect running or queued jobs
    - Does NOT affect disabled companies (use company management for that)
    - Logs action in audit log

    Query params:
        - types: Comma-separated list of types to clear (build_failed, artifact_failed, translation_failed)
                 If not provided, clears all types

    Returns:
        Count of cleared items by type
    """
    from sqlalchemy import delete

    # Parse types filter
    allowed_types = {"build_failed", "artifact_failed", "translation_failed"}
    if types:
        filter_types = set(t.strip() for t in types.split(","))
        filter_types = filter_types & allowed_types  # Only allow valid types
    else:
        filter_types = allowed_types

    cleared_builds = 0
    cleared_artifacts = 0
    cleared_translations = 0

    # 1. Clear failed translation jobs
    if "translation_failed" in filter_types:
        result = await session.execute(
            delete(TranslationJob).where(TranslationJob.status == JobStatus.FAILED)
        )
        cleared_translations = result.rowcount or 0

    # 2. Clear failed artifacts
    if "artifact_failed" in filter_types:
        result = await session.execute(
            delete(ReleaseBuildArtifact).where(ReleaseBuildArtifact.status == ArtifactStatus.FAILED)
        )
        cleared_artifacts = result.rowcount or 0

    # 3. Clear failed builds
    if "build_failed" in filter_types:
        result = await session.execute(
            delete(ReleaseBuild).where(ReleaseBuild.status == BuildStatus.FAILED)
        )
        cleared_builds = result.rowcount or 0

    total_cleared = cleared_builds + cleared_artifacts + cleared_translations

    # Log action in audit
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="attention_inbox_clear",
        entity_type="platform",
        entity_id="attention_inbox",
        metadata={
            "types_cleared": list(filter_types),
            "cleared_builds": cleared_builds,
            "cleared_artifacts": cleared_artifacts,
            "cleared_translations": cleared_translations,
            "total_cleared": total_cleared,
        },
        company_id=None,
    )
    session.add(audit_event)

    await session.commit()

    return ClearAttentionInboxResponse(
        cleared_builds=cleared_builds,
        cleared_artifacts=cleared_artifacts,
        cleared_translations=cleared_translations,
        total_cleared=total_cleared,
    )


# =============================================================================
# Builds Management
# =============================================================================


@router.get("/builds", response_model=BuildListResponse)
async def list_builds(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    company_id: UUID | None = Query(default=None),
    status: BuildStatus | None = Query(default=None),
) -> BuildListResponse:
    """
    List all builds (cross-tenant) with filters.

    Query params:
        - page: Page number (1-indexed)
        - page_size: Items per page (max 100)
        - company_id: Filter by company
        - status: Filter by build status

    Returns:
        Paginated list of builds with company context.
    """
    # Build query
    query = (
        select(ReleaseBuild, Company.slug, Report.company_id)
        .join(Report, ReleaseBuild.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
    )

    # Apply filters
    if company_id:
        query = query.where(Report.company_id == company_id)
    if status:
        query = query.where(ReleaseBuild.status == status)

    # Order by created_at DESC
    query = query.order_by(ReleaseBuild.created_at_utc.desc())

    # Count total (before pagination)
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await session.execute(query)
    rows = result.all()

    items = [
        BuildListItem(
            build_id=str(build.build_id),
            report_id=str(build.report_id),
            company_id=str(company_id_val),
            company_slug=company_slug,
            build_type=build.build_type.value,
            status=build.status.value,
            error_message=build.error_message,
            created_at=build.created_at_utc.isoformat() if build.created_at_utc else "",
            finished_at=build.finished_at_utc.isoformat() if build.finished_at_utc else None,
        )
        for build, company_slug, company_id_val in rows
    ]

    return BuildListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/builds/{build_id}/retry")
async def retry_build(
    build_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> dict:
    """
    Retry a failed build.

    Safe action:
    - Changes status from FAILED -> QUEUED
    - Logs action in audit log
    - Does not modify build content or configuration

    Returns:
        Success message
    """
    # Load build
    build = await session.get(ReleaseBuild, build_id)
    if not build:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Build {build_id} not found",
        )

    # Check status
    if build.status != BuildStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Build must be in FAILED status to retry (current: {build.status.value})",
        )

    # Get company_id for audit
    report = await session.get(Report, build.report_id)
    company_id = report.company_id if report else None
    previous_error = build.error_message

    # Reset build status
    build.status = BuildStatus.QUEUED
    build.error_message = None
    build.finished_at_utc = None

    # Log action in audit
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="build_retry",
        entity_type="release_build",
        entity_id=str(build_id),
        metadata={
            "reason": "manual_retry_by_superuser",
            "previous_error": previous_error,
        },
        company_id=company_id,
    )
    session.add(audit_event)

    await session.commit()

    return {
        "success": True,
        "message": f"Build {build_id} has been queued for retry",
    }


@router.post("/builds/{build_id}/cancel")
async def cancel_build(
    build_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> dict:
    """
    Cancel a queued or running build.

    Safe action:
    - Changes status to FAILED with cancellation message
    - Logs action in audit log

    Returns:
        Success message
    """
    # Load build
    build = await session.get(ReleaseBuild, build_id)
    if not build:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Build {build_id} not found",
        )

    # Check status
    if build.status not in [BuildStatus.QUEUED, BuildStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Build must be QUEUED or RUNNING to cancel (current: {build.status.value})",
        )

    # Get company_id for audit
    report = await session.get(Report, build.report_id)
    company_id = report.company_id if report else None

    # Cancel build
    build.status = BuildStatus.FAILED
    build.error_message = "Cancelled by platform administrator"
    build.finished_at_utc = datetime.now(UTC)

    # Log action in audit
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="build_cancel",
        entity_type="release_build",
        entity_id=str(build_id),
        metadata={
            "reason": "manual_cancel_by_superuser",
        },
        company_id=company_id,
    )
    session.add(audit_event)

    await session.commit()

    return {
        "success": True,
        "message": f"Build {build_id} has been cancelled",
    }


# =============================================================================
# Artifacts Management
# =============================================================================


@router.get("/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    company_id: UUID | None = Query(default=None),
    status: ArtifactStatus | None = Query(default=None),
) -> ArtifactListResponse:
    """
    List all artifacts (cross-tenant) with filters.

    Query params:
        - page: Page number (1-indexed)
        - page_size: Items per page (max 100)
        - company_id: Filter by company
        - status: Filter by artifact status

    Returns:
        Paginated list of artifacts with company context.
    """
    # Build query
    query = (
        select(ReleaseBuildArtifact, Company.slug, Report.company_id)
        .join(ReleaseBuild, ReleaseBuildArtifact.build_id == ReleaseBuild.build_id)
        .join(Report, ReleaseBuild.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
    )

    # Apply filters
    if company_id:
        query = query.where(Report.company_id == company_id)
    if status:
        query = query.where(ReleaseBuildArtifact.status == status)

    # Order by created_at DESC
    query = query.order_by(ReleaseBuildArtifact.created_at_utc.desc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await session.execute(query)
    rows = result.all()

    items = [
        ArtifactListItem(
            artifact_id=str(artifact.artifact_id),
            build_id=str(artifact.build_id),
            company_id=str(company_id_val),
            company_slug=company_slug,
            format=artifact.format.value,
            locale=artifact.locale,
            profile=artifact.profile,
            status=artifact.status.value,
            error_code=artifact.error_code.value if artifact.error_code else None,
            error_message=artifact.error_message,
            created_at=artifact.created_at_utc.isoformat() if artifact.created_at_utc else "",
        )
        for artifact, company_slug, company_id_val in rows
    ]

    return ArtifactListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Translation Jobs Management
# =============================================================================


@router.get("/translations", response_model=TranslationJobListResponse)
async def list_translation_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    company_id: UUID | None = Query(default=None),
    status: JobStatus | None = Query(default=None),
) -> TranslationJobListResponse:
    """
    List all translation jobs (cross-tenant) with filters.

    Query params:
        - page: Page number (1-indexed)
        - page_size: Items per page (max 100)
        - company_id: Filter by company
        - status: Filter by job status

    Returns:
        Paginated list of translation jobs with company context.
    """
    # Build query
    query = (
        select(TranslationJob, Company.slug, Report.company_id)
        .join(Report, TranslationJob.report_id == Report.report_id)
        .join(Company, Report.company_id == Company.company_id)
    )

    # Apply filters
    if company_id:
        query = query.where(Report.company_id == company_id)
    if status:
        query = query.where(TranslationJob.status == status)

    # Order by created_at DESC
    query = query.order_by(TranslationJob.created_at_utc.desc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await session.execute(query)
    rows = result.all()

    items = [
        TranslationJobListItem(
            job_id=str(job.job_id),
            report_id=str(job.report_id),
            company_id=str(company_id_val),
            company_slug=company_slug,
            source_locale=job.source_locale.value,
            target_locales=job.target_locales,
            status=job.status.value,
            error_log=job.error_log,
            created_at=job.created_at_utc.isoformat() if job.created_at_utc else "",
            finished_at=job.finished_at_utc.isoformat() if job.finished_at_utc else None,
        )
        for job, company_slug, company_id_val in rows
    ]

    return TranslationJobListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# =============================================================================
# Audit Events (Cross-Tenant)
# =============================================================================


@router.get("/audit-events", response_model=AuditEventListResponse)
async def list_audit_events(
    session: Annotated[AsyncSession, Depends(get_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    company_id: UUID | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
) -> AuditEventListResponse:
    """
    List all audit events (cross-tenant) with filters.

    Query params:
        - page: Page number (1-indexed)
        - page_size: Items per page (max 100)
        - company_id: Filter by company (NULL = platform events)
        - actor_id: Filter by actor ID
        - action: Filter by action type
        - from_date: Filter events after this timestamp
        - to_date: Filter events before this timestamp

    Returns:
        Paginated list of audit events with company context.
    """
    # Build query - left join to get company_slug even for NULL company_id
    query = select(AuditEvent, Company.slug).outerjoin(
        Company, AuditEvent.company_id == Company.company_id
    )

    # Apply filters
    if company_id is not None:
        query = query.where(AuditEvent.company_id == company_id)
    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if from_date:
        query = query.where(AuditEvent.timestamp_utc >= from_date)
    if to_date:
        query = query.where(AuditEvent.timestamp_utc <= to_date)

    # Order by timestamp DESC
    query = query.order_by(AuditEvent.timestamp_utc.desc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await session.execute(query)
    rows = result.all()

    items = [
        AuditEventListItem(
            event_id=str(event.event_id),
            timestamp_utc=event.timestamp_utc.isoformat() if event.timestamp_utc else "",
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            company_id=str(event.company_id) if event.company_id else None,
            company_slug=company_slug,
            metadata_json=event.metadata_json,
            ip_address=event.ip_address,
        )
        for event, company_slug in rows
    ]

    return AuditEventListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit-events/export")
async def export_audit_events_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
    company_id: UUID | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
) -> Response:
    """
    Export audit events to CSV.

    Query params:
        - Same filters as list endpoint
        - limit: Max rows to export (max 10000)

    Returns:
        CSV file download
    """
    # Build query (same as list, but no pagination)
    query = select(AuditEvent, Company.slug).outerjoin(
        Company, AuditEvent.company_id == Company.company_id
    )

    # Apply filters
    if company_id is not None:
        query = query.where(AuditEvent.company_id == company_id)
    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
    if action:
        query = query.where(AuditEvent.action == action)
    if from_date:
        query = query.where(AuditEvent.timestamp_utc >= from_date)
    if to_date:
        query = query.where(AuditEvent.timestamp_utc <= to_date)

    # Order by timestamp DESC
    query = query.order_by(AuditEvent.timestamp_utc.desc()).limit(limit)

    # Execute
    result = await session.execute(query)
    rows = result.all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "event_id",
        "timestamp_utc",
        "actor_type",
        "actor_id",
        "action",
        "entity_type",
        "entity_id",
        "company_id",
        "company_slug",
        "ip_address",
        "metadata_json",
    ])

    # Rows
    for event, company_slug in rows:
        writer.writerow([
            str(event.event_id),
            event.timestamp_utc.isoformat() if event.timestamp_utc else "",
            event.actor_type,
            event.actor_id,
            event.action,
            event.entity_type,
            event.entity_id,
            str(event.company_id) if event.company_id else "",
            company_slug or "",
            event.ip_address or "",
            str(event.metadata_json) if event.metadata_json else "",
        ])

    # Return as CSV download
    csv_content = output.getvalue()

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=audit_events_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )


# =============================================================================
# AI Incident Help (Advisory)
# =============================================================================


@router.post("/incidents/help", response_model=IncidentHelpResponse)
async def get_incident_help(
    request: IncidentHelpRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> IncidentHelpResponse:
    """
    Get AI advisory help for an incident.

    Safe by default:
    - Does NOT send customer content (reports, blocks)
    - Only sends structured metadata (error codes, types, status)
    - Returns advisory information only
    - Does NOT execute any actions

    Returns:
        Structured advice: meaning, causes, checks, safe actions
    """
    from app.domain.models import AIUsageEvent, AIFeature
    from app.services.ai_pricing import estimate_openai_cost_usd
    from app.services.openai_helper import OpenAIKeyNotAvailableError, get_openai_key_for_company, get_platform_openai_model

    # Build structured prompt (no customer content!)
    prompt = f"""You are a platform operations assistant for an ESG report creator platform.

Incident Details:
- Type: {request.incident_type}
- Error Code: {request.error_code or "N/A"}
- Job Type: {request.job_type or "N/A"}
- Status: {request.status or "N/A"}

Based on this information, provide:
1. A brief explanation of what this incident means
2. 2-3 possible root causes
3. 2-3 things an admin should check
4. Which safe recovery actions are available (retry_build, cancel_build, validate_openai_key, disable_openai_key)

Response format:
{{
    "meaning": "Brief explanation",
    "possible_causes": ["cause1", "cause2"],
    "recommended_checks": ["check1", "check2"],
    "safe_actions": ["action1", "action2"]
}}

Be concise and actionable. Focus on operational recovery, not development fixes."""

    # Resolve platform key + model (DB overrides env/default).
    try:
        api_key = await get_openai_key_for_company(session=session, company_id=None)
        model = await get_platform_openai_model(session=session)
    except OpenAIKeyNotAvailableError:
        return _get_static_incident_help(request.incident_type, request.error_code)

    try:
        # Call OpenAI (simple implementation)
        import json
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful platform operations assistant. Respond with valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        # Extract response
        ai_text = response.choices[0].message.content or "{}"

        # Parse JSON
        try:
            ai_json = json.loads(ai_text)
        except json.JSONDecodeError:
            # Fallback if AI didn't return valid JSON
            ai_json = {
                "meaning": ai_text[:200],
                "possible_causes": ["Unknown"],
                "recommended_checks": ["Check logs"],
                "safe_actions": [],
            }

        # Log AI usage
        usage = response.usage
        if usage:
            total_cost = estimate_openai_cost_usd(
                model,
                int(usage.prompt_tokens or 0),
                int(usage.completion_tokens or 0),
            )

            usage_event = AIUsageEvent.create(
                feature=AIFeature.INCIDENT_HELP,
                model=model,
                input_tokens=int(usage.prompt_tokens or 0),
                output_tokens=int(usage.completion_tokens or 0),
                estimated_cost_usd=total_cost,
                company_id=None,  # Platform usage
                metadata={
                    "incident_type": request.incident_type,
                    "error_code": request.error_code,
                    "admin_user_id": str(admin.user_id),
                },
            )
            session.add(usage_event)
            await session.commit()

        return IncidentHelpResponse(
            meaning=ai_json.get("meaning", "Unknown incident"),
            possible_causes=ai_json.get("possible_causes", []),
            recommended_checks=ai_json.get("recommended_checks", []),
            safe_actions=ai_json.get("safe_actions", []),
        )

    except Exception as e:
        # Fallback on any error
        return _get_static_incident_help(request.incident_type, request.error_code)


def _get_static_incident_help(incident_type: str, error_code: str | None) -> IncidentHelpResponse:
    """
    Fallback static incident help when OpenAI is not available.
    """
    static_help = {
        "build_failed": IncidentHelpResponse(
            meaning="Build process failed during execution",
            possible_causes=[
                "Invalid content or structure",
                "Renderer timeout or crash",
                "Missing dependencies or resources",
            ],
            recommended_checks=[
                "Check build error message",
                "Verify source snapshot integrity",
                "Check artifact generation logs",
            ],
            safe_actions=["retry_build", "cancel_build"],
        ),
        "artifact_failed": IncidentHelpResponse(
            meaning="Individual artifact generation failed",
            possible_causes=[
                "PDF renderer timeout",
                "DOCX template error",
                "Invalid HTML structure",
            ],
            recommended_checks=[
                "Check artifact error code and message",
                "Verify build ZIP is accessible",
                "Check renderer logs",
            ],
            safe_actions=["retry_build"],
        ),
        "translation_failed": IncidentHelpResponse(
            meaning="Translation job failed",
            possible_causes=[
                "OpenAI API key invalid or quota exceeded",
                "Network connectivity issues",
                "Invalid source content",
            ],
            recommended_checks=[
                "Check translation job error log",
                "Validate company OpenAI API key",
                "Check OpenAI API status",
            ],
            safe_actions=["validate_openai_key", "disable_openai_key"],
        ),
        "job_stuck": IncidentHelpResponse(
            meaning="Job is stuck in queued/running state for too long",
            possible_causes=[
                "Worker process crashed or stalled",
                "Resource deadlock or queue backlog",
                "System overload",
            ],
            recommended_checks=[
                "Check worker process status",
                "Check Redis queue length",
                "Check system resources (CPU, memory)",
            ],
            safe_actions=["cancel_build"],
        ),
        "company_disabled": IncidentHelpResponse(
            meaning="Company account is disabled",
            possible_causes=[
                "Manual disable by admin",
                "Subscription expired",
                "Policy violation",
            ],
            recommended_checks=[
                "Check audit log for disable action",
                "Verify company status reason",
                "Contact company owner if needed",
            ],
            safe_actions=[],
        ),
    }

    return static_help.get(incident_type, IncidentHelpResponse(
        meaning="Unknown incident type",
        possible_causes=["Unrecognized incident"],
        recommended_checks=["Review incident details manually"],
        safe_actions=[],
    ))


# =============================================================================
# Company OpenAI Key Management
# =============================================================================


@router.post("/companies/{company_id}/openai-key", response_model=CompanyOpenAIKeyResponse)
async def set_company_openai_key(
    company_id: UUID,
    request: CompanyOpenAIKeyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> CompanyOpenAIKeyResponse:
    """
    Set OpenAI API key for a company.

    The key is encrypted before storage.
    Status is set to 'disabled' until validation succeeds.

    Returns:
        Success status and key information
    """
    # Load company
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found",
        )

    api_key = request.api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key must not be empty",
        )
    encrypted_key = encrypt_secret(api_key)

    # Update company
    company.openai_api_key_encrypted = encrypted_key
    company.openai_key_status = OpenAIKeyStatus.DISABLED
    company.openai_key_last_validated_at = None

    # Log action
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="openai_key_set",
        entity_type="company",
        entity_id=str(company_id),
        metadata={"reason": "manual_set_by_superuser"},
        company_id=company_id,
    )
    session.add(audit_event)

    await session.commit()

    return CompanyOpenAIKeyResponse(
        success=True,
        message="OpenAI API key has been set (disabled until validated)",
        status=company.openai_key_status.value,
        last_validated_at=company.openai_key_last_validated_at.isoformat() if company.openai_key_last_validated_at else None,
    )


@router.post("/companies/{company_id}/openai-key/validate", response_model=CompanyOpenAIKeyResponse)
async def validate_company_openai_key(
    company_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> CompanyOpenAIKeyResponse:
    """
    Validate company's OpenAI API key.

    Makes a test call to OpenAI API to verify the key is valid.
    Updates key status based on result.

    Returns:
        Validation result
    """
    # Load company
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found",
        )

    if not company.openai_api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company does not have an OpenAI API key set",
        )

    # Validate key by making a minimal test call
    try:
        from openai import AsyncOpenAI

        api_key = decrypt_secret(company.openai_api_key_encrypted)
        # If decryption failed (corrupt token), treat it as invalid.
        if api_key.startswith("enc:"):
            raise ValueError("Encrypted key cannot be decrypted (invalid token)")

        client = AsyncOpenAI(api_key=api_key)
        # Minimal test call (no tokens billed)
        await client.models.list()

        # If we got here, key is valid
        company.openai_key_status = OpenAIKeyStatus.ACTIVE
        company.openai_key_last_validated_at = datetime.now(UTC)

        message = "OpenAI API key is valid"

    except Exception as e:
        # Key is invalid
        company.openai_key_status = OpenAIKeyStatus.INVALID
        message = f"OpenAI API key validation failed: {str(e)}"

    # Log action
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="openai_key_validate",
        entity_type="company",
        entity_id=str(company_id),
        metadata={
            "result": company.openai_key_status.value,
            "message": message,
        },
        company_id=company_id,
    )
    session.add(audit_event)

    await session.commit()

    return CompanyOpenAIKeyResponse(
        success=company.openai_key_status == OpenAIKeyStatus.ACTIVE,
        message=message,
        status=company.openai_key_status.value,
        last_validated_at=company.openai_key_last_validated_at.isoformat() if company.openai_key_last_validated_at else None,
    )


@router.post("/companies/{company_id}/openai-key/disable", response_model=CompanyOpenAIKeyResponse)
async def disable_company_openai_key(
    company_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> CompanyOpenAIKeyResponse:
    """
    Disable company's OpenAI API key.

    Key remains stored but won't be used for AI features.

    Returns:
        Disable status
    """
    # Load company
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company {company_id} not found",
        )

    # Disable key
    company.openai_key_status = OpenAIKeyStatus.DISABLED

    # Log action
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="openai_key_disable",
        entity_type="company",
        entity_id=str(company_id),
        metadata={"reason": "manual_disable_by_superuser"},
        company_id=company_id,
    )
    session.add(audit_event)

    await session.commit()

    return CompanyOpenAIKeyResponse(
        success=True,
        message="OpenAI API key has been disabled",
        status=company.openai_key_status.value,
        last_validated_at=company.openai_key_last_validated_at.isoformat() if company.openai_key_last_validated_at else None,
    )


# =============================================================================
# Platform OpenAI Settings (single key + model) — Phase 1
# =============================================================================


async def _get_platform_ai_settings(session: AsyncSession) -> PlatformAISettings:
    """
    Get (or create) the singleton PlatformAISettings row.
    """
    settings_row = await session.get(PlatformAISettings, 1)
    if settings_row:
        return settings_row

    # Safety net for older DBs (migration should insert row).
    settings_row = PlatformAISettings(
        settings_id=1,
        openai_api_key_encrypted=None,
        openai_key_status=OpenAIKeyStatus.DISABLED,
        openai_key_last_validated_at=None,
        openai_model="gpt-4o-mini",
    )
    session.add(settings_row)
    await session.commit()
    await session.refresh(settings_row)
    return settings_row


def _platform_settings_dto(s: PlatformAISettings) -> PlatformOpenAISettingsResponse:
    key_last4: str | None = None
    has_key = bool(s.openai_api_key_encrypted)
    if has_key:
        decrypted = decrypt_secret(s.openai_api_key_encrypted or "")
        # If decrypt failed (returns enc:...), don't show hint.
        if decrypted and not decrypted.startswith("enc:") and len(decrypted) >= 4:
            key_last4 = decrypted[-4:]

    return PlatformOpenAISettingsResponse(
        has_key=has_key,
        key_status=s.openai_key_status.value,
        key_last_validated_at=s.openai_key_last_validated_at.isoformat() if s.openai_key_last_validated_at else None,
        key_last4=key_last4,
        model=s.openai_model,
    )


@router.get("/openai/settings", response_model=PlatformOpenAISettingsResponse)
async def get_platform_openai_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> PlatformOpenAISettingsResponse:
    """
    Get platform-wide OpenAI settings.

    Security: never returns the raw API key.
    """
    s = await _get_platform_ai_settings(session)
    return _platform_settings_dto(s)


@router.post("/openai/key", response_model=PlatformOpenAISettingsResponse)
async def set_platform_openai_key(
    request: PlatformOpenAIKeyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> PlatformOpenAISettingsResponse:
    """
    Set/replace platform OpenAI API key (encrypted).

    Status is set to 'disabled' until validation succeeds.
    """
    api_key = request.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API key must not be empty")

    s = await _get_platform_ai_settings(session)
    s.openai_api_key_encrypted = encrypt_secret(api_key)
    s.openai_key_status = OpenAIKeyStatus.DISABLED
    s.openai_key_last_validated_at = None

    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="platform_openai_key_set",
        entity_type="platform_ai_settings",
        entity_id="1",
        metadata={"reason": "manual_set_by_superuser"},
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()
    await session.refresh(s)
    return _platform_settings_dto(s)


@router.delete("/openai/key", response_model=PlatformOpenAISettingsResponse)
async def delete_platform_openai_key(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> PlatformOpenAISettingsResponse:
    """
    Delete platform OpenAI key (disables AI globally unless per-company keys exist).
    """
    s = await _get_platform_ai_settings(session)
    s.openai_api_key_encrypted = None
    s.openai_key_status = OpenAIKeyStatus.DISABLED
    s.openai_key_last_validated_at = None

    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="platform_openai_key_delete",
        entity_type="platform_ai_settings",
        entity_id="1",
        metadata={"reason": "manual_delete_by_superuser"},
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()
    await session.refresh(s)
    return _platform_settings_dto(s)


@router.post("/openai/key/validate", response_model=PlatformOpenAISettingsResponse)
async def validate_platform_openai_key(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> PlatformOpenAISettingsResponse:
    """
    Validate stored platform OpenAI key (minimal test call: models.list).
    """
    s = await _get_platform_ai_settings(session)
    if not s.openai_api_key_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Platform does not have an OpenAI API key set")

    message = "OpenAI API key is valid"
    try:
        from openai import AsyncOpenAI

        api_key = decrypt_secret(s.openai_api_key_encrypted)
        if api_key.startswith("enc:"):
            raise ValueError("Encrypted key cannot be decrypted (invalid token)")

        client = AsyncOpenAI(api_key=api_key)
        await client.models.list()

        s.openai_key_status = OpenAIKeyStatus.ACTIVE
        s.openai_key_last_validated_at = datetime.now(UTC)
    except Exception as e:
        s.openai_key_status = OpenAIKeyStatus.INVALID
        message = f"OpenAI API key validation failed: {str(e)}"

    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="platform_openai_key_validate",
        entity_type="platform_ai_settings",
        entity_id="1",
        metadata={"result": s.openai_key_status.value, "message": message},
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()
    await session.refresh(s)
    return _platform_settings_dto(s)


@router.post("/openai/model", response_model=PlatformOpenAISettingsResponse)
async def set_platform_openai_model(
    request: PlatformOpenAIModelRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> PlatformOpenAISettingsResponse:
    """
    Set platform default OpenAI model.
    """
    model = request.model.strip()
    if model not in ALLOWED_OPENAI_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model}'. Allowed: {sorted(ALLOWED_OPENAI_MODELS)}",
        )

    s = await _get_platform_ai_settings(session)
    s.openai_model = model

    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="platform_openai_model_set",
        entity_type="platform_ai_settings",
        entity_id="1",
        metadata={"model": model},
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()
    await session.refresh(s)
    return _platform_settings_dto(s)


# =============================================================================
# Translation Prompts Management
# =============================================================================


@router.get("/translation-prompts", response_model=TranslationPromptsResponse)
async def get_translation_prompts(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> TranslationPromptsResponse:
    """
    Get current translation prompt templates.

    Returns both default and custom prompts (if set).
    """
    s = await _get_platform_ai_settings(session)

    return TranslationPromptsResponse(
        reporting_prompt=s.translation_prompt_reporting or DEFAULT_PROMPT_REPORTING,
        marketing_prompt=s.translation_prompt_marketing or DEFAULT_PROMPT_MARKETING,
        reporting_is_custom=s.translation_prompt_reporting is not None,
        marketing_is_custom=s.translation_prompt_marketing is not None,
    )


@router.post("/translation-prompts", response_model=TranslationPromptsResponse)
async def update_translation_prompts(
    request: TranslationPromptsUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> TranslationPromptsResponse:
    """
    Update translation prompt templates.

    Pass NULL/empty string to reset to default.

    Required placeholders:
    - {source_lang} — source language name
    - {target_lang} — target language name
    - {text} — text to translate
    - {glossary_section} — glossary terms section
    """
    s = await _get_platform_ai_settings(session)

    changes = {}

    if request.reporting_prompt is not None:
        prompt = request.reporting_prompt.strip() if request.reporting_prompt else None
        # Validate placeholders
        if prompt:
            required = ["{source_lang}", "{target_lang}", "{text}", "{glossary_section}"]
            missing = [p for p in required if p not in prompt]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Reporting prompt missing required placeholders: {missing}",
                )
        s.translation_prompt_reporting = prompt if prompt else None
        changes["reporting"] = "custom" if prompt else "reset_to_default"

    if request.marketing_prompt is not None:
        prompt = request.marketing_prompt.strip() if request.marketing_prompt else None
        # Validate placeholders
        if prompt:
            required = ["{source_lang}", "{target_lang}", "{text}", "{glossary_section}"]
            missing = [p for p in required if p not in prompt]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Marketing prompt missing required placeholders: {missing}",
                )
        s.translation_prompt_marketing = prompt if prompt else None
        changes["marketing"] = "custom" if prompt else "reset_to_default"

    if changes:
        audit_event = AuditEvent.create(
            actor_type="user",
            actor_id=str(admin.user_id),
            action="translation_prompts_update",
            entity_type="platform_ai_settings",
            entity_id="1",
            metadata={"changes": changes},
            company_id=None,
        )
        session.add(audit_event)
        await session.commit()
        await session.refresh(s)

    return TranslationPromptsResponse(
        reporting_prompt=s.translation_prompt_reporting or DEFAULT_PROMPT_REPORTING,
        marketing_prompt=s.translation_prompt_marketing or DEFAULT_PROMPT_MARKETING,
        reporting_is_custom=s.translation_prompt_reporting is not None,
        marketing_is_custom=s.translation_prompt_marketing is not None,
    )


@router.post("/translation-prompts/reset", response_model=TranslationPromptsResponse)
async def reset_translation_prompts(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
) -> TranslationPromptsResponse:
    """
    Reset both translation prompts to defaults.
    """
    s = await _get_platform_ai_settings(session)

    s.translation_prompt_reporting = None
    s.translation_prompt_marketing = None

    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="translation_prompts_reset",
        entity_type="platform_ai_settings",
        entity_id="1",
        metadata={"action": "reset_all_to_default"},
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()
    await session.refresh(s)

    return TranslationPromptsResponse(
        reporting_prompt=DEFAULT_PROMPT_REPORTING,
        marketing_prompt=DEFAULT_PROMPT_MARKETING,
        reporting_is_custom=False,
        marketing_is_custom=False,
    )


# =============================================================================
# AI Usage Tracking
# =============================================================================


class AIUsageStatsResponse(BaseModel):
    """AI usage statistics."""

    total_events: int
    total_cost_usd: str  # Decimal as string
    by_feature: dict[str, dict[str, str | int]]  # feature -> {count, cost}
    by_company: list[dict[str, str | int]]  # Top companies by usage


@router.get("/ai-usage", response_model=AIUsageStatsResponse)
async def get_ai_usage_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    company_id: UUID | None = Query(default=None),
) -> AIUsageStatsResponse:
    """
    Get AI usage statistics (cross-tenant).

    Query params:
        - from_date: Filter events after this timestamp
        - to_date: Filter events before this timestamp
        - company_id: Filter by specific company

    Returns:
        Aggregated usage stats by feature and company
    """
    from sqlalchemy import func as sql_func

    # Build base query
    query = select(AIUsageEvent)

    # Apply filters
    if from_date:
        query = query.where(AIUsageEvent.timestamp_utc >= from_date)
    if to_date:
        query = query.where(AIUsageEvent.timestamp_utc <= to_date)
    if company_id is not None:
        query = query.where(AIUsageEvent.company_id == company_id)

    # Get all events
    result = await session.execute(query)
    events = result.scalars().all()

    # Calculate stats
    total_events = len(events)
    total_cost = sum(e.estimated_cost_usd for e in events)

    # By feature
    by_feature: dict[str, dict[str, str | int]] = {}
    for event in events:
        feature = event.feature.value
        if feature not in by_feature:
            by_feature[feature] = {"count": 0, "cost_usd": "0.0", "tokens": 0}

        by_feature[feature]["count"] = int(by_feature[feature]["count"]) + 1  # type: ignore
        current_cost = float(by_feature[feature]["cost_usd"])  # type: ignore
        by_feature[feature]["cost_usd"] = str(current_cost + float(event.estimated_cost_usd))
        by_feature[feature]["tokens"] = int(by_feature[feature]["tokens"]) + event.input_tokens + event.output_tokens  # type: ignore

    # By company (top 10)
    company_usage: dict[str, dict[str, float | int]] = {}
    for event in events:
        if event.company_id:
            company_id_str = str(event.company_id)
            if company_id_str not in company_usage:
                company_usage[company_id_str] = {"count": 0, "cost": 0.0}

            company_usage[company_id_str]["count"] += 1
            company_usage[company_id_str]["cost"] += float(event.estimated_cost_usd)

    # Sort companies by cost DESC
    by_company = [
        {
            "company_id": cid,
            "count": int(stats["count"]),
            "cost_usd": str(stats["cost"]),
        }
        for cid, stats in sorted(
            company_usage.items(),
            key=lambda x: x[1]["cost"],
            reverse=True,
        )[:10]
    ]

    return AIUsageStatsResponse(
        total_events=total_events,
        total_cost_usd=str(total_cost),
        by_feature=by_feature,
        by_company=by_company,
    )


# =============================================================================
# Health Check (basic smoke test)
# =============================================================================


# =============================================================================
# Build Cleanup (Retention Policy)
# =============================================================================


class CleanupResultResponse(BaseModel):
    """Result of builds cleanup operation."""

    deleted_builds: int
    deleted_zips: int
    deleted_manifests: int
    freed_mb: float
    errors: list[str]
    dry_run: bool


class OrphanedFilesResultResponse(BaseModel):
    """Result of orphaned files cleanup."""

    orphaned_zips: list[str]
    orphaned_manifests: list[str]
    total_orphaned_mb: float
    deleted: bool  # False if dry_run


@router.post("/builds/cleanup", response_model=CleanupResultResponse)
async def cleanup_old_builds_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
    retention_days: int = Query(default=30, ge=1, le=365, description="Delete DRAFT builds older than N days"),
    dry_run: bool = Query(default=True, description="If True, only report what would be deleted"),
) -> CleanupResultResponse:
    """
    Cleanup old DRAFT builds (retention policy).

    Safe action:
    - Only deletes DRAFT builds (never RELEASE)
    - Default: dry_run=True (preview only)
    - Removes ZIP files, manifests, and DB records
    - Logs action in audit log

    Returns:
        Cleanup statistics
    """
    from app.services.cleanup import cleanup_old_builds

    result = await cleanup_old_builds(
        session=session,
        retention_days=retention_days,
        dry_run=dry_run,
    )

    # Log action
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="builds_cleanup",
        entity_type="platform",
        entity_id="cleanup",
        metadata={
            "retention_days": retention_days,
            "dry_run": dry_run,
            "deleted_builds": len(result.deleted_builds),
            "freed_mb": round(result.freed_bytes / (1024 * 1024), 2),
        },
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()

    return CleanupResultResponse(
        deleted_builds=len(result.deleted_builds),
        deleted_zips=len(result.deleted_zips),
        deleted_manifests=len(result.deleted_manifests),
        freed_mb=round(result.freed_bytes / (1024 * 1024), 2),
        errors=result.errors,
        dry_run=dry_run,
    )


@router.post("/builds/cleanup-orphaned", response_model=OrphanedFilesResultResponse)
async def cleanup_orphaned_files_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Superuser,
    dry_run: bool = Query(default=True, description="If True, only report orphaned files"),
) -> OrphanedFilesResultResponse:
    """
    Find and optionally delete orphaned build files.

    Orphaned files are ZIP/manifest files that exist on disk but have no
    corresponding record in the database (e.g., from crashed builds or
    manual file operations).

    Safe action:
    - Default: dry_run=True (preview only)
    - Scans builds directory for files without DB records
    - Logs action in audit log

    Returns:
        List of orphaned files and cleanup statistics
    """
    from pathlib import Path
    import re

    from app.config import settings
    from app.domain.models.release import ReleaseBuild

    builds_path = Path(settings.builds_local_path)

    if not builds_path.exists():
        return OrphanedFilesResultResponse(
            orphaned_zips=[],
            orphaned_manifests=[],
            total_orphaned_mb=0.0,
            deleted=False,
        )

    # Get all build IDs from database
    result = await session.execute(select(ReleaseBuild.build_id))
    db_build_ids = {str(row[0]) for row in result.all()}

    orphaned_zips: list[str] = []
    orphaned_manifests: list[str] = []
    total_bytes = 0

    # UUID pattern for extracting build_id from filenames
    uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)

    # Scan directory
    for file_path in builds_path.iterdir():
        if not file_path.is_file():
            continue

        filename = file_path.name

        # Extract build_id from filename
        # ZIP: report-{report_id}-{type}-{build_id}.zip
        # Manifest: build-manifest-{build_id}.json
        uuids = uuid_pattern.findall(filename)

        if filename.endswith('.zip') and len(uuids) >= 2:
            # Last UUID is build_id
            build_id = uuids[-1]
            if build_id not in db_build_ids:
                orphaned_zips.append(filename)
                total_bytes += file_path.stat().st_size
                if not dry_run:
                    file_path.unlink()

        elif filename.startswith('build-manifest-') and filename.endswith('.json') and len(uuids) >= 1:
            build_id = uuids[0]
            if build_id not in db_build_ids:
                orphaned_manifests.append(filename)
                total_bytes += file_path.stat().st_size
                if not dry_run:
                    file_path.unlink()

    # Log action
    audit_event = AuditEvent.create(
        actor_type="user",
        actor_id=str(admin.user_id),
        action="orphaned_files_cleanup",
        entity_type="platform",
        entity_id="cleanup",
        metadata={
            "dry_run": dry_run,
            "orphaned_zips": len(orphaned_zips),
            "orphaned_manifests": len(orphaned_manifests),
            "freed_mb": round(total_bytes / (1024 * 1024), 2),
        },
        company_id=None,
    )
    session.add(audit_event)
    await session.commit()

    return OrphanedFilesResultResponse(
        orphaned_zips=orphaned_zips,
        orphaned_manifests=orphaned_manifests,
        total_orphaned_mb=round(total_bytes / (1024 * 1024), 2),
        deleted=not dry_run,
    )


# =============================================================================
# Health Check (basic smoke test)
# =============================================================================


@router.get("/health")
async def admin_health() -> dict:
    """
    Health check for admin endpoints.

    Returns simple status to verify superuser access is working.
    """
    return {
        "status": "ok",
        "message": "Admin endpoints are accessible",
    }

