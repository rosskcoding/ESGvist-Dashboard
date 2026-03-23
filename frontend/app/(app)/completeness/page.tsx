"use client";

import { Fragment, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Globe,
  BarChart3,
  Info,
  ShieldAlert,
} from "lucide-react";

interface DashboardStandardProgress {
  standard_id: number;
  standard: string;
  standard_name: string;
  completion_percent: number;
  complete_items: number;
  partial_items: number;
  missing_items: number;
  total_items: number;
}

interface DashboardProgress {
  standards_progress: DashboardStandardProgress[];
}

interface BoundaryContext {
  boundary_id: number | null;
  boundary_name: string | null;
  snapshot_date: string | null;
  entities_in_scope: number;
  excluded_entities: number;
  snapshot_locked: boolean;
  entities_without_data: string[];
}

interface DisclosureRow {
  disclosure_requirement_id: number;
  code: string | null;
  title: string | null;
  status: "complete" | "partial" | "missing" | "not_applicable";
  completion_percent: number;
  entity_breakdown?: {
    covered_entities: number;
    missing_entities: number;
    excluded_entities: number;
    missing_entity_names?: string[];
  } | null;
}

interface CompletenessResponse {
  overall_percent: number;
  overall_status: string;
  boundary_context?: BoundaryContext | null;
  disclosures: DisclosureRow[];
}

const disclosureStatusConfig: Record<
  DisclosureRow["status"],
  {
    label: string;
    variant: "success" | "warning" | "destructive" | "secondary";
    icon: typeof CheckCircle2;
  }
> = {
  complete: { label: "Complete", variant: "success", icon: CheckCircle2 },
  partial: { label: "Partial", variant: "warning", icon: Clock },
  missing: { label: "Missing", variant: "destructive", icon: XCircle },
  not_applicable: { label: "N/A", variant: "secondary", icon: Info },
};

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

export default function CompletenessPage() {
  const [projectId] = useState(1);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const {
    data: completeness,
    isLoading: completenessLoading,
    error: completenessError,
  } = useApiQuery<CompletenessResponse>(
    ["completeness", projectId],
    `/projects/${projectId}/completeness?boundaryContext=true`
  );
  const {
    data: dashboard,
    isLoading: dashboardLoading,
    error: dashboardError,
  } = useApiQuery<DashboardProgress>(
    ["dashboard", "progress", projectId, "completeness-page"],
    `/dashboard/projects/${projectId}/progress`
  );

  const isLoading = completenessLoading || dashboardLoading;
  const error = completenessError || dashboardError;

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error && isForbidden(error)) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Completeness</h2>
          <p className="mt-1 text-sm text-slate-500">
            Data completeness analysis
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Only admin, ESG manager, and auditor roles can view completeness.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Completeness</h2>
          <p className="mt-1 text-sm text-slate-500">
            Data completeness analysis
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load completeness data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const standards = dashboard?.standards_progress ?? [];
  const disclosures = completeness?.disclosures ?? [];
  const boundary = completeness?.boundary_context;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Completeness</h2>
        <p className="mt-1 text-sm text-slate-500">
          Data completeness analysis for your ESG reporting
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Overall Completeness
            </CardDescription>
            <BarChart3 className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {Math.round(completeness?.overall_percent ?? 0)}%
            </div>
            <Progress
              value={completeness?.overall_percent ?? 0}
              className="mt-3"
              indicatorClassName={cn(
                (completeness?.overall_percent ?? 0) >= 80
                  ? "bg-green-500"
                  : (completeness?.overall_percent ?? 0) >= 50
                    ? "bg-amber-500"
                    : "bg-blue-600"
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Boundary
            </CardDescription>
            <Globe className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">
              {boundary?.boundary_name ?? "No boundary"}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {boundary?.snapshot_locked ? "Snapshot locked" : "Snapshot not locked"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Entities in Scope
            </CardDescription>
            <CheckCircle2 className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {boundary?.entities_in_scope ?? 0}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              excluded: {boundary?.excluded_entities ?? 0}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Completion by Standard</CardTitle>
          <CardDescription>
            Breakdown of completeness across reporting frameworks
          </CardDescription>
        </CardHeader>
        <CardContent>
          {standards.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">
              No standards data available.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {standards.map((std) => (
                <div
                  key={std.standard_id}
                  className="rounded-lg border border-slate-200 p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-semibold">{std.standard}</span>
                      <p className="text-xs text-slate-500">
                        {std.standard_name}
                      </p>
                    </div>
                    <span className="text-lg font-bold">
                      {Math.round(std.completion_percent)}%
                    </span>
                  </div>
                  <Progress
                    value={std.completion_percent}
                    indicatorClassName={cn(
                      std.completion_percent >= 80
                        ? "bg-green-500"
                        : std.completion_percent >= 50
                          ? "bg-amber-500"
                          : "bg-blue-600"
                    )}
                  />
                  <p className="text-xs text-slate-400">
                    {std.complete_items} complete / {std.total_items} items
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Disclosure Details</CardTitle>
          <CardDescription>
            Status of individual disclosures across all standards. Click a row to
            inspect missing entity coverage.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {disclosures.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">
              No disclosure data available.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Covered</TableHead>
                  <TableHead>Missing</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {disclosures.map((disclosure) => {
                  const statusCfg = disclosureStatusConfig[disclosure.status];
                  const StatusIcon = statusCfg.icon;
                  const isExpanded = expandedRow === disclosure.disclosure_requirement_id;
                  const coveredCount = disclosure.entity_breakdown?.covered_entities ?? 0;
                  const missingCount = disclosure.entity_breakdown?.missing_entities ?? 0;
                  const missingNames = disclosure.entity_breakdown?.missing_entity_names ?? [];

                  return (
                    <Fragment key={disclosure.disclosure_requirement_id}>
                      <TableRow
                        className="cursor-pointer"
                        onClick={() =>
                          setExpandedRow(
                            isExpanded ? null : disclosure.disclosure_requirement_id
                          )
                        }
                      >
                        <TableCell className="font-mono text-sm font-medium">
                          {disclosure.code ?? "n/a"}
                        </TableCell>
                        <TableCell>{disclosure.title ?? "Untitled disclosure"}</TableCell>
                        <TableCell>
                          <Badge variant={statusCfg.variant}>
                            <StatusIcon className="mr-1 h-3 w-3" />
                            {statusCfg.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-green-600">{coveredCount}</span>
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              "text-sm",
                              missingCount > 0 ? "font-medium text-red-600" : "text-slate-400"
                            )}
                          >
                            {missingCount}
                          </span>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow>
                          <TableCell colSpan={5} className="bg-slate-50 p-4">
                            <div className="space-y-3">
                              <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3">
                                <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
                                <p className="text-sm text-blue-800">
                                  Completion: {Math.round(disclosure.completion_percent)}%
                                </p>
                              </div>

                              <div>
                                <p className="mb-1 text-xs font-medium text-red-700">
                                  Missing Entities ({missingNames.length})
                                </p>
                                {missingNames.length > 0 ? (
                                  <div className="flex flex-wrap gap-1">
                                    {missingNames.map((entity) => (
                                      <Badge
                                        key={entity}
                                        variant="outline"
                                        className="border-red-200 bg-red-50 text-red-700"
                                      >
                                        {entity}
                                      </Badge>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="text-xs text-slate-400">None</p>
                                )}
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
