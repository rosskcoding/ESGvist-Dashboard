"""
Domain Models — SQLAlchemy ORM

All models follow SYSTEM_REGISTRY.md specifications.

Multi-tenant RBAC models added:
- Company, CompanyMembership (tenant layer)
- RoleAssignment (scoped roles)
- ContentLock (two-layer locks)
- EvidenceItem (audit evidence)
- AuditCheck (audit checklist)
"""

from .asset import Asset, AssetLink
from .ai_usage import AIUsageEvent
from .audit import AuditEvent
from .audit_check import AuditCheck
from .audit_pack import AuditPackArtifact, AuditPackJob
from .base import Base, TimestampMixin
from .block import Block, BlockI18n
from .checkpoint import ReportCheckpoint
from .comment import Comment, CommentThread
from .company import Company, CompanyMembership
from .platform_ai_settings import PlatformAISettings
from .dataset import Dataset, DatasetRevision
from .content_version import ContentVersion
from .content_lock import ContentLock
from .esg_dimensions import EsgEntity, EsgLocation, EsgSegment
from .esg_fact import EsgFact, EsgFactStatus
from .esg_fact_evidence import EsgFactEvidenceItem, EsgFactEvidenceType
from .esg_fact_review_comment import EsgFactReviewComment
from .esg_metric import EsgMetric, EsgMetricValueType
from .esg_metric_assignment import EsgMetricAssignment
from .enums import (
    # Legacy enums
    AssetKind,
    BlockType,
    BlockVariant,
    BuildScope,
    BuildStatus,
    BuildType,
    ContentStatus,
    GlossaryStrictness,
    JobStatus,
    Locale,
    PackageMode,
    RenderMode,
    RenderTarget,
    TranslationStatus,
    # Multi-tenant RBAC enums
    AssignableRole,
    AuditBasis,
    AuditCheckSeverity,
    AuditCheckStatus,
    AuditCheckTargetType,
    CompanyStatus,
    EvidenceSource,
    EvidenceStatus,
    EvidenceType,
    EvidenceVisibility,
    LockLayer,
    LockScopeType,
    OpenAIKeyStatus,
    AIFeature,
    ScopeType,
    StructureStatus,
    ThreadStatus,
    # Export v2 enums
    ArtifactFormat,
    ArtifactStatus,
)
from .artifact import ReleaseBuildArtifact
from .evidence import EvidenceItem
from .refresh_token import RefreshToken
from .release import ReleaseBuild, SourceSnapshot
from .report import Report
from .role_assignment import RoleAssignment
from .section import Section, SectionI18n
from .template import Template, TEMPLATE_SCOPE_BLOCK, TEMPLATE_SCOPE_SECTION, TEMPLATE_SCOPE_REPORT
from .theme import (
    CORPORATE_BLUE_TOKENS,
    DARK_THEME_TOKENS,
    DEFAULT_THEME_TOKENS,
    Theme,
)
from .translation import GlossaryTerm, TranslationJob, TranslationUnit
from .user import User

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    # Legacy Enums
    "Locale",
    "ContentStatus",
    "BlockType",
    "BlockVariant",
    "AssetKind",
    "BuildType",
    "BuildStatus",
    "BuildScope",
    "TranslationStatus",
    "JobStatus",
    "GlossaryStrictness",
    "RenderMode",
    "RenderTarget",
    "PackageMode",
    # Multi-tenant RBAC Enums
    "CompanyStatus",
    "StructureStatus",
    "ThreadStatus",
    "ScopeType",
    "LockScopeType",
    "LockLayer",
    "AssignableRole",
    "EvidenceType",
    "EvidenceStatus",
    "EvidenceVisibility",
    "EvidenceSource",
    "OpenAIKeyStatus",
    "AIFeature",
    "AuditCheckStatus",
    "AuditCheckSeverity",
    "AuditCheckTargetType",
    "AuditBasis",
    # Export v2 Enums
    "ArtifactFormat",
    "ArtifactStatus",
    # Models - Multi-tenant
    "Company",
    "CompanyMembership",
    "RoleAssignment",
    "ContentLock",
    "ContentVersion",
    "EvidenceItem",
    "AuditCheck",
    "AuditPackJob",
    "AuditPackArtifact",
    "CommentThread",
    "Comment",
    "Dataset",
    "DatasetRevision",
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
    "ReportCheckpoint",
    "AIUsageEvent",
    "PlatformAISettings",
    # Models - Core
    "User",
    "RefreshToken",
    "Report",
    "Section",
    "SectionI18n",
    "Block",
    "BlockI18n",
    "Asset",
    "AssetLink",
    "SourceSnapshot",
    "ReleaseBuild",
    "ReleaseBuildArtifact",
    "GlossaryTerm",
    "TranslationJob",
    "TranslationUnit",
    "AuditEvent",
    "Theme",
    "DEFAULT_THEME_TOKENS",
    "DARK_THEME_TOKENS",
    "CORPORATE_BLUE_TOKENS",
    "Template",
    "TEMPLATE_SCOPE_BLOCK",
    "TEMPLATE_SCOPE_SECTION",
    "TEMPLATE_SCOPE_REPORT",
]
