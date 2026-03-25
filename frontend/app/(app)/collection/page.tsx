"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Search,
  Filter,
  ArrowUpDown,
  Repeat2,
  RefreshCcw,
  AlertTriangle,
  Loader2,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/lib/api";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { GuidedEntryDialog } from "./components/guided-entry-dialog";
import { WizardRenderer } from "./components/wizard-renderer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

/* ---------- Types ---------- */

type DataPointStatus = "missing" | "partial" | "complete";
type BoundaryStatus = "included" | "excluded" | "partial";

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
}

interface DataPointsResponse {
  items: DataPoint[];
  total: number;
}

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

/* ---------- Helpers ---------- */

const STATUS_CONFIG: Record<
  DataPointStatus,
  { label: string; variant: "destructive" | "warning" | "success" }
> = {
  missing: { label: "Missing", variant: "destructive" },
  partial: { label: "Partial", variant: "warning" },
  complete: { label: "Complete", variant: "success" },
};

const BOUNDARY_CONFIG: Record<
  BoundaryStatus,
  { label: string; variant: "success" | "secondary" | "warning" }
> = {
  included: { label: "Included", variant: "success" },
  excluded: { label: "Excluded", variant: "secondary" },
  partial: { label: "Partial", variant: "warning" },
};

function buildContextKey(
  sharedElementId?: number | null,
  entityId?: number | null,
  facilityId?: number | null
) {
  return [sharedElementId ?? 0, entityId ?? 0, facilityId ?? 0].join(":");
}

/* ---------- Component ---------- */

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

