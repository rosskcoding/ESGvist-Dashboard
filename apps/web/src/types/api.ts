/**
 * API Types for ESGvist Platform
 *
 * Matches backend Pydantic schemas from app/domain/schemas
 */

// === Enums ===

export type Locale = 'ru' | 'en' | 'kk' | 'de' | 'fr' | 'ar' | 'es' | 'nl' | 'it'

export type ContentStatus = 'draft' | 'ready' | 'qa_required' | 'approved'

export type BlockType =
  | 'text'
  | 'kpi_cards'
  | 'table'
  | 'chart'
  | 'image'
  | 'video'
  | 'quote'
  | 'downloads'
  | 'accordion'
  | 'timeline'
  | 'custom'

export type BlockVariant = 'default' | 'compact' | 'emphasized' | 'full_width'

// === Content Locks ===

export type LockScopeType = 'report' | 'section' | 'block'
export type LockLayer = 'coord' | 'audit'

export interface ContentLock {
  lock_id: string
  company_id: string
  scope_type: LockScopeType
  scope_id: string
  lock_layer: LockLayer
  reason: string
  is_locked: boolean
  locked_by: string
  locked_at_utc: string
  released_by?: string | null
  released_at_utc?: string | null
}

export interface ContentLockCreate {
  scope_type: LockScopeType
  scope_id: string
  lock_layer: LockLayer
  reason: string
}

export interface ContentLockRelease {
  reason?: string | null
}

// === RBAC Enums ===

export type CompanyStatus = 'active' | 'disabled'

export type RoleType =
  // Company level
  | 'corporate_lead'        // Company management, releases, audit override
  // Content roles
  | 'editor'                // Editor in Chief — full CRUD + freeze + approve
  | 'content_editor'        // Editor — scoped editing
  | 'section_editor'        // SME
  | 'viewer'                // Read-only
  // Translation role
  | 'translator'            // Translator — translation/localization workflow
  // Audit roles
  | 'internal_auditor'      // Internal audit (read-only)
  | 'auditor'               // External auditor
  | 'audit_lead'            // Lead external auditor

export type ScopeType = 'company' | 'report' | 'section'

// === User ===

export interface User {
  user_id: string
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
  companies?: UserCompanyDTO[]
  created_at_utc: string
  updated_at_utc: string
}

export interface UserCompanyDTO {
  company_id: string
  company_name: string
  is_corporate_lead: boolean
  is_active: boolean
  roles: string[]
}

export interface UserCreate {
  email: string
  full_name: string
  password: string
  is_superuser?: boolean
}

export interface UserUpdate {
  email?: string
  full_name?: string
  password?: string
  is_active?: boolean
  is_superuser?: boolean
}

// === Company ===

