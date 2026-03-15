"""
Enum schemas for API validation.

Mirrors domain/models/enums.py for Pydantic validation.
"""

from enum import Enum


class LocaleEnum(str, Enum):
    """Supported locales."""

    RU = "ru"
    EN = "en"
    KK = "kk"
    DE = "de"
    FR = "fr"
    AR = "ar"
    ES = "es"
    NL = "nl"
    IT = "it"


class ContentStatusEnum(str, Enum):
    """Content workflow status."""

    DRAFT = "draft"
    READY = "ready"
    QA_REQUIRED = "qa_required"
    APPROVED = "approved"


class BlockTypeEnum(str, Enum):
    """Block types."""

    TEXT = "text"
    KPI_CARDS = "kpi_cards"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    QUOTE = "quote"
    DOWNLOADS = "downloads"
    ACCORDION = "accordion"
    TIMELINE = "timeline"
    CUSTOM = "custom"


class BlockVariantEnum(str, Enum):
    """Block variants."""

    DEFAULT = "default"
    COMPACT = "compact"
    EMPHASIZED = "emphasized"
    FULL_WIDTH = "full_width"


class BuildTypeEnum(str, Enum):
    """Build types."""

    DRAFT = "draft"
    RELEASE = "release"


class BuildStatusEnum(str, Enum):
    """Build status."""

    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    SUCCESS = "success"


class AssetKindEnum(str, Enum):
    """Asset kinds."""

    IMAGE = "image"
    FONT = "font"
    ATTACHMENT = "attachment"
    VIDEO = "video"
    CAPTIONS = "captions"


# =============================================================================
# Multi-tenant RBAC Enums
# =============================================================================


class CompanyStatusEnum(str, Enum):
    """Company status."""

    ACTIVE = "active"
    DISABLED = "disabled"


class StructureStatusEnum(str, Enum):
    """Report structure freeze status."""

    DRAFT = "draft"
    FROZEN = "frozen"


class ScopeTypeEnum(str, Enum):
    """Scope type for role assignments."""

    COMPANY = "company"
    REPORT = "report"
    SECTION = "section"


class LockScopeTypeEnum(str, Enum):
    """Scope type for content locks."""

    REPORT = "report"
    SECTION = "section"
    BLOCK = "block"


class LockLayerEnum(str, Enum):
    """Lock layer type."""

    COORD = "coord"
    AUDIT = "audit"


class AssignableRoleEnum(str, Enum):
    """
    Roles assignable via RoleAssignment.

    All roles are scoped (company/report/section level).

    Company level:
    - CORPORATE_LEAD: company management, releases, audit override

    Content hierarchy:
    - EDITOR (Editor in Chief): full CRUD + freeze + approve + draft exports
    - CONTENT_EDITOR (Editor): edits where assigned (scoped)
    - SECTION_EDITOR (SME): subject matter expert for sections
    - VIEWER: read-only access

    Translation:
    - TRANSLATOR: translation/localization workflow (edit, lock, submit)

    Audit roles:
    - INTERNAL_AUDITOR: internal audit (read-only)
    - AUDITOR: external auditor
    - AUDIT_LEAD: lead external auditor (can finalize, manage locks)
    """

    # Company management
    CORPORATE_LEAD = "corporate_lead"      # Company management, releases, audit override

    # Content roles
    EDITOR = "editor"                      # Editor in Chief — full CRUD + freeze + approve + drafts
    CONTENT_EDITOR = "content_editor"      # Editor — scoped editing
    SECTION_EDITOR = "section_editor"      # SME
    VIEWER = "viewer"                      # Read-only

    # Translation role
    TRANSLATOR = "translator"              # Translation workflow: edit, lock, submit translations

    # Audit roles
    INTERNAL_AUDITOR = "internal_auditor"  # Internal audit (read-only)
    AUDITOR = "auditor"                    # External auditor
    AUDIT_LEAD = "audit_lead"              # Lead external auditor


class EvidenceTypeEnum(str, Enum):
    """Evidence item type."""

    FILE = "file"
    LINK = "link"
    NOTE = "note"


class EvidenceVisibilityEnum(str, Enum):
    """Evidence visibility level."""

    TEAM = "team"
    AUDIT = "audit"
    RESTRICTED = "restricted"


class EvidenceSourceEnum(str, Enum):
    """Evidence source type."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class AuditCheckStatusEnum(str, Enum):
    """Audit check status."""

    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    FLAGGED = "flagged"
    NEEDS_INFO = "needs_info"


class AuditCheckSeverityEnum(str, Enum):
    """Audit check severity."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class AuditCheckTargetTypeEnum(str, Enum):
    """Audit check target type."""

    REPORT = "report"
    SECTION = "section"
    BLOCK = "block"
    EVIDENCE_ITEM = "evidence_item"


class AuditBasisEnum(str, Enum):
    """Audit summary basis."""

    SNAPSHOT = "snapshot"
    LIVE = "live"
