"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  Check,
  Wand2,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";

interface AutoAssignPreviewItem {
  assignment_id: number;
  shared_element_code: string;
  shared_element_name: string;
  entity_id: number | null;
  entity_name: string | null;
  proposed_collector_id: number | null;
  proposed_collector_name: string | null;
  proposed_reviewer_id: number | null;
  proposed_reviewer_name: string | null;
  reason: string;
}

interface AutoAssignPreview {
  mode: "mono" | "multi";
  org_entity_count: number;
  default_collector_user_id: number | null;
  default_collector_name: string | null;
  covered_count: number;
  skipped_count: number;
  items: AutoAssignPreviewItem[];
}

interface OrgUser {
  id: number;
  email: string;
  full_name: string;
}

interface OrgUsersResponse {
  users: OrgUser[];
}

interface Props {
  projectId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onError?: (msg: string | null) => void;
}

export function AutoAssignDialog({
  projectId,
  open,
  onOpenChange,
  onError,
}: Props) {
  const queryClient = useQueryClient();
  const [defaultCollector, setDefaultCollector] = useState<string>("");

  const previewPath = defaultCollector
    ? `/projects/${projectId}/auto-assign/preview?default_collector_user_id=${defaultCollector}`
    : `/projects/${projectId}/auto-assign/preview`;

  const { data: preview, isLoading } = useApiQuery<AutoAssignPreview>(
    ["auto-assign-preview", projectId, defaultCollector],
    previewPath,
    { enabled: open }
  );

  const { data: orgUsersData } = useApiQuery<OrgUsersResponse>(
    ["org-users"],
    "/auth/organization/users",
    { enabled: open }
  );
  const users = orgUsersData?.users ?? [];

  const applyMutation = useApiMutation<
    { updated_count: number; skipped_count: number; mode: string },
    { dry_run: boolean; default_collector_user_id: number | null }
  >(`/projects/${projectId}/auto-assign`, "POST", {
    onMutate: () => onError?.(null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["project-assignments-matrix", projectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["project-workflow-status", projectId],
      });
      onOpenChange(false);
    },
    onError: (err) => onError?.(err.message || "Unable to auto-assign."),
  });

  const coveredPct = useMemo(() => {
    if (!preview) return 0;
    const total = preview.covered_count + preview.skipped_count;
    if (total === 0) return 0;
    return Math.round((preview.covered_count / total) * 100);
  }, [preview]);

  const canApply = (preview?.covered_count ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-cyan-700" />
            Auto-assign unassigned work
          </DialogTitle>
          <DialogDescription>
            {preview?.mode === "mono" ? (
              <>
                Your organization has a single entity — we&apos;ll assign all
                unassigned items to one default collector.
              </>
            ) : (
              <>
                We&apos;ll assign each unassigned item based on the default
                collector/reviewer on its entity (or the nearest parent in the
                tree).
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        {isLoading || !preview ? (
          <div className="flex min-h-[180px] items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Mode & selector */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">
                    Mode:{" "}
                    <span
                      className={
                        preview.mode === "mono"
                          ? "text-emerald-700"
                          : "text-cyan-700"
                      }
                    >
                      {preview.mode === "mono"
                        ? "Mono-company"
                        : "Multi-entity"}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    {preview.org_entity_count}{" "}
                    {preview.org_entity_count === 1 ? "entity" : "entities"} in
                    organization
                  </div>
                </div>
                {preview.mode === "multi" && (
                  <Link
                    href="/settings/company-structure"
                    target="_blank"
                    className="inline-flex items-center gap-1 text-xs text-cyan-700 hover:underline"
                  >
                    Configure entity owners
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                )}
              </div>
            </div>

            {preview.mode === "mono" && (
              <Select
                label="Default collector"
                options={[
                  { value: "", label: "Use entity default (if set)" },
                  ...users.map((u) => ({
                    value: String(u.id),
                    label: u.full_name || u.email,
                  })),
                ]}
                value={defaultCollector}
                onChange={setDefaultCollector}
              />
            )}

            {/* Summary */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-center">
                <div className="text-2xl font-bold text-emerald-700">
                  {preview.covered_count}
                </div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-emerald-700">
                  Will assign
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center">
                <div className="text-2xl font-bold text-slate-900">
                  {coveredPct}%
                </div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  Coverage
                </div>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center">
                <div className="text-2xl font-bold text-amber-700">
                  {preview.skipped_count}
                </div>
                <div className="text-[11px] font-medium uppercase tracking-wider text-amber-700">
                  Skipped
                </div>
              </div>
            </div>

            {/* Preview list */}
            {preview.items.length === 0 ? (
              <div className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
                No unassigned items — nothing to auto-assign.
              </div>
            ) : (
              <div className="max-h-[260px] overflow-y-auto rounded-lg border border-slate-200 bg-white">
                <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] items-center border-b border-slate-100 bg-slate-50 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  <div>Element</div>
                  <div>Entity</div>
                  <div>Collector</div>
                  <div>Reviewer</div>
                </div>
                {preview.items.map((item) => {
                  const willAssign =
                    item.proposed_collector_id !== null ||
                    item.proposed_reviewer_id !== null;
                  return (
                    <div
                      key={item.assignment_id}
                      className={`grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] items-center border-b border-slate-100 px-3 py-2 text-xs ${
                        willAssign ? "" : "bg-amber-50/40"
                      }`}
                    >
                      <div className="min-w-0 pr-2">
                        <div className="truncate font-medium text-slate-900">
                          {item.shared_element_name || item.shared_element_code}
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {item.shared_element_code}
                        </div>
                      </div>
                      <div className="truncate pr-2 text-slate-700">
                        {item.entity_name || (
                          <span className="text-slate-400">—</span>
                        )}
                      </div>
                      <div>
                        {item.proposed_collector_name ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-800">
                            <Check className="h-3 w-3" strokeWidth={3} />
                            {item.proposed_collector_name}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-amber-800">
                            <AlertTriangle className="h-3 w-3" />
                            skip
                          </span>
                        )}
                      </div>
                      <div>
                        {item.proposed_reviewer_name ? (
                          <span className="text-slate-600">
                            {item.proposed_reviewer_name}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              applyMutation.mutate({
                dry_run: false,
                default_collector_user_id: defaultCollector
                  ? Number(defaultCollector)
                  : null,
              })
            }
            disabled={!canApply || applyMutation.isPending}
          >
            {applyMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Wand2 className="h-4 w-4" />
            )}
            Apply{" "}
            {preview
              ? `(${preview.covered_count} assignment${
                  preview.covered_count === 1 ? "" : "s"
                })`
              : ""}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
