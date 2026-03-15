"""
ESG Dashboard API (MVP).

Company-scoped pillar providing:
- Dimensions (entities/locations/segments)
- Metrics
- Facts (versioned) + evidence
"""

from __future__ import annotations

from datetime import UTC, datetime, date, timedelta
from contextlib import suppress
from typing import Annotated
from uuid import UUID

import hashlib
import json
import sqlalchemy as sa
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import CompanyContextRequiredError, CompanySummary
from app.api.v1.deps import CurrentUser, RBACChecker, require_tenant_access
from app.domain.models import (
    Asset,
    AuditEvent,
    Company,
    CompanyMembership,
    Dataset,
    DatasetRevision,
    EsgEntity,
    EsgFact,
    EsgFactEvidenceItem,
    EsgFactEvidenceType,
    EsgFactReviewComment,
    EsgFactStatus,
    EsgLocation,
    EsgMetric,
    EsgMetricAssignment,
    EsgMetricValueType,
    EsgSegment,
    User,
)
from app.domain.schemas import (
    EsgEntityCreate,
    EsgEntityDTO,
    EsgEntityUpdate,
    EsgFactCompareItemDTO,
    EsgFactCompareRequest,
    EsgFactCreate,
    EsgFactDTO,
    EsgFactEvidenceCreate,
    EsgFactEvidenceDTO,
    EsgFactEvidenceUpdate,
    EsgFactLatestDTO,
    EsgFactImportConfirmDTO,
    EsgFactImportPreviewDTO,
    EsgFactRequestChanges,
    EsgFactStatusEnum,
    EsgFactUpdate,
    EsgGapFactAttentionDTO,
    EsgGapIssueDTO,
    EsgGapMetricDTO,
    EsgGapsDTO,
    EsgSnapshotFactDTO,
    EsgSnapshotDTO,
    EsgLocationCreate,
    EsgLocationDTO,
    EsgLocationUpdate,
    EsgMetricCreate,
    EsgMetricDTO,
    EsgMetricOwnerDTO,
    EsgMetricOwnerUpsert,
    EsgMetricUpdate,
    EsgPeriodTypeEnum,
    EsgSegmentCreate,
    EsgSegmentDTO,
    EsgSegmentUpdate,
    EsgFactReviewCommentCreate,
    EsgFactReviewCommentDTO,
    EsgFactTimelineEventDTO,
    PaginatedResponse,
)
from app.infra.database import get_session
from app.infra.db_errors import pg_constraint_name, pg_sqlstate
from app.services.audit_logger import AuditAction, AuditLogger
from app.services.esg_fact_import import EsgFactImportService
from app.services.esg_logical_key import compute_fact_logical_key_hash, normalize_tags

router = APIRouter(prefix="/esg", tags=["ESG"])

_PG_UNIQUE_VIOLATION = "23505"
_UQ_FACT_VERSION = "uq_esg_facts_company_logical_version"