export default function CollectionPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = useMemo(() => {
    const raw = searchParams.get("projectId");
    const parsed = Number(raw ?? "1");
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }, [searchParams]);
  const [openingRowId, setOpeningRowId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [guidedField, setGuidedField] = useState<FormConfigField | null>(null);
  const [guidedRowKey, setGuidedRowKey] = useState<string | null>(null);
  const [resolvedDataPointIds, setResolvedDataPointIds] = useState<Record<string, number>>({});
  const [configActionMessage, setConfigActionMessage] = useState<string | null>(null);
  const [configActionError, setConfigActionError] = useState<string | null>(null);

  /* Filters */
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | DataPointStatus>(
    "all"
  );
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
  const canResyncConfig = roles.some((role) =>
    ["esg_manager", "admin", "platform_admin"].includes(role)
  );

  /* Data */
  const {
    data: assignmentsData,
    isLoading: assignmentsLoading,
    error: assignmentsError,
  } = useApiQuery<AssignmentMatrixResponse>(
    ["collection-assignments", projectId],
    `/projects/${projectId}/assignments`,
    { enabled: canAccess }
  );

  const { data, isLoading, error } = useApiQuery<DataPointsResponse>(
    ["data-points", projectId],
    `/projects/${projectId}/data-points`,
    { enabled: canAccess }
  );
  const {
    data: activeFormConfig,
    isLoading: configLoading,
    error: configError,
  } = useApiQuery<ActiveFormConfig | null>(
    ["active-form-config", projectId],
    `/form-configs/projects/${projectId}/active`,
    { enabled: canAccess }
  );
  const resyncConfigMutation = useApiMutation<ActiveFormConfig, undefined>(
    `/form-configs/projects/${projectId}/resync`,
    "POST",
    {
      onSuccess: async () => {
        setConfigActionError(null);
        setConfigActionMessage("Guided collection config re-synced from live assignments.");
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["active-form-config", projectId] }),
          queryClient.invalidateQueries({ queryKey: ["form-configs"] }),
          queryClient.invalidateQueries({ queryKey: ["collection-assignments", projectId] }),
        ]);
      },
      onError: (error) => {
        setConfigActionMessage(null);
        setConfigActionError(error.message);
      },
    }
  );

  const items = useMemo(() => {
    const points = data?.items ?? [];
    const assignments = assignmentsData?.assignments ?? [];

    const pointsByKey = new Map<string, DataPoint>();
    for (const point of points) {
      const key = buildContextKey(
        point.shared_element_id ?? 0,
        point.entity_id ?? 0,
        point.facility_id ?? 0
      );
      if (!pointsByKey.has(key)) {
        pointsByKey.set(key, point);
      }
    }

    if (assignments.length === 0) {
      return points;
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
        point?.collection_status
        ?? (resolvedDataPointId
          ? "partial"
          : undefined)
        ?? (assignment.status === "completed"
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
          point?.boundary_status
          ?? (assignment.boundary_included ? "included" : "excluded"),
        consolidation_method:
          point?.consolidation_method ?? assignment.consolidation_method ?? "full",
        reused_across_standards: point?.reused_across_standards ?? false,
        standards: point?.standards ?? [],
      } satisfies DataPoint;
    });
  }, [assignmentsData?.assignments, data?.items, resolvedDataPointIds]);

  const accessDenied =
    (Boolean(me) && !canAccess)
    || (!!assignmentsError && isForbidden(assignmentsError))
    || (!!error && isForbidden(error));

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

  const elementNamesById = useMemo(() => {
    const entries = items
      .filter((item) => item.shared_element_id)
      .map((item) => [item.shared_element_id as number, item.element_name] as const);
    return Object.fromEntries(entries);
  }, [items]);

  const resolveFieldMatches = (field: FormConfigField) => {
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
  };

  const guidedSummary = useMemo(() => {
    const steps = activeFormConfig?.config?.steps ?? [];
    if (steps.length === 0) return null;

    let total = 0;
    let complete = 0;
    let missing = 0;
    let ambiguous = 0;

    for (const step of steps) {
      for (const field of step.fields.filter((entry) => entry.visible)) {
        total += 1;
        const matches = resolveFieldMatches(field);
        if (matches.length === 0) {
          missing += 1;
          continue;
        }
        if (matches.length > 1) {
          ambiguous += 1;
          continue;
        }
        if (matches[0].collection_status === "complete") {
          complete += 1;
        }
      }
    }

    return { total, complete, missing, ambiguous };
  }, [activeFormConfig, rowsByAssignment, rowsByContext, rowsByElement]);

  const guidedRow = useMemo(() => {
    if (!guidedField) return null;
    const matches = resolveFieldMatches(guidedField);
    return matches.length === 1 ? matches[0] : null;
  }, [guidedField, rowsByAssignment, rowsByContext, rowsByElement]);

  /* Derived entity / standard lists for filter dropdowns */
  const entities = useMemo(
    () => Array.from(new Set(items.map((d) => d.entity_name))).sort(),
    [items]
  );
  const standards = useMemo(
    () =>
      Array.from(new Set(items.flatMap((d) => d.standards ?? []))).sort(),
    [items]
  );

  /* Filtered + sorted */
  const filtered = useMemo(() => {
    let result = items;

    if (statusFilter !== "all") {
      result = result.filter((d) => d.collection_status === statusFilter);
    }
    if (entityFilter) {
      result = result.filter((d) => d.entity_name === entityFilter);
    }
    if (standardFilter) {
      result = result.filter((d) => d.standards?.includes(standardFilter));
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (d) =>
          d.element_code.toLowerCase().includes(q) ||
          d.element_name.toLowerCase().includes(q)
      );
    }

    result = [...result].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [items, statusFilter, entityFilter, standardFilter, search, sortField, sortDir]);

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const openDataEntry = async (row: DataPoint) => {
    setActionError(null);
    if (row.data_point_id) {
      router.push(`/collection/${row.data_point_id}?projectId=${projectId}`);
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
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to open data entry for this row. Please try again."
      );
    } finally {
      setOpeningRowId(null);
    }
  };

  const scrollToTable = () => {
    if (typeof window !== "undefined") {
      window.requestAnimationFrame(() => {
        document.getElementById("collection-table")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    }
  };

  const showFieldInTable = (sharedElementId?: number) => {
    const firstMatch = sharedElementId
      ? rowsByElement.get(sharedElementId)?.[0]
      : undefined;
    if (firstMatch) {
      setSearch(firstMatch.element_code || firstMatch.element_name);
    }
    scrollToTable();
  };

  /* ---------- Render ---------- */

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Data Collection</h2>
        <p className="mt-1 text-sm text-gray-500">
          Manage and enter ESG data points for the current reporting period.
        </p>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {configActionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {configActionError}
        </div>
      )}

      {configActionMessage && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          {configActionMessage}
        </div>
      )}

      <GuidedEntryDialog
        open={Boolean(guidedField && guidedRow && guidedRowKey)}
        onOpenChange={(open) => {
          if (!open) {
            setGuidedField(null);
            setGuidedRowKey(null);
          }
        }}
        projectId={projectId}
        row={guidedRow}
        field={guidedField}
        rowKey={guidedRowKey}
        onDataPointResolved={(rowKey, dataPointId) => {
          setResolvedDataPointIds((current) =>
            current[rowKey] === dataPointId
              ? current
              : { ...current, [rowKey]: dataPointId }
          );
        }}
      />

      {!accessDenied && !assignmentsLoading && !isLoading && configLoading && !meLoading && (
        <Card className="border-slate-200 p-4">
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading guided collection configuration...
          </div>
        </Card>
      )}

      {!accessDenied && !assignmentsLoading && !isLoading && !configLoading && configError && (
        <Card className="border-red-200 bg-red-50 p-4">
          <div className="flex items-start gap-2 text-sm text-red-700">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Guided collection is unavailable.</p>
              <p className="mt-1">{configError.message}</p>
            </div>
          </div>
        </Card>
      )}

      {!accessDenied && !assignmentsLoading && !isLoading && !configLoading && activeFormConfig?.config?.steps?.length ? (
        <Card className="border-cyan-200 bg-gradient-to-br from-white via-cyan-50 to-slate-50 p-4">
          <div className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Guided Collection</h3>
                <p className="mt-1 text-sm text-slate-600">
                  {activeFormConfig.name}
                  {activeFormConfig.project_id === null ? " (organization default)" : ""}
                </p>
                {activeFormConfig.description && (
                  <p className="mt-2 max-w-3xl text-sm text-slate-500">
                    {activeFormConfig.description}
                  </p>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {activeFormConfig.resolution_scope === "organization_default" && (
                    <Badge variant="outline">Organization default</Badge>
                  )}
                  {activeFormConfig.health?.status === "healthy" && (
                    <Badge variant="success">Healthy</Badge>
                  )}
                  {activeFormConfig.health?.is_stale && (
                    <Badge variant="warning">Stale config</Badge>
                  )}
                  {activeFormConfig.updated_at && (
                    <span className="text-xs text-slate-500">
                      Last updated{" "}
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(activeFormConfig.updated_at))}
                    </span>
                  )}
                </div>
              </div>
              {guidedSummary && (
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline">
                    {guidedSummary.complete}/{guidedSummary.total} complete
                  </Badge>
                  {guidedSummary.missing > 0 && (
                    <Badge variant="secondary">{guidedSummary.missing} not assigned</Badge>
                  )}
                  {guidedSummary.ambiguous > 0 && (
                    <Badge variant="warning">{guidedSummary.ambiguous} multi-context</Badge>
                  )}
                </div>
              )}
            </div>

            {activeFormConfig.health?.is_stale && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="font-medium">
                      This guided config is out of sync with the current assignments or boundary.
                    </p>
                    <div className="space-y-1 text-sm text-amber-900/90">
                      {activeFormConfig.health.issues.map((issue) => (
                        <p key={issue.code}>
                          {issue.message}
                          {issue.affected_fields > 0 ? ` (${issue.affected_fields})` : ""}
                        </p>
                      ))}
                    </div>
                  </div>
                  {canResyncConfig && activeFormConfig.project_id !== null && (
                    <Button
                      variant="outline"
                      disabled={resyncConfigMutation.isPending}
                      onClick={() => {
                        setConfigActionMessage(null);
                        setConfigActionError(null);
                        void resyncConfigMutation.mutateAsync(undefined);
                      }}
                    >
                      {resyncConfigMutation.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCcw className="mr-2 h-4 w-4" />
                      )}
                      Re-sync Config
                    </Button>
                  )}
                </div>
              </div>
            )}

            {guidedSummary && guidedSummary.ambiguous > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                Some configured fields resolve to multiple entity or facility contexts. Those entries
                stay actionable through the collection table below so the collector keeps explicit
                boundary context.
              </div>
            )}

            <WizardRenderer
              config={activeFormConfig.config}
              values={{}}
              elementNames={elementNamesById}
              onSubmit={scrollToTable}
              submitLabel="Open Table View"
              renderField={(field) => {
                const matches = resolveFieldMatches(field);
                const singleMatch = matches.length === 1 ? matches[0] : null;
                const firstMatch = matches[0] ?? null;
                const elementName =
                  singleMatch?.element_name
                  ?? firstMatch?.element_name
                  ?? field.tooltip?.split(": ").slice(1).join(": ")
                  ?? `Element #${field.shared_element_id}`;
                const elementCode = singleMatch?.element_code ?? firstMatch?.element_code ?? null;
                const contextPreview = Array.from(
                  new Set(
                    matches
                      .map((row) =>
                        row.facility_name
                          ? `${row.entity_name} / ${row.facility_name}`
                          : row.entity_name
                      )
                      .filter(Boolean)
                  )
                );
                const standards = Array.from(
                  new Set(matches.flatMap((row) => row.standards ?? []))
                );

                return (
                  <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          {elementCode && (
                            <span className="rounded-md bg-slate-100 px-2 py-1 font-mono text-[11px] text-slate-600">
                              {elementCode}
                            </span>
                          )}
                          <p className="font-medium text-slate-900">{elementName}</p>
                          {field.required && (
                            <Badge variant="outline" className="text-[10px]">
                              Required
                            </Badge>
                          )}
                          {singleMatch ? (
                            <Badge variant={STATUS_CONFIG[singleMatch.collection_status].variant}>
                              {STATUS_CONFIG[singleMatch.collection_status].label}
                            </Badge>
                          ) : matches.length === 0 ? (
                            <Badge variant="secondary">Not assigned</Badge>
                          ) : (
                            <Badge variant="warning">{matches.length} contexts</Badge>
                          )}
                          {singleMatch?.reused_across_standards && (
                            <Badge variant="secondary" className="text-[10px]">
                              <Repeat2 className="mr-1 h-3 w-3" />
                              Reused
                            </Badge>
                          )}
                        </div>

                        {field.help_text && (
                          <p className="whitespace-pre-line text-xs text-slate-500">
                            {field.help_text}
                          </p>
                        )}

                        {singleMatch ? (
                          <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                            <span>Entity: {singleMatch.entity_name}</span>
                            {singleMatch.facility_name && (
                              <span>Facility: {singleMatch.facility_name}</span>
                            )}
                            <span>
                              Boundary: {BOUNDARY_CONFIG[singleMatch.boundary_status].label}
                            </span>
                            <span>Consolidation: {singleMatch.consolidation_method}</span>
                          </div>
                        ) : matches.length > 1 ? (
                          <p className="text-xs text-slate-500">
                            Multiple contexts found: {contextPreview.slice(0, 3).join(", ")}
                            {contextPreview.length > 3 ? ` +${contextPreview.length - 3} more` : ""}
                          </p>
                        ) : (
                          <p className="text-xs text-slate-500">
                            This field is present in the live config, but no matching assignment or data
                            point context was found in the project.
                          </p>
                        )}

                        {standards.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {standards.map((standard) => (
                              <Badge key={standard} variant="outline" className="text-[10px]">
                                {standard}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="flex shrink-0 flex-col items-end gap-2">
                        {singleMatch && (
                          <Badge variant={BOUNDARY_CONFIG[singleMatch.boundary_status].variant}>
                            {BOUNDARY_CONFIG[singleMatch.boundary_status].label}
                          </Badge>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={matches.length === 0}
                          onClick={() => {
                            if (singleMatch) {
                              setGuidedField(field);
                              setGuidedRowKey(
                                buildContextKey(
                                  singleMatch.shared_element_id,
                                  singleMatch.entity_id,
                                  singleMatch.facility_id
                                )
                              );
                              return;
                            }
                            if (matches.length > 1) {
                              showFieldInTable(field.shared_element_id);
                            }
                          }}
                        >
                          {singleMatch ? (
                            singleMatch.data_point_id ? "Continue entry" : "Quick entry"
                          ) : matches.length > 1 ? (
                            "Show rows"
                          ) : (
                            "Unavailable"
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              }}
            />
          </div>
        </Card>
      ) : null}

      {/* Filters row */}
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-4">
          {/* Search */}
          <div className="min-w-[240px] flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <Input
                placeholder="Search by code or name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Status filter */}
          <div className="grid gap-1.5">
            <label className="text-sm font-medium text-slate-700">
              <Filter className="mr-1 inline h-3.5 w-3.5" />
              Status
            </label>
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter(e.target.value as typeof statusFilter)
              }
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
            >
              <option value="all">All statuses</option>
              <option value="missing">Missing</option>
              <option value="partial">Partial</option>
              <option value="complete">Complete</option>
            </select>
          </div>

          {/* Entity filter */}
          <div className="grid gap-1.5">
            <label className="text-sm font-medium text-slate-700">Entity</label>
            <select
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
            >
              <option value="">All entities</option>
              {entities.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          </div>

          {/* Standard filter */}
          <div className="grid gap-1.5">
            <label className="text-sm font-medium text-slate-700">
              Standard
            </label>
            <select
              value={standardFilter}
              onChange={(e) => setStandardFilter(e.target.value)}
              className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
            >
              <option value="">All standards</option>
              {standards.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card id="collection-table">
        {meLoading || assignmentsLoading || isLoading ? (
          <div className="flex min-h-[300px] items-center justify-center p-12 text-gray-400">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Loading data points...
          </div>
        ) : accessDenied ? (
          <div className="flex min-h-[300px] flex-col items-center justify-center p-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Only collectors and ESG managers can access data collection.
            </p>
          </div>
        ) : error ? (
          <div className="flex min-h-[300px] flex-col items-center justify-center p-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Failed to load data points. Please try again.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3">
                    <button
                      onClick={() => toggleSort("element_code")}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                    >
                      Element Code
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      onClick={() => toggleSort("element_name")}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                    >
                      Element Name
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3">
                    <button
                      onClick={() => toggleSort("collection_status")}
                      className="inline-flex items-center gap-1 hover:text-slate-900"
                    >
                      Status
                      <ArrowUpDown className="h-3 w-3" />
                    </button>
                  </th>
                  <th className="px-4 py-3">Entity</th>
                  <th className="px-4 py-3">Facility</th>
                  <th className="px-4 py-3">Boundary</th>
                  <th className="px-4 py-3">Consolidation</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={8}
                      className="px-4 py-12 text-center text-gray-400"
                    >
                      No data points found.
                    </td>
                  </tr>
                ) : (
                  filtered.map((dp) => {
                    const statusCfg = STATUS_CONFIG[dp.collection_status];
                    const boundaryCfg = BOUNDARY_CONFIG[dp.boundary_status];

                    return (
                      <tr
                        key={`${dp.assignment_id ?? "dp"}-${dp.id}`}
                        onClick={() => void openDataEntry(dp)}
                        className="cursor-pointer hover:bg-slate-50 transition-colors"
                      >
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">
                          {dp.element_code}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-slate-900">
                              {dp.element_name}
                            </span>
                            {dp.reused_across_standards && (
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                                <Repeat2 className="mr-0.5 h-3 w-3" />
                                Reused
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={statusCfg.variant}>
                            {statusCfg.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {dp.entity_name}
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {dp.facility_name}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={boundaryCfg.variant}>
                            {boundaryCfg.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {dp.consolidation_method}
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={openingRowId === (dp.assignment_id ?? dp.id)}
                            onClick={(e) => {
                              e.stopPropagation();
                              void openDataEntry(dp);
                            }}
                          >
                            {openingRowId === (dp.assignment_id ?? dp.id) ? (
                              <>
                                <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                                Opening...
                              </>
                            ) : (
                              "Enter Data"
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
        )}

        {/* Footer */}
        {!meLoading && !assignmentsLoading && !isLoading && !error && !assignmentsError && (
          <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
            Showing {filtered.length} of {items.length} data points
          </div>
        )}
      </Card>
    </div>
  );
}
