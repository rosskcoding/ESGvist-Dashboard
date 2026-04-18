"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowUpDown,
  Download,
  Eye,
  ExternalLink,
  Filter,
  FileText,
  LayoutGrid,
  Link2,
  Loader2,
  Plus,
  Repeat2,
  Rows3,
  Search,
  ShieldAlert,
  TriangleAlert,
} from "lucide-react";

import { api, type AppApiError } from "@/lib/api";
import { triggerFileDownload } from "@/lib/download";
import { cn } from "@/lib/utils";
import { useActiveProject } from "@/lib/hooks/use-active-project";
import { useApiQuery } from "@/lib/hooks/use-api";
import { GuidedEntryDialog } from "./components/guided-entry-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

type DataPointStatus = "missing" | "partial" | "complete";
type BoundaryStatus = "included" | "excluded" | "partial";
type FeedSection = "action" | "blocked" | "ready" | "submitted";
type ViewMode = "feed" | "table";

interface AuthMe {
  id: number;
  full_name: string;
  email: string;
  roles: Array<{ role: string }>;
}

interface DataPoint {
  id: number;
  data_point_id?: number | null;
  assignment_id?: number | null;
  shared_element_id?: number | null;
  entity_id?: number | null;
  facility_id?: number | null;
  element_code: string;
  element_name: string;
  collection_status: DataPointStatus;
  entity_name: string;
  facility_name: string | null;
  boundary_status: BoundaryStatus;
  consolidation_method: string;
  collector_id?: number | null;
  collector_name?: string | null;
  reviewer_id?: number | null;
  reviewer_name?: string | null;
  reused_across_standards: boolean;
  standards: string[];
  status?: string | null;
  numeric_value?: number | null;
  text_value?: string | null;
  unit_code?: string | null;
  methodology?: string | null;
  evidence_required?: boolean;
  evidence_count?: number;
  element_type?: "numeric" | "text" | "boolean" | null;
  deadline?: string | null;
  days_overdue?: number;
  days_until_deadline?: number | null;
}

interface DataPointsResponse {
  items: DataPoint[];
  total: number;
}

interface MethodologyReference {
  id: number;
  code: string;
  name: string;
  description?: string | null;
}

const DATA_POINT_PAGE_SIZE = 100;

interface AssignmentRow {
  id: number;
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  entity_id: number | null;
  entity_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  boundary_included: boolean;
  consolidation_method: string;
  collector_id?: number | null;
  collector_name?: string | null;
  reviewer_id?: number | null;
  reviewer_name?: string | null;
  deadline?: string | null;
  days_overdue?: number;
  days_until_deadline?: number | null;
  status: string;
}

interface AssignmentMatrixResponse {
  assignments: AssignmentRow[];
}

interface FormConfigField {
  shared_element_id: number;
  requirement_item_id?: number;
  assignment_id?: number | null;
  entity_id?: number | null;
  facility_id?: number | null;
  visible: boolean;
  required: boolean;
  help_text?: string | null;
  tooltip?: string | null;
  order: number;
}

interface FormConfigStep {
  id: string;
  title: string;
  fields: FormConfigField[];
}

interface FormConfigHealthIssue {
  code: string;
  message: string;
  affected_fields: number;
}

interface FormConfigHealth {
  status: string;
  is_stale: boolean;
  target_project_id?: number | null;
  field_count: number;
  assignment_scoped_fields: number;
  context_scoped_fields: number;
  issue_count: number;
  issues: FormConfigHealthIssue[];
  latest_assignment_updated_at?: string | null;
  latest_boundary_updated_at?: string | null;
}

interface ActiveFormConfig {
  id: number;
  project_id: number | null;
  name: string;
  description: string | null;
  is_active: boolean;
  updated_at?: string | null;
  resolved_for_project_id?: number | null;
  resolution_scope?: string | null;
  health?: FormConfigHealth | null;
  config: {
    steps: FormConfigStep[];
  };
}

interface GuidedFieldDescriptor {
  stepId: string;
  stepTitle: string;
  field: FormConfigField;
}

interface GuidedFieldCard {
  descriptor: GuidedFieldDescriptor;
  matches: DataPoint[];
  primaryRow: DataPoint | null;
}

interface DataPointDetail {
  id: number;
  status: string;
  element_type: "numeric" | "text" | "boolean";
  numeric_value?: number | null;
  text_value?: string | null;
  unit_code?: string | null;
  methodology?: string | null;
  boundary_status: string;
  consolidation_method: string;
  related_standards: Array<{ code: string; name: string }>;
  evidence_required: boolean;
  evidence_count: number;
  methodology_options?: string[];
}

interface EvidenceItem {
  id: number;
  type: "file" | "link";
  title: string;
  description?: string | null;
  url?: string | null;
  file_name?: string | null;
  file_size?: number | null;
  mime_type?: string | null;
  upload_date?: string | null;
  created_by?: number | null;
  created_by_name?: string | null;
  binding_status?: "bound" | "unbound";
  linked_data_points?: Array<{ data_point_id: number; code: string; label: string }>;
  linked_requirement_items?: Array<{
    requirement_item_id: number;
    code: string;
    description: string;
  }>;
}

interface EvidencePreviewTarget {
  item: EvidenceItem;
  row: DataPoint;
}

interface DisplayFramework {
  code: string;
  name: string;
  tone: "framework" | "custom";
}

const BOUNDARY_CONFIG: Record<
  BoundaryStatus,
  { label: string; variant: "success" | "secondary" | "warning" }
> = {
  included: { label: "Included", variant: "success" },
  excluded: { label: "Excluded", variant: "secondary" },
  partial: { label: "Partially included", variant: "warning" },
};

const FEED_SECTION_CONFIG: Record<
  FeedSection,
  { label: string; dotClassName: string; emptyState: string }
> = {
  action: {
    label: "Needs action",
    dotClassName: "bg-red-500",
    emptyState: "No open collection tasks match the current filters.",
  },
  blocked: {
    label: "Blocked",
    dotClassName: "bg-amber-500",
    emptyState: "No blocked contexts match the current filters.",
  },
  ready: {
    label: "Ready",
    dotClassName: "bg-green-500",
    emptyState: "No rows are currently ready to submit.",
  },
  submitted: {
    label: "Submitted",
    dotClassName: "bg-slate-300",
    emptyState: "No submitted or approved rows match the current filters.",
  },
};

const FEED_SECTION_ORDER: FeedSection[] = ["action", "blocked", "ready", "submitted"];
const ONLY_MINE_STORAGE_KEY = "collection-v5-only-mine";

function buildContextKey(
  sharedElementId?: number | null,
  entityId?: number | null,
  facilityId?: number | null
) {
  return [sharedElementId ?? 0, entityId ?? 0, facilityId ?? 0].join(":");
}

function parseOptionalPositiveInt(value: string | null) {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function sanitizeInternalReturnTo(value: string | null) {
  if (!value) return null;
  return value.startsWith("/") ? value : null;
}

async function fetchAllProjectDataPoints(projectId: number): Promise<DataPointsResponse> {
  const items: DataPoint[] = [];
  let page = 1;
  let total = 0;

  while (true) {
    const response = await api.get<DataPointsResponse>(
      `/projects/${projectId}/data-points?page=${page}&page_size=${DATA_POINT_PAGE_SIZE}`
    );
    items.push(...response.items);
    total = response.total;

    if (response.items.length === 0 || items.length >= total) {
      break;
    }

    page += 1;
  }

  return { items, total };
}

function buildRowKey(row: Pick<DataPoint, "shared_element_id" | "entity_id" | "facility_id">) {
  return buildContextKey(row.shared_element_id ?? 0, row.entity_id ?? 0, row.facility_id ?? 0);
}

function formatMetricValue(value: number) {
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
  }).format(value);
}

function getResolvedDataPointId(row: DataPoint) {
  if (row.data_point_id != null) return row.data_point_id;
  if (row.assignment_id == null && row.id > 0) return row.id;
  return null;
}

function getValuePreview(row: DataPoint, detail?: DataPointDetail | null) {
  if (detail?.element_type === "numeric") {
    if (detail.numeric_value == null) return "No value yet";
    return [formatMetricValue(detail.numeric_value), detail.unit_code].filter(Boolean).join(" ");
  }

  if (detail) {
    const detailValue = detail.text_value?.trim();
    return detailValue
      ? [detailValue, detail.unit_code].filter(Boolean).join(" ")
      : "No value yet";
  }

  if (row.numeric_value != null) {
    return [formatMetricValue(row.numeric_value), row.unit_code].filter(Boolean).join(" ");
  }

  const textValue = row.text_value?.trim();
  if (textValue) {
    return [textValue, row.unit_code].filter(Boolean).join(" ");
  }

  return "No value yet";
}

function getDataPointScore(row: DataPoint) {
  const statusScore =
    row.status === "approved"
      ? 50
      : row.status === "in_review"
        ? 40
        : row.status === "submitted"
          ? 35
          : row.status === "needs_revision"
            ? 25
            : row.status === "rejected"
              ? 20
              : row.status === "draft"
                ? 10
                : 0;

  let score = statusScore;
  if (row.numeric_value != null || row.text_value?.trim()) score += 40;
  if (row.unit_code) score += 5;
  if (row.evidence_count && row.evidence_count > 0) score += 10;
  if (row.methodology?.trim()) score += 5;
  return score;
}

function choosePreferredDataPoint(points: DataPoint[]) {
  return points.reduce((best, candidate) => {
    if (!best) return candidate;

    const candidateScore = getDataPointScore(candidate);
    const bestScore = getDataPointScore(best);

    if (candidateScore !== bestScore) {
      return candidateScore > bestScore ? candidate : best;
    }

    return candidate.id > best.id ? candidate : best;
  }, points[0]);
}

