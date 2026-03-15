"""
Enum types for domain models.

Based on SYSTEM_REGISTRY.md Section E (Workflow States).
"""

from enum import Enum


class Locale(str, Enum):
    """Supported locales (Section F.1)."""

    RU = "ru"
    EN = "en"
    KK = "kk"
    DE = "de"
    FR = "fr"
    AR = "ar"
    ES = "es"
    NL = "nl"
    IT = "it"


class ContentStatus(str, Enum):
    """
    Per-locale content status (Section E.1).

    Transitions:
    - draft -> ready
    - ready -> qa_required
    - qa_required -> approved
    - approved -> draft (rollback)
    """

    DRAFT = "draft"
    READY = "ready"
    QA_REQUIRED = "qa_required"
    APPROVED = "approved"


class BlockType(str, Enum):
    """Block types from Content Model."""

    TEXT = "text"
    KPI_CARDS = "kpi_cards"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    QUOTE = "quote"
    DOWNLOADS = "downloads"
    ACCORDION = "accordion"
    TIMELINE = "timeline"
    VIDEO = "video"
    CUSTOM = "custom"


class BlockVariant(str, Enum):
    """Block display variants."""

    DEFAULT = "default"
    COMPACT = "compact"
    EMPHASIZED = "emphasized"
    FULL_WIDTH = "full_width"


class AssetKind(str, Enum):
    """Asset types."""

    IMAGE = "image"
    FONT = "font"
    ATTACHMENT = "attachment"
    VIDEO = "video"
    CAPTIONS = "captions"


class BuildType(str, Enum):
    """Build types for releases."""

    DRAFT = "draft"
    RELEASE = "release"


class BuildStatus(str, Enum):
    """Build job status."""

    QUEUED = "queued"
    RUNNING = "running"
    FAILED = "failed"
    SUCCESS = "success"


class TranslationStatus(str, Enum):
    """Translation unit status."""

    PENDING = "pending"
    TRANSLATED = "translated"
    IMPORTED = "imported"
    QA_REQUIRED = "qa_required"
    APPROVED = "approved"
    FAILED = "failed"


class JobStatus(str, Enum):
    """Background job status."""

    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    SUCCESS = "success"
    CANCELLED = "cancelled"


class GlossaryStrictness(str, Enum):
    """Glossary term strictness level."""

    DO_NOT_TRANSLATE = "do_not_translate"
    STRICT = "strict"
    PREFERRED = "preferred"


class RenderMode(str, Enum):
    """
    Render mode for HTML generation.

    Controls how HTML is rendered (CSS classes, JS inclusion hints).
    """

    PREVIEW = "preview"   # In-app preview with full interactivity
    STATIC = "static"     # Static export HTML
    PRINT = "print"       # Print-optimized HTML (Phase 2 placeholder)


class RenderTarget(str, Enum):
    """
    Target format for rendering (Phase 2 readiness).

    Defines the output format contract for the renderer.
    """

    STATIC_HTML = "static_html"   # Browser-viewable HTML
    PRINT_HTML = "print_html"     # Print-optimized HTML (placeholder)
    DOCX = "docx"                 # Word document (placeholder)


class PackageMode(str, Enum):
    """
    Export package mode.

    Controls what is included in the export ZIP.
    """

    PORTABLE = "portable"       # No JS, no search, works via file://
    INTERACTIVE = "interactive"  # With JS, search, requires http server


class BuildScope(str, Enum):
    """
    Build scope for partial exports.

    Defines what portion of the report to export.
    """

    FULL = "full"         # Entire report
    SECTION = "section"   # Single section
    BLOCK = "block"       # Single block (debug/preview)


# ============================================================================
# Multi-tenant & RBAC Enums (Phase: Company/Roles/Locks/Evidence/Audit)
# ============================================================================


class CompanyStatus(str, Enum):
    """Company tenant status."""

    ACTIVE = "active"
    DISABLED = "disabled"


class StructureStatus(str, Enum):
    """Report structure freeze status."""

    DRAFT = "draft"    # Structure can be modified
    FROZEN = "frozen"  # Structure locked, only content edits allowed


class ScopeType(str, Enum):
    """Scope type for role assignments."""

    COMPANY = "company"
    REPORT = "report"
    SECTION = "section"


class LockScopeType(str, Enum):
    """Scope type for content locks."""

    REPORT = "report"
    SECTION = "section"
    BLOCK = "block"


class LockLayer(str, Enum):
    """
    Lock layer for two-tier content locking.

    Audit lock is stronger than coord lock.
    """

    COORD = "coord"   # Coordinator/internal lock
    AUDIT = "audit"   # Auditor lock (stronger)


class ThreadStatus(str, Enum):
    """Comment thread status."""

    OPEN = "open"
    RESOLVED = "resolved"


