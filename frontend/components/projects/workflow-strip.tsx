"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Loader2,
  Play,
  Eye,
  Send,
  CheckCircle2,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

type ProjectStatus =
  | "draft"
  | "active"
  | "review"
  | "published"
  | "archived";

interface WorkflowBlocker {
  code: string;
  message: string;
  severity: "blocker" | "warning";
  tab: string | null;
}

interface WorkflowStatus {
  current_status: ProjectStatus;
  next_action: string | null;
  next_status: ProjectStatus | null;
  can_advance: boolean;
  blockers: WorkflowBlocker[];
  warnings: WorkflowBlocker[];
}

const STAGES: Array<{
  key: ProjectStatus;
  label: string;
}> = [
  { key: "draft", label: "Draft" },
  { key: "active", label: "Active" },
  { key: "review", label: "Review" },
  { key: "published", label: "Published" },
];

const ACTION_MUTATION_PATH: Record<string, string> = {
  start_project: "activate",
  review_project: "start-review",
  publish_project: "publish",
};

const ACTION_LABEL: Record<string, { label: string; icon: React.ReactNode }> = {
  start_project: { label: "Activate", icon: <Play className="h-4 w-4" /> },
  review_project: {
    label: "Start Review",
    icon: <Eye className="h-4 w-4" />,
  },
  publish_project: { label: "Publish", icon: <Send className="h-4 w-4" /> },
};

interface WorkflowStripProps {
  projectId: string;
  onBlockerClick?: (tab: string | null) => void;
  onError?: (message: string | null) => void;
}

export function WorkflowStrip({
  projectId,
  onBlockerClick,
  onError,
}: WorkflowStripProps) {
  const queryClient = useQueryClient();

  const { data, isLoading } = useApiQuery<WorkflowStatus>(
    ["project-workflow-status", projectId],
    `/projects/${projectId}/workflow-status`
  );

  const action = data?.next_action ?? null;
  const mutationPath = action ? ACTION_MUTATION_PATH[action] : null;

  const advanceMutation = useApiMutation<unknown, void>(
    mutationPath ? `/projects/${projectId}/${mutationPath}` : `/projects/${projectId}/activate`,
    "POST",
    {
      onMutate: () => onError?.(null),
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: ["project-workflow-status", projectId],
        });
        await queryClient.invalidateQueries({
          queryKey: ["project", projectId],
        });
        await queryClient.invalidateQueries({ queryKey: ["projects"] });
      },
      onError: (err) => onError?.(err.message || "Unable to advance project."),
    }
  );

  const currentIndex = useMemo(() => {
    if (!data) return 0;
    return Math.max(
      0,
      STAGES.findIndex((stage) => stage.key === data.current_status)
    );
  }, [data]);

  if (isLoading || !data) {
    return (
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white px-6 py-4 text-sm text-slate-500">
        <Loader2 className="inline h-4 w-4 animate-spin" /> Loading workflow status...
      </div>
    );
  }

  const actionLabel = action ? ACTION_LABEL[action] : null;
  const isPublished = data.current_status === "published";

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-4 px-6 py-4">
        <div className="flex min-w-0 flex-1 items-center">
          {STAGES.map((stage, idx) => {
            const isDone = idx < currentIndex;
            const isCurrent = idx === currentIndex;
            return (
              <div key={stage.key} className="flex flex-1 items-center last:flex-initial">
                <div className="flex items-center gap-2">
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold ${
                      isDone
                        ? "bg-emerald-100 text-emerald-700"
                        : isCurrent
                          ? "bg-cyan-700 text-white"
                          : "bg-slate-100 text-slate-500"
                    }`}
                  >
                    {isDone ? (
                      <Check className="h-3 w-3" strokeWidth={3} />
                    ) : (
                      idx + 1
                    )}
                  </span>
                  <span
                    className={`whitespace-nowrap text-sm ${
                      isCurrent
                        ? "font-semibold text-cyan-800"
                        : isDone
                          ? "text-slate-600"
                          : "text-slate-500"
                    }`}
                  >
                    {stage.label}
                  </span>
                </div>
                {idx < STAGES.length - 1 && (
                  <div
                    className={`mx-2 h-px flex-1 ${
                      isDone ? "bg-emerald-300" : "border-t border-dashed border-slate-200"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {isPublished ? (
          <div className="inline-flex items-center gap-2 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4" />
            Project published
          </div>
        ) : actionLabel ? (
          <Button
            onClick={() => advanceMutation.mutate(undefined)}
            disabled={!data.can_advance || advanceMutation.isPending}
          >
            {advanceMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              actionLabel.icon
            )}
            {actionLabel.label}
            <ChevronRight className="h-4 w-4" />
          </Button>
        ) : null}
      </div>

      {data.blockers.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-amber-50/60 px-6 py-2.5 text-xs">
          <span className="inline-flex items-center gap-1 font-medium text-amber-800">
            <AlertTriangle className="h-3.5 w-3.5" />
            {data.blockers.length}{" "}
            {data.blockers.length === 1 ? "blocker" : "blockers"}{" "}
            {data.next_status ? `before ${STAGES.find((s) => s.key === data.next_status)?.label}` : ""}:
          </span>
          {data.blockers.map((blocker) => (
            <button
              key={blocker.code}
              type="button"
              onClick={() =>
                blocker.tab
                  ? onBlockerClick?.(blocker.tab)
                  : undefined
              }
              className={`inline-flex items-center gap-1 rounded-full border border-amber-200 bg-white px-2 py-0.5 text-amber-800 ${
                blocker.tab
                  ? "cursor-pointer hover:border-amber-300"
                  : "cursor-default"
              }`}
            >
              <AlertTriangle className="h-3 w-3" />
              {blocker.message}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
