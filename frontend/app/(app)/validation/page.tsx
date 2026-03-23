"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowUpDown,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  Loader2,
  MessageSquare,
  RotateCcw,
  Send,
  ShieldAlert,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface ReviewQueueItem {
  id: number;
  project_id: number;
  project_name: string;
  element_name: string;
  element_code: string;
  submitter_name: string;
  submitted_at: string | null;
  status: "submitted" | "in_review";
  urgency: "low" | "medium" | "high" | "critical";
  is_outlier: boolean;
  is_overdue: boolean;
  entity_name: string | null;
  standard_code: string;
  standard_name: string;
  value: string;
  unit: string;
  methodology: string;
  narrative: string;
  previous_value?: string | null;
  previous_unit?: string | null;
  dimensions: {
    scope?: string | null;
    gas_type?: string | null;
    category?: string | null;
  };
  evidence: Array<{
    id: number;
    filename: string | null;
    url: string | null;
    type: string;
  }>;
  boundary_context: {
    entity_name: string | null;
    inclusion_status: string;
    inclusion_reason?: string;
    consolidation_method: string;
    snapshot_version: string;
  };
}

interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
}

interface ReviewComment {
  id: number;
  author_name?: string | null;
  created_at: string | null;
  content: string;
  type: string;
  parent_id?: number | null;
  replies?: ReviewComment[];
}

interface ReviewAssistResult {
  summary: string;
  anomalies: string[];
  missing_evidence: string[];
  draft_comment?: string | null;
  reuse_impact?: string | null;
  provider?: string | null;
}

const URGENCY_CONFIG: Record<
  ReviewQueueItem["urgency"],
  { label: string; variant: "secondary" | "warning" | "destructive" | "default" }
> = {
  low: { label: "Low", variant: "secondary" },
  medium: { label: "Medium", variant: "default" },
  high: { label: "High", variant: "warning" },
  critical: { label: "Critical", variant: "destructive" },
};

const COMMENT_TYPE_CLASSES: Record<string, string> = {
  question: "border-blue-200 bg-blue-50 text-blue-700",
  issue: "border-red-200 bg-red-50 text-red-700",
  suggestion: "border-emerald-200 bg-emerald-50 text-emerald-700",
  general: "border-slate-200 bg-slate-50 text-slate-700",
};

const REJECT_REASONS = [
  { value: "OUT_OF_BOUNDARY_SCOPE", label: "Out of boundary scope" },
  { value: "WRONG_CONSOLIDATION_CONTEXT", label: "Wrong consolidation context" },
  { value: "DATA_QUALITY_ISSUE", label: "Data quality issue" },
  { value: "EVIDENCE_MISSING", label: "Evidence missing" },
] as const;

