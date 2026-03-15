"""
Domain Models — SQLAlchemy ORM

ESGvist Dashboard models:
- User, RefreshToken (auth)
- Company, CompanyMembership (multi-tenant)
- RoleAssignment (scoped roles / RBAC)
- EsgEntity, EsgLocation, EsgSegment (dimensions)
- EsgMetric, EsgMetricAssignment (metrics)
- EsgFact, EsgFactEvidenceItem, EsgFactReviewComment (facts)
- EvidenceItem, AuditCheck (audit support)
- AuditEvent (audit trail)
"""

from .audit import AuditEvent
from .audit_check import AuditCheck
from .base import Base, TimestampMixin
from .company import Company, CompanyMembership
from .esg_dimensions import EsgEntity, EsgLocation, EsgSegment
from .esg_fact import EsgFact, EsgFactStatus
from .esg_fact_evidence import EsgFactEvidenceItem, EsgFactEvidenceType
from .esg_fact_review_comment import EsgFactReviewComment
from .esg_metric import EsgMetric, EsgMetricValueType
from .esg_metric_assignment import EsgMetricAssignment
from .enums import (
    # Multi-tenant RBAC enums
    AssignableRole,
    AuditBasis,
    AuditCheckSeverity,
    AuditCheckStatus,
    AuditCheckTargetType,
    CompanyStatus,
    ContentStatus,
    EvidenceSource,
    EvidenceStatus,
    EvidenceType,
    EvidenceVisibility,
    ScopeType,
)
from .evidence import EvidenceItem
from .refresh_token import RefreshToken
from .role_assignment import RoleAssignment
from .user import User

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Enums
    "CompanyStatus",
    "ContentStatus",
    "ScopeType",
    "AssignableRole",
    "EvidenceType",
    "EvidenceStatus",
    "EvidenceVisibility",
    "EvidenceSource",
    "AuditCheckStatus",
    "AuditCheckSeverity",
    "AuditCheckTargetType",
    "AuditBasis",
    # Models - Auth
    "User",
    "RefreshToken",
    # Models - Multi-tenant
    "Company",
    "CompanyMembership",
    "RoleAssignment",
    "EvidenceItem",
    "AuditCheck",
    "AuditEvent",
    # Models - ESG
    "EsgEntity",
    "EsgLocation",
    "EsgSegment",
    "EsgMetric",
    "EsgMetricValueType",
    "EsgMetricAssignment",
    "EsgFact",
    "EsgFactStatus",
    "EsgFactEvidenceItem",
    "EsgFactEvidenceType",
    "EsgFactReviewComment",
]