async def _infer_company_id(session: AsyncSession, user: CurrentUser, company_id: UUID | None) -> UUID:
    """
    Infer company_id for company-scoped ESG operations.

    Rules:
    - If company_id is provided:
      - Superuser: accepts any company_id.
      - Regular user: must have an active membership in the company_id.
    - If company_id is missing:
      - If the user has exactly 1 active membership -> use it.
      - If the user has >1 active memberships -> require explicit company_id.
    """
    if company_id is not None:
        if user.is_superuser:
            return company_id

        # Regular users can select company_id among their active memberships.
        membership_exists_stmt = select(func.count()).select_from(CompanyMembership).where(
            CompanyMembership.user_id == user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
            CompanyMembership.company_id == company_id,
        )
        has_membership = (await session.execute(membership_exists_stmt)).scalar() or 0
        if has_membership <= 0:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active company membership found")
        return company_id

    # No company_id passed: infer only if unambiguous.
    memberships_stmt = (
        select(CompanyMembership.company_id, Company.name)
        .join(Company, Company.company_id == CompanyMembership.company_id)
        .where(
            CompanyMembership.user_id == user.user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
        .order_by(Company.name.asc())
    )
    rows = (await session.execute(memberships_stmt)).all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active company membership found")
    if len(rows) == 1:
        return rows[0][0]

    companies = [CompanySummary(id=company_id, name=name) for company_id, name in rows]
    raise CompanyContextRequiredError(companies=companies)


# =============================================================================
# Dimensions
# =============================================================================


@router.get("/entities", response_model=PaginatedResponse[EsgEntityDTO])
async def list_entities(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> PaginatedResponse[EsgEntityDTO]:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    stmt = select(EsgEntity).where(EsgEntity.company_id == company_id_resolved)
    if not include_inactive:
        stmt = stmt.where(EsgEntity.is_active == True)  # noqa: E712
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(EsgEntity.name.ilike(like), EsgEntity.code.ilike(like)))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(EsgEntity.name.asc()).offset((page - 1) * page_size).limit(page_size)
    entities = (await session.execute(stmt)).scalars().all()
    return PaginatedResponse[EsgEntityDTO].create(items=entities, total=total, page=page, page_size=page_size)


@router.post("/entities", response_model=EsgEntityDTO, status_code=status.HTTP_201_CREATED)
async def create_entity(
    data: EsgEntityCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgEntityDTO:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    entity = EsgEntity(
        company_id=company_id_resolved,
        code=data.code,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        created_by=current_user.user_id,
    )
    session.add(entity)
    await session.flush()

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_ENTITY_CREATE,
        entity_type="esg_entity",
        entity_id=entity.entity_id,
        company_id=company_id_resolved,
        metadata={"code": data.code, "name": data.name},
    )

    await session.commit()
    await session.refresh(entity)
    return EsgEntityDTO.model_validate(entity)


@router.patch("/entities/{entity_id}", response_model=EsgEntityDTO)
async def update_entity(
    entity_id: UUID,
    data: EsgEntityUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgEntityDTO:
    entity = await session.get(EsgEntity, entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    require_tenant_access(current_user, company_id=entity.company_id, permission="esg:write")

    before = {"code": entity.code, "name": entity.name, "description": entity.description, "is_active": entity.is_active}
    if data.code is not None:
        entity.code = data.code
    if data.name is not None:
        entity.name = data.name
    if data.description is not None:
        entity.description = data.description
    if data.is_active is not None:
        entity.is_active = data.is_active

    after = {"code": entity.code, "name": entity.name, "description": entity.description, "is_active": entity.is_active}

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_ENTITY_UPDATE,
        entity_type="esg_entity",
        entity_id=entity.entity_id,
        company_id=entity.company_id,
        metadata={"before": before, "after": after},
    )

    await session.commit()
    await session.refresh(entity)
    return EsgEntityDTO.model_validate(entity)


@router.get("/locations", response_model=PaginatedResponse[EsgLocationDTO])
async def list_locations(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> PaginatedResponse[EsgLocationDTO]:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    stmt = select(EsgLocation).where(EsgLocation.company_id == company_id_resolved)
    if not include_inactive:
        stmt = stmt.where(EsgLocation.is_active == True)  # noqa: E712
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(EsgLocation.name.ilike(like), EsgLocation.code.ilike(like)))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(EsgLocation.name.asc()).offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()
    return PaginatedResponse[EsgLocationDTO].create(items=items, total=total, page=page, page_size=page_size)


@router.post("/locations", response_model=EsgLocationDTO, status_code=status.HTTP_201_CREATED)
async def create_location(
    data: EsgLocationCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgLocationDTO:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    item = EsgLocation(
        company_id=company_id_resolved,
        code=data.code,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        created_by=current_user.user_id,
    )
    session.add(item)
    await session.flush()

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_LOCATION_CREATE,
        entity_type="esg_location",
        entity_id=item.location_id,
        company_id=company_id_resolved,
        metadata={"code": data.code, "name": data.name},
    )

    await session.commit()
    await session.refresh(item)
    return EsgLocationDTO.model_validate(item)


@router.patch("/locations/{location_id}", response_model=EsgLocationDTO)
async def update_location(
    location_id: UUID,
    data: EsgLocationUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgLocationDTO:
    item = await session.get(EsgLocation, location_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    require_tenant_access(current_user, company_id=item.company_id, permission="esg:write")

    before = {"code": item.code, "name": item.name, "description": item.description, "is_active": item.is_active}
    if data.code is not None:
        item.code = data.code
    if data.name is not None:
        item.name = data.name
    if data.description is not None:
        item.description = data.description
    if data.is_active is not None:
        item.is_active = data.is_active
    after = {"code": item.code, "name": item.name, "description": item.description, "is_active": item.is_active}

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_LOCATION_UPDATE,
        entity_type="esg_location",
        entity_id=item.location_id,
        company_id=item.company_id,
        metadata={"before": before, "after": after},
    )

    await session.commit()
    await session.refresh(item)
    return EsgLocationDTO.model_validate(item)


@router.get("/segments", response_model=PaginatedResponse[EsgSegmentDTO])
async def list_segments(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> PaginatedResponse[EsgSegmentDTO]:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    stmt = select(EsgSegment).where(EsgSegment.company_id == company_id_resolved)
    if not include_inactive:
        stmt = stmt.where(EsgSegment.is_active == True)  # noqa: E712
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(EsgSegment.name.ilike(like), EsgSegment.code.ilike(like)))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(EsgSegment.name.asc()).offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()
    return PaginatedResponse[EsgSegmentDTO].create(items=items, total=total, page=page, page_size=page_size)


@router.post("/segments", response_model=EsgSegmentDTO, status_code=status.HTTP_201_CREATED)
async def create_segment(
    data: EsgSegmentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgSegmentDTO:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    item = EsgSegment(
        company_id=company_id_resolved,
        code=data.code,
        name=data.name,
        description=data.description,
        is_active=data.is_active,
        created_by=current_user.user_id,
    )
    session.add(item)
    await session.flush()

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_SEGMENT_CREATE,
        entity_type="esg_segment",
        entity_id=item.segment_id,
        company_id=company_id_resolved,
        metadata={"code": data.code, "name": data.name},
    )

    await session.commit()
    await session.refresh(item)
    return EsgSegmentDTO.model_validate(item)


@router.patch("/segments/{segment_id}", response_model=EsgSegmentDTO)
async def update_segment(
    segment_id: UUID,
    data: EsgSegmentUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgSegmentDTO:
    item = await session.get(EsgSegment, segment_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    require_tenant_access(current_user, company_id=item.company_id, permission="esg:write")

    before = {"code": item.code, "name": item.name, "description": item.description, "is_active": item.is_active}
    if data.code is not None:
        item.code = data.code
    if data.name is not None:
        item.name = data.name
    if data.description is not None:
        item.description = data.description
    if data.is_active is not None:
        item.is_active = data.is_active
    after = {"code": item.code, "name": item.name, "description": item.description, "is_active": item.is_active}

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_SEGMENT_UPDATE,
        entity_type="esg_segment",
        entity_id=item.segment_id,
        company_id=item.company_id,
        metadata={"before": before, "after": after},
    )

    await session.commit()
    await session.refresh(item)
    return EsgSegmentDTO.model_validate(item)


# =============================================================================
# Metrics
# =============================================================================


@router.get("/metrics", response_model=PaginatedResponse[EsgMetricDTO])
async def list_metrics(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> PaginatedResponse[EsgMetricDTO]:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    stmt = select(EsgMetric).where(EsgMetric.company_id == company_id_resolved)
    if not include_inactive:
        stmt = stmt.where(EsgMetric.is_active == True)  # noqa: E712
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(EsgMetric.name.ilike(like), EsgMetric.code.ilike(like)))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(EsgMetric.name.asc()).offset((page - 1) * page_size).limit(page_size)
    items = (await session.execute(stmt)).scalars().all()
    return PaginatedResponse[EsgMetricDTO].create(items=items, total=total, page=page, page_size=page_size)


@router.post("/metrics", response_model=EsgMetricDTO, status_code=status.HTTP_201_CREATED)
async def create_metric(
    data: EsgMetricCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgMetricDTO:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    metric = EsgMetric(
        company_id=company_id_resolved,
        code=data.code,
        name=data.name,
        description=data.description,
        value_type=EsgMetricValueType(data.value_type.value),
        unit=data.unit,
        value_schema_json=data.value_schema_json,
        is_active=data.is_active,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    session.add(metric)
    await session.flush()

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_METRIC_CREATE,
        entity_type="esg_metric",
        entity_id=metric.metric_id,
        company_id=company_id_resolved,
        metadata={"code": data.code, "name": data.name, "value_type": data.value_type.value},
    )

    await session.commit()
    await session.refresh(metric)
    return EsgMetricDTO.model_validate(metric)


@router.get("/metrics/{metric_id}", response_model=EsgMetricDTO)
async def get_metric(
    metric_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> EsgMetricDTO:
    metric = await session.get(EsgMetric, metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    require_tenant_access(current_user, company_id=metric.company_id, permission="esg:read")
    return EsgMetricDTO.model_validate(metric)


@router.patch("/metrics/{metric_id}", response_model=EsgMetricDTO)
async def update_metric(
    metric_id: UUID,
    data: EsgMetricUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgMetricDTO:
    metric = await session.get(EsgMetric, metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    require_tenant_access(current_user, company_id=metric.company_id, permission="esg:write")

    # Metric type/unit are treated as a contract once facts exist.
    if data.value_type is not None or data.unit is not None:
        facts_count_stmt = (
            select(func.count())
            .select_from(EsgFact)
            .where(EsgFact.company_id == metric.company_id, EsgFact.metric_id == metric.metric_id)
        )
        facts_count = (await session.execute(facts_count_stmt)).scalar() or 0
        if facts_count > 0:
            if data.value_type is not None and EsgMetricValueType(data.value_type.value) != metric.value_type:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Metric has facts and value_type cannot be changed",
                )
            if data.unit is not None and data.unit != metric.unit:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Metric has facts and unit cannot be changed",
                )

    before = {
        "code": metric.code,
        "name": metric.name,
        "description": metric.description,
        "value_type": metric.value_type.value,
        "unit": metric.unit,
        "value_schema_json": metric.value_schema_json,
        "is_active": metric.is_active,
    }

    if data.code is not None:
        metric.code = data.code
    if data.name is not None:
        metric.name = data.name
    if data.description is not None:
        metric.description = data.description
    if data.value_type is not None:
        metric.value_type = EsgMetricValueType(data.value_type.value)
    if data.unit is not None:
        metric.unit = data.unit
    if data.value_schema_json is not None:
        metric.value_schema_json = data.value_schema_json
    if data.is_active is not None:
        metric.is_active = data.is_active

    metric.updated_by = current_user.user_id

    after = {
        "code": metric.code,
        "name": metric.name,
        "description": metric.description,
        "value_type": metric.value_type.value,
        "unit": metric.unit,
        "value_schema_json": metric.value_schema_json,
        "is_active": metric.is_active,
    }

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_METRIC_UPDATE,
        entity_type="esg_metric",
        entity_id=metric.metric_id,
        company_id=metric.company_id,
        metadata={"before": before, "after": after},
    )

    await session.commit()
    await session.refresh(metric)
    return EsgMetricDTO.model_validate(metric)


@router.delete("/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    metric_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> None:
    metric = await session.get(EsgMetric, metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    require_tenant_access(current_user, company_id=metric.company_id, permission="esg:write")

    facts_count_stmt = (
        select(func.count())
        .select_from(EsgFact)
        .where(EsgFact.company_id == metric.company_id, EsgFact.metric_id == metric.metric_id)
    )
    facts_count = (await session.execute(facts_count_stmt)).scalar() or 0
    if facts_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Metric has facts and cannot be deleted",
        )

    before = {
        "metric_id": str(metric.metric_id),
        "code": metric.code,
        "name": metric.name,
        "description": metric.description,
        "value_type": metric.value_type.value,
        "unit": metric.unit,
        "value_schema_json": metric.value_schema_json,
        "is_active": metric.is_active,
    }

    await session.delete(metric)

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_METRIC_DELETE,
        entity_type="esg_metric",
        entity_id=metric_id,
        company_id=metric.company_id,
        metadata={"before": before},
    )

    await session.commit()


# =============================================================================
# Metric Owners (Assignments)
# =============================================================================


@router.get("/metric-owners", response_model=list[EsgMetricOwnerDTO])
async def list_metric_owners(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    metric_ids: list[UUID] | None = Query(default=None),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> list[EsgMetricOwnerDTO]:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    stmt = (
        select(EsgMetricAssignment, User)
        .outerjoin(User, User.user_id == EsgMetricAssignment.owner_user_id)
        .where(EsgMetricAssignment.company_id == company_id_resolved)
    )
    if metric_ids:
        stmt = stmt.where(EsgMetricAssignment.metric_id.in_(metric_ids))
    stmt = stmt.order_by(EsgMetricAssignment.metric_id.asc())

    rows = (await session.execute(stmt)).all()
    out: list[EsgMetricOwnerDTO] = []
    for assignment, owner in rows:
        out.append(
            EsgMetricOwnerDTO(
                metric_id=assignment.metric_id,
                owner_user_id=assignment.owner_user_id,
                owner_user_name=getattr(owner, "full_name", None) if owner else None,
                owner_user_email=getattr(owner, "email", None) if owner else None,
                updated_at_utc=assignment.updated_at_utc,
            )
        )
    return out


@router.put("/metrics/{metric_id}/owner", response_model=EsgMetricOwnerDTO)
async def upsert_metric_owner(
    metric_id: UUID,
    data: EsgMetricOwnerUpsert,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgMetricOwnerDTO:
    metric = await session.get(EsgMetric, metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    require_tenant_access(current_user, company_id=metric.company_id, permission="esg:write")

    owner_user_id = data.owner_user_id
    if owner_user_id is not None:
        # Owner must be an active company member to avoid "orphan" assignments.
        membership_stmt = select(func.count()).select_from(CompanyMembership).where(
            CompanyMembership.company_id == metric.company_id,
            CompanyMembership.user_id == owner_user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
        membership_count = (await session.execute(membership_stmt)).scalar() or 0
        if membership_count <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Owner must be an active company member",
            )

    existing_stmt = select(EsgMetricAssignment).where(
        EsgMetricAssignment.company_id == metric.company_id,
        EsgMetricAssignment.metric_id == metric.metric_id,
    )
    assignment = (await session.execute(existing_stmt)).scalars().first()

    if owner_user_id is None:
        if assignment is not None:
            await session.delete(assignment)
            await session.commit()
        return EsgMetricOwnerDTO(metric_id=metric.metric_id, owner_user_id=None, owner_user_name=None, owner_user_email=None, updated_at_utc=None)

    if assignment is None:
        assignment = EsgMetricAssignment(
            company_id=metric.company_id,
            metric_id=metric.metric_id,
            owner_user_id=owner_user_id,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        session.add(assignment)
    else:
        assignment.owner_user_id = owner_user_id
        assignment.updated_by = current_user.user_id

    await session.commit()
    await session.refresh(assignment)

    owner = await session.get(User, owner_user_id)
    return EsgMetricOwnerDTO(
        metric_id=metric.metric_id,
        owner_user_id=owner_user_id,
        owner_user_name=owner.full_name if owner else None,
        owner_user_email=owner.email if owner else None,
        updated_at_utc=assignment.updated_at_utc,
    )


# =============================================================================
# Facts
# =============================================================================


async def _ensure_dimension_belongs(
    session: AsyncSession,
    *,
    company_id: UUID,
    entity_id: UUID | None,
    location_id: UUID | None,
    segment_id: UUID | None,
) -> None:
    if entity_id is not None:
        entity = await session.get(EsgEntity, entity_id)
        if not entity or entity.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    if location_id is not None:
        location = await session.get(EsgLocation, location_id)
        if not location or location.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    if segment_id is not None:
        segment = await session.get(EsgSegment, segment_id)
        if not segment or segment.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")


async def _ensure_dataset_belongs(session: AsyncSession, *, company_id: UUID, dataset_id: UUID) -> Dataset:
    dataset = await session.get(Dataset, dataset_id)
    if not dataset or dataset.is_deleted or dataset.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


def _validate_value_for_metric(metric: EsgMetric, *, value_json: object | None, dataset_id: UUID | None) -> None:
    if metric.value_type == EsgMetricValueType.DATASET:
        if dataset_id is None or value_json is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Dataset metric requires dataset_id and value_json must be null",
            )
        return

    if value_json is None or dataset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Scalar metric requires value_json and dataset_id must be null",
        )

    if metric.value_type == EsgMetricValueType.BOOLEAN:
        if not isinstance(value_json, bool):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expected boolean value_json")
        return

    # bool is a subclass of int; reject booleans for numeric types.
    if isinstance(value_json, bool):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid value_json type")

    if metric.value_type == EsgMetricValueType.INTEGER:
        if not isinstance(value_json, int):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expected integer value_json")
        return

    if metric.value_type == EsgMetricValueType.NUMBER:
        if not isinstance(value_json, (int, float)):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expected numeric value_json")
        return

    if metric.value_type == EsgMetricValueType.STRING:
        if not isinstance(value_json, str):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expected string value_json")
        return

    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported metric value_type")


async def _snapshot_dataset_revision(
    session: AsyncSession,
    *,
    dataset: Dataset,
    user_id: UUID,
    reason: str,
) -> DatasetRevision:
    # Snapshotting does not change data, but creates an immutable revision and increments `current_revision`.
    dataset.current_revision += 1
    dataset.updated_by = user_id
    dataset.updated_at_utc = datetime.now(UTC)

    revision = DatasetRevision(
        dataset_id=dataset.dataset_id,
        revision_number=dataset.current_revision,
        schema_json=dataset.schema_json,
        rows_json=dataset.rows_json,
        meta_json=dataset.meta_json,
        created_by=user_id,
        reason=reason,
    )
    session.add(revision)
    await session.flush()
    return revision


async def _ensure_fact_is_latest(session: AsyncSession, *, fact: EsgFact) -> None:
    """
    Prevent modifying/publishing older versions in a logical key group.

    This keeps the lifecycle consistent without adding new DB entities.
    """
    max_stmt = select(func.max(EsgFact.version_number)).where(
        EsgFact.company_id == fact.company_id,
        EsgFact.logical_key_hash == fact.logical_key_hash,
    )
    max_version = (await session.execute(max_stmt)).scalar() or 0
    if fact.version_number != max_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the latest fact version can be modified",
        )


async def _collect_fact_quality_gate_issues(
    session: AsyncSession,
    *,
    fact: EsgFact,
    metric: EsgMetric,
    evidence_count: int | None = None,
) -> list[tuple[str, str]]:
    """
    Collect quality gate issues driven by metric.value_schema_json.

    Return value: list of (code, message). Codes are stable enough to summarize in UI.
    """
    schema = metric.value_schema_json or {}
    issues: list[tuple[str, str]] = []

    requirements = schema.get("requirements") if isinstance(schema, dict) else None
    if not isinstance(requirements, dict):
        requirements = {}

    # 1) Required source fields (stored in fact.sources_json).
    src_req = requirements.get("sources")
    if isinstance(src_req, dict):
        required_fields = src_req.get("required_fields")
        if isinstance(required_fields, list):
            sources = fact.sources_json or {}
            for raw in required_fields:
                if not isinstance(raw, str):
                    continue
                key = raw.strip()
                if not key:
                    continue
                v = sources.get(key)
                if v is None:
                    issues.append((f"missing_source:{key}", f"sources_json.{key} is required"))
                    continue
                if isinstance(v, str) and not v.strip():
                    issues.append((f"missing_source:{key}", f"sources_json.{key} is required"))
                    continue
                if isinstance(v, (list, dict)) and len(v) == 0:
                    issues.append((f"missing_source:{key}", f"sources_json.{key} is required"))
                    continue

    # 2) Evidence requirement (stored as rows in esg_fact_evidence).
    ev_req = requirements.get("evidence")
    if isinstance(ev_req, dict):
        min_items = ev_req.get("min_items")
        if isinstance(min_items, int) and min_items > 0:
            ev_count = evidence_count
            if ev_count is None:
                ev_count_stmt = select(func.count()).select_from(EsgFactEvidenceItem).where(
                    EsgFactEvidenceItem.company_id == fact.company_id,
                    EsgFactEvidenceItem.fact_id == fact.fact_id,
                )
                ev_count = (await session.execute(ev_count_stmt)).scalar() or 0
            if ev_count < min_items:
                issues.append(
                    (
                        "missing_evidence",
                        f"At least {min_items} evidence item(s) required (have {ev_count})",
                    )
                )

    # 3) Numeric range checks for scalar facts.
    checks = schema.get("checks") if isinstance(schema, dict) else None
    if not isinstance(checks, dict):
        checks = {}

    range_spec = checks.get("range")
    if range_spec is None and isinstance(schema, dict):
        range_spec = schema.get("range")
    if isinstance(range_spec, dict) and fact.dataset_id is None and fact.value_json is not None:
        if isinstance(fact.value_json, bool):
            # bool is a subclass of int; ignore range checks for booleans.
            pass
        elif isinstance(fact.value_json, (int, float)):
            min_v = range_spec.get("min")
            max_v = range_spec.get("max")
            if isinstance(min_v, (int, float)) and fact.value_json < min_v:
                issues.append(("range_below_min", f"value_json is below min ({fact.value_json} < {min_v})"))
            if isinstance(max_v, (int, float)) and fact.value_json > max_v:
                issues.append(("range_above_max", f"value_json is above max ({fact.value_json} > {max_v})"))

    return issues


async def _validate_fact_quality_gates(session: AsyncSession, *, fact: EsgFact, metric: EsgMetric) -> None:
    issues = await _collect_fact_quality_gate_issues(session, fact=fact, metric=metric)
    if not issues:
        return
    messages = [msg for _code, msg in issues]
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Quality gates failed: " + "; ".join(messages),
    )


@router.post("/facts", response_model=EsgFactDTO, status_code=status.HTTP_201_CREATED)
async def create_fact(
    data: EsgFactCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactDTO:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    metric = await session.get(EsgMetric, data.metric_id)
    if not metric or metric.company_id != company_id_resolved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    await _ensure_dimension_belongs(
        session,
        company_id=company_id_resolved,
        entity_id=data.entity_id,
        location_id=data.location_id,
        segment_id=data.segment_id,
    )

    tags = normalize_tags(data.tags)
    dataset_id = data.dataset_id
    value_json = data.value_json

    _validate_value_for_metric(metric, value_json=value_json, dataset_id=dataset_id)

    if dataset_id is not None:
        await _ensure_dataset_belongs(session, company_id=company_id_resolved, dataset_id=dataset_id)

    logical_key_hash = compute_fact_logical_key_hash(
        metric_id=metric.metric_id,
        period_start=data.period_start,
        period_end=data.period_end,
        period_type=data.period_type.value,
        is_ytd=data.is_ytd,
        entity_id=data.entity_id,
        location_id=data.location_id,
        segment_id=data.segment_id,
        consolidation_approach=data.consolidation_approach,
        ghg_scope=data.ghg_scope,
        scope2_method=data.scope2_method,
        scope3_category=data.scope3_category,
        tags=tags,
    )

    in_review_stmt = select(func.count()).select_from(EsgFact).where(
        EsgFact.company_id == company_id_resolved,
        EsgFact.logical_key_hash == logical_key_hash,
        EsgFact.status == EsgFactStatus.IN_REVIEW,
    )
    in_review_count = (await session.execute(in_review_stmt)).scalar() or 0
    if in_review_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A fact is currently in review for this logical key; request changes before creating a new version",
        )

    latest_stmt = (
        select(EsgFact)
        .where(EsgFact.company_id == company_id_resolved, EsgFact.logical_key_hash == logical_key_hash)
        .order_by(EsgFact.version_number.desc())
        .limit(1)
    )

    # Race condition guard: version_number is computed from latest, so concurrent callers
    # can collide on the same (company_id, logical_key_hash, version_number).
    #
    # We use a SAVEPOINT per attempt so an expected IntegrityError doesn't blow away the
    # whole request transaction (important for tests which use per-test transactions).
    max_retries = 2
    fact: EsgFact | None = None
    version_number: int | None = None
    supersedes_fact_id: UUID | None = None

    for attempt in range(max_retries + 1):
        latest = (await session.execute(latest_stmt)).scalars().first()
        version_number = (latest.version_number + 1) if latest else 1
        supersedes_fact_id = latest.fact_id if latest else None

        fact = EsgFact(
            company_id=company_id_resolved,
            metric_id=metric.metric_id,
            status=EsgFactStatus.DRAFT,
            version_number=version_number,
            supersedes_fact_id=supersedes_fact_id,
            logical_key_hash=logical_key_hash,
            period_type=data.period_type.value,
            period_start=data.period_start,
            period_end=data.period_end,
            is_ytd=data.is_ytd,
            entity_id=data.entity_id,
            location_id=data.location_id,
            segment_id=data.segment_id,
            consolidation_approach=data.consolidation_approach,
            ghg_scope=data.ghg_scope,
            scope2_method=data.scope2_method,
            scope3_category=data.scope3_category,
            tags=tags or None,
            value_json=value_json if dataset_id is None else None,
            dataset_id=dataset_id,
            dataset_revision_id=None,
            quality_json=data.quality_json,
            sources_json=data.sources_json,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )

        try:
            async with session.begin_nested():
                session.add(fact)
                await session.flush()
            break
        except IntegrityError as e:
            # Ensure the failed object doesn't linger in the session.
            with suppress(Exception):
                session.expunge(fact)

            if pg_sqlstate(e) == _PG_UNIQUE_VIOLATION and pg_constraint_name(e) == _UQ_FACT_VERSION:
                if attempt < max_retries:
                    continue
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Fact version conflict. Please retry.",
                )
            raise

    assert fact is not None and version_number is not None

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_CREATE,
        entity_type="esg_fact",
        entity_id=fact.fact_id,
        company_id=company_id_resolved,
        metadata={
            "metric_id": str(metric.metric_id),
            "logical_key_hash": logical_key_hash,
            "version_number": version_number,
        },
    )

    await session.commit()
    await session.refresh(fact)
    return EsgFactDTO.model_validate(fact)


# =============================================================================
# Facts Import
# =============================================================================


@router.post("/facts/import/csv/preview", response_model=EsgFactImportPreviewDTO)
async def import_facts_csv_preview(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
    skip_rows: Annotated[int, Form()] = 0,
    company_id: Annotated[UUID | None, Form()] = None,
) -> EsgFactImportPreviewDTO:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a CSV file (.csv)")

    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    content = await file.read()
    service = EsgFactImportService(session, company_id=company_id_resolved, user_id=current_user.user_id)
    return await service.preview_csv(content=content, skip_rows=skip_rows)


@router.post("/facts/import/csv/confirm", response_model=EsgFactImportConfirmDTO)
async def import_facts_csv_confirm(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
    skip_rows: Annotated[int, Form()] = 0,
    company_id: Annotated[UUID | None, Form()] = None,
) -> EsgFactImportConfirmDTO:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be a CSV file (.csv)")

    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    content = await file.read()
    service = EsgFactImportService(session, company_id=company_id_resolved, user_id=current_user.user_id)
    return await service.confirm_csv(content=content, skip_rows=skip_rows)


@router.post("/facts/import/xlsx/preview", response_model=EsgFactImportPreviewDTO)
async def import_facts_xlsx_preview(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
    sheet_name: Annotated[str | None, Form()] = None,
    skip_rows: Annotated[int, Form()] = 0,
    company_id: Annotated[UUID | None, Form()] = None,
) -> EsgFactImportPreviewDTO:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an Excel file (.xlsx)")

    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    content = await file.read()
    service = EsgFactImportService(session, company_id=company_id_resolved, user_id=current_user.user_id)
    return await service.preview_xlsx(content=content, sheet_name=sheet_name, skip_rows=skip_rows)


@router.post("/facts/import/xlsx/confirm", response_model=EsgFactImportConfirmDTO)
async def import_facts_xlsx_confirm(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
    sheet_name: Annotated[str | None, Form()] = None,
    skip_rows: Annotated[int, Form()] = 0,
    company_id: Annotated[UUID | None, Form()] = None,
) -> EsgFactImportConfirmDTO:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be an Excel file (.xlsx)")

    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:write")

    content = await file.read()
    service = EsgFactImportService(session, company_id=company_id_resolved, user_id=current_user.user_id)
    return await service.confirm_xlsx(content=content, sheet_name=sheet_name, skip_rows=skip_rows)


@router.get("/facts", response_model=PaginatedResponse[EsgFactDTO])
async def list_facts(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    metric_id: UUID | None = Query(default=None),
    logical_key_hash: str | None = Query(default=None),
    entity_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    segment_id: UUID | None = Query(default=None),
    period_from: date | None = Query(default=None),
    period_to: date | None = Query(default=None),
    status_filter: EsgFactStatusEnum | None = Query(default=None, alias="status"),
    latest_only: bool = Query(default=False),
    has_evidence: bool | None = Query(default=None),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> PaginatedResponse[EsgFactDTO]:
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    base_conditions = [EsgFact.company_id == company_id_resolved]
    if metric_id is not None:
        base_conditions.append(EsgFact.metric_id == metric_id)
    if logical_key_hash is not None:
        base_conditions.append(EsgFact.logical_key_hash == logical_key_hash)
    if entity_id is not None:
        base_conditions.append(EsgFact.entity_id == entity_id)
    if location_id is not None:
        base_conditions.append(EsgFact.location_id == location_id)
    if segment_id is not None:
        base_conditions.append(EsgFact.segment_id == segment_id)
    if period_from is not None:
        base_conditions.append(EsgFact.period_end >= period_from)
    if period_to is not None:
        base_conditions.append(EsgFact.period_start <= period_to)
    if status_filter is not None:
        base_conditions.append(EsgFact.status == EsgFactStatus(status_filter.value))

    # Evidence filter:
    # When latest_only=true, filter must apply *after* selecting the latest fact,
    # otherwise an older version might be returned just because it matches the
    # evidence criteria.
    evidence_condition: sa.ColumnElement[bool] | None = None
    if has_evidence is not None:
        evidence_exists = sa.exists(
            select(1).where(
                EsgFactEvidenceItem.company_id == company_id_resolved,
                EsgFactEvidenceItem.fact_id == EsgFact.fact_id,
            )
        )
        evidence_condition = evidence_exists if has_evidence else sa.not_(evidence_exists)

    stmt: sa.Select
    if latest_only:
        if status_filter is not None:
            ordering = [EsgFact.version_number.desc()]
        else:
            status_rank = case(
                (EsgFact.status == EsgFactStatus.PUBLISHED, 3),
                (EsgFact.status == EsgFactStatus.IN_REVIEW, 2),
                (EsgFact.status == EsgFactStatus.DRAFT, 1),
                else_=0,  # superseded and any future states
            )
            ordering = [status_rank.desc(), EsgFact.version_number.desc()]

        ranked = (
            select(
                EsgFact.fact_id.label("fact_id"),
                func.row_number().over(
                    partition_by=EsgFact.logical_key_hash,
                    order_by=ordering,
                ).label("rn"),
            )
            .where(*base_conditions)
            .cte("ranked_facts")
        )

        stmt = (
            select(EsgFact)
            .join(ranked, ranked.c.fact_id == EsgFact.fact_id)
            .where(ranked.c.rn == 1)
        )
        if evidence_condition is not None:
            stmt = stmt.where(evidence_condition)
    else:
        stmt = select(EsgFact).where(*base_conditions)
        if evidence_condition is not None:
            stmt = stmt.where(evidence_condition)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        stmt.order_by(EsgFact.period_end.desc(), EsgFact.metric_id.asc(), EsgFact.version_number.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    facts = (await session.execute(stmt)).scalars().all()

    # Avoid N+1 evidence lookups in UI tables by returning evidence_count for each fact in the page.
    if facts:
        fact_ids = [f.fact_id for f in facts]
        ev_stmt = (
            select(EsgFactEvidenceItem.fact_id, func.count().label("evidence_count"))
            .where(
                EsgFactEvidenceItem.company_id == company_id_resolved,
                EsgFactEvidenceItem.fact_id.in_(fact_ids),
            )
            .group_by(EsgFactEvidenceItem.fact_id)
        )
        evidence_counts = {
            fact_id: int(count) for fact_id, count in (await session.execute(ev_stmt)).all()
        }
        for fact in facts:
            setattr(fact, "evidence_count", evidence_counts.get(fact.fact_id, 0))

    return PaginatedResponse[EsgFactDTO].create(items=facts, total=total, page=page, page_size=page_size)


@router.post("/facts/compare", response_model=list[EsgFactCompareItemDTO])
async def compare_facts(
    data: EsgFactCompareRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> list[EsgFactCompareItemDTO]:
    """
    Batch compare helper for Report integration.

    For each logical_key_hash returns the "latest" fact by the rules:
    - prefer published
    - otherwise prefer in_review
    - otherwise latest draft by version_number
    - otherwise latest superseded
    """
    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    requested: list[str] = []
    seen: set[str] = set()
    for raw in data.logical_key_hashes:
        if not isinstance(raw, str):
            continue
        h = raw.strip().lower()
        if len(h) != 64:
            continue
        if any((c not in "0123456789abcdef") for c in h):
            continue
        if h in seen:
            continue
        seen.add(h)
        requested.append(h)

    if not requested:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No valid logical_key_hashes")

    status_rank = case(
        (EsgFact.status == EsgFactStatus.PUBLISHED, 3),
        (EsgFact.status == EsgFactStatus.IN_REVIEW, 2),
        (EsgFact.status == EsgFactStatus.DRAFT, 1),
        else_=0,
    )
    ranked = (
        select(
            EsgFact.fact_id.label("fact_id"),
            EsgFact.logical_key_hash.label("logical_key_hash"),
            func.row_number()
            .over(
                partition_by=EsgFact.logical_key_hash,
                order_by=[status_rank.desc(), EsgFact.version_number.desc()],
            )
            .label("rn"),
        )
        .where(
            EsgFact.company_id == company_id_resolved,
            EsgFact.logical_key_hash.in_(requested),
        )
        .cte("ranked_compare")
    )

    stmt = (
        select(EsgFact)
        .join(ranked, ranked.c.fact_id == EsgFact.fact_id)
        .where(ranked.c.rn == 1)
    )
    facts = (await session.execute(stmt)).scalars().all()
    by_hash: dict[str, EsgFact] = {f.logical_key_hash: f for f in facts}

    results: list[EsgFactCompareItemDTO] = []
    for h in requested:
        fact = by_hash.get(h)
        latest = EsgFactLatestDTO.model_validate(fact) if fact else None
        results.append(EsgFactCompareItemDTO(logical_key_hash=h, latest=latest))
    return results


def _filter_metrics_by_standard(metrics: list[EsgMetric], *, standard: str | None) -> tuple[list[EsgMetric], str | None]:
    standard_norm: str | None = None
    if isinstance(standard, str) and standard.strip():
        standard_norm = standard.strip().upper()

    if not standard_norm:
        return metrics, None

    filtered: list[EsgMetric] = []
    for m in metrics:
        schema = m.value_schema_json or {}
        if not isinstance(schema, dict):
            continue
        raw = schema.get("standards")
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            s = item.get("standard")
            if isinstance(s, str) and s.strip().upper() == standard_norm:
                filtered.append(m)
                break

    return filtered, standard_norm


@router.get("/gaps", response_model=EsgGapsDTO)
async def get_gaps(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    period_type: EsgPeriodTypeEnum = Query(default=EsgPeriodTypeEnum.YEAR),
    period_start: date = Query(...),
    period_end: date = Query(...),
    is_ytd: bool = Query(default=False),
    entity_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    segment_id: UUID | None = Query(default=None),
    include_inactive_metrics: bool = Query(default=False),
    standard: str | None = Query(default=None, max_length=32, description="Filter metrics by mapping standard (e.g., GRI)"),
    review_overdue_days: int = Query(default=14, ge=1, le=365),
    max_attention_facts: int = Query(default=200, ge=1, le=1000),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> EsgGapsDTO:
    """
    Compute "what's missing" for a given reporting period.

    MVP scope (no new DB entities):
    - Missing published facts per metric for the period
    - Draft/in_review facts that fail publish-time quality gates (sources/evidence/range)
    - Overdue in_review facts (time-based)
    """
    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_start must be <= period_end",
        )

    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    metrics_stmt = select(EsgMetric).where(EsgMetric.company_id == company_id_resolved)
    if not include_inactive_metrics:
        metrics_stmt = metrics_stmt.where(EsgMetric.is_active == True)  # noqa: E712
    metrics_stmt = metrics_stmt.order_by(EsgMetric.name.asc())
    metrics = (await session.execute(metrics_stmt)).scalars().all()

    metrics, standard_norm = _filter_metrics_by_standard(metrics, standard=standard)

    metric_by_id: dict[UUID, EsgMetric] = {m.metric_id: m for m in metrics}
    metric_ids = list(metric_by_id.keys())

    if not metric_ids:
        return EsgGapsDTO(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            is_ytd=is_ytd,
            standard=standard_norm,
            metrics_total=0,
            metrics_with_published=0,
            metrics_missing_published=0,
            missing_metrics=[],
            attention_facts=[],
            issue_counts={},
            in_review_overdue=0,
        )

    base_fact_conditions: list[sa.ColumnElement[bool]] = [
        EsgFact.company_id == company_id_resolved,
        EsgFact.metric_id.in_(metric_ids),
        EsgFact.period_type == period_type.value,
        EsgFact.period_start == period_start,
        EsgFact.period_end == period_end,
        EsgFact.is_ytd == is_ytd,
    ]
    if entity_id is not None:
        base_fact_conditions.append(EsgFact.entity_id == entity_id)
    if location_id is not None:
        base_fact_conditions.append(EsgFact.location_id == location_id)
    if segment_id is not None:
        base_fact_conditions.append(EsgFact.segment_id == segment_id)

    published_metric_stmt = (
        select(EsgFact.metric_id)
        .distinct()
        .where(
            *base_fact_conditions,
            EsgFact.status == EsgFactStatus.PUBLISHED,
        )
    )
    published_metric_ids = set((await session.execute(published_metric_stmt)).scalars().all())

    missing_metric_dtos: list[EsgGapMetricDTO] = []
    for m in metrics:
        if m.metric_id in published_metric_ids:
            continue
        missing_metric_dtos.append(
            EsgGapMetricDTO(
                metric_id=m.metric_id,
                code=m.code,
                name=m.name,
                value_type=m.value_type.value,
                unit=m.unit,
            )
        )

    # Find latest version per logical key for the period, then check draft/in_review quality issues.
    ranked_latest = (
        select(
            EsgFact.fact_id.label("fact_id"),
            func.row_number()
            .over(
                partition_by=EsgFact.logical_key_hash,
                order_by=[EsgFact.version_number.desc()],
            )
            .label("rn"),
        )
        .where(*base_fact_conditions)
        .cte("ranked_gap_latest")
    )

    status_rank = case(
        (EsgFact.status == EsgFactStatus.IN_REVIEW, 2),
        (EsgFact.status == EsgFactStatus.DRAFT, 1),
        else_=0,
    )
    attention_stmt = (
        select(EsgFact, EsgMetric)
        .join(ranked_latest, ranked_latest.c.fact_id == EsgFact.fact_id)
        .join(EsgMetric, EsgMetric.metric_id == EsgFact.metric_id)
        .where(
            ranked_latest.c.rn == 1,
            EsgFact.status.in_([EsgFactStatus.DRAFT, EsgFactStatus.IN_REVIEW]),
        )
        .order_by(status_rank.desc(), EsgFact.updated_at_utc.asc(), EsgMetric.name.asc())
        .limit(max_attention_facts)
    )
    attention_rows = (await session.execute(attention_stmt)).all()
    attention_pairs: list[tuple[EsgFact, EsgMetric]] = [(f, m) for f, m in attention_rows]

    attention_fact_ids = [f.fact_id for f, _m in attention_pairs]
    evidence_counts: dict[UUID, int] = {}
    if attention_fact_ids:
        ev_stmt = (
            select(EsgFactEvidenceItem.fact_id, func.count())
            .where(
                EsgFactEvidenceItem.company_id == company_id_resolved,
                EsgFactEvidenceItem.fact_id.in_(attention_fact_ids),
            )
            .group_by(EsgFactEvidenceItem.fact_id)
        )
        ev_rows = (await session.execute(ev_stmt)).all()
        evidence_counts = {fact_id: int(cnt) for fact_id, cnt in ev_rows}

    cutoff = datetime.now(UTC) - timedelta(days=review_overdue_days)
    issue_counts: dict[str, int] = {}
    in_review_overdue = 0
    attention_fact_dtos: list[EsgGapFactAttentionDTO] = []

    for fact, metric in attention_pairs:
        ev_count = evidence_counts.get(fact.fact_id, 0)
        issues_pairs = await _collect_fact_quality_gate_issues(
            session,
            fact=fact,
            metric=metric,
            evidence_count=ev_count,
        )
        issues = [EsgGapIssueDTO(code=code, message=msg) for code, msg in issues_pairs]

        if fact.status == EsgFactStatus.IN_REVIEW and fact.updated_at_utc < cutoff:
            issues.append(
                EsgGapIssueDTO(
                    code="review_overdue",
                    message=f"In review for more than {review_overdue_days} day(s)",
                )
            )
            in_review_overdue += 1

        if not issues:
            continue

        metric_dto = EsgGapMetricDTO(
            metric_id=metric.metric_id,
            code=metric.code,
            name=metric.name,
            value_type=metric.value_type.value,
            unit=metric.unit,
        )
        attention_fact_dtos.append(
            EsgGapFactAttentionDTO(
                fact_id=fact.fact_id,
                metric=metric_dto,
                logical_key_hash=fact.logical_key_hash,
                status=EsgFactStatusEnum(fact.status.value),
                updated_at_utc=fact.updated_at_utc,
                issues=issues,
            )
        )

        for i in issues:
            issue_counts[i.code] = issue_counts.get(i.code, 0) + 1

    return EsgGapsDTO(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        is_ytd=is_ytd,
        standard=standard_norm,
        metrics_total=len(metrics),
        metrics_with_published=len(published_metric_ids),
        metrics_missing_published=len(missing_metric_dtos),
        missing_metrics=missing_metric_dtos,
        attention_facts=attention_fact_dtos,
        issue_counts=issue_counts,
        in_review_overdue=in_review_overdue,
    )


@router.get("/snapshot", response_model=EsgSnapshotDTO)
async def get_snapshot(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    period_type: EsgPeriodTypeEnum = Query(default=EsgPeriodTypeEnum.YEAR),
    period_start: date = Query(...),
    period_end: date = Query(...),
    is_ytd: bool = Query(default=False),
    standard: str | None = Query(default=None, max_length=32, description="Filter metrics by mapping standard (e.g., GRI)"),
    entity_id: UUID | None = Query(default=None),
    location_id: UUID | None = Query(default=None),
    segment_id: UUID | None = Query(default=None),
    include_inactive_metrics: bool = Query(default=False),
    company_id: UUID | None = Query(default=None, description="Target company_id (superuser only)"),
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> EsgSnapshotDTO:
    """
    Compute a deterministic snapshot of published ESG facts for a period.

    MVP scope (no new DB entities):
    - Filter metrics by standard mapping (optional)
    - Return all published facts for the period + dimension filters
    - Return missing metrics (no published facts for that metric in the filtered set)
    - Return snapshot_hash for downstream "freeze" references
    """
    if period_start > period_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="period_start must be <= period_end",
        )

    company_id_resolved = await _infer_company_id(session, current_user, company_id)
    require_tenant_access(current_user, company_id=company_id_resolved, permission="esg:read")

    metrics_stmt = select(EsgMetric).where(EsgMetric.company_id == company_id_resolved)
    if not include_inactive_metrics:
        metrics_stmt = metrics_stmt.where(EsgMetric.is_active == True)  # noqa: E712
    metrics_stmt = metrics_stmt.order_by(EsgMetric.name.asc())
    metrics = (await session.execute(metrics_stmt)).scalars().all()

    metrics, standard_norm = _filter_metrics_by_standard(metrics, standard=standard)
    metric_ids = [m.metric_id for m in metrics]

    base_fact_conditions: list[sa.ColumnElement[bool]] = [
        EsgFact.company_id == company_id_resolved,
        EsgFact.metric_id.in_(metric_ids) if metric_ids else sa.false(),
        EsgFact.period_type == period_type.value,
        EsgFact.period_start == period_start,
        EsgFact.period_end == period_end,
        EsgFact.is_ytd == is_ytd,
    ]
    if entity_id is not None:
        base_fact_conditions.append(EsgFact.entity_id == entity_id)
    if location_id is not None:
        base_fact_conditions.append(EsgFact.location_id == location_id)
    if segment_id is not None:
        base_fact_conditions.append(EsgFact.segment_id == segment_id)

    facts_stmt = (
        select(EsgFact)
        .where(
            *base_fact_conditions,
            EsgFact.status == EsgFactStatus.PUBLISHED,
        )
        .order_by(EsgFact.logical_key_hash.asc())
    )
    facts = (await session.execute(facts_stmt)).scalars().all()

    published_metric_ids = {f.metric_id for f in facts}
    missing_metric_dtos: list[EsgGapMetricDTO] = []
    for m in metrics:
        if m.metric_id in published_metric_ids:
            continue
        missing_metric_dtos.append(
            EsgGapMetricDTO(
                metric_id=m.metric_id,
                code=m.code,
                name=m.name,
                value_type=m.value_type.value,
                unit=m.unit,
            )
        )

    metric_dto_by_id: dict[UUID, EsgGapMetricDTO] = {
        m.metric_id: EsgGapMetricDTO(
            metric_id=m.metric_id,
            code=m.code,
            name=m.name,
            value_type=m.value_type.value,
            unit=m.unit,
        )
        for m in metrics
    }
    fact_wrappers: list[EsgSnapshotFactDTO] = [
        EsgSnapshotFactDTO(
            fact=EsgFactDTO.model_validate(f),
            metric=metric_dto_by_id[f.metric_id],
        )
        for f in facts
    ]

    canonical = {
        "period_type": period_type.value,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "is_ytd": bool(is_ytd),
        "standard": standard_norm,
        "facts": [
            {
                "logical_key_hash": f.logical_key_hash,
                "fact_id": str(f.fact_id),
                "version_number": int(f.version_number),
            }
            for f in facts
        ],
        "missing_metric_ids": sorted([str(m.metric_id) for m in missing_metric_dtos]),
    }
    canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    snapshot_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    now = datetime.now(UTC)
    return EsgSnapshotDTO(
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        is_ytd=is_ytd,
        standard=standard_norm,
        generated_at_utc=now,
        snapshot_hash=snapshot_hash,
        metrics_total=len(metrics),
        facts_published=len(facts),
        missing_metrics=missing_metric_dtos,
        facts=fact_wrappers,
    )


@router.get("/facts/{fact_id}", response_model=EsgFactDTO)
async def get_fact(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> EsgFactDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:read")
    return EsgFactDTO.model_validate(fact)


@router.patch("/facts/{fact_id}", response_model=EsgFactDTO)
async def update_fact(
    fact_id: UUID,
    data: EsgFactUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:write")

    await _ensure_fact_is_latest(session, fact=fact)

    if fact.status != EsgFactStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft facts can be updated")

    metric = await session.get(EsgMetric, fact.metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    before = {
        "value_json": fact.value_json,
        "dataset_id": str(fact.dataset_id) if fact.dataset_id else None,
        "quality_json": fact.quality_json,
        "sources_json": fact.sources_json,
    }

    next_value_json = fact.value_json if data.value_json is None else data.value_json
    next_dataset_id = fact.dataset_id if data.dataset_id is None else data.dataset_id

    _validate_value_for_metric(metric, value_json=next_value_json, dataset_id=next_dataset_id)
    if next_dataset_id is not None:
        await _ensure_dataset_belongs(session, company_id=fact.company_id, dataset_id=next_dataset_id)

    if data.value_json is not None:
        fact.value_json = data.value_json
    if data.dataset_id is not None:
        fact.dataset_id = data.dataset_id
        # Draft facts must not carry a frozen revision.
        fact.dataset_revision_id = None
    if data.quality_json is not None:
        fact.quality_json = data.quality_json
    if data.sources_json is not None:
        fact.sources_json = data.sources_json

    fact.updated_by = current_user.user_id

    after = {
        "value_json": fact.value_json,
        "dataset_id": str(fact.dataset_id) if fact.dataset_id else None,
        "quality_json": fact.quality_json,
        "sources_json": fact.sources_json,
    }

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_UPDATE,
        entity_type="esg_fact",
        entity_id=fact.fact_id,
        company_id=fact.company_id,
        metadata={
            "logical_key_hash": fact.logical_key_hash,
            "version_number": fact.version_number,
            "before": before,
            "after": after,
        },
    )

    await session.commit()
    await session.refresh(fact)
    return EsgFactDTO.model_validate(fact)


@router.post("/facts/{fact_id}/submit-review", response_model=EsgFactDTO)
async def submit_fact_for_review(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:write")

    await _ensure_fact_is_latest(session, fact=fact)

    if fact.status != EsgFactStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft facts can be submitted for review")

    other_in_review_stmt = select(func.count()).select_from(EsgFact).where(
        EsgFact.company_id == fact.company_id,
        EsgFact.logical_key_hash == fact.logical_key_hash,
        EsgFact.status == EsgFactStatus.IN_REVIEW,
        EsgFact.fact_id != fact.fact_id,
    )
    other_in_review = (await session.execute(other_in_review_stmt)).scalar() or 0
    if other_in_review > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Another fact version is already in review")

    fact.status = EsgFactStatus.IN_REVIEW
    fact.updated_by = current_user.user_id
    fact.updated_at_utc = datetime.now(UTC)

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_SUBMIT_REVIEW,
        entity_type="esg_fact",
        entity_id=fact.fact_id,
        company_id=fact.company_id,
        metadata={
            "logical_key_hash": fact.logical_key_hash,
            "version_number": fact.version_number,
        },
    )

    await session.commit()
    await session.refresh(fact)
    return EsgFactDTO.model_validate(fact)


@router.post("/facts/{fact_id}/request-changes", response_model=EsgFactDTO)
async def request_fact_changes(
    fact_id: UUID,
    data: EsgFactRequestChanges,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:publish")),
) -> EsgFactDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:publish")

    await _ensure_fact_is_latest(session, fact=fact)

    if fact.status != EsgFactStatus.IN_REVIEW:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only in_review facts can be sent back for changes",
        )

    fact.status = EsgFactStatus.DRAFT
    fact.updated_by = current_user.user_id
    fact.updated_at_utc = datetime.now(UTC)

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_REQUEST_CHANGES,
        entity_type="esg_fact",
        entity_id=fact.fact_id,
        company_id=fact.company_id,
        metadata={
            "logical_key_hash": fact.logical_key_hash,
            "version_number": fact.version_number,
            "reason": data.reason,
        },
    )

    await session.commit()
    await session.refresh(fact)
    return EsgFactDTO.model_validate(fact)


@router.post("/facts/{fact_id}/restatement", response_model=EsgFactDTO, status_code=status.HTTP_201_CREATED)
async def restate_fact(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactDTO:
    old = await session.get(EsgFact, fact_id)
    if not old:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=old.company_id, permission="esg:write")

    if old.status not in (EsgFactStatus.PUBLISHED, EsgFactStatus.SUPERSEDED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only published facts can be restated")

    max_stmt = select(func.max(EsgFact.version_number)).where(
        EsgFact.company_id == old.company_id,
        EsgFact.logical_key_hash == old.logical_key_hash,
    )
    max_version = (await session.execute(max_stmt)).scalar() or 0
    version_number = max_version + 1

    fact = EsgFact(
        company_id=old.company_id,
        metric_id=old.metric_id,
        status=EsgFactStatus.DRAFT,
        version_number=version_number,
        supersedes_fact_id=old.fact_id,
        logical_key_hash=old.logical_key_hash,
        period_type=old.period_type,
        period_start=old.period_start,
        period_end=old.period_end,
        is_ytd=old.is_ytd,
        entity_id=old.entity_id,
        location_id=old.location_id,
        segment_id=old.segment_id,
        consolidation_approach=old.consolidation_approach,
        ghg_scope=old.ghg_scope,
        scope2_method=old.scope2_method,
        scope3_category=old.scope3_category,
        tags=old.tags,
        value_json=old.value_json,
        dataset_id=old.dataset_id,
        dataset_revision_id=None,
        quality_json=old.quality_json,
        sources_json=old.sources_json,
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    session.add(fact)
    await session.flush()

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_RESTATEMENT,
        entity_type="esg_fact",
        entity_id=fact.fact_id,
        company_id=old.company_id,
        metadata={
            "logical_key_hash": old.logical_key_hash,
            "from_fact_id": str(old.fact_id),
            "to_fact_id": str(fact.fact_id),
            "version_number": version_number,
        },
    )

    await session.commit()
    await session.refresh(fact)
    return EsgFactDTO.model_validate(fact)


@router.post("/facts/{fact_id}/publish", response_model=EsgFactDTO)
async def publish_fact(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:publish")),
) -> EsgFactDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:publish")

    await _ensure_fact_is_latest(session, fact=fact)

    if fact.status not in (EsgFactStatus.DRAFT, EsgFactStatus.IN_REVIEW):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft or in_review facts can be published",
        )

    metric = await session.get(EsgMetric, fact.metric_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")

    await _validate_fact_quality_gates(session, fact=fact, metric=metric)

    # Ensure no other published fact exists for the logical key.
    await session.execute(
        sa.update(EsgFact)
        .where(
            EsgFact.company_id == fact.company_id,
            EsgFact.logical_key_hash == fact.logical_key_hash,
            EsgFact.status == EsgFactStatus.PUBLISHED,
            EsgFact.fact_id != fact.fact_id,
        )
        .values(
            status=EsgFactStatus.SUPERSEDED,
            updated_by=current_user.user_id,
            updated_at_utc=datetime.now(UTC),
        )
    )
    await session.flush()

    # Freeze dataset at publish time (if any).
    dataset_revision_id: str | None = None
    if fact.dataset_id is not None:
        dataset = await _ensure_dataset_belongs(session, company_id=fact.company_id, dataset_id=fact.dataset_id)
        revision = await _snapshot_dataset_revision(
            session,
            dataset=dataset,
            user_id=current_user.user_id,
            reason=f"ESG fact publish {fact.fact_id}",
        )
        fact.dataset_revision_id = revision.revision_id
        dataset_revision_id = str(revision.revision_id)

    fact.status = EsgFactStatus.PUBLISHED
    fact.published_at_utc = datetime.now(UTC)
    fact.published_by = current_user.user_id
    fact.updated_by = current_user.user_id

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_PUBLISH,
        entity_type="esg_fact",
        entity_id=fact.fact_id,
        company_id=fact.company_id,
        metadata={
            "logical_key_hash": fact.logical_key_hash,
            "version_number": fact.version_number,
            "dataset_id": str(fact.dataset_id) if fact.dataset_id else None,
            "dataset_revision_id": dataset_revision_id,
        },
    )

    await session.commit()
    await session.refresh(fact)
    return EsgFactDTO.model_validate(fact)


# =============================================================================
# Fact Review (Comments + Timeline)
# =============================================================================


@router.get("/facts/{fact_id}/comments", response_model=list[EsgFactReviewCommentDTO])
async def list_fact_review_comments(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> list[EsgFactReviewCommentDTO]:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:read")

    stmt = (
        select(EsgFactReviewComment, User.full_name, User.email)
        .outerjoin(User, User.user_id == EsgFactReviewComment.created_by)
        .where(
            EsgFactReviewComment.company_id == fact.company_id,
            EsgFactReviewComment.logical_key_hash == fact.logical_key_hash,
        )
        .order_by(EsgFactReviewComment.created_at_utc.asc())
    )
    rows = (await session.execute(stmt)).all()

    items: list[EsgFactReviewCommentDTO] = []
    for comment, author_name, author_email in rows:
        dto = EsgFactReviewCommentDTO.model_validate(comment)
        dto.created_by_name = author_name
        dto.created_by_email = author_email
        items.append(dto)
    return items


@router.post("/facts/{fact_id}/comments", response_model=EsgFactReviewCommentDTO, status_code=status.HTTP_201_CREATED)
async def create_fact_review_comment(
    fact_id: UUID,
    data: EsgFactReviewCommentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactReviewCommentDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:write")

    body_md = data.body_md.strip()
    if not body_md:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="body_md is required")

    comment = EsgFactReviewComment(
        company_id=fact.company_id,
        logical_key_hash=fact.logical_key_hash,
        fact_id=fact.fact_id,
        body_md=body_md,
        created_by=current_user.user_id,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    dto = EsgFactReviewCommentDTO.model_validate(comment)
    dto.created_by_name = current_user.full_name
    dto.created_by_email = current_user.email
    return dto


@router.get("/facts/{fact_id}/timeline", response_model=list[EsgFactTimelineEventDTO])
async def list_fact_timeline(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> list[EsgFactTimelineEventDTO]:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:read")

    fact_ids_stmt = select(EsgFact.fact_id).where(
        EsgFact.company_id == fact.company_id,
        EsgFact.logical_key_hash == fact.logical_key_hash,
    )
    fact_ids = [str(x) for x in (await session.execute(fact_ids_stmt)).scalars().all()]
    if not fact_ids:
        return []

    events_stmt = (
        select(AuditEvent)
        .where(
            AuditEvent.company_id == fact.company_id,
            AuditEvent.entity_type == "esg_fact",
            AuditEvent.entity_id.in_(fact_ids),
        )
        .order_by(AuditEvent.timestamp_utc.asc())
    )
    events = (await session.execute(events_stmt)).scalars().all()

    # Enrich with actor details (only for user actors).
    actor_ids: set[UUID] = set()
    actor_id_to_uuid: dict[str, UUID] = {}
    for ev in events:
        if ev.actor_type != "user":
            continue
        with suppress(Exception):
            uid = UUID(ev.actor_id)
            actor_ids.add(uid)
            actor_id_to_uuid[ev.actor_id] = uid

    users_by_id: dict[UUID, User] = {}
    if actor_ids:
        users_stmt = select(User).where(User.user_id.in_(actor_ids))
        users = (await session.execute(users_stmt)).scalars().all()
        users_by_id = {u.user_id: u for u in users}

    out: list[EsgFactTimelineEventDTO] = []
    for ev in events:
        actor_name: str | None = None
        actor_email: str | None = None
        if ev.actor_type == "user":
            uid = actor_id_to_uuid.get(ev.actor_id)
            if uid:
                u = users_by_id.get(uid)
                if u:
                    actor_name = u.full_name
                    actor_email = u.email

        out.append(
            EsgFactTimelineEventDTO(
                event_id=ev.event_id,
                timestamp_utc=ev.timestamp_utc,
                actor_type=ev.actor_type,
                actor_id=ev.actor_id,
                actor_name=actor_name,
                actor_email=actor_email,
                action=ev.action,
                entity_type=ev.entity_type,
                entity_id=ev.entity_id,
                metadata_json=ev.metadata_json,
            )
        )

    return out


# =============================================================================
# Fact Evidence
# =============================================================================


@router.get("/facts/{fact_id}/evidence", response_model=list[EsgFactEvidenceDTO])
async def list_fact_evidence(
    fact_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:read")),
) -> list[EsgFactEvidenceDTO]:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:read")

    stmt = (
        select(EsgFactEvidenceItem)
        .where(EsgFactEvidenceItem.company_id == fact.company_id, EsgFactEvidenceItem.fact_id == fact.fact_id)
        .order_by(EsgFactEvidenceItem.created_at_utc.desc())
    )
    items = (await session.execute(stmt)).scalars().all()
    return [EsgFactEvidenceDTO.model_validate(i) for i in items]


@router.post("/facts/{fact_id}/evidence", response_model=EsgFactEvidenceDTO, status_code=status.HTTP_201_CREATED)
async def create_fact_evidence(
    fact_id: UUID,
    data: EsgFactEvidenceCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactEvidenceDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:write")

    if data.owner_user_id is not None:
        owner_membership_stmt = select(func.count()).select_from(CompanyMembership).where(
            CompanyMembership.company_id == fact.company_id,
            CompanyMembership.user_id == data.owner_user_id,
            CompanyMembership.is_active == True,  # noqa: E712
        )
        owner_ok = (await session.execute(owner_membership_stmt)).scalar() or 0
        if owner_ok <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner must be an active company member")

    if data.type.value == "file":
        asset = await session.get(Asset, data.asset_id)
        if not asset or asset.company_id != fact.company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    source = data.source.strip() if data.source else None

    item = EsgFactEvidenceItem(
        company_id=fact.company_id,
        fact_id=fact.fact_id,
        type=EsgFactEvidenceType(data.type.value),
        title=data.title,
        description=data.description,
        source=source,
        source_date=data.source_date,
        owner_user_id=data.owner_user_id,
        asset_id=data.asset_id,
        url=data.url,
        note_md=data.note_md,
        created_by=current_user.user_id,
    )
    session.add(item)
    await session.flush()

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_EVIDENCE_CREATE,
        entity_type="esg_fact_evidence",
        entity_id=item.evidence_id,
        company_id=fact.company_id,
        metadata={
            "fact_id": str(fact.fact_id),
            "logical_key_hash": fact.logical_key_hash,
            "type": item.type.value,
            "asset_id": str(item.asset_id) if item.asset_id else None,
        },
    )

    await session.commit()
    await session.refresh(item)
    return EsgFactEvidenceDTO.model_validate(item)


@router.patch("/facts/{fact_id}/evidence/{evidence_id}", response_model=EsgFactEvidenceDTO)
async def update_fact_evidence(
    fact_id: UUID,
    evidence_id: UUID,
    data: EsgFactEvidenceUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> EsgFactEvidenceDTO:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:write")

    item = await session.get(EsgFactEvidenceItem, evidence_id)
    if not item or item.company_id != fact.company_id or item.fact_id != fact.fact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found")

    changed_fields: list[str] = []

    if "title" in data.model_fields_set:
        if data.title is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title cannot be null")
        item.title = data.title
        changed_fields.append("title")

    if "description" in data.model_fields_set:
        item.description = data.description.strip() if data.description else None
        changed_fields.append("description")

    if "source" in data.model_fields_set:
        item.source = data.source.strip() if data.source else None
        changed_fields.append("source")

    if "source_date" in data.model_fields_set:
        item.source_date = data.source_date
        changed_fields.append("source_date")

    if "owner_user_id" in data.model_fields_set:
        if data.owner_user_id is not None:
            owner_membership_stmt = select(func.count()).select_from(CompanyMembership).where(
                CompanyMembership.company_id == fact.company_id,
                CompanyMembership.user_id == data.owner_user_id,
                CompanyMembership.is_active == True,  # noqa: E712
            )
            owner_ok = (await session.execute(owner_membership_stmt)).scalar() or 0
            if owner_ok <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Owner must be an active company member",
                )
        item.owner_user_id = data.owner_user_id
        changed_fields.append("owner_user_id")

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_EVIDENCE_UPDATE,
        entity_type="esg_fact_evidence",
        entity_id=item.evidence_id,
        company_id=fact.company_id,
        metadata={
            "fact_id": str(fact.fact_id),
            "logical_key_hash": fact.logical_key_hash,
            "changed_fields": changed_fields,
        },
    )

    await session.commit()
    await session.refresh(item)
    return EsgFactEvidenceDTO.model_validate(item)


@router.delete("/facts/{fact_id}/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact_evidence(
    fact_id: UUID,
    evidence_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: CurrentUser,
    _: None = Depends(RBACChecker.require_permission("esg:write")),
) -> None:
    fact = await session.get(EsgFact, fact_id)
    if not fact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")

    require_tenant_access(current_user, company_id=fact.company_id, permission="esg:write")

    item = await session.get(EsgFactEvidenceItem, evidence_id)
    if not item or item.company_id != fact.company_id or item.fact_id != fact.fact_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence item not found")

    await session.delete(item)

    audit_logger = AuditLogger(session)
    await audit_logger.log_action(
        actor=current_user,
        action=AuditAction.ESG_FACT_EVIDENCE_DELETE,
        entity_type="esg_fact_evidence",
        entity_id=item.evidence_id,
        company_id=fact.company_id,
        metadata={
            "fact_id": str(fact.fact_id),
            "logical_key_hash": fact.logical_key_hash,
            "type": item.type.value,
        },
    )

    await session.commit()
