"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  BellOff,
  CheckCheck,
  Loader2,
  Mail,
  MailOpen,
  ShieldAlert,
  SlidersHorizontal,
} from "lucide-react";

import { api } from "@/lib/api";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

type RoleBinding = {
  role: string;
};

type Notification = {
  id: number;
  type: string;
  title: string;
  message: string;
  severity: "info" | "warning" | "important" | "critical";
  channel: string;
  is_read: boolean;
  created_at: string | null;
};

type NotificationListResponse = {
  items: Notification[];
  total: number;
};

type NotificationPreferences = {
  email: boolean;
  in_app: boolean;
  email_info_level: boolean;
};

function relativeTime(value: string | null) {
  if (!value) return "Unknown";
  const diffMinutes = Math.floor((Date.now() - new Date(value).getTime()) / 60000);
  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

function severityVariant(severity: Notification["severity"]) {
  if (severity === "critical") return "destructive" as const;
  if (severity === "important") return "warning" as const;
  if (severity === "warning") return "secondary" as const;
  return "outline" as const;
}

export default function NotificationsPage() {
  const [readFilter, setReadFilter] = useState<"all" | "unread" | "read">("unread");
  const [severityFilter, setSeverityFilter] = useState("");

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me", "notifications-page"],
    "/auth/me"
  );

  const roles = me?.roles ?? [];
  const accessDenied = roles.length > 0 && roles.every((binding) => binding.role === "auditor");

  const params = new URLSearchParams();
  params.set("page_size", "100");
  if (readFilter === "unread") params.set("is_read", "false");
  if (readFilter === "read") params.set("is_read", "true");
  if (severityFilter) params.set("severity", severityFilter);

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useApiQuery<NotificationListResponse>(
    ["notifications", readFilter, severityFilter],
    `/notifications?${params.toString()}`,
    { enabled: !accessDenied }
  );

  const {
    data: preferences,
    isLoading: preferencesLoading,
    refetch: refetchPreferences,
  } = useApiQuery<NotificationPreferences>(
    ["notification-preferences"],
    "/notifications/preferences",
    { enabled: !accessDenied }
  );

  const markAllRead = useApiMutation("/notifications/read-all", "POST");
  const updatePreferences = useApiMutation<
    NotificationPreferences,
    Partial<NotificationPreferences>
  >("/notifications/preferences", "PATCH");

  const notifications = data?.items ?? [];
  const unreadCount = useMemo(
    () => notifications.filter((notification) => !notification.is_read).length,
    [notifications]
  );
  const emailEnabled = preferences?.email ?? true;
  const inAppEnabled = preferences?.in_app ?? true;

  async function markNotificationRead(notificationId: number) {
    await api.patch(`/notifications/${notificationId}/read`);
    await refetch();
  }

  async function markAll() {
    await markAllRead.mutateAsync(undefined as never);
    await refetch();
  }

  async function updatePreference<K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K]
  ) {
    await updatePreferences.mutateAsync({ [key]: value } as Partial<NotificationPreferences>);
    await refetchPreferences();
    await refetch();
  }

  if (meLoading || (!accessDenied && (isLoading || preferencesLoading))) {
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
          <h2 className="text-2xl font-bold text-slate-900">Notifications</h2>
          <p className="mt-1 text-sm text-slate-500">
            Review in-app updates and adjust delivery preferences.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Auditor accounts do not receive notification center access.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Notifications</h2>
          <p className="mt-1 text-sm text-slate-500">
            Track workflow updates, delivery channels, and read status for your organization context.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={markAll} disabled={markAllRead.isPending || unreadCount === 0}>
            <CheckCheck className="mr-2 h-4 w-4" />
            Mark all as read
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Unread</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{unreadCount}</p>
            <p className="mt-1 text-xs text-slate-500">Unread notifications in the current view.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Delivery</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm font-medium text-slate-900">
              {inAppEnabled ? "In-app enabled" : "In-app disabled"}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {emailEnabled ? "Email notifications are active." : "Email notifications are paused."}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Inbox Size</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{data?.total ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Total notifications returned by the current filters.</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Delivery Preferences</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-lg border border-slate-200 p-4">
            <Switch
              checked={preferences?.in_app ?? true}
              onCheckedChange={(value) => void updatePreference("in_app", value)}
              label="In-app notifications"
            />
            <p className="mt-2 text-xs text-slate-500">
              Keep workflow alerts in the notification center.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 p-4">
            <Switch
              checked={preferences?.email ?? true}
              onCheckedChange={(value) => void updatePreference("email", value)}
              label="Email delivery"
            />
            <p className="mt-2 text-xs text-slate-500">
              Receive important alerts by email when available.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 p-4">
            <Switch
              checked={preferences?.email_info_level ?? false}
              onCheckedChange={(value) => void updatePreference("email_info_level", value)}
              label="Email info-level alerts"
            />
            <p className="mt-2 text-xs text-slate-500">
              Include informational events in email delivery, not just important and critical ones.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <CardTitle>Notification Center</CardTitle>
            <p className="mt-1 text-sm text-slate-500">
              Filter by read state and severity, then inspect each event in context.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[420px]">
            <Select
              label="Read Status"
              value={readFilter}
              onChange={(value) => setReadFilter(value as "all" | "unread" | "read")}
              options={[
                { value: "unread", label: "Unread" },
                { value: "read", label: "Read" },
                { value: "all", label: "All" },
              ]}
            />
            <Select
              label="Severity"
              value={severityFilter}
              onChange={setSeverityFilter}
              options={[
                { value: "", label: "All severities" },
                { value: "info", label: "Info" },
                { value: "warning", label: "Warning" },
                { value: "important", label: "Important" },
                { value: "critical", label: "Critical" },
              ]}
            />
          </div>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Failed to load notifications.
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <BellOff className="mb-3 h-10 w-10 text-slate-300" />
              <p className="font-medium">No notifications found.</p>
              <p className="mt-1 text-sm">Change your filters or come back after the next workflow event.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  className={
                    notification.is_read
                      ? "rounded-lg border border-slate-200 px-4 py-4"
                      : "rounded-lg border border-blue-200 bg-blue-50 px-4 py-4"
                  }
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {notification.is_read ? (
                          <MailOpen className="h-4 w-4 text-slate-400" />
                        ) : (
                          <Mail className="h-4 w-4 text-blue-600" />
                        )}
                        <p className="font-medium text-slate-900">{notification.title}</p>
                        <Badge variant={severityVariant(notification.severity)}>{notification.severity}</Badge>
                        <Badge variant="outline">{notification.channel}</Badge>
                        <Badge variant="secondary">{notification.type}</Badge>
                      </div>
                      <p className="text-sm text-slate-600">{notification.message}</p>
                      <div className="flex items-center gap-2 text-xs text-slate-400">
                        <SlidersHorizontal className="h-3.5 w-3.5" />
                        <span>{relativeTime(notification.created_at)}</span>
                      </div>
                    </div>
                    {!notification.is_read && (
                      <Button variant="outline" size="sm" onClick={() => void markNotificationRead(notification.id)}>
                        Mark as read
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="text-right">
        <Button variant="ghost" asChild>
          <Link href="/dashboard">Back to dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