class OpenAIKeyStatus(str, Enum):
    """Per-company OpenAI API key status."""

    ACTIVE = "active"
    INVALID = "invalid"
    DISABLED = "disabled"


class AIFeature(str, Enum):
    """AI feature identifier for usage tracking."""

    INCIDENT_HELP = "incident_help"
    TRANSLATION = "translation"


class AssignableRole(str, Enum):
    """
    Roles that can be assigned via RoleAssignment.

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
    CORPORATE_LEAD = "corporate_lead"    # Company management, releases, audit override

    # Content roles
    EDITOR = "editor"                    # Editor in Chief — full CRUD + freeze + approve + drafts
    CONTENT_EDITOR = "content_editor"    # Editor — scoped editing
    SECTION_EDITOR = "section_editor"    # SME
    VIEWER = "viewer"                    # Read-only

    # Translation role
    TRANSLATOR = "translator"            # Translation workflow: edit, lock, submit translations

    # Audit roles
    INTERNAL_AUDITOR = "internal_auditor"  # Internal audit (read-only)
    AUDITOR = "auditor"                    # External auditor
    AUDIT_LEAD = "audit_lead"              # Lead external auditor


class EvidenceType(str, Enum):
    """Evidence item type."""

    FILE = "file"
    LINK = "link"
    NOTE = "note"


class EvidenceStatus(str, Enum):
    """Evidence workflow status."""

    PROVIDED = "provided"
    REVIEWED = "reviewed"
    ISSUE = "issue"
    RESOLVED = "resolved"


class EvidenceVisibility(str, Enum):
    """
    Evidence visibility level.

    - team: visible to company team (editor/reviewer/etc)
    - audit: visible to auditors in scope
    - restricted: limited access (future)
    """

    TEAM = "team"
    AUDIT = "audit"
    RESTRICTED = "restricted"


class EvidenceSource(str, Enum):
    """Evidence source type."""

    INTERNAL = "internal"
    EXTERNAL = "external"


class AuditCheckStatus(str, Enum):
    """Audit check status."""

    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"
    FLAGGED = "flagged"
    NEEDS_INFO = "needs_info"


class AuditCheckSeverity(str, Enum):
    """Severity of audit findings."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class AuditCheckTargetType(str, Enum):
    """Target type for audit checks."""

    REPORT = "report"
    SECTION = "section"
    BLOCK = "block"
    EVIDENCE_ITEM = "evidence_item"


class AuditBasis(str, Enum):
    """
    Basis for audit summary in release.

    - snapshot: based on specific source snapshot
    - live: based on live content at release time
    """

    SNAPSHOT = "snapshot"
    LIVE = "live"


# ============================================================================
# Export v2: Artifact Enums
# ============================================================================


class ArtifactFormat(str, Enum):
    """
    Export artifact format.

    - zip: Static HTML bundle (always generated)
    - print_html: Linear print-ready HTML (intermediate for pdf/docx)
    - pdf: PDF document via Playwright
    - docx: Word document via python-docx
    """

    ZIP = "zip"
    PRINT_HTML = "print_html"
    PDF = "pdf"
    DOCX = "docx"


class ArtifactStatus(str, Enum):
    """
    Export artifact generation status.

    Transitions:
    - queued -> processing
    - processing -> done | failed
    - failed -> queued (retry)
    """

    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactErrorCode(str, Enum):
    """
    Structured error codes for export artifacts.

    Categories:
    - TIMEOUT_* — Task exceeded time limits
    - RENDERER_* — PDF/DOCX generation errors
    - BUILD_* — Build/ZIP-related errors
    - VALIDATION_* — Input validation errors
    """

    # No error
    NONE = "none"

    # Timeout errors (transient, can retry)
    TIMEOUT_OVERALL = "timeout_overall"  # Task exceeded total time limit
    TIMEOUT_PLAYWRIGHT = "timeout_playwright"  # Playwright PDF generation timeout
    TIMEOUT_DOWNLOAD = "timeout_download"  # Asset download timeout

    # Renderer errors
    RENDERER_PLAYWRIGHT_CRASH = "renderer_playwright_crash"  # Playwright process crashed
    RENDERER_DOCX_TEMPLATE = "renderer_docx_template"  # DOCX template error
    RENDERER_HTML_INVALID = "renderer_html_invalid"  # Invalid HTML for rendering

    # Build errors
    BUILD_NOT_FOUND = "build_not_found"  # ReleaseBuild not found
    BUILD_ZIP_NOT_FOUND = "build_zip_not_found"  # Build ZIP file not found on disk
    BUILD_ZIP_CORRUPT = "build_zip_corrupt"  # ZIP file is corrupt

    # Validation errors (don't retry)
    VALIDATION_LOCALE = "validation_locale"  # Invalid locale
    VALIDATION_PROFILE = "validation_profile"  # Invalid PDF profile

    # Unknown/generic error
    UNKNOWN = "unknown"
