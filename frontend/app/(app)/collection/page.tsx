"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpDown,
  CheckCircle2,
  Circle,
  Filter,
  Loader2,
  Repeat2,
  Rows3,
  Search,
  ShieldAlert,
  Sparkles,
  Table2,
  TriangleAlert,
} from "lucide-react";

import { api, type AppApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useActiveProject } from "@/lib/hooks/use-active-project";
import { useApiQuery } from "@/lib/hooks/use-api";
import { GuidedEntryDialog } from "./components/guided-entry-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type DataPointStatus = "missing" | "partial" | "complete";
type BoundaryStatus = "included" | "excluded" | "partial";
type FeedSection = "action" | "blocked" | "done" | "all";
type ViewMode = "feed" | "table";
type ReadinessTone = "done" | "pending" | "warning";

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

interface ReadinessItem {
  label: string;
  tone: ReadinessTone;
}

const STATUS_CONFIG: Record<
  DataPointStatus,
  { label: string; variant: "destructive" | "warning" | "success" }
> = {
  missing: { label: "Not started", variant: "destructive" },
  partial: { label: "In progress", variant: "warning" },
  complete: { label: "Complete", variant: "success" },
};

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
  done: {
    label: "Completed",
    dotClassName: "bg-green-500",
    emptyState: "No completed collection rows match the current filters.",
  },
  all: {
    label: "All tasks",
    dotClassName: "bg-slate-400",
    emptyState: "No collection rows match the current filters.",
  },
};

const FEED_SECTION_ORDER: FeedSection[] = ["action", "blocked", "done", "all"];

function buildContextKey(
  sharedElementId?: number | null,
  entityId?: number | null,
  facilityId?: number | null
) {
  return [sharedElementId ?? 0, entityId ?? 0, facilityId ?? 0].join(":");
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

function getFeedSection(row: DataPoint): FeedSection {
  if (row.boundary_status !== "included") return "blocked";
  if (row.collection_status === "complete") return "done";
  return "action";
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
  if (row.boundary_status === "excluded") {
    return "Excluded from reporting boundary";
  }
  if (row.boundary_status === "partial") {
    return "Boundary review recommended";
  }

  const missing: string[] = [];
  if (!hasCreatedEntry(row)) missing.push("Draft");
  if (!hasValue(detail, row)) missing.push("Value");
  if (detail && !hasMethodology(detail, row, hasMethodologyCatalog)) {
    missing.push("Methodology");
  }
  if (!hasEvidence(detail, row)) missing.push("Evidence");
  if (missing.length > 0) return missing.join(", ");
  if (!detail && row.collection_status !== "complete") return "Continue entry";
  return "All required inputs look complete";
}

function getProgressCount(row: DataPoint, detail?: DataPointDetail | null) {
  let count = 0;
  if (hasCreatedEntry(row)) count += 1;
  if (row.boundary_status === "included") count += 1;
  if (hasValue(detail, row)) count += 1;
  if (hasEvidence(detail, row)) count += 1;
  return count;
}

function formatContext(row: Pick<DataPoint, "entity_name" | "facility_name">) {
  return row.facility_name ? `${row.entity_name} / ${row.facility_name}` : row.entity_name;
}

function ReadinessIcon({ tone }: { tone: ReadinessTone }) {
  if (tone === "done") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-md bg-green-500 text-white">
        <CheckCircle2 className="h-3.5 w-3.5" />
      </span>
    );
  }

  if (tone === "warning") {
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-md border border-amber-300 bg-amber-50 text-amber-700">
        <TriangleAlert className="h-3.5 w-3.5" />
      </span>
    );
  }

  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-400">
      <Circle className="h-3.5 w-3.5" />
    </span>
  );
}

