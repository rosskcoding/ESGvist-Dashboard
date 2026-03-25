"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  FileOutput,
  FileSpreadsheet,
  FileText,
  Loader2,
  RefreshCw,
  Send,
  Shield,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { withQuery } from "@/lib/api";

type ReadinessDetail = {
  code: string;
  message: string;
  count: number;
};

type BoundaryValidation = {
  selected_boundary: string;
  snapshot_locked: boolean;
  entities_in_scope: number;
  manual_overrides: number;
  boundary_differs_from_default: boolean;
  entities_without_data: string[];
};

type ReadinessResponse = {
  ready: boolean;
  overall_ready: boolean;
  completion_percent: number;
  total_items: number;
  complete: number;
  partial: number;
  missing: number;
  blocking_issues: number;
  warnings: number;
  blocking_issue_details: ReadinessDetail[];
  warning_details: ReadinessDetail[];
  boundary_validation: BoundaryValidation | null;
};

type ExportJob = {
  id: number;
  report_type: string;
  export_format: string;
  status: string;
  artifact_name: string | null;
  created_at: string | null;
  completed_at: string | null;
  error_message: string | null;
};

type ExportListResponse = {
  items: ExportJob[];
  total: number;
};

type ExportAction = {
  key: string;
  label: string;
  description: string;
  route: string;
  icon: typeof FileText;
};

const exportActions: ExportAction[] = [
  {
    key: "gri-pdf",
    label: "GRI Index PDF",
    description: "Queue GRI content index as PDF.",
    route: "export/gri-index?export_format=pdf",
    icon: FileText,
  },
  {
    key: "gri-xlsx",
    label: "GRI Index XLSX",
    description: "Queue GRI content index as Excel.",
    route: "export/gri-index?export_format=xlsx",
    icon: FileSpreadsheet,
  },
  {
    key: "report-pdf",
    label: "Full Report PDF",
    description: "Queue the full project report as PDF.",
    route: "export/report?export_format=pdf",
    icon: FileOutput,
  },
  {
    key: "report-xlsx",
    label: "Full Report XLSX",
    description: "Queue the full project report as Excel.",
    route: "export/report?export_format=xlsx",
    icon: FileSpreadsheet,
  },
  {
    key: "xbrl",
    label: "XBRL Instance",
    description: "Queue the XBRL export instance.",
    route: "export/xbrl",
    icon: FileOutput,
  },
];

function formatTimestamp(value: string | null) {
  if (!value) return "Pending";
  return new Date(value).toLocaleString();
}

