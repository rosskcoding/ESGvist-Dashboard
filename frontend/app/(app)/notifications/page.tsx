"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Bell,
  BellOff,
  Check,
  CheckCheck,
  ChevronRight,
  Filter,
  Info,
  AlertTriangle,
  XCircle,
  Loader2,
  Mail,
  MailOpen,
} from "lucide-react";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/* ---------- Types ---------- */

type NotificationSeverity = "info" | "warning" | "error" | "success";
type NotificationType =
  | "data_submitted"
  | "review_complete"
  | "revision_requested"
  | "comment_added"
  | "deadline_approaching"
  | "gate_check_failed"
  | "system";

interface Notification {
  id: string;
  title: string;
  message: string;
  type: NotificationType;
  severity: NotificationSeverity;
  read: boolean;
  created_at: string;
  entity_id?: string;
  entity_name?: string;
  link?: string;
}

/* ---------- Config ---------- */

const SEVERITY_CONFIG: Record<
  NotificationSeverity,
  {
    variant: "secondary" | "warning" | "destructive" | "success";
    icon: typeof Info;
    label: string;
  }
> = {
  info: { variant: "secondary", icon: Info, label: "Info" },
  warning: { variant: "warning", icon: AlertTriangle, label: "Warning" },
  error: { variant: "destructive", icon: XCircle, label: "Error" },
  success: { variant: "success", icon: Check, label: "Success" },
};

const TYPE_LABELS: Record<NotificationType, string> = {
  data_submitted: "Data Submitted",
  review_complete: "Review Complete",
  revision_requested: "Revision Requested",
  comment_added: "Comment Added",
  deadline_approaching: "Deadline Approaching",
  gate_check_failed: "Gate Check Failed",
  system: "System",
};

/* ---------- Helpers ---------- */

