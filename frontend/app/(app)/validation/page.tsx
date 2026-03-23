"use client";

import { useState, useMemo, useCallback } from "react";
import {
  AlertTriangle,
  ArrowUpDown,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Download,
  ExternalLink,
  Eye,
  FileText,
  Loader2,
  MessageSquare,
  RotateCcw,
  Send,
  XCircle,
} from "lucide-react";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/* ---------- Types ---------- */

interface ReviewItem {
  id: string;
  element_name: string;
  element_code: string;
  submitter_name: string;
  submitted_at: string;
  status: "submitted" | "in_review";
  urgency: "low" | "medium" | "high" | "critical";
  is_outlier: boolean;
  is_overdue: boolean;
  entity_name: string;
  standard_code: string;
  standard_name: string;
  value: string;
  unit: string;
  methodology: string;
  narrative: string;
  previous_value?: string;
  previous_unit?: string;
  dimensions: { scope?: string; gas_type?: string; category?: string };
  evidence: { id: string; filename: string; url: string; type: string }[];
  boundary_context: {
    entity_name: string;
    inclusion_status: string;
    consolidation_method: string;
    snapshot_version: string;
  };
  comments: Comment[];
}

interface Comment {
  id: string;
  author_name: string;
  created_at: string;
  content: string;
  type: "question" | "issue" | "suggestion";
  parent_id?: string;
  replies?: Comment[];
}

type RejectReason =
  | "OUT_OF_BOUNDARY_SCOPE"
  | "WRONG_CONSOLIDATION_CONTEXT"
  | "DATA_QUALITY_ISSUE"
  | "EVIDENCE_MISSING";

const REJECT_REASONS: { value: RejectReason; label: string }[] = [
  { value: "OUT_OF_BOUNDARY_SCOPE", label: "Out of Boundary Scope" },
  { value: "WRONG_CONSOLIDATION_CONTEXT", label: "Wrong Consolidation Context" },
  { value: "DATA_QUALITY_ISSUE", label: "Data Quality Issue" },
  { value: "EVIDENCE_MISSING", label: "Evidence Missing" },
];

const URGENCY_CONFIG: Record<
  string,
  { label: string; variant: "secondary" | "warning" | "destructive" | "default" }
> = {
  low: { label: "Low", variant: "secondary" },
  medium: { label: "Medium", variant: "default" },
  high: { label: "High", variant: "warning" },
  critical: { label: "Critical", variant: "destructive" },
};

const COMMENT_TYPE_COLORS: Record<string, string> = {
  question: "text-blue-600 bg-blue-50 border-blue-200",
  issue: "text-red-600 bg-red-50 border-red-200",
  suggestion: "text-green-600 bg-green-50 border-green-200",
};

/* ---------- Helpers ---------- */

