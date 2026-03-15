"""
Pydantic Schemas — DTOs and Validation

All schemas follow SYSTEM_REGISTRY.md specifications.

Multi-tenant RBAC schemas added:
- Company, CompanyMembership DTOs
- RoleAssignment DTOs
- ContentLock DTOs
- EvidenceItem DTOs
- AuditCheck DTOs
"""

from .asset import (
    AssetDTO,
    AssetLinkCreate,
    AssetLinkDTO,
    AssetUploadResponse,
    SignedUrlRequest,
    SignedUrlResponse,
)
from .audit_check import (
    AuditCheckCreate,
    AuditCheckDTO,
    AuditCheckFilter,
    AuditCheckUpdate,
    AuditCheckWithAuditorDTO,
    AuditFinalizeRequest,
    AuditSummaryDTO,
    SectionAuditStatusDTO,
)
from .audit_pack import (
    AuditPackArtifactDTO,
    AuditPackJobDTO,
    AuditPackRequest,
)
from .auth import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
)
from .block import (
    BlockBase,
    BlockCreate,
    BlockDTO,
    BlockI18nCreate,
    BlockI18nDTO,
    BlockI18nUpdate,
    BlockReorderRequest,
    BlockUpdate,
)
from .common import (
    BaseSchema,
    PaginatedResponse,
    PaginationParams,
    TimestampSchema,
)
from .company import (
    CompanyCreate,
    CompanyDTO,
    CompanyListDTO,
    CompanyUpdate,
    MembershipDTO,
    MembershipInvite,
    MembershipUpdate,
    MembershipWithUserDTO,
    UserCompanyDTO,
)
from .content_lock import (
    ContentLockCreate,
    ContentLockDTO,
    ContentLockOverride,
    ContentLockRelease,
    ContentLockWithUserDTO,
    HierarchicalLockInfo,
    LockCheckResult,
    LockStatusDTO,
)
from .content_version import (
    ContentVersionDTO,
    ContentVersionListDTO,
)
from .design import (
    BlockTypePresets,
    LayoutSettings,
    PresetInfo,
    PresetsResponse,
    ReportDesignSettings,
    ReportDesignUpdate,
    TypographySettings,
)
from .enums import (
    # Legacy enums
    AssetKindEnum,
    BlockTypeEnum,
    BlockVariantEnum,
    ContentStatusEnum,
    LocaleEnum,
    # Multi-tenant RBAC enums
    AssignableRoleEnum,
    AuditBasisEnum,
    AuditCheckSeverityEnum,
    AuditCheckStatusEnum,
    AuditCheckTargetTypeEnum,
    CompanyStatusEnum,
    EvidenceSourceEnum,
    EvidenceTypeEnum,
    EvidenceVisibilityEnum,
    LockLayerEnum,
    LockScopeTypeEnum,
    ScopeTypeEnum,
    StructureStatusEnum,
)
from .evidence import (
    EvidenceFileCreate,
    EvidenceFilter,
    EvidenceItemCreate,
    EvidenceItemDTO,
    EvidenceItemUpdate,
    EvidenceItemWithAssetDTO,
    EvidenceLinkCreate,
    EvidenceNoteCreate,
    EvidenceSummaryDTO,
)
from .esg import (
    EsgEntityCreate,
    EsgEntityDTO,
    EsgEntityUpdate,
    EsgFactCompareItemDTO,
    EsgFactCompareRequest,
    EsgFactCreate,
    EsgFactDTO,
    EsgFactEvidenceCreate,
    EsgFactEvidenceDTO,
    EsgFactEvidenceTypeEnum,
    EsgFactEvidenceUpdate,
    EsgFactLatestDTO,
    EsgFactRequestChanges,
    EsgFactStatusEnum,
    EsgFactUpdate,
    EsgLocationCreate,
    EsgLocationDTO,
    EsgLocationUpdate,
    EsgMetricCreate,
    EsgMetricDTO,
    EsgMetricOwnerDTO,
    EsgMetricOwnerUpsert,
    EsgMetricUpdate,
    EsgMetricValueTypeEnum,
    EsgPeriodTypeEnum,
    EsgSegmentCreate,
    EsgSegmentDTO,
    EsgSegmentUpdate,
)
from .esg_import import (
    EsgFactImportConfirmDTO,
    EsgFactImportPreviewDTO,
    EsgFactImportRowErrorDTO,
    EsgFactImportRowPreviewDTO,
)
from .esg_gaps import (
    EsgGapFactAttentionDTO,
    EsgGapIssueDTO,
    EsgGapMetricDTO,
    EsgGapsDTO,
)
from .esg_snapshot import (
    EsgSnapshotFactDTO,
    EsgSnapshotDTO,
)
from .esg_review import (
    EsgFactReviewCommentCreate,
    EsgFactReviewCommentDTO,
    EsgFactTimelineEventDTO,
)
from .report import (
    ReportBase,
    ReportCreate,
    ReportDTO,
    ReportUpdate,
)
from .role_assignment import (
    RoleAssignmentBulkCreate,
    RoleAssignmentBulkDelete,
    RoleAssignmentCreate,
    RoleAssignmentDTO,
    RoleAssignmentFilter,
    RoleAssignmentUpdate,
    RoleAssignmentWithUserDTO,
)
from .section import (
    BulkReorderRequest,
    SectionBase,
    SectionCreate,
    SectionDTO,
    SectionI18nCreate,
    SectionI18nDTO,
    SectionI18nUpdate,
    SectionReorderItem,
    SectionUpdate,
)
from .template import (
    ApplyTemplateRequest,
    TemplateCreate,
    TemplateDTO,
    TemplateListItem,
    TemplateUpdate,
)
from .artifact import (
    ArtifactCreate,
    ArtifactDTO,
    ArtifactListResponse,
)
from .checkpoint import (
    BlockAutosaveRequest,
    CheckpointCreate,
    CheckpointDTO,
    CheckpointMetadata,
    CheckpointRestoreRequest,
    CheckpointRestoreResponse,
)
from .comment import (
    CommentCreate,
    CommentDTO,
    CommentDeleteRequest,
    CommentThreadCreate,
    CommentThreadDTO,
    CommentThreadFilter,
    CommentThreadReopenRequest,
    CommentThreadResolveRequest,
    CommentThreadSummaryDTO,
    CommentThreadWithCommentsDTO,
)
from .theme import (
    ThemeCSSResponse,
    ThemeCreate,
    ThemeDTO,
    ThemeListDTO,
    ThemeUpdate,
)
from .user import (
    UserBase,
    UserCreate,
    UserDTO,
    UserInDB,
    UserUpdate,
)

