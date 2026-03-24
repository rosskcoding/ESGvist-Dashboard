"use client";

import { useMemo, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Eye,
  Layers,
  GitMerge,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";

// ---------- Types ----------

interface MergeStandard {
  standard_id: number;
  code: string;
  name: string;
  coverage_pct: number;
}

interface BoundaryEntity {
  entity_id: number;
  name: string;
  included: boolean;
}

interface BoundaryScope {
  entities: BoundaryEntity[];
  consolidation_method: string;
}

interface MergeCell {
  standard_id: number;
  status: "complete" | "partial" | "missing";
  binding_type: "full" | "partial" | "derived";
  requirement_details?: string;
  current_value?: string;
  evidence_status?: "attached" | "pending" | "none";
  entity_scope?: string;
}

interface MergeElement {
  element_id: number;
  code: string;
  name: string;
  domain: string;
  reuse_count: number;
  has_delta: boolean;
  delta_description?: string;
  cells: MergeCell[];
  boundary_scope?: BoundaryScope;
}

interface MergeSummary {
  common_elements: number;
  unique_elements: number;
  delta_count: number;
}

interface MergeData {
  standards: MergeStandard[];
  elements: MergeElement[];
  summary: MergeSummary;
}

// ---------- Helpers ----------

const STATUS_COLORS: Record<string, string> = {
  complete: "bg-green-500",
  partial: "bg-amber-400",
  missing: "bg-red-500",
};

const BINDING_VARIANTS: Record<string, "default" | "secondary" | "warning"> = {
  full: "default",
  partial: "warning",
  derived: "secondary",
};

function StatusDot({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full",
        STATUS_COLORS[status] ?? "bg-slate-300"
      )}
      title={status}
    />
  );
}

// ---------- Component ----------