function relativeTime(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ---------- Component ---------- */

export default function ValidationPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<
    "all" | "submitted" | "in_review"
  >("all");
  const [sortBy, setSortBy] = useState<"date" | "urgency">("date");

  /* Action state */
  const [actionMode, setActionMode] = useState<
    "none" | "reject" | "revision"
  >("none");
  const [actionComment, setActionComment] = useState("");
  const [rejectReason, setRejectReason] = useState<RejectReason | "">("");

  /* Comment form */
  const [newComment, setNewComment] = useState("");
  const [commentType, setCommentType] = useState<"question" | "issue" | "suggestion">("question");
  const [replyToId, setReplyToId] = useState<string | null>(null);

  /* Fetch review items */
  const { data: reviewItems, isLoading, refetch } = useApiQuery<ReviewItem[]>(
    ["review-items"],
    "/data-points?status=submitted,in_review"
  );

  const items = reviewItems ?? [];

  /* Mutations */
  const approveMutation = useApiMutation(
    `/api/data-points/${selectedId}/review`,
    "POST"
  );
  const rejectMutation = useApiMutation(
    `/api/data-points/${selectedId}/review`,
    "POST"
  );
  const commentMutation = useApiMutation(
    `/api/data-points/${selectedId}/comments`,
    "POST"
  );

  /* Filter + sort */
  const filteredItems = useMemo(() => {
    let result = items;
    if (statusFilter !== "all") {
      result = result.filter((item) => item.status === statusFilter);
    }

    const urgencyOrder = { critical: 0, high: 1, medium: 2, low: 3 };
    result = [...result].sort((a, b) => {
      if (sortBy === "date") {
        return (
          new Date(b.submitted_at).getTime() -
          new Date(a.submitted_at).getTime()
        );
      }
      return (
        (urgencyOrder[a.urgency] ?? 3) - (urgencyOrder[b.urgency] ?? 3)
      );
    });

    return result;
  }, [items, statusFilter, sortBy]);

  const selectedItem = useMemo(
    () => items.find((i) => i.id === selectedId) ?? null,
    [items, selectedId]
  );

  /* Actions */
  const handleApprove = async () => {
    if (!selectedId) return;
    try {
      await approveMutation.mutateAsync({ action: "approve" });
      refetch();
      setSelectedId(null);
    } catch {
      // handled by mutation state
    }
  };

  const handleReject = async () => {
    if (!selectedId || !actionComment.trim() || !rejectReason) return;
    try {
      await rejectMutation.mutateAsync({
        action: "reject",
        reason_code: rejectReason,
        comment: actionComment,
      });
      setActionMode("none");
      setActionComment("");
      setRejectReason("");
      refetch();
      setSelectedId(null);
    } catch {
      // handled by mutation state
    }
  };

  const handleRevision = async () => {
    if (!selectedId || !actionComment.trim() || !rejectReason) return;
    try {
      await rejectMutation.mutateAsync({
        action: "request_revision",
        reason_code: rejectReason,
        comment: actionComment,
      });
      setActionMode("none");
      setActionComment("");
      setRejectReason("");
      refetch();
      setSelectedId(null);
    } catch {
      // handled by mutation state
    }
  };

  const handleAddComment = async () => {
    if (!selectedId || !newComment.trim()) return;
    try {
      await commentMutation.mutateAsync({
        content: newComment,
        type: commentType,
        parent_id: replyToId ?? undefined,
      });
      setNewComment("");
      setReplyToId(null);
      refetch();
    } catch {
      // handled by mutation state
    }
  };

  /* ---------- Render ---------- */

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Validation Review</h2>
        <p className="mt-1 text-sm text-gray-500">
          Review submitted data points and approve, reject, or request revisions.
        </p>
      </div>

      <div className="flex h-[calc(100vh-220px)] gap-4">
        {/* ===== LEFT PANEL ===== */}
        <div className="flex w-[40%] flex-col rounded-xl border border-slate-200 bg-white">
          {/* Left panel header */}
          <div className="border-b border-slate-200 p-4">
            <div className="flex items-center gap-3">
              <select
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(
                    e.target.value as typeof statusFilter
                  )
                }
                className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
              >
                <option value="all">All statuses</option>
                <option value="submitted">Submitted</option>
                <option value="in_review">In Review</option>
              </select>

              <div className="flex rounded-md border border-slate-200 text-xs">
                <button
                  onClick={() => setSortBy("date")}
                  className={cn(
                    "px-3 py-1.5 transition-colors",
                    sortBy === "date"
                      ? "bg-slate-900 text-white"
                      : "hover:bg-slate-50"
                  )}
                >
                  <Clock className="mr-1 inline h-3 w-3" />
                  Date
                </button>
                <button
                  onClick={() => setSortBy("urgency")}
                  className={cn(
                    "px-3 py-1.5 transition-colors",
                    sortBy === "urgency"
                      ? "bg-slate-900 text-white"
                      : "hover:bg-slate-50"
                  )}
                >
                  <ArrowUpDown className="mr-1 inline h-3 w-3" />
                  Urgency
                </button>
              </div>

              <span className="ml-auto text-xs text-slate-400">
                {filteredItems.length} items
              </span>
            </div>
          </div>

          {/* Left panel list */}
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center p-12 text-slate-400">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading...
              </div>
            ) : filteredItems.length === 0 ? (
              <div className="flex items-center justify-center p-12 text-slate-400">
                No items to review.
              </div>
            ) : (
              filteredItems.map((item) => {
                const urgencyCfg = URGENCY_CONFIG[item.urgency];
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setSelectedId(item.id);
                      setActionMode("none");
                      setActionComment("");
                      setRejectReason("");
                    }}
                    className={cn(
                      "flex w-full flex-col gap-1 border-b border-slate-100 px-4 py-3 text-left transition-colors hover:bg-slate-50",
                      selectedId === item.id && "bg-blue-50 hover:bg-blue-50"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-sm font-medium text-slate-900 leading-tight">
                        {item.is_outlier && (
                          <AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" />
                        )}
                        {item.is_overdue && (
                          <span className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />
                        )}
                        {item.element_name}
                      </span>
                      <Badge variant={urgencyCfg.variant} className="shrink-0 text-[10px]">
                        {urgencyCfg.label}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <span>{item.submitter_name}</span>
                      <span>&middot;</span>
                      <span>{relativeTime(item.submitted_at)}</span>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* ===== RIGHT PANEL ===== */}
        <div className="flex w-[60%] flex-col rounded-xl border border-slate-200 bg-white">
          {!selectedItem ? (
            <div className="flex flex-1 items-center justify-center text-slate-400">
              Select an item from the list to review.
            </div>
          ) : (
            <div className="flex flex-1 flex-col overflow-hidden">
              {/* Header */}
              <div className="border-b border-slate-200 p-5">
                <h3 className="text-lg font-semibold text-slate-900">
                  {selectedItem.element_name}
                </h3>
                <div className="mt-1 flex items-center gap-3 text-xs text-slate-400">
                  <span>{selectedItem.entity_name}</span>
                  <span>&middot;</span>
                  <span>
                    {selectedItem.standard_code} &mdash;{" "}
                    {selectedItem.standard_name}
                  </span>
                </div>
              </div>

              {/* Scrollable content */}
              <div className="flex-1 space-y-5 overflow-y-auto p-5">
                {/* Value display */}
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <p className="text-xs font-medium uppercase text-slate-400">
                        Value
                      </p>
                      <p className="mt-1 text-xl font-bold text-slate-900">
                        {selectedItem.value}{" "}
                        <span className="text-sm font-normal text-slate-500">
                          {selectedItem.unit}
                        </span>
                      </p>
                    </div>
                    {selectedItem.previous_value && (
                      <div>
                        <p className="text-xs font-medium uppercase text-slate-400">
                          Previous Period
                        </p>
                        <p className="mt-1 text-xl font-bold text-slate-500">
                          {selectedItem.previous_value}{" "}
                          <span className="text-sm font-normal">
                            {selectedItem.previous_unit}
                          </span>
                        </p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs font-medium uppercase text-slate-400">
                        Methodology
                      </p>
                      <p className="mt-1 text-sm text-slate-700">
                        {selectedItem.methodology}
                      </p>
                    </div>
                  </div>
                  {selectedItem.narrative && (
                    <div className="mt-3 border-t border-slate-200 pt-3">
                      <p className="text-xs font-medium uppercase text-slate-400">
                        Narrative
                      </p>
                      <p className="mt-1 text-sm text-slate-700">
                        {selectedItem.narrative}
                      </p>
                    </div>
                  )}
                </div>

                {/* Dimensions */}
                {(selectedItem.dimensions?.scope ||
                  selectedItem.dimensions?.gas_type ||
                  selectedItem.dimensions?.category) && (
                  <div>
                    <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                      Dimensions
                    </h4>
                    <div className="flex gap-2">
                      {selectedItem.dimensions.scope && (
                        <Badge variant="secondary">
                          Scope: {selectedItem.dimensions.scope}
                        </Badge>
                      )}
                      {selectedItem.dimensions.gas_type && (
                        <Badge variant="secondary">
                          Gas: {selectedItem.dimensions.gas_type}
                        </Badge>
                      )}
                      {selectedItem.dimensions.category && (
                        <Badge variant="secondary">
                          Category: {selectedItem.dimensions.category}
                        </Badge>
                      )}
                    </div>
                  </div>
                )}

                {/* Evidence */}
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                    Evidence ({(selectedItem.evidence ?? []).length})
                  </h4>
                  {(selectedItem.evidence ?? []).length === 0 ? (
                    <p className="text-sm text-slate-400">
                      No evidence attached.
                    </p>
                  ) : (
                    <ul className="space-y-2">
                      {(selectedItem.evidence ?? []).map((ev) => (
                        <li
                          key={ev.id}
                          className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 px-3 py-2"
                        >
                          <span className="flex items-center gap-2 text-sm text-slate-700">
                            <FileText className="h-4 w-4 text-slate-400" />
                            {ev.filename}
                          </span>
                          <div className="flex gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => window.open(ev.url, "_blank")}
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                            <Button size="sm" variant="ghost" asChild>
                              <a href={ev.url} download={ev.filename}>
                                <Download className="h-3.5 w-3.5" />
                              </a>
                            </Button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Boundary context card */}
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                    Boundary Context
                  </h4>
                  <Card>
                    <CardContent className="grid grid-cols-2 gap-3 p-4 text-sm">
                      <div>
                        <p className="text-xs text-slate-400">Entity</p>
                        <p className="font-medium text-slate-900">
                          {selectedItem.boundary_context?.entity_name}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">
                          Inclusion Status
                        </p>
                        <p className="font-medium text-slate-900">
                          {selectedItem.boundary_context?.inclusion_status}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">
                          Consolidation Method
                        </p>
                        <p className="font-medium text-slate-900">
                          {selectedItem.boundary_context?.consolidation_method}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">
                          Snapshot Version
                        </p>
                        <p className="font-medium text-slate-900">
                          {selectedItem.boundary_context?.snapshot_version}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                </div>

                {/* Comments */}
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                    <MessageSquare className="mr-1 inline h-3.5 w-3.5" />
                    Comments ({(selectedItem.comments ?? []).length})
                  </h4>

                  {(selectedItem.comments ?? []).length > 0 && (
                    <div className="space-y-3 mb-4">
                      {(selectedItem.comments ?? []).map((comment) => (
                        <CommentThread
                          key={comment.id}
                          comment={comment}
                          onReply={(id) => setReplyToId(id)}
                        />
                      ))}
                    </div>
                  )}

                  {/* Add comment form */}
                  <div className="rounded-lg border border-slate-200 p-3">
                    {replyToId && (
                      <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                        <span>Replying to comment</span>
                        <button
                          onClick={() => setReplyToId(null)}
                          className="text-slate-400 hover:text-red-500"
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                    <div className="flex gap-2 mb-2">
                      {(["question", "issue", "suggestion"] as const).map(
                        (t) => (
                          <button
                            key={t}
                            onClick={() => setCommentType(t)}
                            className={cn(
                              "rounded-md border px-2 py-1 text-xs font-medium capitalize transition-colors",
                              commentType === t
                                ? COMMENT_TYPE_COLORS[t]
                                : "border-slate-200 text-slate-400 hover:text-slate-600"
                            )}
                          >
                            {t}
                          </button>
                        )
                      )}
                    </div>
                    <div className="flex gap-2">
                      <textarea
                        rows={2}
                        value={newComment}
                        onChange={(e) => setNewComment(e.target.value)}
                        placeholder="Add a comment..."
                        className="flex-1 rounded-md border border-slate-200 bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-950"
                      />
                      <Button
                        size="sm"
                        onClick={handleAddComment}
                        disabled={
                          !newComment.trim() || commentMutation.isPending
                        }
                        className="self-end"
                      >
                        <Send className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action bar */}
              <div className="border-t border-slate-200 p-4">
                {actionMode === "none" ? (
                  <div className="flex gap-3">
                    <Button
                      onClick={handleApprove}
                      disabled={approveMutation.isPending}
                      className="flex-1 bg-green-600 hover:bg-green-700"
                    >
                      {approveMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4" />
                      )}
                      Approve
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => setActionMode("reject")}
                      className="flex-1"
                    >
                      <XCircle className="h-4 w-4" />
                      Reject
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => setActionMode("revision")}
                      className="flex-1 border-amber-300 text-amber-700 hover:bg-amber-50"
                    >
                      <RotateCcw className="h-4 w-4" />
                      Request Revision
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          actionMode === "reject" ? "destructive" : "warning"
                        }
                      >
                        {actionMode === "reject"
                          ? "Rejecting"
                          : "Requesting Revision"}
                      </Badge>
                      <button
                        onClick={() => {
                          setActionMode("none");
                          setActionComment("");
                          setRejectReason("");
                        }}
                        className="ml-auto text-xs text-slate-400 hover:text-slate-600"
                      >
                        Cancel
                      </button>
                    </div>

                    <select
                      value={rejectReason}
                      onChange={(e) =>
                        setRejectReason(e.target.value as RejectReason)
                      }
                      className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                    >
                      <option value="">Select reason code...</option>
                      {REJECT_REASONS.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </select>

                    <textarea
                      rows={2}
                      value={actionComment}
                      onChange={(e) => setActionComment(e.target.value)}
                      placeholder="Provide a comment (required)..."
                      className="w-full rounded-md border border-slate-200 bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-slate-950"
                    />

                    <Button
                      onClick={
                        actionMode === "reject" ? handleReject : handleRevision
                      }
                      disabled={
                        !actionComment.trim() ||
                        !rejectReason ||
                        rejectMutation.isPending
                      }
                      variant={
                        actionMode === "reject" ? "destructive" : "default"
                      }
                      className={cn(
                        "w-full",
                        actionMode === "revision" &&
                          "bg-amber-500 hover:bg-amber-600"
                      )}
                    >
                      {rejectMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : actionMode === "reject" ? (
                        "Confirm Rejection"
                      ) : (
                        "Send Revision Request"
                      )}
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- Comment Thread sub-component ---------- */

function CommentThread({
  comment,
  onReply,
  depth = 0,
}: {
  comment: Comment;
  onReply: (id: string) => void;
  depth?: number;
}) {
  const typeColor = COMMENT_TYPE_COLORS[comment.type] ?? "";

  return (
    <div className={cn(depth > 0 && "ml-6 border-l-2 border-slate-100 pl-3")}>
      <div className="rounded-lg border border-slate-100 bg-white p-3">
        <div className="mb-1 flex items-center gap-2 text-xs">
          <span className="font-medium text-slate-700">
            {comment.author_name}
          </span>
          <span className="text-slate-400">
            {relativeTime(comment.created_at)}
          </span>
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px] font-semibold capitalize",
              typeColor
            )}
          >
            {comment.type}
          </span>
        </div>
        <p className="text-sm text-slate-700">{comment.content}</p>
        <button
          onClick={() => onReply(comment.id)}
          className="mt-1 text-xs text-slate-400 hover:text-blue-600"
        >
          Reply
        </button>
      </div>
      {comment.replies?.map((reply) => (
        <CommentThread
          key={reply.id}
          comment={reply}
          onReply={onReply}
          depth={depth + 1}
        />
      ))}
    </div>
  );
}