export interface Company {
  company_id: string
  name: string
  slug: string
  status: CompanyStatus
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface CompanyCreate {
  name: string
  status?: CompanyStatus
}

export interface CompanyUpdate {
  name?: string
  status?: CompanyStatus
}

// === Company Membership ===

export interface CompanyMembership {
  membership_id: string
  company_id: string
  user_id: string
  is_active: boolean
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
  // Embedded user info from MembershipWithUserDTO
  user_email?: string
  user_name?: string
  is_corporate_lead?: boolean
}

export interface CompanyMembershipCreate {
  user_id: string
  is_active?: boolean
}

export interface CompanyMembershipUpdate {
  is_active?: boolean
  full_name?: string
}

// === Role Assignment ===

export interface RoleAssignment {
  assignment_id: string
  company_id: string
  user_id: string
  role: RoleType
  scope_type: ScopeType
  scope_id: string | null
  locales: string[] | null
  created_by: string | null
  created_at_utc: string
  // Embedded user info from RoleAssignmentWithUserDTO
  user_email?: string
  user_name?: string
}

export interface RoleAssignmentCreate {
  user_id: string
  role: RoleType
  scope_type: ScopeType
  scope_id?: string | null
  locales?: string[] | null
}

export interface RoleAssignmentUpdate {
  role?: RoleType
  scope_type?: ScopeType
  scope_id?: string | null
  locales?: string[] | null
}

// === Auth ===

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

// === Report ===

export interface Report {
  report_id: string
  company_id: string
  year: number
  title: string
  slug: string
  source_locale: Locale
  default_locale: Locale
  enabled_locales: string[]
  release_locales: string[]
  theme_slug: string
  created_at_utc: string
  updated_at_utc: string
  sections_count?: number
  blocks_count?: number
}

export interface ReportCreate {
  year: number
  title: string
  slug?: string
  source_locale?: Locale
  default_locale?: Locale
  enabled_locales?: string[]
  release_locales?: string[]
  theme_slug?: string
}

export interface ReportUpdate {
  title?: string
  slug?: string
  source_locale?: Locale
  default_locale?: Locale
  enabled_locales?: string[]
  release_locales?: string[]
  theme_slug?: string
}

// === Section ===

export interface SectionI18n {
  locale: Locale
  title: string
  slug: string
  summary?: string | null
}

export interface Section {
  section_id: string
  report_id: string
  order_index: number
  parent_section_id?: string | null
  // Structure fields for TOC
  depth: number
  label_prefix?: string | null
  label_suffix?: string | null
  created_at_utc: string
  updated_at_utc: string
  i18n: SectionI18n[]
  blocks_count?: number
}

export interface SectionI18nCreate {
  locale: Locale
  title: string
  slug: string
  summary?: string | null
}

export interface SectionCreate {
  report_id: string
  order_index?: number
  parent_section_id?: string | null
  // Structure fields
  depth?: number
  label_prefix?: string | null
  label_suffix?: string | null
  i18n: SectionI18nCreate[]
}

export interface SectionUpdate {
  order_index?: number
  parent_section_id?: string | null
  // Structure fields
  depth?: number
  label_prefix?: string | null
  label_suffix?: string | null
}

export interface SectionI18nUpdate {
  title?: string
  slug?: string
  summary?: string | null
}

// Bulk reorder
export interface SectionReorderItem {
  section_id: string
  order_index: number
  parent_section_id: string | null
  depth: number
}

export interface BulkReorderRequest {
  report_id: string
  items: SectionReorderItem[]
}

// === Block ===

export interface BlockI18n {
  locale: Locale
  status: ContentStatus
  qa_flags_by_locale: string[]
  fields_json: Record<string, unknown>
  custom_html_sanitized?: string | null
  custom_css_validated?: string | null
  last_approved_at_utc?: string | null
}

export interface Block {
  block_id: string
  report_id: string
  section_id: string
  type: BlockType
  variant: BlockVariant
  order_index: number
  data_json: Record<string, unknown>
  qa_flags_global: string[]
  custom_override_enabled: boolean
  version: number
  owner_user_id?: string | null
  created_at_utc: string
  updated_at_utc: string
  i18n: BlockI18n[]
}

export interface BlockI18nCreate {
  locale: Locale
  status?: ContentStatus
  qa_flags_by_locale?: string[]
  fields_json?: Record<string, unknown>
  custom_html_sanitized?: string | null
  custom_css_validated?: string | null
}

export interface BlockCreate {
  report_id: string
  section_id: string
  type: BlockType
  variant?: BlockVariant
  order_index?: number
  data_json?: Record<string, unknown>
  qa_flags_global?: string[]
  custom_override_enabled?: boolean
  i18n?: BlockI18nCreate[]
}

export interface BlockUpdate {
  variant?: BlockVariant
  order_index?: number
  data_json?: Record<string, unknown>
  qa_flags_global?: string[]
  custom_override_enabled?: boolean
  expected_version?: number
}

export interface BlockI18nUpdate {
  status?: ContentStatus
  qa_flags_by_locale?: string[]
  fields_json?: Record<string, unknown>
  custom_html_sanitized?: string | null
  custom_css_validated?: string | null
}

// === Pagination ===

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean
  has_prev: boolean
}

// === Block Type Specific Schemas ===

// Text block
export interface TextBlockData {
  anchor_id?: string
}

export interface TextBlockI18n {
  body_html: string
}

// KPI block
export interface KpiCard {
  id: string
  metric_key: string
  format: 'number' | 'percent' | 'currency' | 'custom'
  decimals?: number
  unit_position?: 'before' | 'after'
  delta_mode?: 'absolute' | 'percent' | 'none'
}

export interface KpiCardsData {
  cards: KpiCard[]
  columns?: 2 | 3 | 4
}

export interface KpiCardI18n {
  id: string
  label: string
  value: string
  unit?: string
  delta?: string
  delta_label?: string
  footnote?: string
}

export interface KpiCardsI18n {
  cards: KpiCardI18n[]
}

// Table block
export interface TableColumn {
  id: string
  width?: string
  align?: 'left' | 'center' | 'right'
  type?: 'text' | 'number' | 'percent' | 'currency'
}