__all__ = [
    # Common
    "BaseSchema",
    "TimestampSchema",
    "PaginationParams",
    "PaginatedResponse",
    # Legacy Enums
    "LocaleEnum",
    "ContentStatusEnum",
    "BlockTypeEnum",
    "BlockVariantEnum",
    "AssetKindEnum",
    # Multi-tenant RBAC Enums
    "CompanyStatusEnum",
    "StructureStatusEnum",
    "ScopeTypeEnum",
    "LockScopeTypeEnum",
    "LockLayerEnum",
    "AssignableRoleEnum",
    "EvidenceTypeEnum",
    "EvidenceVisibilityEnum",
    "EvidenceSourceEnum",
    "AuditCheckStatusEnum",
    "AuditCheckSeverityEnum",
    "AuditCheckTargetTypeEnum",
    "AuditBasisEnum",
    # Company
    "CompanyCreate",
    "CompanyUpdate",
    "CompanyDTO",
    "CompanyListDTO",
    "MembershipInvite",
    "MembershipUpdate",
    "MembershipDTO",
    "MembershipWithUserDTO",
    "UserCompanyDTO",
    # RoleAssignment
    "RoleAssignmentCreate",
    "RoleAssignmentUpdate",
    "RoleAssignmentDTO",
    "RoleAssignmentWithUserDTO",
    "RoleAssignmentFilter",
    "RoleAssignmentBulkCreate",
    "RoleAssignmentBulkDelete",
    # ContentLock
    "ContentLockCreate",
    "ContentLockRelease",
    "ContentLockOverride",
    "ContentLockDTO",
    "ContentLockWithUserDTO",
    "LockStatusDTO",
    "LockCheckResult",
    "HierarchicalLockInfo",
    # ContentVersion
    "ContentVersionDTO",
    "ContentVersionListDTO",
    # Evidence
    "EvidenceFileCreate",
    "EvidenceLinkCreate",
    "EvidenceNoteCreate",
    "EvidenceItemCreate",
    "EvidenceItemUpdate",
    "EvidenceItemDTO",
    "EvidenceItemWithAssetDTO",
    "EvidenceFilter",
    "EvidenceSummaryDTO",
    # ESG Dashboard
    "EsgMetricValueTypeEnum",
    "EsgFactStatusEnum",
    "EsgPeriodTypeEnum",
    "EsgFactEvidenceTypeEnum",
    "EsgEntityCreate",
    "EsgEntityUpdate",
    "EsgEntityDTO",
    "EsgLocationCreate",
    "EsgLocationUpdate",
    "EsgLocationDTO",
    "EsgSegmentCreate",
    "EsgSegmentUpdate",
    "EsgSegmentDTO",
    "EsgMetricCreate",
    "EsgMetricUpdate",
    "EsgMetricDTO",
    "EsgFactCreate",
    "EsgFactUpdate",
    "EsgFactRequestChanges",
    "EsgFactDTO",
    "EsgFactEvidenceCreate",
    "EsgFactEvidenceDTO",
    "EsgFactEvidenceUpdate",
    "EsgFactCompareRequest",
    "EsgFactLatestDTO",
    "EsgFactCompareItemDTO",
    "EsgFactImportPreviewDTO",
    "EsgFactImportConfirmDTO",
    "EsgFactImportRowPreviewDTO",
    "EsgFactImportRowErrorDTO",
    "EsgFactReviewCommentCreate",
    "EsgFactReviewCommentDTO",
    "EsgFactTimelineEventDTO",
    # AuditCheck
    "AuditCheckCreate",
    "AuditCheckUpdate",
    "AuditCheckDTO",
    "AuditCheckWithAuditorDTO",
    "AuditCheckFilter",
    "AuditSummaryDTO",
    "AuditFinalizeRequest",
    "SectionAuditStatusDTO",
    # AuditPack
    "AuditPackRequest",
    "AuditPackJobDTO",
    "AuditPackArtifactDTO",
    # Comments
    "CommentThreadCreate",
    "CommentThreadDTO",
    "CommentThreadWithCommentsDTO",
    "CommentThreadFilter",
    "CommentThreadSummaryDTO",
    "CommentThreadResolveRequest",
    "CommentThreadReopenRequest",
    "CommentCreate",
    "CommentDTO",
    "CommentDeleteRequest",
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserDTO",
    "UserInDB",
    # Report
    "ReportBase",
    "ReportCreate",
    "ReportUpdate",
    "ReportDTO",
    # Section
    "SectionBase",
    "SectionCreate",
    "SectionUpdate",
    "SectionDTO",
    "SectionI18nCreate",
    "SectionI18nUpdate",
    "SectionI18nDTO",
    "SectionReorderItem",
    "BulkReorderRequest",
    # Block
    "BlockBase",
    "BlockCreate",
    "BlockUpdate",
    "BlockDTO",
    "BlockI18nCreate",
    "BlockI18nUpdate",
    "BlockI18nDTO",
    "BlockReorderRequest",
    # Asset
    "AssetDTO",
    "AssetUploadResponse",
    "AssetLinkDTO",
    "AssetLinkCreate",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    # Theme
    "ThemeCreate",
    "ThemeUpdate",
    "ThemeDTO",
    "ThemeListDTO",
    "ThemeCSSResponse",
    # Template
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateDTO",
    "TemplateListItem",
    "ApplyTemplateRequest",
    # Design
    "LayoutSettings",
    "TypographySettings",
    "ReportDesignSettings",
    "ReportDesignUpdate",
    "PresetInfo",
    "BlockTypePresets",
    "PresetsResponse",
    # Artifact (Export v2)
    "ArtifactCreate",
    "ArtifactDTO",
    "ArtifactListResponse",
    # Checkpoint / Autosave
    "BlockAutosaveRequest",
    "CheckpointCreate",
    "CheckpointDTO",
    "CheckpointMetadata",
    "CheckpointRestoreRequest",
    "CheckpointRestoreResponse",
]
