"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowLeft, FileSearch, Loader2, ShieldAlert } from "lucide-react";

import { useApiQuery } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type ExportJob = {
  id: number;
  report_type: string;
  export_format: string;
  status: string;
  artifact_name: string | null;
  artifact_encoding: string | null;
  created_at: string | null;
  completed_at: string | null;
};

type ExportListResponse = {
  items: ExportJob[];
  total: number;
};

type ArtifactResponse = {
  job_id: number;
  export_format: string;
  content_type: string;
  artifact_encoding: string;
  artifact_name: string;
  content: string | Record<string, unknown>;
};

export default function ReportPreviewPage() {
  const searchParams = useSearchParams();
  const jobId = searchParams.get("jobId");
  const resolvedProjectId = Number(searchParams.get("projectId") || "1");
  const projectId = Number.isFinite(resolvedProjectId) && resolvedProjectId > 0 ? resolvedProjectId : 1;

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me", "report-preview"], "/auth/me");

  const role = me?.roles?.[0]?.role ?? "";
  const canAccess = role === "admin" || role === "esg_manager";
  const accessDenied = Boolean(role) && !canAccess;

  const { data: jobs, isLoading: jobsLoading } = useApiQuery<ExportListResponse>(
    ["report-preview", "exports", projectId],
    `/projects/${projectId}/exports`,
    { enabled: canAccess }
  );

  const selectedJob = useMemo(() => {
    const items = jobs?.items ?? [];
    if (jobId) {
      const exact = items.find((item) => String(item.id) === jobId);
      if (exact) return exact;
    }
    return items.find((item) => item.status === "completed") ?? items[0] ?? null;
  }, [jobId, jobs?.items]);

  const {
    data: artifact,
    isLoading: artifactLoading,
    error: artifactError,
  } = useApiQuery<ArtifactResponse>(
    ["report-preview", "artifact", selectedJob?.id],
    selectedJob ? `/exports/${selectedJob.id}/artifact` : "/exports/0/artifact",
    { enabled: canAccess && Boolean(selectedJob?.id) && selectedJob?.status === "completed" }
  );

  if (meLoading || (canAccess && (jobsLoading || artifactLoading))) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="space-y-6">
        <Header projectId={projectId} />
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only admin and ESG manager roles can preview report exports.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Header projectId={projectId} />
      {!selectedJob ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-slate-500">
            <FileSearch className="mb-3 h-10 w-10 text-slate-300" />
            <p>No export jobs found.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Preview Job</CardTitle>
              <CardDescription>
                {selectedJob.artifact_name ?? `${selectedJob.report_type}.${selectedJob.export_format}`}
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <PreviewMetric label="Job ID" value={String(selectedJob.id)} />
              <PreviewMetric label="Status" value={selectedJob.status} />
              <PreviewMetric label="Format" value={selectedJob.export_format.toUpperCase()} />
              <PreviewMetric label="Completed" value={selectedJob.completed_at ? new Date(selectedJob.completed_at).toLocaleString() : "Pending"} />
            </CardContent>
          </Card>

          {selectedJob.status !== "completed" ? (
            <Card>
              <CardContent className="flex items-center gap-3 p-6 text-amber-700">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <p>This export job is not completed yet. Run export jobs or wait for processing before previewing.</p>
              </CardContent>
            </Card>
          ) : artifactError ? (
            <Card>
              <CardContent className="flex items-center gap-3 p-6 text-red-700">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <p>Unable to load artifact preview.</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Artifact Preview</CardTitle>
                <CardDescription>
                  {artifact?.artifact_name} • {artifact?.content_type}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="max-h-[560px] overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">
                  {formatArtifactContent(artifact?.content)}
                </pre>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function Header({ projectId }: { projectId: number }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Report Preview</h2>
        <p className="mt-1 text-sm text-slate-500">
          Inspect the latest generated export artifact before sharing it.
        </p>
      </div>
      <Button variant="outline" asChild>
        <Link href={`/report?projectId=${projectId}`}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to report
        </Link>
      </Button>
    </div>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 px-3 py-2">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function formatArtifactContent(content: ArtifactResponse["content"] | undefined) {
  if (content === undefined) return "No artifact content available.";
  if (typeof content === "string") return content;
  return JSON.stringify(content, null, 2);
}