function relativeTime(dateStr: string | null) {
  if (!dateStr) return "Unknown";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.max(0, Math.floor(diff / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function buildReviewComment(reasonCode: string, freeText: string) {
  const reasonLabel = REJECT_REASONS.find((reason) => reason.value === reasonCode)?.label;
  return [reasonLabel ? `Reason: ${reasonLabel}` : null, freeText.trim()]
    .filter(Boolean)
    .join("\n\n");
}

export default function ValidationPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | "submitted" | "in_review">("all");
  const [sortBy, setSortBy] = useState<"date" | "urgency">("date");
  const [replyToId, setReplyToId] = useState<number | null>(null);
  const [commentDraft, setCommentDraft] = useState("");
  const [commentType, setCommentType] = useState<"question" | "issue" | "suggestion">("question");
  const [actionMode, setActionMode] = useState<"none" | "reject" | "revision">("none");
  const [actionComment, setActionComment] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [batchMode, setBatchMode] = useState<"none" | "approve" | "reject" | "revision">("none");
  const [batchComment, setBatchComment] = useState("");
  const [batchReason, setBatchReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [aiAssist, setAiAssist] = useState<ReviewAssistResult | null>(null);
  const [aiAssistLoading, setAiAssistLoading] = useState(false);
  const [aiAssistError, setAiAssistError] = useState<string | null>(null);

  const { data: me } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me", "validation"], "/auth/me");

  const role = me?.roles?.[0]?.role ?? "";
  const isReviewer = role === "reviewer";
  const isAuditor = role === "auditor";
  const accessDenied = Boolean(role) && !isReviewer && !isAuditor;

  const statusesParam = statusFilter === "all" ? "submitted,in_review" : statusFilter;
  const {
    data,
    isLoading,
    error,
    refetch,
  } = useApiQuery<ReviewQueueResponse>(
    ["review-items", statusesParam],
    `/review/items?statuses=${statusesParam}`,
    { enabled: !accessDenied }
  );

  const filteredItems = useMemo(() => {
    const items = [...(data?.items ?? [])];
    const urgencyOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    items.sort((left, right) => {
      if (sortBy === "urgency") {
        return urgencyOrder[left.urgency] - urgencyOrder[right.urgency];
      }
      return new Date(right.submitted_at ?? 0).getTime() - new Date(left.submitted_at ?? 0).getTime();
    });
    return items;
  }, [data?.items, sortBy]);

  useEffect(() => {
    if (filteredItems.length === 0) {
      setSelectedId(null);
      setSelectedIds([]);
      return;
    }
    if (!selectedId || !filteredItems.some((item) => item.id === selectedId)) {
      setSelectedId(filteredItems[0].id);
    }
    setSelectedIds((prev) => prev.filter((id) => filteredItems.some((item) => item.id === id)));
  }, [filteredItems, selectedId]);

  useEffect(() => {
    setAiAssist(null);
    setAiAssistError(null);
  }, [selectedId]);

  const selectedItem = useMemo(
    () => filteredItems.find((item) => item.id === selectedId) ?? null,
    [filteredItems, selectedId]
  );

  const {
    data: comments = [],
    isLoading: commentsLoading,
    refetch: refetchComments,
  } = useApiQuery<ReviewComment[]>(
    ["review-comments", selectedId],
    selectedId ? `/comments/data-point/${selectedId}` : "/comments/data-point/0",
    { enabled: Boolean(selectedId) && !accessDenied }
  );

  async function refreshQueue() {
    await refetch();
    if (selectedId) {
      await refetchComments();
    }
  }

  async function runSingleAction(mode: "approve" | "reject" | "revision") {
    if (!selectedId) return;
    setActionError(null);
    setIsSubmitting(true);
    try {
      if (mode === "approve") {
        await api.post(`/data-points/${selectedId}/approve`, {});
      } else if (mode === "reject") {
        await api.post(`/data-points/${selectedId}/reject`, {
          comment: buildReviewComment(rejectReason, actionComment),
        });
      } else {
        await api.post(`/data-points/${selectedId}/request-revision`, {
          comment: buildReviewComment(rejectReason, actionComment),
        });
      }
      setActionMode("none");
      setActionComment("");
      setRejectReason("");
      await refreshQueue();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runBatchAction(mode: "approve" | "reject" | "revision") {
    if (selectedIds.length === 0) return;
    setActionError(null);
    setIsSubmitting(true);
    try {
      if (mode === "approve") {
        await api.post("/review/batch-approve", {
          data_point_ids: selectedIds,
          comment: "Batch-approved from validation screen.",
        });
      } else if (mode === "reject") {
        await api.post("/review/batch-reject", {
          data_point_ids: selectedIds,
          comment: buildReviewComment(batchReason, batchComment),
        });
      } else {
        await api.post("/review/batch-request-revision", {
          data_point_ids: selectedIds,
          comment: buildReviewComment(batchReason, batchComment),
        });
      }
      setSelectedIds([]);
      setBatchMode("none");
      setBatchComment("");
      setBatchReason("");
      await refreshQueue();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function addComment() {
    if (!selectedId || !commentDraft.trim()) return;
    setActionError(null);
    setIsSubmitting(true);
    try {
      await api.post("/comments", {
        body: commentDraft,
        comment_type: commentType,
        data_point_id: selectedId,
        parent_comment_id: replyToId ?? undefined,
      });
      setCommentDraft("");
      setReplyToId(null);
      await refetchComments();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runAiReviewAssist() {
    if (!selectedId || !isReviewer) return;
    setAiAssistError(null);
    setAiAssistLoading(true);
    try {
      const result = await api.post<ReviewAssistResult>(`/ai/review-assist?data_point_id=${selectedId}`);
      setAiAssist(result);
    } catch (err) {
      setAiAssistError((err as Error).message);
    } finally {
      setAiAssistLoading(false);
    }
  }

  function toggleSelected(id: number) {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id]));
  }

  function toggleAllVisible() {
    if (selectedIds.length === filteredItems.length) {
      setSelectedIds([]);
      return;
    }
    setSelectedIds(filteredItems.map((item) => item.id));
  }

  if (accessDenied) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Validation Review</h2>
          <p className="mt-1 text-sm text-gray-500">
            Review submitted data points and validation decisions.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only reviewers and auditors can access validation.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Validation Review</h2>
        <p className="mt-1 text-sm text-gray-500">
          Review submitted data points, validate supporting evidence, and drive approval decisions.
        </p>
      </div>

      {isAuditor && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 p-4 text-amber-800">
            <Eye className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Auditor access is read-only.</p>
              <p className="text-sm">Comments and review decisions are disabled on this screen.</p>
            </div>
          </CardContent>
        </Card>
      )}

      {actionError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">{actionError}</CardContent>
        </Card>
      )}

      <div className="flex h-[calc(100vh-240px)] gap-4">
        <div className="flex w-[42%] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="space-y-3 border-b border-slate-200 p-4">
            <div className="flex items-center gap-3">
              <select
                aria-label="Status filter"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
                className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
              >
                <option value="all">All statuses</option>
                <option value="submitted">Submitted</option>
                <option value="in_review">In Review</option>
              </select>

              <div className="flex rounded-md border border-slate-200 text-xs">
                <button
                  onClick={() => setSortBy("date")}
                  className={cn(
                    "px-3 py-2 transition-colors",
                    sortBy === "date" ? "bg-slate-900 text-white" : "hover:bg-slate-50"
                  )}
                >
                  <Clock className="mr-1 inline h-3 w-3" />
                  Date
                </button>
                <button
                  onClick={() => setSortBy("urgency")}
                  className={cn(
                    "px-3 py-2 transition-colors",
                    sortBy === "urgency" ? "bg-slate-900 text-white" : "hover:bg-slate-50"
                  )}
                >
                  <ArrowUpDown className="mr-1 inline h-3 w-3" />
                  Urgency
                </button>
              </div>

              <span className="ml-auto text-xs text-slate-400">{filteredItems.length} items</span>
            </div>

            {isReviewer && filteredItems.length > 0 && (
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between text-sm text-slate-600">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedIds.length > 0 && selectedIds.length === filteredItems.length}
                      onChange={toggleAllVisible}
                    />
                    <span>Select visible</span>
                  </label>
                  <span>{selectedIds.length} selected</span>
                </div>

                {selectedIds.length > 0 && batchMode === "none" && (
                  <div className="flex gap-2">
                    <Button size="sm" className="flex-1 bg-green-600 hover:bg-green-700" onClick={() => setBatchMode("approve")}>Approve Selected</Button>
                    <Button size="sm" variant="destructive" className="flex-1" onClick={() => setBatchMode("reject")}>Reject Selected</Button>
                    <Button size="sm" variant="outline" className="flex-1 border-amber-300 text-amber-700 hover:bg-amber-50" onClick={() => setBatchMode("revision")}>Request Revision Selected</Button>
                  </div>
                )}

                {selectedIds.length > 0 && batchMode !== "none" && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm font-medium text-slate-700">
                      <span>
                        {batchMode === "approve" ? "Batch approve" : batchMode === "reject" ? "Batch reject" : "Batch revision request"}
                      </span>
                      <button
                        className="text-xs text-slate-400 hover:text-slate-600"
                        onClick={() => {
                          setBatchMode("none");
                          setBatchComment("");
                          setBatchReason("");
                        }}
                      >
                        Cancel
                      </button>
                    </div>

                    {batchMode !== "approve" && (
                      <>
                        <select
                          aria-label="Batch reason"
                          value={batchReason}
                          onChange={(event) => setBatchReason(event.target.value)}
                          className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        >
                          <option value="">Select reason code...</option>
                          {REJECT_REASONS.map((reason) => (
                            <option key={reason.value} value={reason.value}>{reason.label}</option>
                          ))}
                        </select>
                        <textarea
                          aria-label="Batch comment"
                          rows={3}
                          value={batchComment}
                          onChange={(event) => setBatchComment(event.target.value)}
                          placeholder="Provide a reviewer note for all selected items..."
                          className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        />
                      </>
                    )}

                    <Button
                      size="sm"
                      onClick={() => runBatchAction(batchMode)}
                      disabled={
                        isSubmitting ||
                        (batchMode !== "approve" && (!batchReason || !batchComment.trim()))
                      }
                      className={cn(
                        "w-full",
                        batchMode === "approve" && "bg-green-600 hover:bg-green-700",
                        batchMode === "revision" && "bg-amber-500 hover:bg-amber-600"
                      )}
                      variant={batchMode === "reject" ? "destructive" : "default"}
                    >
                      {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Confirm batch action"}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center p-12 text-slate-400">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading review queue...
              </div>
            ) : error ? (
              <div className="p-6 text-sm text-red-600">{error.message}</div>
            ) : filteredItems.length === 0 ? (
              <div className="flex items-center justify-center p-12 text-slate-400">No items to review.</div>
            ) : (
              filteredItems.map((item) => {
                const urgency = URGENCY_CONFIG[item.urgency];
                const selected = selectedId === item.id;
                const checked = selectedIds.includes(item.id);
                return (
                  <button
                    key={item.id}
                    className={cn(
                      "flex w-full flex-col gap-2 border-b border-slate-100 px-4 py-3 text-left transition-colors hover:bg-slate-50",
                      selected && "bg-blue-50 hover:bg-blue-50"
                    )}
                    onClick={() => {
                      setSelectedId(item.id);
                      setActionMode("none");
                      setActionComment("");
                      setRejectReason("");
                    }}
                  >
                    <div className="flex items-start gap-3">
                      {isReviewer && (
                        <input
                          aria-label={`Select review item ${item.element_code}`}
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSelected(item.id)}
                          onClick={(event) => event.stopPropagation()}
                          className="mt-1"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-medium leading-tight text-slate-900">
                            {item.is_outlier && <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" />}
                            {item.is_overdue && <span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />}
                            {item.element_name}
                          </span>
                          <Badge variant={urgency.variant} className="shrink-0 text-[10px]">{urgency.label}</Badge>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                          <span>{item.project_name}</span>
                          <span>&middot;</span>
                          <span>{item.submitter_name}</span>
                          <span>&middot;</span>
                          <span>{relativeTime(item.submitted_at)}</span>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          {item.element_code} · {item.standard_code} · {item.status.replace("_", " ")}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div className="flex w-[58%] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
          {!selectedItem ? (
            <div className="flex flex-1 items-center justify-center text-slate-400">Select an item from the review queue.</div>
          ) : (
            <div className="flex flex-1 flex-col overflow-hidden">
              <div className="border-b border-slate-200 p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">{selectedItem.element_name}</h3>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                      <span>{selectedItem.project_name}</span>
                      <span>&middot;</span>
                      <span>{selectedItem.entity_name || selectedItem.boundary_context.entity_name || "Project-level"}</span>
                      <span>&middot;</span>
                      <span>{selectedItem.standard_code} — {selectedItem.standard_name}</span>
                    </div>
                  </div>
                  <Badge variant="secondary">{selectedItem.status.replace("_", " ")}</Badge>
                </div>
              </div>

              <div className="flex-1 space-y-5 overflow-y-auto p-5">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="text-xs font-medium uppercase text-slate-400">Value</p>
                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {selectedItem.value}
                        {selectedItem.unit ? <span className="ml-1 text-sm font-normal text-slate-500">{selectedItem.unit}</span> : null}
                      </p>
                    </div>
                    {selectedItem.previous_value ? (
                      <div>
                        <p className="text-xs font-medium uppercase text-slate-400">Previous period</p>
                        <p className="mt-1 text-xl font-bold text-slate-500">{selectedItem.previous_value}</p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-xs font-medium uppercase text-slate-400">Submitter</p>
                        <p className="mt-1 text-sm text-slate-700">{selectedItem.submitter_name}</p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs font-medium uppercase text-slate-400">Methodology</p>
                      <p className="mt-1 text-sm text-slate-700">{selectedItem.methodology}</p>
                    </div>
                  </div>
                  {selectedItem.narrative && (
                    <div className="mt-3 border-t border-slate-200 pt-3">
                      <p className="text-xs font-medium uppercase text-slate-400">Narrative</p>
                      <p className="mt-1 text-sm text-slate-700">{selectedItem.narrative}</p>
                    </div>
                  )}
                </div>

                {(selectedItem.dimensions.scope || selectedItem.dimensions.gas_type || selectedItem.dimensions.category) && (
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">Dimensions</h4>
                    <div className="flex flex-wrap gap-2">
                      {selectedItem.dimensions.scope && <Badge variant="secondary">Scope: {selectedItem.dimensions.scope}</Badge>}
                      {selectedItem.dimensions.gas_type && <Badge variant="secondary">Gas: {selectedItem.dimensions.gas_type}</Badge>}
                      {selectedItem.dimensions.category && <Badge variant="secondary">Category: {selectedItem.dimensions.category}</Badge>}
                    </div>
                  </div>
                )}

                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">Evidence ({selectedItem.evidence.length})</h4>
                  {selectedItem.evidence.length === 0 ? (
                    <p className="text-sm text-slate-400">No evidence attached.</p>
                  ) : (
                    <ul className="space-y-2">
                      {selectedItem.evidence.map((evidence) => (
                        <li key={evidence.id} className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 px-3 py-2">
                          <span className="flex items-center gap-2 text-sm text-slate-700">
                            <FileText className="h-4 w-4 text-slate-400" />
                            {evidence.filename || `Evidence #${evidence.id}`}
                          </span>
                          {evidence.url ? (
                            <a href={evidence.url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">
                              Open
                            </a>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">Boundary Context</h4>
                  <Card>
                    <CardContent className="grid grid-cols-2 gap-3 p-4 text-sm">
                      <div>
                        <p className="text-xs text-slate-400">Entity</p>
                        <p className="font-medium text-slate-900">{selectedItem.boundary_context.entity_name || "Project-level"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Inclusion status</p>
                        <p className="font-medium text-slate-900">{selectedItem.boundary_context.inclusion_status}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Consolidation method</p>
                        <p className="font-medium text-slate-900">{selectedItem.boundary_context.consolidation_method}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Snapshot</p>
                        <p className="font-medium text-slate-900">{selectedItem.boundary_context.snapshot_version}</p>
                      </div>
                      {selectedItem.boundary_context.inclusion_reason ? (
                        <div className="col-span-2">
                          <p className="text-xs text-slate-400">Inclusion reason</p>
                          <p className="font-medium text-slate-900">{selectedItem.boundary_context.inclusion_reason}</p>
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-xs font-semibold uppercase text-slate-400">Review AI Assistant</h4>
                    {isReviewer ? (
                      <Button size="sm" variant="outline" onClick={runAiReviewAssist} disabled={aiAssistLoading}>
                        {aiAssistLoading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : null}
                        Run AI Review Assist
                      </Button>
                    ) : null}
                  </div>
                  <Card>
                    <CardContent className="space-y-3 p-4 text-sm">
                      {isAuditor ? (
                        <p className="text-slate-500">Review assist is unavailable in auditor read-only mode.</p>
                      ) : aiAssistError ? (
                        <p className="text-red-600">{aiAssistError}</p>
                      ) : aiAssist ? (
                        <>
                          <p className="text-slate-700">{aiAssist.summary}</p>
                          {aiAssist.provider ? (
                            <Badge variant="secondary">{aiAssist.provider}</Badge>
                          ) : null}
                          <div className="grid gap-3 md:grid-cols-2">
                            <div>
                              <p className="text-xs font-medium uppercase text-slate-400">Anomalies</p>
                              {aiAssist.anomalies.length > 0 ? (
                                <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">
                                  {aiAssist.anomalies.map((item) => (
                                    <li key={item}>{item}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="mt-2 text-slate-500">No anomalies detected.</p>
                              )}
                            </div>
                            <div>
                              <p className="text-xs font-medium uppercase text-slate-400">Missing Evidence</p>
                              {aiAssist.missing_evidence.length > 0 ? (
                                <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-700">
                                  {aiAssist.missing_evidence.map((item) => (
                                    <li key={item}>{item}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="mt-2 text-slate-500">No missing evidence flagged.</p>
                              )}
                            </div>
                          </div>
                          {aiAssist.reuse_impact ? (
                            <div>
                              <p className="text-xs font-medium uppercase text-slate-400">Reuse Impact</p>
                              <p className="mt-1 text-slate-700">{aiAssist.reuse_impact}</p>
                            </div>
                          ) : null}
                          {aiAssist.draft_comment ? (
                            <div>
                              <p className="text-xs font-medium uppercase text-slate-400">Suggested Comment</p>
                              <p className="mt-1 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                                {aiAssist.draft_comment}
                              </p>
                            </div>
                          ) : null}
                        </>
                      ) : (
                        <p className="text-slate-500">Run AI review assist for anomaly and evidence hints on the selected item.</p>
                      )}
                    </CardContent>
                  </Card>
                </div>

                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                    <MessageSquare className="mr-1 inline h-3.5 w-3.5" />
                    Comments ({comments.length})
                  </h4>

                  {commentsLoading ? (
                    <div className="flex items-center gap-2 text-sm text-slate-400">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading comments...
                    </div>
                  ) : comments.length > 0 ? (
                    <div className="mb-4 space-y-3">
                      {comments.map((comment) => (
                        <CommentThread key={comment.id} comment={comment} onReply={setReplyToId} />
                      ))}
                    </div>
                  ) : (
                    <p className="mb-4 text-sm text-slate-400">No review comments yet.</p>
                  )}

                  <div className="rounded-lg border border-slate-200 p-3">
                    {replyToId ? (
                      <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                        <span>Replying to comment #{replyToId}</span>
                        <button className="text-slate-400 hover:text-red-500" onClick={() => setReplyToId(null)}>
                          <XCircle className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ) : null}

                    <div className="mb-2 flex gap-2">
                      {(["question", "issue", "suggestion"] as const).map((type) => (
                        <button
                          key={type}
                          onClick={() => setCommentType(type)}
                          disabled={isAuditor}
                          className={cn(
                            "rounded-md border px-2 py-1 text-xs font-medium capitalize transition-colors",
                            commentType === type
                              ? COMMENT_TYPE_CLASSES[type]
                              : "border-slate-200 text-slate-400 hover:text-slate-600",
                            isAuditor && "cursor-not-allowed opacity-60"
                          )}
                        >
                          {type}
                        </button>
                      ))}
                    </div>

                    <div className="flex gap-2">
                      <textarea
                        aria-label="Review comment"
                        rows={3}
                        value={commentDraft}
                        onChange={(event) => setCommentDraft(event.target.value)}
                        placeholder={isAuditor ? "Auditor comment input is disabled." : "Add a review comment..."}
                        disabled={isAuditor}
                        className="flex-1 rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950 disabled:cursor-not-allowed disabled:bg-slate-50"
                      />
                      <Button aria-label="Send comment" size="sm" className="self-end" disabled={isAuditor || !commentDraft.trim() || isSubmitting} onClick={addComment}>
                        {isSubmitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              {isReviewer ? (
                <div className="border-t border-slate-200 p-4">
                  {actionMode === "none" ? (
                    <div className="flex gap-3">
                      <Button className="flex-1 bg-green-600 hover:bg-green-700" disabled={isSubmitting} onClick={() => runSingleAction("approve")}>
                        {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                        Approve
                      </Button>
                      <Button className="flex-1" variant="destructive" onClick={() => setActionMode("reject")}>
                        <XCircle className="h-4 w-4" />
                        Reject
                      </Button>
                      <Button className="flex-1 border-amber-300 text-amber-700 hover:bg-amber-50" variant="outline" onClick={() => setActionMode("revision")}>
                        <RotateCcw className="h-4 w-4" />
                        Request Revision
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={actionMode === "reject" ? "destructive" : "warning"}>
                          {actionMode === "reject" ? "Rejecting" : "Requesting revision"}
                        </Badge>
                        <button
                          className="ml-auto text-xs text-slate-400 hover:text-slate-600"
                          onClick={() => {
                            setActionMode("none");
                            setActionComment("");
                            setRejectReason("");
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                      <select
                        aria-label="Review reason"
                        value={rejectReason}
                        onChange={(event) => setRejectReason(event.target.value)}
                        className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                      >
                        <option value="">Select reason code...</option>
                        {REJECT_REASONS.map((reason) => (
                          <option key={reason.value} value={reason.value}>{reason.label}</option>
                        ))}
                      </select>
                      <textarea
                        aria-label="Review action comment"
                        rows={3}
                        value={actionComment}
                        onChange={(event) => setActionComment(event.target.value)}
                        placeholder="Provide a reviewer note..."
                        className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                      />
                      <Button
                        className={cn("w-full", actionMode === "revision" && "bg-amber-500 hover:bg-amber-600")}
                        variant={actionMode === "reject" ? "destructive" : "default"}
                        disabled={isSubmitting || !rejectReason || !actionComment.trim()}
                        onClick={() => runSingleAction(actionMode === "reject" ? "reject" : "revision")}
                      >
                        {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : actionMode === "reject" ? "Confirm rejection" : "Send revision request"}
                      </Button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="border-t border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">
                  Audit mode: review decisions and comment actions are disabled.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CommentThread({
  comment,
  onReply,
  depth = 0,
}: {
  comment: ReviewComment;
  onReply: (id: number) => void;
  depth?: number;
}) {
  const typeClass = COMMENT_TYPE_CLASSES[comment.type] ?? COMMENT_TYPE_CLASSES.general;

  return (
    <div className={cn(depth > 0 && "ml-6 border-l-2 border-slate-100 pl-3")}>
      <div className="rounded-lg border border-slate-100 bg-white p-3">
        <div className="mb-1 flex items-center gap-2 text-xs">
          <span className="font-medium text-slate-700">{comment.author_name || "Unknown user"}</span>
          <span className="text-slate-400">{relativeTime(comment.created_at)}</span>
          <span className={cn("rounded border px-1.5 py-0.5 text-[10px] font-semibold capitalize", typeClass)}>
            {comment.type}
          </span>
        </div>
        <p className="text-sm text-slate-700">{comment.content}</p>
        <button className="mt-1 text-xs text-slate-400 hover:text-blue-600" onClick={() => onReply(comment.id)}>
          Reply
        </button>
      </div>
      {comment.replies?.map((reply) => (
        <CommentThread key={reply.id} comment={reply} onReply={onReply} depth={depth + 1} />
      ))}
    </div>
  );
}