export default function MergePage() {
  const [projectId] = useState(1);
  const [standardFilter, setStandardFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [domainFilter, setDomainFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedCell, setSelectedCell] = useState<{
    element: MergeElement;
    cell: MergeCell;
    standard: MergeStandard;
  } | null>(null);

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");

  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) => ["admin", "esg_manager", "auditor"].includes(role));
  const accessDenied = roles.length > 0 && !canAccess;
  const isAuditor = roles.includes("auditor");

  const { data, isLoading, error } = useApiQuery<MergeData>(
    ["merge", projectId],
    `/projects/${projectId}/merge`,
    { enabled: canAccess }
  );

  const standards = data?.standards ?? [];
  const allElements = data?.elements ?? [];
  const summary = data?.summary ?? {
    common_elements: 0,
    unique_elements: 0,
    delta_count: 0,
  };

  // Domain options derived from data
  const domainOptions = useMemo(() => {
    const domains = new Set(allElements.map((e) => e.domain));
    return Array.from(domains)
      .sort()
      .map((d) => ({ value: d, label: d }));
  }, [allElements]);

  // Filtered standards for columns
  const visibleStandards = useMemo(() => {
    if (!standardFilter) return standards;
    return standards.filter((s) => s.standard_id === Number(standardFilter));
  }, [standards, standardFilter]);

  // Filtered elements for rows
  const filteredElements = useMemo(() => {
    let result = allElements;

    if (domainFilter) {
      result = result.filter((e) => e.domain === domainFilter);
    }

    if (statusFilter) {
      result = result.filter((e) =>
        e.cells.some((c) => c.status === statusFilter)
      );
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (e) =>
          e.code.toLowerCase().includes(q) ||
          e.name.toLowerCase().includes(q)
      );
    }

    return result;
  }, [allElements, domainFilter, statusFilter, searchQuery]);

  const toggleRow = (id: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // ---------- Renders ----------

  if (meLoading || (canAccess && isLoading)) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <GitMerge className="h-6 w-6" />
            Merge View
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Cross-standard data element coverage matrix
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only admin, ESG manager, and auditor roles can access merge analysis.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Merge View</h2>
          <p className="mt-1 text-sm text-slate-500">
            Cross-standard data element coverage matrix
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load merge data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <GitMerge className="h-6 w-6" />
            Merge View
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Cross-standard data element coverage matrix
          </p>
        </div>
      </div>

      {isAuditor && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 p-4 text-amber-800">
            <Eye className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Auditor access is read-only.</p>
              <p className="text-sm">
                Merge analysis is available for inspection, but editing remains disabled elsewhere.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 py-4">
          <div className="w-48">
            <Select
              label="Standard"
              placeholder="All Standards"
              value={standardFilter}
              onChange={setStandardFilter}
              options={[
                { value: "", label: "All Standards" },
                ...standards.map((s) => ({
                  value: String(s.standard_id),
                  label: s.code,
                })),
              ]}
            />
          </div>
          <div className="w-40">
            <Select
              label="Status"
              placeholder="All Statuses"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "", label: "All Statuses" },
                { value: "complete", label: "Complete" },
                { value: "partial", label: "Partial" },
                { value: "missing", label: "Missing" },
              ]}
            />
          </div>
          <div className="w-48">
            <Select
              label="Domain"
              placeholder="All Domains"
              value={domainFilter}
              onChange={setDomainFilter}
              options={[
                { value: "", label: "All Domains" },
                ...domainOptions,
              ]}
            />
          </div>
          <div className="w-64">
            <Input
              label="Search"
              placeholder="Search by code or name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Summary bar */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {standards.map((std) => (
          <Card key={std.standard_id}>
            <CardContent className="py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{std.code}</span>
                <span className="text-sm font-semibold">
                  {Math.round(std.coverage_pct)}%
                </span>
              </div>
              <Progress
                value={std.coverage_pct}
                className="mt-2"
                indicatorClassName={cn(
                  std.coverage_pct >= 80
                    ? "bg-green-500"
                    : std.coverage_pct >= 50
                      ? "bg-amber-500"
                      : "bg-red-500"
                )}
              />
            </CardContent>
          </Card>
        ))}
        <Card>
          <CardContent className="flex items-center gap-6 py-3">
            <div className="text-center">
              <p className="text-lg font-bold">{summary.common_elements}</p>
              <p className="text-xs text-slate-500">Common</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold">{summary.unique_elements}</p>
              <p className="text-xs text-slate-500">Unique</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold">{summary.delta_count}</p>
              <p className="text-xs text-slate-500">Deltas</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Matrix table */}
      <Card>
        <CardHeader>
          <CardTitle>Element Coverage Matrix</CardTitle>
          <CardDescription>
            {filteredElements.length} element{filteredElements.length !== 1 && "s"}{" "}
            across {visibleStandards.length} standard{visibleStandards.length !== 1 && "s"}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead className="min-w-[100px]">Code</TableHead>
                <TableHead className="min-w-[200px]">Element Name</TableHead>
                {visibleStandards.map((std) => (
                  <TableHead key={std.standard_id} className="text-center">
                    {std.code}
                  </TableHead>
                ))}
                <TableHead className="text-center">Indicators</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredElements.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={4 + visibleStandards.length}
                    className="py-12 text-center text-sm text-slate-400"
                  >
                    No elements match the current filters.
                  </TableCell>
                </TableRow>
              ) : (
                filteredElements.map((element) => {
                  const isExpanded = expandedRows.has(element.element_id);
                  return (
                    <ElementRows
                      key={element.element_id}
                      element={element}
                      standards={visibleStandards}
                      isExpanded={isExpanded}
                      onToggle={() => toggleRow(element.element_id)}
                      onCellClick={(cell, standard) =>
                        setSelectedCell({ element, cell, standard })
                      }
                    />
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Cell detail dialog */}
      <Dialog
        open={selectedCell !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedCell(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedCell?.element.code} &mdash; {selectedCell?.standard.code}
            </DialogTitle>
            <DialogDescription>
              {selectedCell?.element.name}
            </DialogDescription>
          </DialogHeader>

          {selectedCell && (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-medium text-slate-500">Status</p>
                  <div className="mt-1 flex items-center gap-2">
                    <StatusDot status={selectedCell.cell.status} />
                    <span className="text-sm capitalize">
                      {selectedCell.cell.status}
                    </span>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Binding Type
                  </p>
                  <Badge
                    variant={
                      BINDING_VARIANTS[selectedCell.cell.binding_type] ??
                      "secondary"
                    }
                    className="mt-1"
                  >
                    {selectedCell.cell.binding_type}
                  </Badge>
                </div>
              </div>

              {selectedCell.cell.requirement_details && (
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Requirement Details
                  </p>
                  <p className="mt-1 text-sm">
                    {selectedCell.cell.requirement_details}
                  </p>
                </div>
              )}

              {selectedCell.cell.current_value && (
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Current Value
                  </p>
                  <p className="mt-1 rounded-md border border-slate-200 bg-slate-50 p-2 text-sm">
                    {selectedCell.cell.current_value}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Evidence Status
                  </p>
                  <Badge
                    variant={
                      selectedCell.cell.evidence_status === "attached"
                        ? "success"
                        : selectedCell.cell.evidence_status === "pending"
                          ? "warning"
                          : "secondary"
                    }
                    className="mt-1"
                  >
                    {selectedCell.cell.evidence_status ?? "none"}
                  </Badge>
                </div>
                {selectedCell.cell.entity_scope && (
                  <div>
                    <p className="text-xs font-medium text-slate-500">
                      Entity Scope
                    </p>
                    <p className="mt-1 text-sm">
                      {selectedCell.cell.entity_scope}
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------- Element rows (main + boundary) ----------

function ElementRows({
  element,
  standards,
  isExpanded,
  onToggle,
  onCellClick,
}: {
  element: MergeElement;
  standards: MergeStandard[];
  isExpanded: boolean;
  onToggle: () => void;
  onCellClick: (cell: MergeCell, standard: MergeStandard) => void;
}) {
  const cellMap = useMemo(() => {
    const map = new Map<number, MergeCell>();
    for (const cell of element.cells) {
      map.set(cell.standard_id, cell);
    }
    return map;
  }, [element.cells]);

  return (
    <>
      {/* Main row */}
      <TableRow className="group cursor-pointer hover:bg-slate-50">
        <TableCell className="w-8">
          <button
            type="button"
            onClick={onToggle}
            className="rounded p-0.5 hover:bg-slate-200"
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-slate-500" />
            ) : (
              <ChevronRight className="h-4 w-4 text-slate-500" />
            )}
          </button>
        </TableCell>
        <TableCell className="font-mono text-sm font-medium">
          {element.code}
        </TableCell>
        <TableCell className="text-sm">{element.name}</TableCell>
        {standards.map((std) => {
          const cell = cellMap.get(std.standard_id);
          if (!cell) {
            return (
              <TableCell key={std.standard_id} className="text-center">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-slate-200" />
              </TableCell>
            );
          }
          return (
            <TableCell key={std.standard_id} className="text-center">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded px-1.5 py-1 hover:bg-slate-100"
                onClick={() => onCellClick(cell, std)}
                aria-label={`Open ${element.code} coverage for ${std.code}`}
              >
                <StatusDot status={cell.status} />
                <Badge
                  variant={
                    BINDING_VARIANTS[cell.binding_type] ?? "secondary"
                  }
                  className="text-[10px] px-1.5 py-0"
                >
                  {cell.binding_type}
                </Badge>
              </button>
            </TableCell>
          );
        })}
        <TableCell className="text-center">
          <div className="flex items-center justify-center gap-1.5">
            {element.reuse_count >= 2 && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                <RefreshCw className="mr-0.5 h-3 w-3" />
                {element.reuse_count}x
              </Badge>
            )}
            {element.has_delta && (
              <Badge variant="warning" className="text-[10px] px-1.5 py-0">
                +&Delta;
              </Badge>
            )}
          </div>
        </TableCell>
      </TableRow>

      {/* Boundary scope (collapsible) */}
      {isExpanded && (
        <TableRow className="bg-slate-50/70">
          <TableCell />
          <TableCell colSpan={2 + standards.length + 1}>
            <BoundaryScopeSection
              scope={element.boundary_scope}
              deltaDescription={element.delta_description}
            />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ---------- Boundary scope section ----------

function BoundaryScopeSection({
  scope,
  deltaDescription,
}: {
  scope?: BoundaryScope;
  deltaDescription?: string;
}) {
  if (!scope) {
    return (
      <p className="py-2 text-sm text-slate-400">
        No boundary scope information available.
      </p>
    );
  }

  const included = scope.entities.filter((e) => e.included);
  const excluded = scope.entities.filter((e) => !e.included);

  return (
    <div className="space-y-3 py-2">
      <div className="flex items-center gap-2">
        <Layers className="h-4 w-4 text-slate-400" />
        <span className="text-sm font-medium text-slate-700">
          Boundary Scope
        </span>
        <Badge variant="secondary" className="text-[10px]">
          {scope.consolidation_method}
        </Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-slate-500">
            Entities in Scope ({included.length})
          </p>
          {included.length === 0 ? (
            <p className="text-xs text-slate-400">None</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {included.map((ent) => (
                <Badge key={ent.entity_id} variant="success" className="text-[10px]">
                  {ent.name}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-slate-500">
            Excluded Entities ({excluded.length})
          </p>
          {excluded.length === 0 ? (
            <p className="text-xs text-slate-400">None</p>
          ) : (
            <div className="flex flex-wrap gap-1">
              {excluded.map((ent) => (
                <Badge key={ent.entity_id} variant="secondary" className="text-[10px]">
                  {ent.name}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      {deltaDescription && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-2">
          <p className="text-xs font-medium text-amber-700">
            +&Delta; Additional Requirements
          </p>
          <p className="mt-0.5 text-xs text-amber-600">{deltaDescription}</p>
        </div>
      )}
    </div>
  );
}