export default function ReportPage() {
  const searchParams = useSearchParams();
  const resolvedProjectId = Number(searchParams.get("projectId") || "1");
  const projectId = Number.isFinite(resolvedProjectId) && resolvedProjectId > 0 ? resolvedProjectId : 1;
  const queryClient = useQueryClient();
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [activeExportKey, setActiveExportKey] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const cachedMe = queryClient.getQueryData<{
    roles: Array<{ role: string }>;
  }>(["auth-me"]);
  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me", {
    initialData: cachedMe,
    staleTime: 60_000,
    refetchOnMount: false,
  });

  const roles = me?.roles?.map((entry) => entry.role) ?? [];
  const primaryRole = roles[0] ?? "";
  const canAccess = primaryRole === "admin" || primaryRole === "esg_manager";
  const accessDenied = roles.length > 0 && !canAccess;

  const {
    data: readiness,
    isLoading: readinessLoading,
    error: readinessError,
  } = useApiQuery<ReadinessResponse>(
    ["report", "readiness", projectId],
    `/projects/${projectId}/export/readiness`,
    { enabled: canAccess }
  );

  const {
    data: exportJobs,
    isLoading: exportJobsLoading,
  } = useApiQuery<ExportListResponse>(
    ["report", "exports", projectId],
    `/projects/${projectId}/exports`,
    { enabled: canAccess }
  );

  const publishMutation = useApiMutation<{ id: number; status: string }, void>(
    `/projects/${projectId}/publish`,
    "POST",
    {
      onMutate: () => {
        setActionError(null);
      },
      onSuccess: async (result) => {
        queryClient.setQueryData(["project", String(projectId)], (current: Record<string, unknown> | undefined) =>
          current ? { ...current, status: result.status } : current
        );
        queryClient.setQueryData<ExportListResponse>(["report", "exports", projectId], (current) => current);
        queryClient.setQueryData<{ items: Array<Record<string, unknown>>; total: number }>(
          ["projects"],
          (current) => {
            if (!current) return current;
            return {
              ...current,
              items: current.items.map((item) =>
                Number(item.id) === projectId ? { ...item, status: result.status } : item
              ),
            };
          }
        );
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["report", "readiness", projectId] }),
          queryClient.invalidateQueries({ queryKey: ["dashboard", "progress", projectId] }),
        ]);
      },
      onError: (error) => {
        setActionError(error.message || "Unable to publish project.");
      },
    }
  );

  const latestCompletedJob = useMemo(
    () => exportJobs?.items.find((job) => job.status === "completed") ?? null,
    [exportJobs?.items]
  );

  const statusTone = useMemo(() => {
    if (readiness?.overall_ready) {
      return {
        icon: CheckCircle2,
        label: "Ready to Publish",
        badge: "default" as const,
        className: "border-green-200 bg-green-50 text-green-700",
      };
    }
    if ((readiness?.warning_details?.length ?? 0) > 0) {
      return {
        icon: AlertTriangle,
        label: "Warnings Present",
        badge: "warning" as const,
        className: "border-amber-200 bg-amber-50 text-amber-700",
      };
    }
    return {
      icon: XCircle,
      label: "Blocking Issues",
      badge: "destructive" as const,
      className: "border-red-200 bg-red-50 text-red-700",
    };
  }, [readiness?.overall_ready, readiness?.warning_details?.length]);

  async function refreshAll() {
    setActionError(null);
    setIsRefreshing(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["report", "readiness", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["report", "exports", projectId] }),
      ]);
    } finally {
      setIsRefreshing(false);
    }
  }

  async function queueExport(route: string, exportKey: string) {
    if (activeExportKey) return;
    setActiveExportKey(exportKey);
    setActionError(null);
    try {
      const queued = await api.post<ExportJob>(`/projects/${projectId}/${route}`);
      queryClient.setQueryData<ExportListResponse>(["report", "exports", projectId], (current) => {
        if (!current) {
          return { items: [queued], total: 1 };
        }
        const exists = current.items.some((item) => item.id === queued.id);
        return {
          items: exists ? current.items.map((item) => (item.id === queued.id ? queued : item)) : [queued, ...current.items],
          total: exists ? current.total : current.total + 1,
        };
      });
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Unable to queue export job. Please try again."
      );
    } finally {
      setActiveExportKey(null);
    }
  }

  async function handlePublish() {
    try {
      await publishMutation.mutateAsync(undefined);
      setPublishDialogOpen(false);
    } catch {
      // Error banner is handled by mutation state.
    }
  }

  if (accessDenied) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Report &amp; Export</h2>
          <p className="mt-1 text-sm text-slate-500">
            Check readiness, preview exports, and publish reporting output.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only admin and ESG manager roles can access report readiness and export.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (readinessError || !readiness) {
    if (meLoading || (canAccess && (readinessLoading || exportJobsLoading))) {
      return (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">Report &amp; Export</h2>
              <p className="mt-1 text-sm text-slate-500">
                Check readiness, preview exports, and publish reporting output.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" disabled>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Refresh readiness
              </Button>
              <Button variant="outline" disabled>
                <Eye className="mr-2 h-4 w-4" />
                Preview latest
              </Button>
              <Button disabled>
                <Send className="mr-2 h-4 w-4" />
                Publish Project
              </Button>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Readiness Summary</CardTitle>
                <CardDescription>Overall state before export or publish.</CardDescription>
              </CardHeader>
              <CardContent className="flex min-h-[180px] items-center justify-center text-sm text-slate-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading readiness snapshot...
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Boundary Validation</CardTitle>
                <CardDescription>
                  Snapshot lock and scope checks for the active reporting boundary.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex min-h-[180px] items-center justify-center text-sm text-slate-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading boundary checks...
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Blocking Issues</CardTitle>
                <CardDescription>These must be cleared before publish.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-slate-500">Loading issue summary...</CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Warnings</CardTitle>
                <CardDescription>These do not block export but should be reviewed.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-slate-500">Loading warning summary...</CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Export Formats</CardTitle>
              <CardDescription>
                Queue report artifacts and open the preview screen for completed jobs.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex min-h-[160px] items-center justify-center text-sm text-slate-500">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Loading export actions...
            </CardContent>
          </Card>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Report &amp; Export</h2>
          <p className="mt-1 text-sm text-slate-500">
            Check readiness, preview exports, and publish reporting output.
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load readiness data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const StatusIcon = statusTone.icon;
  const completedExports = exportJobs?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Report &amp; Export</h2>
          <p className="mt-1 text-sm text-slate-500">
            Check readiness, preview exports, and publish reporting output.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={refreshAll} disabled={isRefreshing}>
            {isRefreshing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Refresh readiness
          </Button>
          <Button variant="outline" asChild disabled={!latestCompletedJob}>
            <Link
              href={
                latestCompletedJob
                  ? withQuery("/report/preview", { projectId, jobId: latestCompletedJob.id })
                  : withQuery("/report/preview", { projectId })
              }
            >
              <Eye className="mr-2 h-4 w-4" />
              Preview latest
            </Link>
          </Button>
          <Button
            onClick={() => setPublishDialogOpen(true)}
            disabled={!readiness.overall_ready || publishMutation.isPending || activeExportKey !== null}
          >
            <Send className="mr-2 h-4 w-4" />
            Publish Project
          </Button>
        </div>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card className={cn("border", statusTone.className)}>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <StatusIcon className="h-5 w-5" />
              Readiness Summary
            </CardTitle>
            <CardDescription>
              Overall state before export or publish.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant={statusTone.badge}>{statusTone.label}</Badge>
              <span className="text-2xl font-bold text-slate-900">
                {Math.round(readiness.completion_percent)}%
              </span>
            </div>
            <Progress
              value={readiness.completion_percent}
              className="h-3"
              indicatorClassName={cn(
                readiness.completion_percent >= 80
                  ? "bg-green-500"
                  : readiness.completion_percent >= 50
                    ? "bg-amber-500"
                    : "bg-red-500"
              )}
            />
            <div className="grid gap-3 sm:grid-cols-4">
              <MetricCard label="Total" value={readiness.total_items} />
              <MetricCard label="Complete" value={readiness.complete} />
              <MetricCard label="Partial" value={readiness.partial} />
              <MetricCard label="Missing" value={readiness.missing} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-slate-600" />
              Boundary Validation
            </CardTitle>
            <CardDescription>
              Snapshot lock and scope checks for the active reporting boundary.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <BoundaryRow label="Selected Boundary" value={readiness.boundary_validation?.selected_boundary ?? "None"} />
            <BoundaryRow
              label="Snapshot Locked"
              value={readiness.boundary_validation?.snapshot_locked ? "Locked" : "Not locked"}
            />
            <BoundaryRow
              label="Entities in Scope"
              value={String(readiness.boundary_validation?.entities_in_scope ?? 0)}
            />
            <BoundaryRow
              label="Manual Overrides"
              value={String(readiness.boundary_validation?.manual_overrides ?? 0)}
            />
            <BoundaryRow
              label="Differs from Default"
              value={readiness.boundary_validation?.boundary_differs_from_default ? "Yes" : "No"}
            />
            {(readiness.boundary_validation?.entities_without_data?.length ?? 0) > 0 && (
              <div>
                <p className="mb-1 text-xs font-medium text-slate-500">Entities Without Data</p>
                <div className="flex flex-wrap gap-2">
                  {readiness.boundary_validation!.entities_without_data.map((name) => (
                    <Badge key={name} variant="secondary">
                      {name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {(readiness.blocking_issue_details.length > 0 || readiness.warning_details.length > 0) && (
        <div className="grid gap-6 lg:grid-cols-2">
          <IssueList
            title="Blocking Issues"
            description="These must be cleared before publish."
            icon={XCircle}
            tone="red"
            items={readiness.blocking_issue_details}
          />
          <IssueList
            title="Warnings"
            description="These do not block export but should be reviewed."
            icon={AlertTriangle}
            tone="amber"
            items={readiness.warning_details}
          />
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Export Formats</CardTitle>
          <CardDescription>
            Queue report artifacts and open the preview screen for completed jobs.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          {exportActions.map((action) => {
            const Icon = action.icon;
            const isRunning = activeExportKey === action.key;
            const exportBusy = activeExportKey !== null || publishMutation.isPending;
            return (
              <div key={action.key} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-slate-600" />
                      <p className="font-medium text-slate-900">{action.label}</p>
                    </div>
                    <p className="mt-1 text-sm text-slate-500">{action.description}</p>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => queueExport(action.route, action.key)}
                    disabled={!readiness.overall_ready || exportBusy}
                    aria-label={`Queue ${action.label}`}
                  >
                    {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : "Generate"}
                  </Button>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Export Jobs</CardTitle>
          <CardDescription>
            Latest queued, completed, and failed report artifacts.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {completedExports.length === 0 ? (
            <p className="text-sm text-slate-500">No export jobs yet.</p>
          ) : (
            <div className="space-y-3">
              {completedExports.map((job) => (
                <div
                  key={job.id}
                  className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between"
                >
                  <div>
                    <p className="font-medium text-slate-900">
                      {job.artifact_name ?? `${job.report_type}.${job.export_format}`}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {job.report_type} • {job.export_format.toUpperCase()} • created {formatTimestamp(job.created_at)}
                    </p>
                    {job.error_message && (
                      <p className="mt-1 text-sm text-red-600">{job.error_message}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        job.status === "completed"
                          ? "success"
                          : job.status === "failed" || job.status === "dead_letter"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {job.status}
                    </Badge>
                    <Button variant="outline" size="sm" asChild>
                      <Link href={withQuery("/report/preview", { projectId, jobId: job.id })}>Preview</Link>
                    </Button>
                    {job.status === "completed" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => window.open(`/api/exports/${job.id}/artifact`, "_blank")}
                      >
                        Open artifact
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Publish Project</DialogTitle>
            <DialogDescription>
              Publishing locks the current reporting project and exposes the final reporting state.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPublishDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handlePublish} disabled={publishMutation.isPending}>
              {publishMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-2 h-4 w-4" />
              )}
              Confirm Publish
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function BoundaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-slate-500">{label}</span>
      <span className="text-sm font-medium text-slate-900">{value}</span>
    </div>
  );
}

function IssueList({
  title,
  description,
  icon: Icon,
  tone,
  items,
}: {
  title: string;
  description: string;
  icon: typeof AlertTriangle;
  tone: "red" | "amber";
  items: ReadinessDetail[];
}) {
  if (items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-500">No items.</p>
        </CardContent>
      </Card>
    );
  }

  const classes =
    tone === "red"
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-amber-200 bg-amber-50 text-amber-700";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-5 w-5" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {items.map((item) => (
          <div key={item.code} className={cn("rounded-lg border px-4 py-3", classes)}>
            <p className="font-medium">{item.message}</p>
            <p className="mt-1 text-sm">Code: {item.code} • Count: {item.count}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