export default function CollectionPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const {
    activeProject,
    projectId,
    isLoading: projectsLoading,
    error: projectsError,
  } = useActiveProject("collection");

  const [openingRowId, setOpeningRowId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [guidedField, setGuidedField] = useState<FormConfigField | null>(null);
  const [guidedRowKey, setGuidedRowKey] = useState<string | null>(null);
  const [resolvedDataPointIds, setResolvedDataPointIds] = useState<Record<string, number>>({});
  const [configActionMessage, setConfigActionMessage] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("feed");
  const [feedSection, setFeedSection] = useState<FeedSection>("action");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [selectedRowKey, setSelectedRowKey] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DataPointStatus>("all");
  const [boundaryFilter, setBoundaryFilter] = useState<"all" | BoundaryStatus>("all");
  const [entityFilter, setEntityFilter] = useState("");
  const [standardFilter, setStandardFilter] = useState("");
  const [sortField, setSortField] = useState<
    "element_code" | "element_name" | "collection_status"
  >("element_code");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");

  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) =>
    ["collector", "esg_manager", "admin", "platform_admin"].includes(role)
  );

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

  const {
    data: activeFormConfig,
    isLoading: configLoading,
    error: configError,
  } = useApiQuery<ActiveFormConfig | null>(
    ["active-form-config", projectId],
    `/form-configs/projects/${projectId}/active`,
    { enabled: canAccess && projectId !== null }
  );

  const { data: methodologies } = useApiQuery<MethodologyReference[]>(
    ["reference-methodologies"],
    "/references/methodologies",
    { enabled: canAccess }
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
      } satisfies DataPoint;
    });
  }, [assignmentsData?.assignments, data?.items, resolvedDataPointIds]);

  const accessDenied =
    (Boolean(me) && !canAccess) ||
    (!!projectsError && isForbidden(projectsError)) ||
    (!!assignmentsError && isForbidden(assignmentsError)) ||
    (!!error && isForbidden(error));

  const rowsByElement = useMemo(() => {
    const map = new Map<number, DataPoint[]>();
    for (const item of items) {
      if (!item.shared_element_id) continue;
      const current = map.get(item.shared_element_id) ?? [];
      current.push(item);
      map.set(item.shared_element_id, current);
    }
    return map;
  }, [items]);

  const rowsByAssignment = useMemo(() => {
    const map = new Map<number, DataPoint>();
    for (const item of items) {
      if (item.assignment_id) {
        map.set(item.assignment_id, item);
      }
    }
    return map;
  }, [items]);

  const rowsByContext = useMemo(() => {
    const map = new Map<string, DataPoint[]>();
    for (const item of items) {
      const key = buildContextKey(
        item.shared_element_id ?? 0,
        item.entity_id ?? 0,
        item.facility_id ?? 0
      );
      const current = map.get(key) ?? [];
      current.push(item);
      map.set(key, current);
    }
    return map;
  }, [items]);

  const resolveFieldMatches = useCallback(
    (field: FormConfigField) => {
      if (field.assignment_id) {
        const match = rowsByAssignment.get(field.assignment_id);
        return match ? [match] : [];
      }
      if (field.entity_id != null || field.facility_id != null) {
        return (
          rowsByContext.get(
            buildContextKey(
              field.shared_element_id,
              field.entity_id ?? 0,
              field.facility_id ?? 0
            )
          ) ?? []
        );
      }
      return rowsByElement.get(field.shared_element_id) ?? [];
    },
    [rowsByAssignment, rowsByContext, rowsByElement]
  );

  const entities = useMemo(
    () => Array.from(new Set(items.map((item) => item.entity_name))).sort(),
    [items]
  );
  const standards = useMemo(
    () => Array.from(new Set(items.flatMap((item) => item.standards ?? []))).sort(),
    [items]
  );

  const filtered = useMemo(() => {
    let result = items;

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
        [item.element_code, item.element_name, item.entity_name, item.facility_name ?? ""]
          .join(" ")
          .toLowerCase()
          .includes(query)
      );
    }

    return [...result].sort((left, right) => {
      const leftValue = String(left[sortField] ?? "");
      const rightValue = String(right[sortField] ?? "");
      const comparison = leftValue.localeCompare(rightValue);
      return sortDir === "asc" ? comparison : -comparison;
    });
  }, [
    items,
    statusFilter,
    boundaryFilter,
    entityFilter,
    standardFilter,
    search,
    sortField,
    sortDir,
  ]);

  const orderedFeedItems = useMemo(() => {
    const priority: Record<FeedSection, number> = {
      action: 0,
      blocked: 1,
      done: 2,
      all: 3,
    };

    return [...filtered].sort((left, right) => {
      const sectionCompare = priority[getFeedSection(left)] - priority[getFeedSection(right)];
      if (sectionCompare !== 0) return sectionCompare;

      const leftValue = String(left[sortField] ?? "");
      const rightValue = String(right[sortField] ?? "");
      const comparison = leftValue.localeCompare(rightValue);
      return sortDir === "asc" ? comparison : -comparison;
    });
  }, [filtered, sortField, sortDir]);

  const feedCounts = useMemo(() => {
    return orderedFeedItems.reduce(
      (current, item) => {
        current[getFeedSection(item)] += 1;
        current.all += 1;
        return current;
      },
      { action: 0, blocked: 0, done: 0, all: 0 } satisfies Record<FeedSection, number>
    );
  }, [orderedFeedItems]);

  useEffect(() => {
    if (feedCounts[feedSection] > 0 || feedCounts.all === 0) return;
    const next = FEED_SECTION_ORDER.find((section) => feedCounts[section] > 0) ?? "all";
    setFeedSection(next);
  }, [feedCounts, feedSection]);

  const visibleFeedItems = useMemo(() => {
    if (feedSection === "all") return orderedFeedItems;
    return orderedFeedItems.filter((item) => getFeedSection(item) === feedSection);
  }, [feedSection, orderedFeedItems]);

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

  const filteredRowKeys = useMemo(() => new Set(filtered.map((item) => buildRowKey(item))), [filtered]);

  useEffect(() => {
    if (!selectedRowKey) return;
    if (!filteredRowKeys.has(selectedRowKey)) {
      setSelectedRowKey(null);
    }
  }, [filteredRowKeys, selectedRowKey]);

  useEffect(() => {
    if (viewMode !== "feed" || !selectedRowKey) return;
    if (!visibleFeedRowKeys.has(selectedRowKey)) {
      setSelectedRowKey(null);
    }
  }, [selectedRowKey, viewMode, visibleFeedRowKeys]);

  const selectedRow = selectedRowKey ? rowsByKey.get(selectedRowKey) ?? null : null;
  const selectedDataPointId = selectedRow ? getResolvedDataPointId(selectedRow) : null;

  const {
    data: selectedDetail,
    isLoading: selectedDetailLoading,
    error: selectedDetailError,
  } = useApiQuery<DataPointDetail>(
    ["collection-selected-detail", selectedDataPointId],
    `/data-points/${selectedDataPointId}`,
    { enabled: canAccess && Boolean(selectedDataPointId) }
  );

  const readinessItems = useMemo<ReadinessItem[]>(() => {
    if (!selectedRow) return [];

    const contextTone: ReadinessTone =
      selectedRow.boundary_status === "included"
        ? "done"
        : selectedRow.boundary_status === "partial"
          ? "warning"
          : "warning";

    return [
      { label: "Draft created", tone: hasCreatedEntry(selectedRow) ? "done" : "pending" },
      { label: "Value entered", tone: hasValue(selectedDetail, selectedRow) ? "done" : "pending" },
      {
        label: "Methodology selected",
        tone: hasMethodology(selectedDetail, selectedRow, hasMethodologyCatalog)
          ? "done"
          : "pending",
      },
      {
        label: "Evidence attached",
        tone: hasEvidence(selectedDetail, selectedRow) ? "done" : "pending",
      },
      {
        label:
          selectedRow.boundary_status === "included"
            ? "Context in boundary"
            : selectedRow.boundary_status === "partial"
              ? "Boundary needs review"
              : "Outside reporting boundary",
        tone: contextTone,
      },
    ];
  }, [hasMethodologyCatalog, selectedDetail, selectedRow]);

  const missingReadinessCount = readinessItems.filter((item) => item.tone !== "done").length;
  const hasActiveFilters =
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

  const scrollToTable = useCallback(() => {
    if (typeof window === "undefined") return;
    window.setTimeout(() => {
      document.getElementById("collection-table")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 50);
  }, []);

  const showFieldInTable = useCallback(
    (sharedElementId?: number) => {
      const firstMatch = sharedElementId ? rowsByElement.get(sharedElementId)?.[0] : undefined;
      if (firstMatch) {
        setSearch(firstMatch.element_code || firstMatch.element_name);
        setSelectedRowKey(buildRowKey(firstMatch));
      }
      setViewMode("table");
      scrollToTable();
    },
    [rowsByElement, scrollToTable]
  );

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
    setSelectedRowKey(rowKey);
  }, []);

  const openDataEntry = async (row: DataPoint) => {
    setActionError(null);

    if (row.data_point_id) {
      router.push(`/collection/${row.data_point_id}?projectId=${projectId}`);
      return;
    }

    const resolvedDataPointId = getResolvedDataPointId(row);
    if (resolvedDataPointId) {
      router.push(`/collection/${resolvedDataPointId}?projectId=${projectId}`);
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
      router.push(`/collection/${created.id}?projectId=${projectId}`);
    } catch (openError) {
      setActionError(
        openError instanceof Error
          ? openError.message
          : "Unable to open data entry for this row. Please try again."
      );
    } finally {
      setOpeningRowId(null);
    }
  };

  const resumeGuidedSession = useCallback(() => {
    const steps = activeFormConfig?.config?.steps ?? [];
    if (steps.length === 0) return;

    setConfigActionMessage(null);

    for (const step of steps) {
      for (const field of step.fields.filter((entry) => entry.visible)) {
        const matches = resolveFieldMatches(field);
        if (matches.length === 1 && matches[0].collection_status !== "complete") {
          openQuickEntry(matches[0], field.help_text);
          return;
        }
        if (matches.length > 1) {
          showFieldInTable(field.shared_element_id);
          setConfigActionMessage(
            "This guided field maps to multiple contexts, so the table view was opened for a precise selection."
          );
          return;
        }
      }
    }

    setConfigActionMessage("All guided collection fields currently look complete.");
  }, [activeFormConfig, openQuickEntry, resolveFieldMatches, showFieldInTable]);

  const resetFilters = () => {
    setSearch("");
    setStatusFilter("all");
    setBoundaryFilter("all");
    setEntityFilter("");
    setStandardFilter("");
    setSortField("element_code");
    setSortDir("asc");
  };

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
    <div className="space-y-6">
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

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Data Collection</h2>
          <p className="mt-1 text-sm text-slate-500">
            {activeProject?.name ?? `Project #${projectId}`} · {roleLabel}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!configLoading && !configError && activeFormConfig?.config?.steps?.length ? (
            <Button size="sm" variant="outline" onClick={() => resumeGuidedSession()}>
              <Sparkles className="h-4 w-4" />
              Guided mode
            </Button>
          ) : null}
          <Button
            size="sm"
            variant={viewMode === "feed" ? "secondary" : "outline"}
            onClick={() => setViewMode("feed")}
          >
            <Rows3 className="h-4 w-4" />
            Task feed
          </Button>
          <Button
            size="sm"
            variant={viewMode === "table" ? "secondary" : "outline"}
            onClick={() => setViewMode("table")}
          >
            <Table2 className="h-4 w-4" />
            Table view
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {configActionMessage && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {configActionMessage}
        </div>
      )}

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="relative max-w-xl flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search metrics, codes, entities, or facilities..."
            className="pl-9"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600">
            {roles.includes("collector") ? "Your assigned work" : "Project-wide collection"}
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={() => setFiltersOpen((current) => !current)}
            aria-label="Toggle advanced filters"
          >
            <Filter className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {(filtersOpen || hasActiveFilters) && (
        <Card className="border-slate-200 p-4">
          <div className="grid gap-4 xl:grid-cols-6">
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">Status</label>
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
              >
                <option value="all">All statuses</option>
                <option value="missing">Not started</option>
                <option value="partial">In progress</option>
                <option value="complete">Complete</option>
              </select>
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">Boundary</label>
              <select
                value={boundaryFilter}
                onChange={(event) => setBoundaryFilter(event.target.value as typeof boundaryFilter)}
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
              >
                <option value="all">All contexts</option>
                <option value="included">Included</option>
                <option value="partial">Partial</option>
                <option value="excluded">Excluded</option>
              </select>
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">Entity</label>
              <select
                value={entityFilter}
                onChange={(event) => setEntityFilter(event.target.value)}
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
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
              <label className="text-sm font-medium text-slate-700">Standard</label>
              <select
                value={standardFilter}
                onChange={(event) => setStandardFilter(event.target.value)}
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
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
              <label className="text-sm font-medium text-slate-700">Sort by</label>
              <select
                value={sortField}
                onChange={(event) => setSortField(event.target.value as typeof sortField)}
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
              >
                <option value="element_code">Metric code</option>
                <option value="element_name">Metric name</option>
                <option value="collection_status">Progress</option>
              </select>
            </div>

            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">Order</label>
              <div className="flex items-center gap-2">
                <select
                  value={sortDir}
                  onChange={(event) => setSortDir(event.target.value as typeof sortDir)}
                  className="h-9 flex-1 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                >
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
                <Button variant="ghost" size="sm" onClick={resetFilters}>
                  Reset
                </Button>
              </div>
            </div>
          </div>
        </Card>
      )}

      {meLoading || assignmentsLoading || isLoading ? (
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
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
              <div className="grid grid-cols-2 sm:grid-cols-4">
                {FEED_SECTION_ORDER.map((section) => (
                  <button
                    key={section}
                    type="button"
                    className={cn(
                      "flex items-center justify-center gap-2 border-r border-slate-200 px-4 py-3 text-sm font-medium text-slate-500 transition-colors last:border-r-0 hover:bg-slate-50",
                      feedSection === section && "bg-slate-900 text-white hover:bg-slate-900"
                    )}
                    onClick={() => setFeedSection(section)}
                  >
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-full",
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
              <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {visibleFeedItems.map((row) => {
                  const rowKey = buildRowKey(row);
                  const statusConfig = STATUS_CONFIG[row.collection_status];
                  const boundaryConfig = BOUNDARY_CONFIG[row.boundary_status];
                  const cardSection = getFeedSection(row);
                  const progressCount = getProgressCount(row);
                  const needsText = getNeedsText(row, undefined, hasMethodologyCatalog);
                  const isSelected = selectedRowKey === rowKey;
                  const valuePreview = getValuePreview(row);
                  const actionLabel =
                    cardSection === "blocked"
                      ? "Review"
                      : row.collection_status === "complete"
                        ? "Open"
                        : hasCreatedEntry(row)
                          ? "Continue"
                          : "Start";

                  return (
                    <Card
                      key={rowKey}
                      className={cn(
                        "flex h-full cursor-pointer flex-col justify-between border-slate-200 p-5 transition-all hover:border-cyan-300 hover:shadow-md",
                        isSelected && "border-cyan-400 shadow-md ring-2 ring-cyan-100"
                      )}
                      onClick={() => setSelectedRowKey(rowKey)}
                    >
                      <div className="space-y-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h3 className="line-clamp-2 text-base font-semibold text-slate-900">
                              {row.element_name}
                            </h3>
                            <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
                              {row.element_code}
                            </p>
                          </div>
                          <Badge variant={statusConfig.variant}>{statusConfig.label}</Badge>
                        </div>

                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Reported value
                          </p>
                          <p
                            className={cn(
                              "mt-2 text-xl font-semibold text-slate-900",
                              !hasValue(undefined, row) && "text-slate-400"
                            )}
                          >
                            {valuePreview}
                          </p>
                          <p className="mt-2 text-sm text-slate-500">{formatContext(row)}</p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          {row.standards.map((standard) => (
                            <Badge
                              key={`${rowKey}-${standard}`}
                              variant="outline"
                              className="text-[10px] uppercase tracking-wide"
                            >
                              {standard}
                            </Badge>
                          ))}
                          <Badge variant={boundaryConfig.variant}>{boundaryConfig.label}</Badge>
                          {row.reused_across_standards && (
                            <Badge variant="secondary" className="text-[10px]">
                              <Repeat2 className="mr-1 h-3 w-3" />
                              Reused
                            </Badge>
                          )}
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded-lg border border-slate-200 px-3 py-2">
                            <p className="text-slate-500">Draft</p>
                            <p className="mt-1 font-medium text-slate-900">
                              {hasCreatedEntry(row) ? "Created" : "Missing"}
                            </p>
                          </div>
                          <div className="rounded-lg border border-slate-200 px-3 py-2">
                            <p className="text-slate-500">Evidence</p>
                            <p className="mt-1 font-medium text-slate-900">
                              {row.evidence_required
                                ? `${row.evidence_count ?? 0} attached`
                                : "Not required"}
                            </p>
                          </div>
                        </div>

                        <div
                          className={cn(
                            "flex items-center gap-2 text-xs font-medium",
                            cardSection === "blocked" ? "text-red-700" : "text-amber-700"
                          )}
                        >
                          <TriangleAlert className="h-4 w-4 shrink-0" />
                          <span>{needsText}</span>
                        </div>
                      </div>

                      <div className="mt-5 flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
                        <div className="flex items-center gap-1">
                          {Array.from({ length: 4 }).map((_, index) => (
                            <span
                              key={index}
                              className={cn(
                                "h-2.5 w-2.5 rounded-full",
                                index < progressCount ? "bg-green-500" : "bg-slate-200"
                              )}
                            />
                          ))}
                          <span className="ml-1 text-xs font-medium text-slate-500">
                            {progressCount}/4
                          </span>
                        </div>

                        <Button
                          size="sm"
                          variant={cardSection === "blocked" ? "outline" : "default"}
                          onClick={(event) => {
                            event.stopPropagation();
                            setSelectedRowKey(rowKey);
                            if (cardSection === "blocked") return;
                            if (row.collection_status === "complete") {
                              void openDataEntry(row);
                              return;
                            }
                            openQuickEntry(row);
                          }}
                        >
                          {actionLabel}
                        </Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>

          <aside className="xl:sticky xl:top-6 xl:self-start">
            <Card className="overflow-hidden border-slate-200">
              {!selectedRow ? (
                <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 p-6 text-center text-sm text-slate-500">
                  <Rows3 className="h-8 w-8 text-slate-300" />
                  Click any task to see readiness and next actions.
                </div>
              ) : (
                <div className="space-y-5 p-5">
                  <div className="space-y-1">
                    <h3 className="text-base font-semibold text-slate-900">
                      {selectedRow.element_name}
                    </h3>
                    <p className="font-mono text-xs text-slate-500">{selectedRow.element_code}</p>
                  </div>

                  <p className="text-sm text-slate-600">{formatContext(selectedRow)}</p>

                  <div className="rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Current value
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-slate-900">
                      {getValuePreview(selectedRow, selectedDetail)}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {(selectedDetail?.related_standards?.length
                      ? selectedDetail.related_standards.map((standard) => standard.code)
                      : selectedRow.standards
                    ).map((standard) => (
                      <Badge key={`${selectedRowKey}-${standard}`} variant="outline" className="text-[10px] uppercase tracking-wide">
                        {standard}
                      </Badge>
                    ))}
                    <Badge variant={BOUNDARY_CONFIG[selectedRow.boundary_status].variant}>
                      {BOUNDARY_CONFIG[selectedRow.boundary_status].label}
                    </Badge>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Readiness
                      </p>
                      {selectedDetailLoading && (
                        <div className="flex items-center gap-1 text-xs text-slate-400">
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Loading
                        </div>
                      )}
                    </div>

                    <div className="space-y-3">
                      {readinessItems.map((item) => (
                        <div
                          key={item.label}
                          className="flex items-center gap-3 border-b border-slate-200/80 pb-3 last:border-b-0 last:pb-0"
                        >
                          <ReadinessIcon tone={item.tone} />
                          <span className="text-sm text-slate-700">{item.label}</span>
                        </div>
                      ))}
                    </div>

                    <div className="mt-4 flex items-center justify-between border-t border-slate-200 pt-3">
                      <span className="text-xs text-slate-500">Missing</span>
                      <span className="text-sm font-semibold text-amber-700">
                        {missingReadinessCount}
                      </span>
                    </div>
                  </div>

                  {selectedRow.boundary_status !== "included" && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      This row is not fully inside the reporting boundary, so it should be reviewed before submission.
                    </div>
                  )}

                  {selectedDetailError && (
                    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                      {selectedDetailError.message}
                    </div>
                  )}

                  <div className="space-y-2">
                    <Button
                      className="w-full"
                      disabled={selectedRow.boundary_status === "excluded"}
                      onClick={() => {
                        if (selectedRow.collection_status === "complete") {
                          void openDataEntry(selectedRow);
                          return;
                        }
                        openQuickEntry(selectedRow);
                      }}
                    >
                      {selectedRow.collection_status === "complete"
                        ? "Open entry"
                        : hasCreatedEntry(selectedRow)
                          ? "Continue quick entry"
                          : "Start quick entry"}
                    </Button>

                    <Button
                      className="w-full"
                      variant="ghost"
                      disabled={
                        selectedRow.boundary_status === "excluded" &&
                        !getResolvedDataPointId(selectedRow)
                      }
                      onClick={() => void openDataEntry(selectedRow)}
                    >
                      Open full wizard
                      <ArrowRight className="h-4 w-4" />
                    </Button>

                    <Button
                      className="w-full"
                      variant="ghost"
                      onClick={() => {
                        setViewMode("table");
                        scrollToTable();
                      }}
                    >
                      Show in table
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          </aside>
        </div>
      ) : (
        <Card id="collection-table" className="border-slate-200">
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
                  <th className="px-4 py-3">Facility</th>
                  <th className="px-4 py-3">Reporting Boundary</th>
                  <th className="px-4 py-3">Consolidation</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                      {emptyTableMessage}
                    </td>
                  </tr>
                ) : (
                  filtered.map((row) => {
                    const rowKey = buildRowKey(row);
                    const statusConfig = STATUS_CONFIG[row.collection_status];
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
                                  Reused
                                </Badge>
                              )}
                            </div>
                            {row.standards.length > 0 && (
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
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={statusConfig.variant}>{statusConfig.label}</Badge>
                        </td>
                        <td className="px-4 py-3 text-slate-600">{row.entity_name}</td>
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
    </div>
  );
}