function relativeTime(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

/* ---------- Component ---------- */

export default function NotificationsPage() {
  const [readFilter, setReadFilter] = useState<"all" | "unread">("unread");
  const [typeFilter, setTypeFilter] = useState<NotificationType | "all">("all");
  const [severityFilter, setSeverityFilter] = useState<
    NotificationSeverity | "all"
  >("all");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  /* Data */
  const {
    data: notifications,
    isLoading,
    error,
    refetch,
  } = useApiQuery<Notification[]>(["notifications"], "/notifications");

  const items = notifications ?? [];

  /* Mutations */
  const markReadMutation = useApiMutation(
    "/notifications/mark-read",
    "POST"
  );
  const markAllReadMutation = useApiMutation(
    "/notifications/mark-all-read",
    "POST"
  );

  /* Counts */
  const unreadCount = useMemo(
    () => items.filter((n) => !n.read).length,
    [items]
  );

  /* Unique types for filter */
  const availableTypes = useMemo(
    () => Array.from(new Set(items.map((n) => n.type))).sort(),
    [items]
  );

  /* Filtered */
  const filtered = useMemo(() => {
    let result = items;
    if (readFilter === "unread") {
      result = result.filter((n) => !n.read);
    }
    if (typeFilter !== "all") {
      result = result.filter((n) => n.type === typeFilter);
    }
    if (severityFilter !== "all") {
      result = result.filter((n) => n.severity === severityFilter);
    }
    return result.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [items, readFilter, typeFilter, severityFilter]);

  /* Selection */
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    if (selectedIds.size === filtered.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((n) => n.id)));
    }
  }, [filtered, selectedIds]);

  /* Actions */
  const handleMarkRead = async (ids: string[]) => {
    try {
      await markReadMutation.mutateAsync({ notification_ids: ids });
      setSelectedIds(new Set());
      refetch();
    } catch {
      // handled by mutation
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllReadMutation.mutateAsync({});
      refetch();
    } catch {
      // handled by mutation
    }
  };

  /* ---------- Render ---------- */

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Notifications</h2>
          <p className="mt-1 text-sm text-gray-500">
            {unreadCount > 0
              ? `You have ${unreadCount} unread notification${unreadCount !== 1 ? "s" : ""}.`
              : "You're all caught up."}
          </p>
        </div>
        {unreadCount > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleMarkAllRead}
            disabled={markAllReadMutation.isPending}
          >
            <CheckCheck className="h-4 w-4" />
            Mark all as read
          </Button>
        )}
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Read/Unread toggle */}
          <div className="flex rounded-md border border-slate-200 text-sm">
            <button
              onClick={() => setReadFilter("unread")}
              className={cn(
                "px-3 py-1.5 transition-colors",
                readFilter === "unread"
                  ? "bg-slate-900 text-white"
                  : "hover:bg-slate-50"
              )}
            >
              <Mail className="mr-1 inline h-3.5 w-3.5" />
              Unread
              {unreadCount > 0 && (
                <span className="ml-1 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                  {unreadCount}
                </span>
              )}
            </button>
            <button
              onClick={() => setReadFilter("all")}
              className={cn(
                "px-3 py-1.5 transition-colors",
                readFilter === "all"
                  ? "bg-slate-900 text-white"
                  : "hover:bg-slate-50"
              )}
            >
              <MailOpen className="mr-1 inline h-3.5 w-3.5" />
              All
            </button>
          </div>

          {/* Type filter */}
          <div className="flex items-center gap-1.5">
            <Filter className="h-3.5 w-3.5 text-slate-400" />
            <select
              value={typeFilter}
              onChange={(e) =>
                setTypeFilter(e.target.value as typeof typeFilter)
              }
              className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
            >
              <option value="all">All types</option>
              {availableTypes.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABELS[t] ?? t}
                </option>
              ))}
            </select>
          </div>

          {/* Severity filter */}
          <select
            value={severityFilter}
            onChange={(e) =>
              setSeverityFilter(e.target.value as typeof severityFilter)
            }
            className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
          >
            <option value="all">All severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="success">Success</option>
          </select>

          {/* Bulk action */}
          {selectedIds.size > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleMarkRead(Array.from(selectedIds))}
              disabled={markReadMutation.isPending}
              className="ml-auto"
            >
              <Check className="h-3.5 w-3.5" />
              Mark selected as read ({selectedIds.size})
            </Button>
          )}
        </div>
      </Card>

      {/* Notification list */}
      <Card>
        {isLoading ? (
          <div className="flex items-center justify-center p-12 text-slate-400">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Loading notifications...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center p-12 text-red-500">
            Failed to load notifications.
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-12 text-slate-400">
            <BellOff className="h-8 w-8 mb-2" />
            <p>No notifications found.</p>
          </div>
        ) : (
          <div>
            {/* Select all row */}
            <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-2">
              <input
                type="checkbox"
                checked={
                  selectedIds.size > 0 && selectedIds.size === filtered.length
                }
                onChange={selectAll}
                className="h-4 w-4 rounded border-slate-300"
              />
              <span className="text-xs text-slate-400">
                {filtered.length} notification{filtered.length !== 1 ? "s" : ""}
              </span>
            </div>

            {/* Items */}
            {filtered.map((notification) => {
              const severityCfg = SEVERITY_CONFIG[notification.severity];
              const SeverityIcon = severityCfg.icon;

              return (
                <div
                  key={notification.id}
                  className={cn(
                    "flex items-start gap-3 border-b border-slate-50 px-4 py-4 transition-colors hover:bg-slate-50",
                    !notification.read && "bg-blue-50/50"
                  )}
                >
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={selectedIds.has(notification.id)}
                    onChange={() => toggleSelect(notification.id)}
                    className="mt-1 h-4 w-4 rounded border-slate-300"
                  />

                  {/* Icon */}
                  <div
                    className={cn(
                      "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                      notification.severity === "info" &&
                        "bg-slate-100 text-slate-500",
                      notification.severity === "warning" &&
                        "bg-amber-100 text-amber-600",
                      notification.severity === "error" &&
                        "bg-red-100 text-red-600",
                      notification.severity === "success" &&
                        "bg-green-100 text-green-600"
                    )}
                  >
                    <SeverityIcon className="h-4 w-4" />
                  </div>

                  {/* Content */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p
                          className={cn(
                            "text-sm leading-tight",
                            !notification.read
                              ? "font-semibold text-slate-900"
                              : "font-medium text-slate-700"
                          )}
                        >
                          {!notification.read && (
                            <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-blue-500" />
                          )}
                          {notification.title}
                        </p>
                        <p className="mt-0.5 text-sm text-slate-500 line-clamp-2">
                          {notification.message}
                        </p>
                      </div>

                      <div className="flex shrink-0 items-center gap-2">
                        <Badge variant={severityCfg.variant} className="text-[10px]">
                          {severityCfg.label}
                        </Badge>
                        <span className="whitespace-nowrap text-xs text-slate-400">
                          {relativeTime(notification.created_at)}
                        </span>
                      </div>
                    </div>

                    {/* Entity link + actions */}
                    <div className="mt-2 flex items-center gap-3">
                      {notification.entity_name && (
                        <span className="inline-flex items-center gap-1 text-xs text-blue-600">
                          {notification.entity_name}
                          <ChevronRight className="h-3 w-3" />
                        </span>
                      )}

                      {!notification.read && (
                        <button
                          onClick={() => handleMarkRead([notification.id])}
                          className="text-xs text-slate-400 hover:text-slate-600"
                        >
                          Mark as read
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
