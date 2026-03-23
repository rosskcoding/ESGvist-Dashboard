"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Shield,
  Download,
  FileText,
  FileSpreadsheet,
  FileOutput,
  Code,
  Loader2,
  RefreshCw,
  Send,
  Clock,
} from "lucide-react";

interface BlockingIssue {
  id: string;
  message: string;
  link: string;
  entity_type: string;
}

interface Warning {
  id: string;
  message: string;
  link: string;
  entity_type: string;
}

interface BoundaryValidation {
  boundary_name: string;
  boundary_id: number | null;
  snapshot_locked: boolean;
  entities_in_scope: number;
  manual_overrides: number;
}

interface ExportFile {
  id: number;
  filename: string;
  format: string;
  created_at: string;
  size_bytes: number;
  download_url: string;
}

interface ReadinessData {
  status?: "ready" | "warnings" | "blocking";
  ready?: boolean;
  overall_ready?: boolean;
  completion_percent?: number;
  completion_percentage?: number;
  boundary?: BoundaryValidation;
  blocking_issues?: BlockingIssue[];
  warnings?: Warning[];
  exports?: ExportFile[];
}

export default function ReportPage() {
  const [projectId] = useState(1);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [selectedFormats, setSelectedFormats] = useState<Record<string, boolean>>({
    gri_pdf: false,
    gri_excel: false,
    full_pdf: false,
    data_excel: false,
    xbrl: false,
  });

  const { data, isLoading, error, refetch } = useApiQuery<ReadinessData>(
    ["report", "readiness", projectId],
    `/projects/${projectId}/export/readiness`
  );

  const readinessCheck = useApiMutation<ReadinessData>(
    `/projects/${projectId}/export/readiness`,
    "POST"
  );

  const publishMutation = useApiMutation(
    `/projects/${projectId}/publish`,
    "POST"
  );

  const exportMutation = useApiMutation<{ download_url: string }, { format: string }>(
    `/projects/${projectId}/export`,
    "POST"
  );

  const handleRunReadiness = async () => {
    await readinessCheck.mutateAsync(undefined);
    refetch();
  };

  const handlePublish = async () => {
    await publishMutation.mutateAsync(undefined);
    setPublishDialogOpen(false);
    refetch();
  };

  const handleExport = async (format: string) => {
    const result = await exportMutation.mutateAsync({ format });
    if (result?.download_url) {
      window.open(result.download_url, "_blank");
    }
    refetch();
  };

  const toggleFormat = (key: string) => {
    if (key === "xbrl") return;
    setSelectedFormats((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Report &amp; Export</h2>
          <p className="mt-1 text-sm text-slate-500">
            Check readiness and export your report
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

  const readiness = data ?? {
    status: "blocking" as const,
    completion_percentage: 0,
    boundary: {
      boundary_name: "No boundary",
      boundary_id: null,
      snapshot_locked: false,
      entities_in_scope: 0,
      manual_overrides: 0,
    },
    blocking_issues: [],
    warnings: [],
    exports: [],
  };

  const statusConfig = {
    ready: {
      icon: CheckCircle2,
      label: "Ready to Publish",
      color: "text-green-600",
      bg: "bg-green-50 border-green-200",
      badge: "default" as const,
    },
    warnings: {
      icon: AlertTriangle,
      label: "Warnings Present",
      color: "text-amber-600",
      bg: "bg-amber-50 border-amber-200",
      badge: "warning" as const,
    },
    blocking: {
      icon: XCircle,
      label: "Blocking Issues",
      color: "text-red-600",
      bg: "bg-red-50 border-red-200",
      badge: "destructive" as const,
    },
  };

  const derivedStatus = readiness.ready ? "ready" : ((readiness.warnings ?? []).length > 0 && (readiness.blocking_issues ?? []).length === 0) ? "warnings" : "blocking";
  const sc = statusConfig[derivedStatus as keyof typeof statusConfig] ?? statusConfig.blocking;
  const StatusIcon = sc.icon;

  const formatCards = [
    {
      key: "gri_pdf",
      label: "GRI Content Index",
      format: "PDF",
      icon: FileText,
      disabled: false,
    },
    {
      key: "gri_excel",
      label: "GRI Content Index",
      format: "Excel",
      icon: FileSpreadsheet,
      disabled: false,
    },
    {
      key: "full_pdf",
      label: "Full Report",
      format: "PDF",
      icon: FileOutput,
      disabled: false,
    },
    {
      key: "data_excel",
      label: "Data Export",
      format: "Excel",
      icon: FileSpreadsheet,
      disabled: false,
    },
    {
      key: "xbrl",
      label: "XBRL",
      format: "Coming Soon",
      icon: Code,
      disabled: true,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Report &amp; Export</h2>
          <p className="mt-1 text-sm text-slate-500">
            Check readiness and export your report
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={handleRunReadiness}
            disabled={readinessCheck.isPending}
          >
            {readinessCheck.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Run Readiness Check
          </Button>
          <Button
            onClick={() => setPublishDialogOpen(true)}
            disabled={derivedStatus !== "ready"}
          >
            <Send className="mr-2 h-4 w-4" />
            Publish Project
          </Button>
        </div>
      </div>

      {/* Readiness Check Section */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Overall Status */}
        <Card className={cn("border", sc.bg)}>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <StatusIcon className={cn("h-5 w-5", sc.color)} />
              Overall Status
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <Badge variant={sc.badge} className="text-sm">
                {sc.label}
              </Badge>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">Completion</span>
                <span className="text-2xl font-bold text-slate-900">
                  {Math.round((readiness.completion_percentage ?? readiness.completion_percent ?? 0))}%
                </span>
              </div>
              <Progress
                value={(readiness.completion_percentage ?? readiness.completion_percent ?? 0)}
                className="h-3"
                indicatorClassName={cn(
                  (readiness.completion_percentage ?? readiness.completion_percent ?? 0) >= 80
                    ? "bg-green-500"
                    : (readiness.completion_percentage ?? readiness.completion_percent ?? 0) >= 50
                      ? "bg-amber-500"
                      : "bg-red-500"
                )}
              />
            </div>
          </CardContent>
        </Card>

        {/* Boundary Validation */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-slate-600" />
              Boundary Validation
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">Selected Boundary</span>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {(readiness.boundary ?? {} as any).boundary_name}
                </span>
                <Badge variant="secondary">Active</Badge>
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">Snapshot Locked</span>
              {(readiness.boundary ?? {} as any).snapshot_locked ? (
                <Badge variant="default">
                  <CheckCircle2 className="mr-1 h-3 w-3" /> Locked
                </Badge>
              ) : (
                <Badge variant="destructive">
                  <XCircle className="mr-1 h-3 w-3" /> Not Locked
                </Badge>
              )}
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">Entities in Scope</span>
              <span className="text-sm font-semibold">
                {(readiness.boundary ?? {} as any).entities_in_scope}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">Manual Overrides</span>
              <span className="text-sm font-semibold">
                {(readiness.boundary ?? {} as any).manual_overrides}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Issues Lists */}
      {(readiness.blocking_issues ?? []).length > 0 && (
        <Card className="border-red-200">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-red-600">
              <XCircle className="h-5 w-5" />
              Blocking Issues ({(readiness.blocking_issues ?? []).length})
            </CardTitle>
            <CardDescription>
              These must be resolved before publishing
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(readiness.blocking_issues ?? []).map((issue) => (
                <Link
                  key={issue.id}
                  href={issue.link}
                  className="flex items-center gap-3 rounded-lg border border-red-100 bg-red-50 p-3 transition-colors hover:bg-red-100"
                >
                  <XCircle className="h-4 w-4 shrink-0 text-red-500" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-red-800">
                      {issue.message}
                    </p>
                    <p className="text-xs text-red-600">{issue.entity_type}</p>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {(readiness.warnings ?? []).length > 0 && (
        <Card className="border-amber-200">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-amber-600">
              <AlertTriangle className="h-5 w-5" />
              Warnings ({(readiness.warnings ?? []).length})
            </CardTitle>
            <CardDescription>
              These are recommended but not required
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(readiness.warnings ?? []).map((warning) => (
                <Link
                  key={warning.id}
                  href={warning.link}
                  className="flex items-center gap-3 rounded-lg border border-amber-100 bg-amber-50 p-3 transition-colors hover:bg-amber-100"
                >
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-amber-800">
                      {warning.message}
                    </p>
                    <p className="text-xs text-amber-600">{warning.entity_type}</p>
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Export Section */}
      <Card>
        <CardHeader>
          <CardTitle>Export</CardTitle>
          <CardDescription>
            Select formats and generate your reports
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Format Cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {formatCards.map((fc) => {
              const Icon = fc.icon;
              const checked = selectedFormats[fc.key] ?? false;
              return (
                <div
                  key={fc.key}
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-4 transition-colors",
                    fc.disabled
                      ? "cursor-not-allowed border-slate-100 bg-slate-50 opacity-60"
                      : checked
                        ? "border-blue-200 bg-blue-50"
                        : "cursor-pointer border-slate-200 hover:border-slate-300"
                  )}
                  onClick={() => toggleFormat(fc.key)}
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={() => toggleFormat(fc.key)}
                    disabled={fc.disabled}
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-slate-600" />
                      <span className="text-sm font-medium">{fc.label}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{fc.format}</p>
                  </div>
                  {!fc.disabled && checked && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExport(fc.key);
                      }}
                      disabled={exportMutation.isPending}
                    >
                      {exportMutation.isPending ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        "Generate"
                      )}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Previously Generated Exports */}
          {(readiness.exports ?? []).length > 0 && (
            <div>
              <h4 className="mb-3 text-sm font-medium text-slate-700">
                Previously Generated Exports
              </h4>
              <div className="space-y-2">
                {(readiness.exports ?? []).map((exp) => (
                  <div
                    key={exp.id}
                    className="flex items-center justify-between rounded-lg border border-slate-200 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <FileText className="h-4 w-4 text-slate-400" />
                      <div>
                        <p className="text-sm font-medium">{exp.filename}</p>
                        <p className="text-xs text-slate-500">
                          {new Date(exp.created_at).toLocaleString()} &middot;{" "}
                          {(exp.size_bytes / 1024).toFixed(1)} KB
                        </p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(exp.download_url, "_blank")}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Publish Confirmation Dialog */}
      <Dialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Publish Project</DialogTitle>
            <DialogDescription>
              Are you sure you want to publish this project? This will lock the
              current reporting period and make the data available for external
              stakeholders. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button
              variant="outline"
              onClick={() => setPublishDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handlePublish}
              disabled={publishMutation.isPending}
            >
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