export interface TableBuilderData {
  mode: 'rows_only' | 'columns_only' | 'full_matrix' | 'key_value'
  columns?: TableColumn[]
  row_count?: number
  has_header_row?: boolean
  has_total_row?: boolean
}

export interface TableRow {
  id: string
  cells: Record<string, string>
}

export interface TableBuilderI18n {
  caption?: string
  header?: Record<string, string>
  rows: TableRow[]
  footer?: Record<string, string>
}

// Image block
export interface ImageBlockData {
  asset_id: string
  aspect_ratio?: '16:9' | '4:3' | '1:1' | 'original'
  layout?: 'full' | 'left' | 'right' | 'center'
}

export interface ImageBlockI18n {
  alt_text: string
  caption?: string
  credit?: string
}

// Quote block
export interface QuoteBlockData {
  style: 'blockquote' | 'pullquote' | 'testimonial'
}

export interface QuoteBlockI18n {
  quote_html: string
  attribution?: string
  attribution_title?: string
}

// Chart block
export interface ChartDataset {
  id: string
  type: 'bar' | 'line' | 'pie' | 'doughnut' | 'area'
  color?: string
  stack_group?: string
}

export interface ChartBlockData {
  chart_type: 'bar' | 'line' | 'pie' | 'doughnut' | 'area' | 'stacked_bar'
  datasets: ChartDataset[]
  x_axis_key?: string
  show_legend?: boolean
  show_grid?: boolean
}

export interface ChartDataPoint {
  label: string
  values: Record<string, number | string>
}

export interface ChartBlockI18n {
  title?: string
  subtitle?: string
  x_axis_label?: string
  y_axis_label?: string
  data: ChartDataPoint[]
  legend_labels?: Record<string, string>
  footnote?: string
}

// === Theme ===

export interface Theme {
  theme_id: string
  slug: string
  name: string
  description?: string | null
  tokens_json: Record<string, string>
  is_default: boolean
  is_active: boolean
  created_at_utc: string
  updated_at_utc: string
}

export interface ThemeListItem {
  theme_id: string
  slug: string
  name: string
  is_default: boolean
  is_active: boolean
}

export interface ThemeCreate {
  slug: string
  name: string
  description?: string | null
  tokens_json?: Record<string, string>
  is_default?: boolean
  is_active?: boolean
}

export interface ThemeUpdate {
  name?: string
  description?: string | null
  tokens_json?: Record<string, string>
  is_default?: boolean
  is_active?: boolean
}

// ============================================================
// Template Types
// ============================================================

export type TemplateScope = 'block' | 'section' | 'report'

export interface Template {
  template_id: string
  scope: TemplateScope
  block_type: BlockType | null
  name: string
  description: string | null
  tags: string[]
  template_json: Record<string, unknown>
  is_system: boolean
  is_active: boolean
  created_at_utc: string
  updated_at_utc: string
}

export interface TemplateListItem {
  template_id: string
  scope: string
  block_type: string | null
  name: string
  description: string | null
  tags: string[]
  is_system: boolean
}

export interface TemplateCreate {
  scope: TemplateScope
  block_type?: string | null
  name: string
  description?: string | null
  tags?: string[]
  template_json: Record<string, unknown>
  is_system?: boolean
}

export interface TemplateUpdate {
  name?: string
  description?: string | null
  tags?: string[]
  template_json?: Record<string, unknown>
  is_active?: boolean
}

export interface ApplyTemplateRequest {
  template_id: string
  section_id: string
  report_id: string
  order_index?: number
  overrides?: Record<string, unknown>
}

// ============================================================
// Asset Types
// ============================================================

export type AssetKind = 'image' | 'font' | 'attachment' | 'video'

export interface Asset {
  asset_id: string
  kind: AssetKind
  filename: string
  storage_path: string
  mime_type: string
  size_bytes: number
  sha256: string
  created_at_utc: string
  url: string
}

export interface AssetUploadResponse {
  asset: Asset
  message: string
}

export interface AssetLinkCreate {
  block_id: string
  purpose?: string
}

export interface AssetLink {
  block_id: string
  asset_id: string
  purpose: string
}

export interface SignedUrlRequest {
  ttl_seconds?: number
}

export interface SignedUrlResponse {
  url: string
  expires_at: number
  ttl_seconds: number
}

// ============================================================
// Evidence / Audit / Audit Pack / Content Versions
// ============================================================

