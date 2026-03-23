"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  Filter,
  ArrowUpDown,
  Repeat2,
  AlertTriangle,
  Loader2,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks/use-api";
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

/* ---------- Component ---------- */

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

export default function CollectionPage() {
  const router = useRouter();
  const [projectId] = useState(1);
  const [openingRowId, setOpeningRowId] = useState<number | null>(null);

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
  }>(["auth-me", "collection"], "/auth/me");
  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) =>
    ["collector", "esg_manager", "admin", "platform_admin"].includes(role)
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

  const items = useMemo(() => {
    const points = data?.items ?? [];
    const assignments = assignmentsData?.assignments ?? [];

    const pointsByKey = new Map<string, DataPoint>();
    for (const point of points) {
      const key = [
        point.shared_element_id ?? 0,
        point.entity_id ?? 0,
        point.facility_id ?? 0,
      ].join(":");
      if (!pointsByKey.has(key)) {
        pointsByKey.set(key, point);
      }
    }

    if (assignments.length === 0) {
      return points;
    }

    return assignments.map((assignment) => {
      const key = [
        assignment.shared_element_id,
        assignment.entity_id ?? 0,
        assignment.facility_id ?? 0,
      ].join(":");
      const point = pointsByKey.get(key);
      const collectionStatus =
        point?.collection_status
        ?? (assignment.status === "completed"
          ? "complete"
          : assignment.status === "in_progress"
            ? "partial"
            : "missing");

      return {
        id: point?.id ?? -assignment.id,
        data_point_id: point?.id ?? null,
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
  }, [assignmentsData?.assignments, data?.items]);

  const accessDenied =
    (Boolean(me) && !canAccess)
    || (!!assignmentsError && isForbidden(assignmentsError))
    || (!!error && isForbidden(error));

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
    if (row.data_point_id) {
      router.push(`/collection/${row.data_point_id}`);
      return;
    }
    if (!row.shared_element_id) {
      return;
    }

    setOpeningRowId(row.assignment_id ?? row.id);
    try {
      const created = await api.post<{ id: number }>(`/projects/${projectId}/data-points`, {
        shared_element_id: row.shared_element_id,
        entity_id: row.entity_id ?? undefined,
        facility_id: row.facility_id ?? undefined,
      });
      router.push(`/collection/${created.id}`);
    } finally {
      setOpeningRowId(null);
    }
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
      <Card>
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