function isForbidden(error: Error | null) {
  const code = (error as (Error & { code?: string }) | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

function getRoleLabel(roles: string[]) {
  if (roles.includes("collector")) return "Collector";
  if (roles.includes("esg_manager")) return "ESG Manager";
  if (roles.includes("admin")) return "Admin";
  if (roles.includes("platform_admin")) return "Platform Admin";
  return "Workspace";
}

function hasCreatedEntry(row: DataPoint) {
  return Boolean(getResolvedDataPointId(row));
}

function isSubmittedStatus(status?: string | null) {
  return ["submitted", "in_review", "approved"].includes(status ?? "");
}

function hasContextValid(row: DataPoint) {
  return row.boundary_status === "included";
}

function hasReviewer(row: DataPoint) {
  return Boolean(row.reviewer_id);
}

function hasValue(detail: DataPointDetail | null | undefined, row: DataPoint) {
  if (detail) {
    if (detail.element_type === "numeric") return detail.numeric_value != null;
    return Boolean(detail.text_value?.trim());
  }
  if (row.numeric_value != null) return true;
  return Boolean(row.text_value?.trim());
}

function methodologySelectionRequired(
  detail: DataPointDetail | null | undefined,
  hasMethodologyCatalog = true
) {
  if (detail) {
    return (detail.methodology_options?.length ?? 0) > 0;
  }
  return hasMethodologyCatalog;
}

function hasMethodology(
  detail: DataPointDetail | null | undefined,
  row: DataPoint,
  hasMethodologyCatalog = true
) {
  if (detail) {
    return (
      !methodologySelectionRequired(detail, hasMethodologyCatalog) ||
      Boolean(detail.methodology?.trim())
    );
  }
  return !hasMethodologyCatalog || row.collection_status === "complete";
}

function hasEvidence(detail: DataPointDetail | null | undefined, row: DataPoint) {
  if (detail) return !detail.evidence_required || detail.evidence_count > 0;
  return !row.evidence_required || (row.evidence_count ?? 0) > 0;
}

function getNeedsText(
  row: DataPoint,
  detail?: DataPointDetail | null,
  hasMethodologyCatalog = true
) {
  const missing: string[] = [];
  if (!hasValue(detail, row)) missing.push("Value");
  if (!hasMethodology(detail, row, hasMethodologyCatalog)) {
    missing.push("Methodology");
  }
  if (!hasEvidence(detail, row)) missing.push("Evidence");
  if (missing.length > 0) return `Needs: ${missing.join(", ")}`;
  return "All required inputs look complete";
}

function getProgressCount(row: DataPoint, detail?: DataPointDetail | null) {
  let count = 0;
  if (hasValue(detail, row)) count += 1;
  if (hasMethodology(detail, row)) count += 1;
  if (hasEvidence(detail, row)) count += 1;
  if (hasContextValid(row)) count += 1;
  return count;
}

function formatContext(row: Pick<DataPoint, "entity_name" | "facility_name">) {
  return row.facility_name ? `${row.entity_name} / ${row.facility_name}` : row.entity_name;
}

function fieldMatchesRow(field: FormConfigField, row: DataPoint) {
  if (field.assignment_id != null && row.assignment_id === field.assignment_id) {
    return true;
  }

  if (row.shared_element_id !== field.shared_element_id) {
    return false;
  }

  if (field.facility_id != null) {
    return row.facility_id === field.facility_id;
  }

  if (field.entity_id != null) {
    return row.entity_id === field.entity_id && row.facility_id == null;
  }

  return true;
}

function getBlockingReason(row: DataPoint) {
  if (row.boundary_status === "excluded") return "Excluded from reporting boundary";
  if (row.boundary_status === "partial") return "Boundary needs review";
  if (!hasReviewer(row)) return "Reviewer is not assigned";
  return "Needs review before submission";
}

function isReadyToSubmit(row: DataPoint, detail?: DataPointDetail | null, hasMethodologyCatalog = true) {
  return (
    !isSubmittedStatus(detail?.status ?? row.status) &&
    hasContextValid(row) &&
    hasReviewer(row) &&
    hasValue(detail, row) &&
    hasMethodology(detail, row, hasMethodologyCatalog) &&
    hasEvidence(detail, row)
  );
}

function isBlockedRow(row: DataPoint) {
  return row.boundary_status !== "included" || !hasReviewer(row);
}

function getFeedSection(
  row: DataPoint,
  detail?: DataPointDetail | null,
  hasMethodologyCatalog = true
): FeedSection {
  if (isSubmittedStatus(detail?.status ?? row.status) || row.collection_status === "complete") {
    return "submitted";
  }
  if (isBlockedRow(row)) return "blocked";
  if (isReadyToSubmit(row, detail, hasMethodologyCatalog)) return "ready";
  return "action";
}

function getStatusBadgeMeta(
  row: DataPoint,
  detail?: DataPointDetail | null,
  hasMethodologyCatalog = true
) {
  const rawStatus = detail?.status ?? row.status;
  if (isSubmittedStatus(rawStatus) || row.collection_status === "complete") {
    if (rawStatus === "submitted" || rawStatus === "in_review") {
      return {
        label: rawStatus === "in_review" ? "In review" : "Submitted",
        className: "border-cyan-200 bg-cyan-50 text-cyan-700",
      };
    }
    return {
      label: "Approved",
      className: "border-green-200 bg-green-50 text-green-700",
    };
  }
  if (isBlockedRow(row)) {
    return {
      label: "Blocked",
      className: "border-red-200 bg-red-50 text-red-700",
    };
  }
  if (isReadyToSubmit(row, detail, hasMethodologyCatalog)) {
    return {
      label: "Ready",
      className: "border-green-200 bg-green-50 text-green-700",
    };
  }
  if (row.collection_status === "missing") {
    return {
      label: "Not started",
      className: "border-red-200 bg-red-50 text-red-700",
    };
  }
  return {
    label: "Draft",
    className: "border-amber-200 bg-amber-50 text-amber-700",
  };
}

function getRowActionMeta(
  row: DataPoint,
  detail?: DataPointDetail | null,
  hasMethodologyCatalog = true
) {
  if (isSubmittedStatus(detail?.status ?? row.status) || row.collection_status === "complete") {
    return { label: "View", variant: "outline" as const, intent: "wizard" as const };
  }
  if (isReadyToSubmit(row, detail, hasMethodologyCatalog)) {
    return { label: "Submit", variant: "default" as const, intent: "submit" as const };
  }
  if (row.collection_status === "missing") {
    return {
      label: isBlockedRow(row) ? (row.boundary_status === "excluded" ? "Review" : "Open") : "Open",
      variant: isBlockedRow(row) ? "outline" as const : "default" as const,
      intent:
        isBlockedRow(row) && row.boundary_status === "excluded"
          ? ("wizard" as const)
          : ("quick" as const),
    };
  }
  return {
    label: isBlockedRow(row) ? (row.boundary_status === "excluded" ? "Review" : "Continue") : "Continue",
    variant: isBlockedRow(row) ? "outline" as const : "default" as const,
    intent:
      isBlockedRow(row) && row.boundary_status === "excluded"
        ? ("wizard" as const)
        : ("quick" as const),
  };
}

function getOverdueLabel(daysOverdue?: number | null) {
  if (!daysOverdue || daysOverdue <= 0) return null;
  return `${daysOverdue}D OVERDUE`;
}

function getUserInitials(name?: string | null) {
  const parts = (name ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  if (parts.length === 0) return "NA";
  return parts.map((part) => part[0]?.toUpperCase() ?? "").join("");
}

function getUserAvatarStyle(id?: number | null, name?: string | null) {
  const seed = `${id ?? 0}-${name ?? ""}`;
  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = seed.charCodeAt(index) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  return { backgroundColor: `hsl(${hue} 72% 54%)` };
}

function isImportPseudoStandard(code?: string | null, name?: string | null) {
  const normalizedCode = (code ?? "").toUpperCase();
  const normalizedName = (name ?? "").toLowerCase();
  return normalizedCode.includes("DATASHEET") || normalizedName.includes("proxy import");
}

function getDisplayFrameworks(
  standards: Array<{ code: string; name: string }>
): DisplayFramework[] {
  const realStandards = standards.filter(
    (standard) => !isImportPseudoStandard(standard.code, standard.name)
  );

  if (realStandards.length > 0) {
    return realStandards.map((standard) => ({
      code: standard.code,
      name: standard.name,
      tone: "framework",
    }));
  }

  if (standards.length > 0) {
    return [{ code: "CUSTOM", name: "Imported mapping", tone: "custom" }];
  }

  return [{ code: "NOT DEFINED", name: "No framework mapping", tone: "custom" }];
}

function formatFileSize(bytes?: number | null): string | null {
  if (bytes == null) return null;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatEvidenceDate(date?: string | null): string {
  if (!date) return "Unknown";
  return new Date(date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function CollectionPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    activeProject,
    projectId,
    isLoading: projectsLoading,
    error: projectsError,
  } = useActiveProject("collection");

  const [openingRowId, setOpeningRowId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [guidedConfigMessage, setGuidedConfigMessage] = useState<string | null>(null);
  const [guidedConfigMessageTone, setGuidedConfigMessageTone] = useState<
    "success" | "error" | "info"
  >("info");
  const [resyncingGuidedConfig, setResyncingGuidedConfig] = useState(false);
  const [guidedField, setGuidedField] = useState<FormConfigField | null>(null);
  const [guidedRowKey, setGuidedRowKey] = useState<string | null>(null);
  const [resolvedDataPointIds, setResolvedDataPointIds] = useState<Record<string, number>>({});
  const [viewMode, setViewMode] = useState<ViewMode>("feed");
  const [feedSection, setFeedSection] = useState<FeedSection>("action");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null);
  const [checkedRowKeys, setCheckedRowKeys] = useState<string[]>([]);
  const [onlyMine, setOnlyMine] = useState(false);
  const [evidencePreviewTarget, setEvidencePreviewTarget] =
    useState<EvidencePreviewTarget | null>(null);
  const deepLinkHandledRef = useRef<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DataPointStatus>("all");
  const [boundaryFilter, setBoundaryFilter] = useState<"all" | BoundaryStatus>("all");
  const [entityFilter, setEntityFilter] = useState("");
  const [standardFilter, setStandardFilter] = useState("");
  const [sortField, setSortField] = useState<
    "element_code" | "element_name" | "collection_status"
  >("element_code");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const deepLinkSharedElementId = parseOptionalPositiveInt(searchParams.get("sharedElementId"));
  const deepLinkEntityId = parseOptionalPositiveInt(searchParams.get("entityId"));
  const deepLinkFacilityId = parseOptionalPositiveInt(searchParams.get("facilityId"));
  const deepLinkOpenContext = searchParams.get("openContext") === "1";
  const deepLinkReturnTo = sanitizeInternalReturnTo(searchParams.get("returnTo"));
  const deepLinkReturnLabel = searchParams.get("returnLabel") || undefined;
  const deepLinkRowKey = deepLinkSharedElementId
    ? buildContextKey(deepLinkSharedElementId, deepLinkEntityId, deepLinkFacilityId)
    : null;

  const { data: me, isLoading: meLoading } = useApiQuery<AuthMe>(["auth-me"], "/auth/me");

  const roles = useMemo(() => me?.roles?.map((binding) => binding.role) ?? [], [me?.roles]);
  const isCollector = roles.includes("collector");
  const canAccess = roles.some((role) =>
    ["collector", "esg_manager", "admin", "platform_admin"].includes(role)
  );

  useEffect(() => {
    if (typeof window === "undefined" || roles.length === 0) return;
    const stored = window.localStorage.getItem(ONLY_MINE_STORAGE_KEY);
    const nextOnlyMine =
      stored === "true" || stored === "false" ? stored === "true" : isCollector;
    setOnlyMine((current) => (current === nextOnlyMine ? current : nextOnlyMine));
  }, [isCollector, roles.length]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ONLY_MINE_STORAGE_KEY, String(onlyMine));
  }, [onlyMine]);

  const {
    data: assignmentsData,
    isLoading: assignmentsLoading,
    error: assignmentsError,
  } = useApiQuery<AssignmentMatrixResponse>(
    ["collection-assignments", projectId],
    `/projects/${projectId}/assignments`,
    { enabled: canAccess && projectId !== null }
  );

  const {
    data,
    isLoading,
    error,
  } = useQuery<DataPointsResponse, AppApiError>({
    queryKey: ["data-points", projectId, "all"],
    queryFn: () => {
      if (projectId == null) {
        throw new Error("Project context is not ready yet.");
      }
      return fetchAllProjectDataPoints(projectId);
    },
    enabled: canAccess && projectId !== null,
  });

  const { data: methodologies } = useApiQuery<MethodologyReference[]>(
    ["reference-methodologies"],
    "/references/methodologies",
    { enabled: canAccess }
  );
  const {
    data: activeFormConfig,
    isLoading: activeFormConfigLoading,
    error: activeFormConfigError,
  } = useApiQuery<ActiveFormConfig | null>(
    ["active-form-config", projectId],
    `/form-configs/projects/${projectId}/active`,
    { enabled: canAccess && projectId !== null }
  );

  const hasMethodologyCatalog = (methodologies?.length ?? 0) > 0;

  const items = useMemo(() => {
    const points = data?.items ?? [];
    const assignments = assignmentsData?.assignments ?? [];

    const pointGroups = new Map<string, DataPoint[]>();
    for (const point of points) {
      const key = buildContextKey(
        point.shared_element_id ?? 0,
        point.entity_id ?? 0,
        point.facility_id ?? 0
      );
      const existing = pointGroups.get(key) ?? [];
      existing.push(point);
      pointGroups.set(key, existing);
    }

    const pointsByKey = new Map<string, DataPoint>();
    for (const [key, groupedPoints] of pointGroups.entries()) {
      pointsByKey.set(key, choosePreferredDataPoint(groupedPoints));
    }

    if (assignments.length === 0) {
      return Array.from(pointsByKey.values()).map((point) => ({
        ...point,
        data_point_id: point.id,
      }));
    }

    return assignments.map((assignment) => {
      const key = buildContextKey(
        assignment.shared_element_id,
        assignment.entity_id ?? 0,
        assignment.facility_id ?? 0
      );
      const point = pointsByKey.get(key);
      const resolvedDataPointId = point?.id ?? resolvedDataPointIds[key] ?? null;
      const collectionStatus =
        point?.collection_status ??
        (resolvedDataPointId ? "partial" : undefined) ??
        (assignment.status === "completed"
          ? "complete"
          : assignment.status === "in_progress"
            ? "partial"
            : "missing");

      return {
        id: point?.id ?? resolvedDataPointId ?? -assignment.id,
        data_point_id: point?.id ?? resolvedDataPointId,
        assignment_id: assignment.id,
        shared_element_id: assignment.shared_element_id,
        entity_id: assignment.entity_id,
        facility_id: assignment.facility_id,
        element_code: point?.element_code ?? assignment.shared_element_code,
        element_name: point?.element_name ?? assignment.shared_element_name,
        collection_status: collectionStatus,
        entity_name: point?.entity_name ?? assignment.entity_name ?? "Organization",
        facility_name: point?.facility_name ?? assignment.facility_name ?? null,
        boundary_status:
          point?.boundary_status ??
          (assignment.boundary_included ? "included" : "excluded"),
        consolidation_method:
          point?.consolidation_method ?? assignment.consolidation_method ?? "full",
        collector_id: assignment.collector_id ?? null,
        collector_name: assignment.collector_name ?? null,
        reviewer_id: assignment.reviewer_id ?? null,
        reviewer_name: assignment.reviewer_name ?? null,
        reused_across_standards: point?.reused_across_standards ?? false,
        standards: point?.standards ?? [],
        status: point?.status ?? null,
        numeric_value: point?.numeric_value ?? null,
        text_value: point?.text_value ?? null,
        unit_code: point?.unit_code ?? null,
        methodology: point?.methodology ?? null,
        evidence_required: point?.evidence_required ?? false,
        evidence_count: point?.evidence_count ?? 0,
        element_type: point?.element_type ?? null,
        deadline: assignment.deadline ?? null,
        days_overdue: assignment.days_overdue ?? 0,
        days_until_deadline: assignment.days_until_deadline ?? null,
      } satisfies DataPoint;
    });
  }, [assignmentsData?.assignments, data?.items, resolvedDataPointIds]);

  const accessDenied =
    (Boolean(me) && !canAccess) ||
    (!!projectsError && isForbidden(projectsError)) ||
    (!!assignmentsError && isForbidden(assignmentsError)) ||
    (!!error && isForbidden(error)) ||
    (!!activeFormConfigError && isForbidden(activeFormConfigError));

  const entities = useMemo(
    () => Array.from(new Set(items.map((item) => item.entity_name))).sort(),
    [items]
  );
  const standards = useMemo(
    () => Array.from(new Set(items.flatMap((item) => item.standards ?? []))).sort(),
    [items]
  );

  const filteredItems = useMemo(() => {
    let result = items;

    if (onlyMine && me?.id != null) {
      result = result.filter((item) => item.collector_id === me.id);
    }
    if (statusFilter !== "all") {
      result = result.filter((item) => item.collection_status === statusFilter);
    }
    if (boundaryFilter !== "all") {
      result = result.filter((item) => item.boundary_status === boundaryFilter);
    }
    if (entityFilter) {
      result = result.filter((item) => item.entity_name === entityFilter);
    }
    if (standardFilter) {
      result = result.filter((item) => item.standards.includes(standardFilter));
    }
    if (search.trim()) {
      const query = search.trim().toLowerCase();
      result = result.filter((item) =>
        [
          item.element_code,
          item.element_name,
          item.entity_name,
          item.facility_name ?? "",
          item.collector_name ?? "",
        ]
          .join(" ")
          .toLowerCase()
          .includes(query)
      );
    }

    return result;
  }, [
    items,
    onlyMine,
    me?.id,
    statusFilter,
    boundaryFilter,
    entityFilter,
    standardFilter,
    search,
  ]);

  const guidedScopeItems = useMemo(() => {
    let result = items;
    if (onlyMine && me?.id != null) {
      result = result.filter((item) => item.collector_id === me.id);
    }
    return result;
  }, [items, me?.id, onlyMine]);

  const filtered = useMemo(() => {
    return [...filteredItems].sort((left, right) => {
      const leftValue = String(left[sortField] ?? "");
      const rightValue = String(right[sortField] ?? "");
      const comparison = leftValue.localeCompare(rightValue);
      return sortDir === "asc" ? comparison : -comparison;
    });
  }, [
    filteredItems,
    sortField,
    sortDir,
  ]);

  const orderedFeedItems = useMemo(() => {
    const priority: Record<FeedSection, number> = {
      action: 0,
      blocked: 1,
      ready: 2,
      submitted: 3,
    };

    return [...filteredItems].sort((left, right) => {
      const sectionCompare =
        priority[getFeedSection(left, undefined, hasMethodologyCatalog)] -
        priority[getFeedSection(right, undefined, hasMethodologyCatalog)];
      if (sectionCompare !== 0) return sectionCompare;

      const overdueCompare = (right.days_overdue ?? 0) - (left.days_overdue ?? 0);
      if (overdueCompare !== 0) return overdueCompare;

      const leftDeadline = left.deadline ?? "";
      const rightDeadline = right.deadline ?? "";
      if (leftDeadline !== rightDeadline) {
        if (!leftDeadline) return 1;
        if (!rightDeadline) return -1;
        return leftDeadline.localeCompare(rightDeadline);
      }

      return left.element_code.localeCompare(right.element_code);
    });
  }, [filteredItems, hasMethodologyCatalog]);

  const feedCounts = useMemo(() => {
    return orderedFeedItems.reduce(
      (current, item) => {
        current[getFeedSection(item, undefined, hasMethodologyCatalog)] += 1;
        return current;
      },
      { action: 0, blocked: 0, ready: 0, submitted: 0 } satisfies Record<FeedSection, number>
    );
  }, [orderedFeedItems, hasMethodologyCatalog]);

  useEffect(() => {
    const totalVisible = Object.values(feedCounts).reduce((sum, count) => sum + count, 0);
    if (feedCounts[feedSection] > 0 || totalVisible === 0) return;
    const next = FEED_SECTION_ORDER.find((section) => feedCounts[section] > 0) ?? "action";
    setFeedSection(next);
  }, [feedCounts, feedSection]);

  const visibleFeedItems = useMemo(() => {
    return orderedFeedItems.filter(
      (item) => getFeedSection(item, undefined, hasMethodologyCatalog) === feedSection
    );
  }, [feedSection, hasMethodologyCatalog, orderedFeedItems]);

  const visibleFeedRowKeys = useMemo(
    () => new Set(visibleFeedItems.map((item) => buildRowKey(item))),
    [visibleFeedItems]
  );

  const rowsByKey = useMemo(() => {
    const map = new Map<string, DataPoint>();
    for (const item of items) {
      map.set(buildRowKey(item), item);
    }
    return map;
  }, [items]);

  const filteredRowKeys = useMemo(
    () => new Set(filteredItems.map((item) => buildRowKey(item))),
    [filteredItems]
  );
  const guidedDescriptors = useMemo<GuidedFieldDescriptor[]>(() => {
    const steps = activeFormConfig?.config?.steps ?? [];
    return steps.flatMap((step) =>
      (step.fields ?? []).map((field) => ({
        stepId: step.id,
        stepTitle: step.title,
        field,
      }))
    );
  }, [activeFormConfig?.config?.steps]);
  const guidedCards = useMemo<GuidedFieldCard[]>(() => {
    return guidedDescriptors
      .map((descriptor) => {
        const matches = guidedScopeItems.filter((row) =>
          fieldMatchesRow(descriptor.field, row)
        );
        return {
          descriptor,
          matches,
          primaryRow: matches[0] ?? null,
        } satisfies GuidedFieldCard;
      })
      .filter((card) => card.matches.length > 0);
  }, [guidedDescriptors, guidedScopeItems]);
  const hasGuidedCollection = guidedCards.length > 0;
  const checkedRowKeySet = useMemo(() => new Set(checkedRowKeys), [checkedRowKeys]);
  const checkedRows = useMemo(
    () => checkedRowKeys.map((rowKey) => rowsByKey.get(rowKey)).filter(Boolean) as DataPoint[],
    [checkedRowKeys, rowsByKey]
  );
  const allCheckedRowsReady = useMemo(
    () =>
      checkedRows.length > 0 &&
      checkedRows.every((row) => isReadyToSubmit(row, undefined, hasMethodologyCatalog)),
    [checkedRows, hasMethodologyCatalog]
  );

  useEffect(() => {
    if (!selectedRowKey) return;
    if (selectedRowKey === deepLinkRowKey) return;
    if (!filteredRowKeys.has(selectedRowKey)) {
      setSelectedRowKey(null);
    }
  }, [deepLinkRowKey, filteredRowKeys, selectedRowKey]);

  useEffect(() => {
    setCheckedRowKeys((current) => current.filter((rowKey) => filteredRowKeys.has(rowKey)));
  }, [filteredRowKeys]);

  useEffect(() => {
    if (viewMode !== "feed") return;
    setCheckedRowKeys((current) => current.filter((rowKey) => visibleFeedRowKeys.has(rowKey)));
  }, [viewMode, visibleFeedRowKeys]);

  useEffect(() => {
    if (viewMode === "feed" || !selectedRowKey) return;
    setSelectedRowKey(null);
  }, [selectedRowKey, viewMode]);

  useEffect(() => {
    if (viewMode !== "feed" || !selectedRowKey) return;
    if (selectedRowKey === deepLinkRowKey) return;
    if (!visibleFeedRowKeys.has(selectedRowKey)) {
      setSelectedRowKey(null);
    }
  }, [deepLinkRowKey, selectedRowKey, viewMode, visibleFeedRowKeys]);

  const selectedRow = selectedRowKey ? rowsByKey.get(selectedRowKey) ?? null : null;
  const selectedDataPointId = selectedRow ? getResolvedDataPointId(selectedRow) : null;

  const { data: selectedDetail } = useApiQuery<DataPointDetail>(
    ["collection-selected-detail", selectedDataPointId],
    `/data-points/${selectedDataPointId}`,
    { enabled: canAccess && Boolean(selectedDataPointId) }
  );
  const { data: selectedEvidence, isLoading: selectedEvidenceLoading } =
    useApiQuery<EvidenceItem[]>(
      ["collection-selected-evidence", selectedDataPointId],
      `/data-points/${selectedDataPointId}/evidences`,
      { enabled: canAccess && Boolean(selectedDataPointId) }
    );
  const evidencePreviewId = evidencePreviewTarget?.item.id ?? null;
  const { data: evidencePreviewDetail, isLoading: evidencePreviewLoading } =
    useApiQuery<EvidenceItem>(
      ["collection-evidence-preview", evidencePreviewId],
      `/evidences/${evidencePreviewId ?? 0}`,
      { enabled: canAccess && Boolean(evidencePreviewId) }
    );
  const activeEvidencePreview = evidencePreviewDetail ?? evidencePreviewTarget?.item ?? null;
  const hasActiveFilters =
    onlyMine ||
    Boolean(search.trim()) ||
    statusFilter !== "all" ||
    boundaryFilter !== "all" ||
    Boolean(entityFilter) ||
    Boolean(standardFilter);
  const roleLabel = getRoleLabel(roles);

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortField(field);
    setSortDir("asc");
  };

  const openQuickEntry = useCallback((row: DataPoint, helpText?: string | null) => {
    if (!row.shared_element_id) {
      setActionError("This assignment is missing its shared element binding and cannot be opened.");
      return;
    }

    setActionError(null);
    setGuidedField({
      shared_element_id: row.shared_element_id,
      assignment_id: row.assignment_id ?? undefined,
      entity_id: row.entity_id ?? undefined,
      facility_id: row.facility_id ?? undefined,
      visible: true,
      required: row.collection_status !== "complete",
      help_text: helpText ?? null,
      order: 0,
    });
    const rowKey = buildRowKey(row);
    setGuidedRowKey(rowKey);
  }, []);

  const openEvidencePreview = useCallback((row: DataPoint, item: EvidenceItem) => {
    setEvidencePreviewTarget({ row, item });
  }, []);

  const openEvidenceRepository = useCallback(
    (evidenceId?: number | null) => {
      const params = new URLSearchParams();
      params.set("projectId", String(projectId));
      if (evidenceId) {
        params.set("evidenceId", String(evidenceId));
        router.push(`/evidence?${params.toString()}`);
        return;
      }
      router.push(`/evidence?${params.toString()}`);
    },
    [projectId, router]
  );

  const buildCollectionDetailUrl = useCallback(
    (
      dataPointId: number,
      options?: { returnTo?: string | null; returnLabel?: string | undefined }
    ) => {
      const params = new URLSearchParams();
      params.set("projectId", String(projectId));
      if (options?.returnTo) {
        params.set("returnTo", options.returnTo);
      }
      if (options?.returnLabel) {
        params.set("returnLabel", options.returnLabel);
      }
      return `/collection/${dataPointId}?${params.toString()}`;
    },
    [projectId]
  );

  const openDataEntry = useCallback(async (
    row: DataPoint,
    options?: { returnTo?: string | null; returnLabel?: string | undefined }
  ) => {
    setActionError(null);

    if (row.data_point_id) {
      router.push(buildCollectionDetailUrl(row.data_point_id, options));
      return;
    }

    const resolvedDataPointId = getResolvedDataPointId(row);
    if (resolvedDataPointId) {
      router.push(buildCollectionDetailUrl(resolvedDataPointId, options));
      return;
    }
    if (!row.shared_element_id) {
      setActionError("This assignment is missing its shared element binding and cannot be opened.");
      return;
    }

    setOpeningRowId(row.assignment_id ?? row.id);
    try {
      const created = await api.post<{ id: number }>(`/projects/${projectId}/data-points`, {
        shared_element_id: row.shared_element_id,
        entity_id: row.entity_id ?? undefined,
        facility_id: row.facility_id ?? undefined,
      });
      router.push(buildCollectionDetailUrl(created.id, options));
    } catch (openError) {
      setActionError(
        openError instanceof Error
          ? openError.message
          : "Unable to open data entry for this row. Please try again."
      );
    } finally {
      setOpeningRowId(null);
    }
  }, [buildCollectionDetailUrl, projectId, router]);

  const submitRow = useCallback(
    async (row: DataPoint) => {
      const dataPointId = getResolvedDataPointId(row);
      if (!dataPointId) {
        setActionError("Create a draft entry before submitting this metric.");
        return;
      }

      setActionError(null);
      setOpeningRowId(row.assignment_id ?? row.id);
      try {
        await api.post(`/data-points/${dataPointId}/submit`);
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["data-points", projectId, "all"] }),
          queryClient.invalidateQueries({ queryKey: ["collection-assignments", projectId] }),
          queryClient.invalidateQueries({
            queryKey: ["collection-selected-detail", dataPointId],
          }),
        ]);
      } catch (submitError) {
        setActionError(
          submitError instanceof Error
            ? submitError.message
            : "Unable to submit this row. Please try again."
        );
      } finally {
        setOpeningRowId(null);
      }
    },
    [projectId, queryClient]
  );

  useEffect(() => {
    if (!deepLinkRowKey) return;
    const row = rowsByKey.get(deepLinkRowKey);
    if (row) {
      const targetFeedSection = getFeedSection(row, undefined, hasMethodologyCatalog);
      if (viewMode === "feed" && feedSection !== targetFeedSection) {
        setFeedSection(targetFeedSection);
      }
      if (!deepLinkOpenContext && selectedRowKey !== deepLinkRowKey) {
        setSelectedRowKey(deepLinkRowKey);
      }
      if (deepLinkOpenContext && deepLinkHandledRef.current !== deepLinkRowKey) {
        deepLinkHandledRef.current = deepLinkRowKey;
        void openDataEntry(row, {
          returnTo: deepLinkReturnTo,
          returnLabel: deepLinkReturnLabel,
        });
      }
      return;
    }

    if (projectsLoading || meLoading || assignmentsLoading || isLoading) {
      return;
    }

    const missingKey = `${deepLinkRowKey}:missing`;
    if (deepLinkHandledRef.current === missingKey) {
      return;
    }
    deepLinkHandledRef.current = missingKey;
    setActionError("Unable to find this datasheet metric context in collection.");
  }, [
    assignmentsLoading,
    deepLinkOpenContext,
    deepLinkReturnLabel,
    deepLinkReturnTo,
    deepLinkRowKey,
    feedSection,
    hasMethodologyCatalog,
    isLoading,
    meLoading,
    openDataEntry,
    projectsLoading,
    rowsByKey,
    selectedRowKey,
    viewMode,
  ]);

  const resetFilters = () => {
    setSearch("");
    setStatusFilter("all");
    setBoundaryFilter("all");
    setEntityFilter("");
    setStandardFilter("");
    setSortField("element_code");
    setSortDir("asc");
  };

  const toggleCheckedRow = useCallback((rowKey: string, checked: boolean) => {
    setCheckedRowKeys((current) => {
      if (checked) {
        if (current.includes(rowKey)) return current;
        return [...current, rowKey];
      }
      return current.filter((entry) => entry !== rowKey);
    });
  }, []);

  const clearCheckedRows = useCallback(() => {
    setCheckedRowKeys([]);
  }, []);

  const submitCheckedRows = useCallback(async () => {
    if (checkedRows.length === 0) return;

    const nonReady = checkedRows.filter(
      (row) => !isReadyToSubmit(row, undefined, hasMethodologyCatalog)
    );
    if (nonReady.length > 0) {
      setActionError("Only rows that are ready to submit can be submitted in batch.");
      return;
    }

    setActionError(null);

    try {
      for (const row of checkedRows) {
        const dataPointId = getResolvedDataPointId(row);
        if (!dataPointId) {
          throw new Error("One of the selected rows does not have a draft yet.");
        }
        await api.post(`/data-points/${dataPointId}/submit`);
      }
      clearCheckedRows();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["data-points", projectId, "all"] }),
        queryClient.invalidateQueries({ queryKey: ["collection-assignments", projectId] }),
      ]);
      if (selectedDataPointId) {
        await queryClient.invalidateQueries({
          queryKey: ["collection-selected-detail", selectedDataPointId],
        });
      }
    } catch (submitError) {
      setActionError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to submit the selected rows. Please try again."
      );
    }
  }, [
    checkedRows,
    clearCheckedRows,
    hasMethodologyCatalog,
    projectId,
    queryClient,
    selectedDataPointId,
  ]);

  const headerSubtitle = [activeProject?.name ?? `Project #${projectId}`, roleLabel]
    .filter(Boolean)
    .join(" · ");

  const runRowAction = useCallback(
    (row: DataPoint, intent: "quick" | "wizard" | "submit") => {
      if (intent === "submit") {
        void submitRow(row);
        return;
      }
      if (intent === "wizard") {
        void openDataEntry(row);
        return;
      }
      openQuickEntry(row);
    },
    [openDataEntry, openQuickEntry, submitRow]
  );
  const handleGuidedResync = useCallback(async () => {
    setGuidedConfigMessage(null);
    setResyncingGuidedConfig(true);
    try {
      await api.post(`/form-configs/projects/${projectId}/resync`);
      setGuidedConfigMessageTone("success");
      setGuidedConfigMessage("Guided collection config re-synced from live assignments.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["active-form-config", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["collection-assignments", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["data-points", projectId, "all"] }),
      ]);
    } catch (resyncError) {
      setGuidedConfigMessageTone("error");
      setGuidedConfigMessage(
        resyncError instanceof Error
          ? resyncError.message
          : "Unable to re-sync the guided collection config."
      );
    } finally {
      setResyncingGuidedConfig(false);
    }
  }, [projectId, queryClient]);

  const emptyTableMessage = hasActiveFilters
    ? "No data points match the current filters."
    : "No data points found.";

  if (projectsLoading || projectId === null) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <GuidedEntryDialog
        open={Boolean(guidedField && guidedRowKey)}
        onOpenChange={(open) => {
          if (!open) {
            setGuidedField(null);
            setGuidedRowKey(null);
            if (selectedDataPointId) {
              void queryClient.invalidateQueries({
                queryKey: ["collection-selected-detail", selectedDataPointId],
              });
              void queryClient.invalidateQueries({
                queryKey: ["collection-selected-evidence", selectedDataPointId],
              });
            }
          }
        }}
        projectId={projectId}
        row={guidedRowKey ? rowsByKey.get(guidedRowKey) ?? null : null}
        field={guidedField}
        rowKey={guidedRowKey}
        onDataPointResolved={(rowKey, dataPointId) => {
          setResolvedDataPointIds((current) =>
            current[rowKey] === dataPointId ? current : { ...current, [rowKey]: dataPointId }
          );
        }}
      />

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[20px] font-bold tracking-tight text-slate-950">Data Collection</h2>
          <p className="mt-1 text-[12px] text-slate-500">{headerSubtitle}</p>
          <p className="mt-3 max-w-3xl text-sm text-slate-600">
            Track assigned metrics, open data entry, and submit values for the current
            reporting period.
          </p>
          <p className="mt-1 text-xs text-slate-500">
            This is not a Jira-style task board. Each row is one assigned metric context.
          </p>
        </div>

        <Button
          size="sm"
          variant="outline"
          onClick={() => setViewMode((current) => (current === "feed" ? "table" : "feed"))}
          className="h-8 rounded-lg px-3 text-[11px]"
        >
          <LayoutGrid className="h-4 w-4" />
          {viewMode === "feed" ? "Table" : "Compact feed"}
        </Button>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {guidedConfigMessage && (
        <div
          className={cn(
            "flex items-center gap-2 rounded-lg border px-4 py-3 text-sm",
            guidedConfigMessageTone === "success" &&
              "border-green-200 bg-green-50 text-green-800",
            guidedConfigMessageTone === "error" && "border-red-200 bg-red-50 text-red-800",
            guidedConfigMessageTone === "info" && "border-slate-200 bg-slate-50 text-slate-700"
          )}
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {guidedConfigMessage}
        </div>
      )}

      {meLoading || assignmentsLoading || isLoading || activeFormConfigLoading ? (
        <Card className="flex min-h-[320px] items-center justify-center border-slate-200 p-12 text-slate-500">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading collection data...
        </Card>
      ) : accessDenied ? (
        <Card className="flex min-h-[320px] flex-col items-center justify-center p-12">
          <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
          <p className="text-sm font-medium text-slate-900">Access denied</p>
          <p className="mt-1 text-sm text-slate-500">
            Only collectors and ESG managers can access data collection.
          </p>
        </Card>
      ) : error || assignmentsError ? (
        <Card className="flex min-h-[320px] flex-col items-center justify-center p-12">
          <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
          <p className="text-sm text-slate-500">
            Failed to load collection data. Please try again.
          </p>
        </Card>
      ) : viewMode === "feed" ? (
          <div className="space-y-4">
            {activeFormConfig && (
              <Card className="border-slate-200 p-5">
                <div className="space-y-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-950">Guided Collection</h3>
                      <p className="mt-1 text-sm text-slate-600">
                        {activeFormConfig.name}
                        {activeFormConfig.resolution_scope === "organization_default"
                          ? " (organization default)"
                          : ""}
                      </p>
                      {activeFormConfig.description ? (
                        <p className="mt-1 text-xs text-slate-500">{activeFormConfig.description}</p>
                      ) : null}
                    </div>
                    <div className="text-xs text-slate-500">
                      {guidedCards.length} guided {guidedCards.length === 1 ? "field" : "fields"}
                    </div>
                  </div>

                  {activeFormConfig.health?.is_stale ? (
                    <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 text-sm font-semibold text-amber-900">
                            <TriangleAlert className="h-4 w-4" />
                            Stale config
                          </div>
                          <p className="text-sm text-amber-900">
                            This guided config is out of sync with the current assignments or
                            boundary.
                          </p>
                          <div className="space-y-1">
                            {activeFormConfig.health.issues.map((issue) => (
                              <p
                                key={`${issue.code}-${issue.message}`}
                                className="text-xs text-amber-800"
                              >
                                {issue.message}
                              </p>
                            ))}
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={resyncingGuidedConfig}
                          className="border-amber-300 bg-white text-amber-900 hover:bg-amber-100"
                          onClick={() => void handleGuidedResync()}
                        >
                          {resyncingGuidedConfig ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Re-syncing...
                            </>
                          ) : (
                            "Re-sync Config"
                          )}
                        </Button>
                      </div>
                    </div>
                  ) : null}

                  {hasGuidedCollection ? (
                    <div className="grid gap-3 lg:grid-cols-2">
                      {guidedCards.map((card) => {
                        const row = card.primaryRow;
                        const rowKey = row ? buildRowKey(row) : null;
                        const hasMultipleContexts = card.matches.length > 1;
                        const canContinueEntry = row ? hasCreatedEntry(row) : false;
                        const quickActionLabel = canContinueEntry ? "Continue entry" : "Quick entry";

                        return (
                          <div
                            key={`${card.descriptor.stepId}-${card.descriptor.field.order}-${card.descriptor.field.shared_element_id}-${card.descriptor.field.assignment_id ?? "na"}`}
                            className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                          >
                            <div className="space-y-3">
                              <div className="space-y-1">
                                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                                  {card.descriptor.stepTitle}
                                </div>
                                <div className="text-base font-semibold text-slate-950">
                                  {row?.element_name ?? row?.element_code ?? "Guided metric"}
                                </div>
                                {row?.element_code ? (
                                  <div className="font-mono text-xs text-slate-500">
                                    {row.element_code}
                                  </div>
                                ) : null}
                              </div>

                              {row ? (
                                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                  <span>{formatContext(row)}</span>
                                  <span className="text-slate-300">•</span>
                                  <span>
                                    {card.matches.length === 1
                                      ? "1 context"
                                      : `${card.matches.length} matched rows`}
                                  </span>
                                </div>
                              ) : null}

                              {card.descriptor.field.help_text ? (
                                <p className="text-sm text-slate-600">{card.descriptor.field.help_text}</p>
                              ) : null}

                              {hasMultipleContexts ? (
                                <div className="flex items-center justify-between gap-3">
                                  <div className="text-sm font-medium text-slate-700">
                                    {card.matches.length} contexts
                                  </div>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => {
                                      setSearch(row?.element_code ?? "");
                                      setViewMode("table");
                                      setSelectedRowKey(rowKey);
                                      requestAnimationFrame(() => {
                                        document
                                          .getElementById("collection-table")
                                          ?.scrollIntoView({ behavior: "smooth", block: "start" });
                                      });
                                    }}
                                  >
                                    Show rows
                                  </Button>
                                </div>
                              ) : row ? (
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                  <span className="text-xs text-slate-500">
                                    {canContinueEntry
                                      ? "Draft already exists for this metric context."
                                      : "Open quick entry to capture the value, methodology, and evidence."}
                                  </span>
                                  <Button
                                    size="sm"
                                    onClick={() =>
                                      openQuickEntry(row, card.descriptor.field.help_text ?? null)
                                    }
                                  >
                                    {quickActionLabel}
                                  </Button>
                                </div>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
                      No guided fields in this config currently resolve to visible assignment
                      contexts.
                    </div>
                  )}
                </div>
              </Card>
            )}

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
                <div className="relative w-full max-w-[260px]">
                  <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                  <Input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search metrics..."
                    className="h-8 rounded-lg border-slate-200 pl-8 text-[12px]"
                  />
                </div>

                <div className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5">
                  <Rows3 className="h-3.5 w-3.5 text-slate-400" />
                  <span className="text-[12px] font-medium text-slate-600">Only mine</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={onlyMine}
                    onClick={() => setOnlyMine((current) => !current)}
                    className={cn(
                      "relative ml-1 inline-flex h-4 w-7 items-center rounded-full transition-colors",
                      onlyMine ? "bg-blue-500" : "bg-slate-200"
                    )}
                  >
                    <span
                      className={cn(
                        "inline-block h-3 w-3 rounded-full bg-white shadow transition-transform",
                        onlyMine ? "translate-x-3.5" : "translate-x-0.5"
                      )}
                    />
                  </button>
                </div>
              </div>

              <div className="relative">
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setFiltersOpen((current) => !current)}
                  aria-label="Toggle advanced filters"
                  className={cn("h-8 w-8 rounded-lg", filtersOpen && "border-slate-300 bg-slate-50")}
                >
                  <Filter className="h-4 w-4" />
                </Button>

                {filtersOpen && (
                  <div className="absolute right-0 top-12 z-20 w-[320px] rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
                    <div className="grid gap-4">
                      <div className="grid gap-1.5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Entity
                        </label>
                        <select
                          value={entityFilter}
                          onChange={(event) => setEntityFilter(event.target.value)}
                          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        >
                          <option value="">All entities</option>
                          {entities.map((entity) => (
                            <option key={entity} value={entity}>
                              {entity}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="grid gap-1.5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Standard
                        </label>
                        <select
                          value={standardFilter}
                          onChange={(event) => setStandardFilter(event.target.value)}
                          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        >
                          <option value="">All standards</option>
                          {standards.map((standard) => (
                            <option key={standard} value={standard}>
                              {standard}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="grid gap-1.5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Boundary
                        </label>
                        <select
                          value={boundaryFilter}
                          onChange={(event) =>
                            setBoundaryFilter(event.target.value as typeof boundaryFilter)
                          }
                          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        >
                          <option value="all">All contexts</option>
                          <option value="included">Included</option>
                          <option value="partial">Partial</option>
                          <option value="excluded">Excluded</option>
                        </select>
                      </div>

                      <div className="grid gap-1.5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Status
                        </label>
                        <select
                          value={statusFilter}
                          onChange={(event) =>
                            setStatusFilter(event.target.value as typeof statusFilter)
                          }
                          className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        >
                          <option value="all">All statuses</option>
                          <option value="missing">Not started</option>
                          <option value="partial">In progress</option>
                          <option value="complete">Complete</option>
                        </select>
                      </div>

                      <div className="flex justify-end">
                        <Button variant="ghost" size="sm" onClick={resetFilters}>
                          Reset filters
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {checkedRowKeys.length > 0 && (
              <div className="flex flex-wrap items-center gap-3 rounded-xl bg-blue-500 px-4 py-3 text-sm text-white">
                <span>
                  <span className="font-semibold">{checkedRowKeys.length}</span> selected
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!allCheckedRowsReady}
                  className="border-white/30 bg-white/10 text-white hover:bg-white/20 hover:text-white"
                  onClick={() => void submitCheckedRows()}
                >
                  Submit selected
                </Button>
                <button
                  type="button"
                  className="ml-auto text-sm font-medium text-white/90 transition hover:text-white"
                  onClick={clearCheckedRows}
                >
                  Clear
                </button>
              </div>
            )}

            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="grid grid-cols-2 sm:grid-cols-4">
                {FEED_SECTION_ORDER.map((section) => (
                  <button
                    key={section}
                    type="button"
                    className={cn(
                      "flex items-center justify-center gap-2 border-r border-slate-200 px-4 py-2.5 text-[12px] font-medium text-slate-500 transition-colors last:border-r-0 hover:bg-slate-50",
                      feedSection === section && "bg-slate-900 text-white hover:bg-slate-900"
                    )}
                    onClick={() => setFeedSection(section)}
                  >
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        FEED_SECTION_CONFIG[section].dotClassName,
                        feedSection === section && "opacity-80"
                      )}
                    />
                    <span>{FEED_SECTION_CONFIG[section].label}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        feedSection === section ? "bg-white/15 text-white" : "bg-slate-100 text-slate-700"
                      )}
                    >
                      {feedCounts[section]}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {visibleFeedItems.length === 0 ? (
              <Card className="border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">
                {FEED_SECTION_CONFIG[feedSection].emptyState}
              </Card>
            ) : (
              <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <div className="overflow-x-auto">
                  <div className="min-w-[860px]">
                    <div className="grid grid-cols-[28px_minmax(200px,1fr)_130px_120px_52px_68px_78px] border-b border-slate-200 px-4 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      <div className="py-3.5" />
                      <div className="py-3.5">Metric</div>
                      <div className="py-3.5">Entity</div>
                      <div className="py-3.5">Assignee</div>
                      <div className="py-3.5" />
                      <div className="py-3.5">Status</div>
                      <div className="py-3.5" />
                    </div>

                    {visibleFeedItems.map((row) => {
                      const rowKey = buildRowKey(row);
                      const isSelected = selectedRowKey === rowKey;
                      const detailForRow = isSelected ? selectedDetail : null;
                      const valueMissing = !hasValue(detailForRow, row);
                      const methodologyRequired = Boolean(
                        detailForRow &&
                          methodologySelectionRequired(detailForRow, hasMethodologyCatalog)
                      );
                      const methodologySelected = Boolean(
                        detailForRow?.methodology?.trim() || row.methodology?.trim()
                      );
                      const evidenceItems = isSelected ? selectedEvidence ?? [] : [];
                      const evidenceCount =
                        detailForRow?.evidence_count ?? row.evidence_count ?? evidenceItems.length ?? 0;
                      const visibleEvidenceItems = evidenceItems.slice(0, 2);
                      const hasEvidenceItems = evidenceItems.length > 0 || evidenceCount > 0;
                      const rowStatus = getStatusBadgeMeta(
                        row,
                        detailForRow,
                        hasMethodologyCatalog
                      );
                      const actionMeta = getRowActionMeta(
                        row,
                        detailForRow,
                        hasMethodologyCatalog
                      );
                      const progressCount = getProgressCount(row, detailForRow);
                      const overdueLabel = getOverdueLabel(row.days_overdue);
                      const openingThisRow = openingRowId === (row.assignment_id ?? row.id);
                      const displayFrameworks = getDisplayFrameworks(
                        selectedDetail?.related_standards?.length
                          ? selectedDetail.related_standards
                          : row.standards.map((standard) => ({ code: standard, name: "" }))
                      );

                      return (
                        <div key={rowKey}>
                          <div
                            className={cn(
                              "grid cursor-pointer grid-cols-[28px_minmax(200px,1fr)_130px_120px_52px_68px_78px] items-center border-b border-slate-100 px-4 transition-colors hover:bg-slate-50",
                              row.days_overdue ? "border-l-4 border-l-red-500 pl-3" : "border-l-4 border-l-transparent",
                              isSelected && "bg-blue-50/70"
                            )}
                            onClick={() =>
                              setSelectedRowKey((current) => (current === rowKey ? null : rowKey))
                            }
                          >
                            <div className="flex items-center justify-center py-3">
                              <input
                                type="checkbox"
                                checked={checkedRowKeySet.has(rowKey)}
                                disabled={feedSection === "blocked" || feedSection === "submitted"}
                                onClick={(event) => event.stopPropagation()}
                                onChange={(event) => toggleCheckedRow(rowKey, event.target.checked)}
                                className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
                              />
                            </div>

                            <div className="py-3 pr-3">
                              <div className="flex items-center gap-2 text-[13px] font-medium leading-[1.25] text-slate-900">
                                <span className="truncate" title={row.element_name}>
                                  {row.element_name}
                                </span>
                                {overdueLabel && (
                                  <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.12em] text-red-500">
                                    {overdueLabel}
                                  </span>
                                )}
                              </div>
                              <div className="mt-0.5 truncate font-mono text-[10px] text-slate-400">
                                {row.element_code}
                              </div>
                            </div>

                            <div className="truncate py-3 pr-3 text-[11px] text-slate-500">
                              {formatContext(row)}
                            </div>

                            <div className="py-3 pr-3">
                              <div className="flex items-center gap-2 overflow-hidden">
                                <span
                                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white"
                                  style={getUserAvatarStyle(row.collector_id, row.collector_name)}
                                >
                                  {getUserInitials(row.collector_name)}
                                </span>
                                <span className="truncate text-[11px] text-slate-500">
                                  {row.collector_name ?? "Unassigned"}
                                </span>
                              </div>
                            </div>

                            <div className="py-3 pr-3">
                              <div className="flex items-center gap-1">
                                {Array.from({ length: 4 }).map((_, index) => (
                                  <span
                                    key={index}
                                    className={cn(
                                      "h-2 w-2 rounded-full",
                                      index < progressCount ? "bg-green-500" : "bg-slate-200"
                                    )}
                                  />
                                ))}
                                <span className="ml-1 text-[10px] font-medium text-slate-400">
                                  {progressCount}/4
                                </span>
                              </div>
                            </div>

                            <div className="py-3 pr-3">
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold",
                                  rowStatus.className
                                )}
                              >
                                {rowStatus.label}
                              </span>
                            </div>

                            <div className="flex justify-end py-3">
                              <Button
                                size="sm"
                                variant={actionMeta.variant}
                                disabled={openingThisRow}
                                className="h-7 min-w-[72px] px-2.5 text-[11px]"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  runRowAction(row, actionMeta.intent);
                                }}
                              >
                                {openingThisRow ? (
                                  <>
                                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    Opening...
                                  </>
                                ) : (
                                  actionMeta.label
                                )}
                              </Button>
                            </div>
                          </div>

                          {isSelected && (
                            <div className="border-b border-slate-200 bg-slate-50/80 py-3 pl-[34px] pr-3">
                              <div className="space-y-3.5">
                                <div className="max-w-[760px] space-y-3.5">
                                  <div className="text-[13px] font-semibold leading-[1.35] text-slate-900">
                                    {row.element_name} · {row.element_code}
                                  </div>

                                  <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
                                    <div>
                                      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                        Entity / Facility
                                      </div>
                                      <div className="mt-1 text-[11px] font-medium text-slate-900">
                                        {formatContext(row)}
                                      </div>
                                    </div>
                                    <div>
                                      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                        Boundary
                                      </div>
                                      <div className="mt-1 text-[11px] font-medium text-slate-900">
                                        {BOUNDARY_CONFIG[row.boundary_status].label} ·{" "}
                                        {row.consolidation_method.replace(/_/g, " ")}
                                      </div>
                                    </div>
                                    <div>
                                      <div
                                        className={cn(
                                          "text-[10px] font-semibold uppercase tracking-[0.16em]",
                                          valueMissing ? "text-red-400" : "text-slate-400"
                                        )}
                                      >
                                        Value
                                      </div>
                                      <div
                                        className={cn(
                                          "mt-1 text-[11px] font-medium",
                                          valueMissing ? "text-red-600" : "text-slate-900"
                                        )}
                                      >
                                        {getValuePreview(row, detailForRow)}
                                      </div>
                                    </div>
                                    <div>
                                      <div
                                        className={cn(
                                          "text-[10px] font-semibold uppercase tracking-[0.16em]",
                                          methodologyRequired && !methodologySelected
                                            ? "text-amber-500"
                                            : "text-slate-400"
                                        )}
                                      >
                                        Methodology
                                      </div>
                                      <div
                                        className={cn(
                                          "mt-1 text-[11px] font-medium",
                                          methodologySelected
                                            ? "text-slate-900"
                                            : methodologyRequired
                                              ? "text-amber-700"
                                              : "text-slate-400"
                                        )}
                                      >
                                        {detailForRow?.methodology ??
                                          row.methodology ??
                                          "Not selected"}
                                      </div>
                                    </div>
                                  </div>

                                  <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
                                    <div>
                                      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                        Frameworks
                                      </div>
                                      <div className="mt-2 flex flex-wrap gap-1.5">
                                        {displayFrameworks.map((standard) => (
                                          <span
                                            key={`${rowKey}-${standard.code}`}
                                            className={cn(
                                              "inline-flex max-w-full items-center rounded-full border px-2 py-0.5 text-[10px]",
                                              standard.tone === "framework"
                                                ? "border-slate-200 bg-white text-slate-600"
                                                : "border-slate-200 bg-slate-100 text-slate-500"
                                            )}
                                          >
                                            <span
                                              className={cn(
                                                "mr-1 font-mono font-semibold",
                                                standard.tone === "framework"
                                                  ? "text-slate-900"
                                                  : "text-slate-700"
                                              )}
                                            >
                                              {standard.code}
                                            </span>
                                            {standard.name ? (
                                              <span className="truncate">{standard.name}</span>
                                            ) : null}
                                          </span>
                                        ))}
                                      </div>
                                    </div>

                                    <div>
                                      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                                        Evidence
                                      </div>
                                      <div className="mt-2 space-y-2">
                                        {selectedDataPointId && selectedEvidenceLoading ? (
                                          <div className="flex items-center gap-2 text-[11px] text-slate-500">
                                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                            Loading evidence...
                                          </div>
                                        ) : hasEvidenceItems ? (
                                          <>
                                            <div className="text-[10px] text-slate-400">
                                              Linked evidence ({evidenceCount})
                                            </div>
                                            <div className="space-y-2">
                                              {(visibleEvidenceItems.length > 0
                                                ? visibleEvidenceItems
                                                : [
                                                    {
                                                      id: 0,
                                                      type: "file" as const,
                                                      title: `${evidenceCount} linked evidence`,
                                                    },
                                                  ]
                                              ).map((item) => (
                                                <div
                                                  key={`${rowKey}-evidence-${item.id}-${item.title}`}
                                                  className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-2.5 py-2"
                                                >
                                                  <button
                                                    type="button"
                                                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                                                    onClick={(event) => {
                                                      event.stopPropagation();
                                                      if (!selectedDataPointId || item.id === 0) {
                                                        openQuickEntry(row);
                                                        return;
                                                      }
                                                      openEvidencePreview(row, item);
                                                    }}
                                                  >
                                                    {item.type === "file" ? (
                                                      <FileText className="h-3.5 w-3.5 shrink-0 text-cyan-600" />
                                                    ) : (
                                                      <Link2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                                                    )}
                                                    <div className="min-w-0">
                                                      <div className="truncate text-[11px] font-medium text-slate-700">
                                                        {item.title || item.file_name || "Evidence item"}
                                                      </div>
                                                      {item.id !== 0 ? (
                                                        <div className="truncate text-[10px] text-slate-400">
                                                          Click to preview evidence details
                                                        </div>
                                                      ) : (
                                                        <div className="truncate text-[10px] text-slate-400">
                                                          Open this metric to manage linked evidence
                                                        </div>
                                                      )}
                                                    </div>
                                                  </button>

                                                  {item.id !== 0 ? (
                                                    <div className="flex items-center gap-1">
                                                      <button
                                                        type="button"
                                                        className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
                                                        title="Preview evidence"
                                                        onClick={(event) => {
                                                          event.stopPropagation();
                                                          openEvidencePreview(row, item);
                                                        }}
                                                      >
                                                        <Eye className="h-3.5 w-3.5" />
                                                      </button>
                                                      <button
                                                        type="button"
                                                        className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
                                                        title={
                                                          item.type === "file"
                                                            ? "Download evidence"
                                                            : "Open evidence link"
                                                        }
                                                        onClick={(event) => {
                                                          event.stopPropagation();
                                                          if (item.type === "file") {
                                                            void triggerFileDownload(
                                                              `/api/evidences/${item.id}/download`
                                                            );
                                                            return;
                                                          }
                                                          if (item.url) {
                                                            window.open(item.url, "_blank");
                                                          }
                                                        }}
                                                      >
                                                        {item.type === "file" ? (
                                                          <Download className="h-3.5 w-3.5" />
                                                        ) : (
                                                          <ExternalLink className="h-3.5 w-3.5" />
                                                        )}
                                                      </button>
                                                    </div>
                                                  ) : null}
                                                </div>
                                              ))}
                                            </div>

                                            <div className="flex flex-wrap items-center gap-3">
                                              <Button
                                                type="button"
                                                size="sm"
                                                variant="outline"
                                                className="h-7 px-2.5 text-[11px]"
                                                onClick={(event) => {
                                                  event.stopPropagation();
                                                  openEvidenceRepository(evidenceItems[0]?.id);
                                                }}
                                              >
                                                Manage evidence
                                              </Button>
                                              {evidenceItems.length > 2 && (
                                                <button
                                                  type="button"
                                                  className="text-[10px] font-medium text-slate-500 transition hover:text-slate-700"
                                                  onClick={(event) => {
                                                    event.stopPropagation();
                                                    openEvidenceRepository(evidenceItems[0]?.id);
                                                  }}
                                                >
                                                  +{evidenceItems.length - 2} more in repository
                                                </button>
                                              )}
                                            </div>
                                          </>
                                        ) : (
                                          <div className="flex flex-wrap items-center gap-3">
                                            <span className="text-[11px] font-medium text-amber-700">
                                              Missing evidence
                                            </span>
                                            <Button
                                              type="button"
                                              size="sm"
                                              variant="outline"
                                              className="h-7 border-amber-200 px-2.5 text-[11px] text-amber-700 hover:bg-amber-50 hover:text-amber-800"
                                              onClick={(event) => {
                                                event.stopPropagation();
                                                openQuickEntry(row);
                                              }}
                                            >
                                              <Plus className="h-3.5 w-3.5" />
                                              Add evidence
                                            </Button>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>

                                  <div
                                    className={cn(
                                      "flex items-center gap-2 text-[11px] font-medium",
                                      getFeedSection(row, detailForRow, hasMethodologyCatalog) ===
                                        "blocked"
                                        ? "text-red-700"
                                        : "text-amber-700"
                                    )}
                                  >
                                    <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
                                    <span>
                                      {getFeedSection(row, detailForRow, hasMethodologyCatalog) ===
                                      "blocked"
                                        ? getBlockingReason(row)
                                        : getNeedsText(row, detailForRow, hasMethodologyCatalog)}
                                    </span>
                                  </div>
                                </div>

                                <div className="flex justify-end pt-1 pr-1">
                                  <Button
                                    size="sm"
                                    variant={actionMeta.variant}
                                    disabled={openingThisRow}
                                    className="h-8 min-w-[88px] px-3 text-[11px]"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      runRowAction(row, actionMeta.intent);
                                    }}
                                  >
                                    {openingThisRow ? (
                                      <>
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        Opening...
                                      </>
                                    ) : (
                                      actionMeta.label
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          )}

                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
      ) : (
        <Card id="collection-table" className="border-slate-200">
          <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full max-w-md">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by metric code or name..."
                className="h-9 rounded-lg border-slate-200 pl-8 text-sm"
              />
            </div>
            {hasActiveFilters ? (
              <Button variant="ghost" size="sm" onClick={resetFilters}>
                Reset filters
              </Button>
            ) : null}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">
                    <button
                      onClick={() => toggleSort("element_code")}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                    >
                      Metric Code
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      onClick={() => toggleSort("element_name")}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                    >
                      Metric
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      onClick={() => toggleSort("collection_status")}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                    >
                      Progress
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3">Entity</th>
                  <th className="px-4 py-3">Responsible</th>
                  <th className="px-4 py-3">Facility</th>
                  <th className="px-4 py-3">Reporting Boundary</th>
                  <th className="px-4 py-3">Consolidation</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                      {emptyTableMessage}
                    </td>
                  </tr>
                ) : (
                  filtered.map((row) => {
                    const rowKey = buildRowKey(row);
                    const boundaryConfig = BOUNDARY_CONFIG[row.boundary_status];
                    const isRowOpening = openingRowId === (row.assignment_id ?? row.id);

                    return (
                      <tr
                        key={rowKey}
                        className="cursor-pointer transition-colors hover:bg-slate-50"
                        onClick={() => {
                          setSelectedRowKey(rowKey);
                          void openDataEntry(row);
                        }}
                      >
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">
                          {row.element_code}
                        </td>
                        <td className="px-4 py-3">
                          <div className="space-y-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium text-slate-900">{row.element_name}</span>
                              {row.reused_across_standards && (
                                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                  <Repeat2 className="mr-0.5 h-3 w-3" />
                                  Used in {row.standards.length} standards
                                </Badge>
                              )}
                            </div>
                            {row.standards.length > 0 && (
                              <div className="space-y-1">
                                <div className="flex flex-wrap gap-1.5">
                                  {row.standards.map((standard) => (
                                    <Badge
                                      key={`${rowKey}-${standard}`}
                                      variant="outline"
                                      className="text-[10px] uppercase tracking-wide"
                                    >
                                      {standard}
                                    </Badge>
                                  ))}
                                </div>
                                {row.reused_across_standards && (
                                  <p className="text-xs text-slate-500">
                                    One shared data point stays in sync across these linked standards.
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {(() => {
                            const rowStatus = getStatusBadgeMeta(
                              row,
                              undefined,
                              hasMethodologyCatalog
                            );
                            return (
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold",
                                  rowStatus.className
                                )}
                              >
                                {rowStatus.label}
                              </span>
                            );
                          })()}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{row.entity_name}</td>
                        <td className="px-4 py-3 text-slate-600">
                          {row.collector_name ?? "—"}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{row.facility_name ?? "—"}</td>
                        <td className="px-4 py-3">
                          <Badge variant={boundaryConfig.variant}>{boundaryConfig.label}</Badge>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{row.consolidation_method}</td>
                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isRowOpening}
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedRowKey(rowKey);
                              void openDataEntry(row);
                            }}
                          >
                            {isRowOpening ? (
                              <>
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                Opening...
                              </>
                            ) : (
                              "Enter data"
                            )}
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
            Showing {filtered.length} of {items.length} data points
          </div>
        </Card>
      )}

      <Dialog
        open={Boolean(evidencePreviewTarget)}
        onOpenChange={(open) => {
          if (!open) {
            setEvidencePreviewTarget(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          {activeEvidencePreview ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {activeEvidencePreview.type === "file" ? (
                    <FileText className="h-5 w-5 text-cyan-500" />
                  ) : (
                    <Link2 className="h-5 w-5 text-emerald-500" />
                  )}
                  {activeEvidencePreview.title || activeEvidencePreview.file_name || "Evidence"}
                </DialogTitle>
                <DialogDescription>
                  {activeEvidencePreview.description?.trim() ||
                    "Review this evidence, download it, or open it in the evidence repository."}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                {evidencePreviewLoading ? (
                  <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading evidence details...
                  </div>
                ) : null}

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <div className="text-xs font-medium text-slate-500">Type</div>
                    <div className="mt-1 text-sm capitalize text-slate-900">
                      {activeEvidencePreview.type}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-500">Binding status</div>
                    <div className="mt-1">
                      <Badge
                        variant={
                          activeEvidencePreview.binding_status === "bound"
                            ? "success"
                            : "secondary"
                        }
                      >
                        {activeEvidencePreview.binding_status ?? "linked"}
                      </Badge>
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-500">Uploaded</div>
                    <div className="mt-1 text-sm text-slate-900">
                      {formatEvidenceDate(activeEvidencePreview.upload_date)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-500">Created by</div>
                    <div className="mt-1 text-sm text-slate-900">
                      {activeEvidencePreview.created_by_name ?? "Unknown"}
                    </div>
                  </div>
                </div>

                {activeEvidencePreview.type === "file" ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="text-xs font-medium text-slate-500">File</div>
                    <div className="mt-1 text-sm font-medium text-slate-900">
                      {activeEvidencePreview.file_name ??
                        activeEvidencePreview.title ??
                        "Attached file"}
                    </div>
                    {formatFileSize(activeEvidencePreview.file_size) ? (
                      <div className="mt-1 text-xs text-slate-500">
                        {formatFileSize(activeEvidencePreview.file_size)}
                        {activeEvidencePreview.mime_type
                          ? ` · ${activeEvidencePreview.mime_type}`
                          : ""}
                      </div>
                    ) : null}
                  </div>
                ) : activeEvidencePreview.url ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="text-xs font-medium text-slate-500">Link</div>
                    <a
                      href={activeEvidencePreview.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-cyan-700 hover:underline"
                    >
                      {activeEvidencePreview.url}
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </div>
                ) : null}

                <div>
                  <div className="text-xs font-medium text-slate-500">
                    Linked data points (
                    {(activeEvidencePreview.linked_data_points ?? []).length})
                  </div>
                  {(activeEvidencePreview.linked_data_points ?? []).length === 0 ? (
                    <div className="mt-1 text-xs text-slate-400">None</div>
                  ) : (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(activeEvidencePreview.linked_data_points ?? []).map((point) => (
                        <Badge key={point.data_point_id} variant="outline" className="text-[10px]">
                          {point.code} · {point.label}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <DialogFooter className="gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    if (!activeEvidencePreview) return;
                    setEvidencePreviewTarget(null);
                    openEvidenceRepository(activeEvidencePreview.id);
                  }}
                >
                  Manage evidence
                </Button>
                {activeEvidencePreview.type === "file" ? (
                  <Button
                    type="button"
                    onClick={() => {
                      void triggerFileDownload(
                        `/api/evidences/${activeEvidencePreview.id}/download`
                      );
                    }}
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </Button>
                ) : (
                  <Button
                    type="button"
                    onClick={() => {
                      if (activeEvidencePreview.url) {
                        window.open(activeEvidencePreview.url, "_blank");
                      }
                    }}
                  >
                    <ExternalLink className="h-4 w-4" />
                    Open link
                  </Button>
                )}
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