export type EvidenceScopeType = 'report' | 'section' | 'block'
export type EvidenceType = 'file' | 'link' | 'note'
export type EvidenceVisibility = 'team' | 'audit' | 'restricted'
export type EvidenceSource = 'internal' | 'external'
export type EvidenceStatus = 'provided' | 'reviewed' | 'issue' | 'resolved'
export type EvidenceSubAnchorType = 'table' | 'chart' | 'datapoint' | 'audit_check_item'

export interface EvidenceItem {
  evidence_id: string
  company_id: string
  report_id: string
  scope_type: EvidenceScopeType
  scope_id: string
  status: EvidenceStatus
  sub_anchor_type: EvidenceSubAnchorType | null
  sub_anchor_key: string | null
  sub_anchor_label: string | null
  owner_user_id: string | null
  period_start: string | null
  period_end: string | null
  version_label: string | null
  deleted_at: string | null
  deleted_by: string | null
  locale: Locale | null
  type: EvidenceType
  title: string
  description: string | null
  tags: string[] | null
  source: EvidenceSource | null
  visibility: EvidenceVisibility
  asset_id: string | null
  url: string | null
  note_md: string | null
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

// ============================================================
// ESG Dashboard
// ============================================================

export type EsgMetricValueType = 'number' | 'integer' | 'boolean' | 'string' | 'dataset'

export interface EsgEntity {
  entity_id: string
  company_id: string
  code: string | null
  name: string
  description: string | null
  is_active: boolean
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgLocation {
  location_id: string
  company_id: string
  code: string | null
  name: string
  description: string | null
  is_active: boolean
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgSegment {
  segment_id: string
  company_id: string
  code: string | null
  name: string
  description: string | null
  is_active: boolean
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgMetric {
  metric_id: string
  company_id: string
  code: string | null
  name: string
  description: string | null
  value_type: EsgMetricValueType
  unit: string | null
  value_schema_json: Record<string, unknown>
  is_active: boolean
  created_by: string | null
  updated_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgMetricOwner {
  metric_id: string
  owner_user_id: string | null
  owner_user_name: string | null
  owner_user_email: string | null
  updated_at_utc: string | null
}

export interface EsgMetricOwnerUpsert {
  owner_user_id: string | null
}

export interface EsgMetricCreate {
  code?: string | null
  name: string
  description?: string | null
  value_type: EsgMetricValueType
  unit?: string | null
  value_schema_json?: Record<string, unknown>
  is_active?: boolean
}

export interface EsgMetricUpdate {
  code?: string | null
  name?: string
  description?: string | null
  value_type?: EsgMetricValueType
  unit?: string | null
  value_schema_json?: Record<string, unknown>
  is_active?: boolean
}

export type EsgFactStatus = 'draft' | 'in_review' | 'published' | 'superseded'

export type EsgPeriodType = 'day' | 'month' | 'quarter' | 'year' | 'custom'

export interface EsgFact {
  fact_id: string
  company_id: string
  metric_id: string
  status: EsgFactStatus
  version_number: number
  supersedes_fact_id: string | null
  logical_key_hash: string
  evidence_count?: number | null

  period_type: EsgPeriodType
  period_start: string
  period_end: string
  is_ytd: boolean

  entity_id: string | null
  location_id: string | null
  segment_id: string | null
  consolidation_approach: string | null
  ghg_scope: string | null
  scope2_method: string | null
  scope3_category: string | null
  tags: string[] | null

  value_json: unknown | null
  dataset_id: string | null
  dataset_revision_id: string | null

  quality_json: Record<string, unknown>
  sources_json: Record<string, unknown>

  published_at_utc: string | null
  published_by: string | null
  created_by: string | null
  updated_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgFactCreate {
  metric_id: string
  period_type: EsgPeriodType
  period_start: string
  period_end: string
  is_ytd?: boolean

  entity_id?: string | null
  location_id?: string | null
  segment_id?: string | null
  consolidation_approach?: string | null
  ghg_scope?: string | null
  scope2_method?: string | null
  scope3_category?: string | null
  tags?: string[] | null

  value_json?: unknown | null
  dataset_id?: string | null

  quality_json?: Record<string, unknown>
  sources_json?: Record<string, unknown>
}

export interface EsgFactUpdate {
  value_json?: unknown | null
  dataset_id?: string | null
  quality_json?: Record<string, unknown>
  sources_json?: Record<string, unknown>
}

export interface EsgFactRequestChanges {
  reason: string
}

export interface EsgFactReviewCommentCreate {
  body_md: string
}

export interface EsgFactReviewComment {
  comment_id: string
  company_id: string
  logical_key_hash: string
  fact_id: string
  body_md: string
  created_by: string | null
  created_by_name: string | null
  created_by_email: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgFactTimelineEvent {
  event_id: string
  timestamp_utc: string
  actor_type: string
  actor_id: string
  actor_name: string | null
  actor_email: string | null
  action: string
  entity_type: string
  entity_id: string
  metadata_json: Record<string, unknown> | null
}

export interface EsgGapMetric {
  metric_id: string
  code: string | null
  name: string
  value_type: EsgMetricValueType
  unit: string | null
}

export interface EsgGapIssue {
  code: string
  message: string
}

export interface EsgGapFactAttention {
  fact_id: string
  metric: EsgGapMetric
  logical_key_hash: string
  status: EsgFactStatus
  updated_at_utc: string
  issues: EsgGapIssue[]
}

export interface EsgGaps {
  period_type: EsgPeriodType
  period_start: string
  period_end: string
  is_ytd: boolean
  standard?: string | null
  metrics_total: number
  metrics_with_published: number
  metrics_missing_published: number
  missing_metrics: EsgGapMetric[]
  attention_facts: EsgGapFactAttention[]
  issue_counts: Record<string, number>
  in_review_overdue: number
}

export interface EsgSnapshot {
  period_type: EsgPeriodType
  period_start: string
  period_end: string
  is_ytd: boolean
  standard?: string | null
  generated_at_utc: string
  snapshot_hash: string
  metrics_total: number
  facts_published: number
  missing_metrics: EsgGapMetric[]
  facts: EsgSnapshotFact[]
}

export interface EsgSnapshotFact {
  fact: EsgFact
  metric: EsgGapMetric
}

export type EsgFactImportRowAction = 'create' | 'skip' | 'error'

export interface EsgFactImportRowError {
  row_number: number
  message: string
  metric_code: string | null
  logical_key_hash: string | null
}

export interface EsgFactImportRowPreview {
  row_number: number
  action: EsgFactImportRowAction
  message: string | null
  metric_code: string | null
  logical_key_hash: string | null
}

export interface EsgFactImportPreview {
  total_rows: number
  create_rows: number
  skip_rows: number
  error_rows: number
  rows: EsgFactImportRowPreview[]
  errors: EsgFactImportRowError[]
}

export interface EsgFactImportConfirm {
  total_rows: number
  created: number
  skipped: number
  error_rows: number
  errors: EsgFactImportRowError[]
}

export type EsgFactEvidenceType = 'file' | 'link' | 'note'

export interface EsgFactEvidenceItem {
  evidence_id: string
  company_id: string
  fact_id: string
  type: EsgFactEvidenceType
  title: string
  description: string | null
  source: string | null
  source_date: string | null
  owner_user_id: string | null
  asset_id: string | null
  url: string | null
  note_md: string | null
  created_by: string | null
  created_at_utc: string
  updated_at_utc: string
}

export interface EsgFactEvidenceCreate {
  type: EsgFactEvidenceType
  title: string
  description?: string | null
  source?: string | null
  source_date?: string | null
  owner_user_id?: string | null
  asset_id?: string | null
  url?: string | null
  note_md?: string | null
}

export interface EsgFactEvidenceUpdate {
  title?: string
  description?: string | null
  source?: string | null
  source_date?: string | null
  owner_user_id?: string | null
}

export interface EsgFactLatest {
  fact_id: string
  metric_id: string
  logical_key_hash: string
  version_number: number
  status: EsgFactStatus
  dataset_id: string | null
  dataset_revision_id: string | null
  updated_at_utc: string
  published_at_utc: string | null
}

export interface EsgFactCompareItem {
  logical_key_hash: string
  latest: EsgFactLatest | null
}

export interface EsgFactCompareRequest {
  logical_key_hashes: string[]
}

export interface AuditCheckSummary {
  total_checks: number
  by_status: Record<string, number>
  by_severity: Record<string, number>
  coverage_percent: number
  has_critical_issues: boolean
  has_major_issues: boolean
}

// === Comment Types ===

// Comment anchor types (where comment can be attached)
export type CommentAnchorType = 'report' | 'section' | 'block'

// Comment thread status
export type CommentThreadStatus = 'open' | 'resolved'

// Comment thread base
export interface CommentThread {
  thread_id: string
  company_id: string
  report_id: string
  anchor_type: CommentAnchorType
  anchor_id: string
  sub_anchor_type: string | null
  sub_anchor_key: string | null
  sub_anchor_label: string | null
  status: CommentThreadStatus
  created_at: string
  created_by: string | null
  resolved_at: string | null
  resolved_by: string | null
  comment_count: number
  open_comment_count: number
}

// Comment thread with nested comments
export interface CommentThreadWithComments extends CommentThread {
  comments: Comment[]
}

// Comment thread create request
export interface CommentThreadCreate {
  anchor_type: CommentAnchorType
  anchor_id: string
  sub_anchor_type?: string | null
  sub_anchor_key?: string | null
  sub_anchor_label?: string | null
  first_comment_body: string
  is_internal?: boolean
}

// Individual comment
export interface Comment {
  comment_id: string
  thread_id: string
  company_id: string
  author_user_id: string | null
  author_role_snapshot: string | null
  body: string
  is_internal: boolean
  created_at: string
  deleted_at: string | null
  deleted_by: string | null
  is_deleted: boolean
  author_name: string | null
  author_email: string | null
}

// Comment create request
export interface CommentCreate {
  body: string
  is_internal?: boolean
}

// === Audit Check Types ===

// Audit Check target types
export type AuditCheckTargetType = 'report' | 'section' | 'block' | 'evidence_item'

// Audit Check statuses
export type AuditCheckStatus = 'not_started' | 'in_review' | 'reviewed' | 'flagged' | 'needs_info'

// Audit Check severity levels
export type AuditCheckSeverity = 'critical' | 'major' | 'minor' | 'info'

// Audit Check DTO (response from backend)
export interface AuditCheckDTO {
  check_id: string
  company_id: string
  report_id: string
  source_snapshot_id: string | null
  auditor_id: string
  target_type: AuditCheckTargetType
  target_id: string
  status: AuditCheckStatus
  severity: AuditCheckSeverity | null
  comment: string | null
  reviewed_at_utc: string | null
  created_at_utc: string
  updated_at_utc: string
}

// Create audit check request
export interface AuditCheckCreate {
  report_id: string
  source_snapshot_id?: string | null
  target_type: AuditCheckTargetType
  target_id: string
  status?: AuditCheckStatus
  severity?: AuditCheckSeverity | null
  comment?: string | null
}

// Update audit check request
export interface AuditCheckUpdate {
  status?: AuditCheckStatus
  severity?: AuditCheckSeverity | null
  comment?: string | null
}

// Filter params for listing audit checks
export interface AuditCheckListParams {
  report_id?: string
  target_type?: AuditCheckTargetType
  target_id?: string
  check_status?: AuditCheckStatus
  auditor_id?: string
}

export type AuditPackFormat =
  | 'report_pdf'
  | 'report_docx'
  | 'evidences_csv'
  | 'comments_csv'
  | 'evidence_summary_pdf'
  | 'audit_pack_zip'

export type AuditPackJobStatus = 'queued' | 'running' | 'success' | 'partial_success' | 'failed' | 'cancelled'

export interface AuditPackRequest {
  formats?: AuditPackFormat[]
  locales?: string[]
  include_internal_comments?: boolean
  evidence_statuses?: string[] | null
  pdf_profile?: 'audit' | 'screen'
}

export interface AuditPackArtifact {
  artifact_id: string
  job_id: string
  format: AuditPackFormat
  locale: string | null
  filename: string
  path: string | null
  size_bytes: number | null
  sha256: string | null
  created_at_utc: string
  attachments_excluded: boolean
  warning_message: string | null
}

export interface AuditPackJob {
  job_id: string
  report_id: string
  company_id: string
  status: AuditPackJobStatus
  formats: AuditPackFormat[]
  locales: string[]
  include_internal_comments: boolean
  evidence_statuses: string[] | null
  pdf_profile: string
  created_at_utc: string
  created_by: string | null
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  artifacts: AuditPackArtifact[]
}

export interface ContentVersion {
  version_id: string
  company_id: string
  report_id: string
  block_id: string
  locale: string
  saved_at: string
  saved_by: string | null
  fields_json_snapshot: Record<string, unknown>
  saver_name: string | null
  saver_email: string | null
}

export interface ContentVersionList {
  block_id: string
  locale: string
  versions: ContentVersion[]
  total_count: number
}
