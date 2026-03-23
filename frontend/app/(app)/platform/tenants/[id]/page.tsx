"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, PlayCircle, ShieldAlert } from "lucide-react";

import { api } from "@/lib/api";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

type RoleBinding = { role: string };

type TenantDetail = {
  id: number;
  name: string;
  country: string | null;
  industry: string | null;
  default_currency: string | null;
  status: "active" | "suspended" | "archived";
  setup_completed: boolean;
};

type PlatformUser = { id: number; email: string; full_name: string; is_active: boolean };

type PlatformUserResponse = { items: PlatformUser[] };

type SelfRegistrationConfig = { allow_self_registration: boolean };
type TenantUpdatePayload = {
  name: string;
  country: string | null;
  industry: string | null;
  status: TenantDetail["status"];
};

type JobStatusResponse = {
  worker: {
    active_leases: Array<{
      name: string;
      owner_id: string;
      last_status: string | null;
    }>;
  };
  queues: {
    exports: { queue_depth: number; due_retries: number };
    webhooks: { queue_depth: number; due_retries: number };
  };
};

function statusVariant(status: TenantDetail["status"]) {
  if (status === "active") return "success" as const;
  if (status === "suspended") return "warning" as const;
  return "secondary" as const;
}

export default function TenantDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const tenantId = Number(params.id);
  const [form, setForm] = useState<{
    name: string;
    country: string;
    industry: string;
    status: TenantDetail["status"];
  }>({ name: "", country: "", industry: "", status: "active" });
  const [selectedUserId, setSelectedUserId] = useState("");
  const [assignmentMessage, setAssignmentMessage] = useState("");
  const [tenantMessage, setTenantMessage] = useState("");
  const [jobMessage, setJobMessage] = useState("");

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me", "tenant-detail"],
    "/auth/me"
  );

  const canAccess = (me?.roles ?? []).some((binding) => binding.role === "platform_admin");
  const accessDenied = Boolean(me) && !canAccess;

  const { data: tenant, isLoading, refetch } = useApiQuery<TenantDetail>(
    ["platform-tenant", tenantId],
    `/platform/tenants/${tenantId}`,
    { enabled: canAccess && Number.isFinite(tenantId) }
  );

  const { data: users } = useApiQuery<PlatformUserResponse>(["platform-users"], "/platform/users", {
    enabled: canAccess,
  });

  const { data: selfRegistration, refetch: refetchSelfRegistration } = useApiQuery<SelfRegistrationConfig>(
    ["self-registration"],
    "/platform/config/self-registration",
    { enabled: canAccess }
  );

  const { data: jobStatus, refetch: refetchJobStatus } = useApiQuery<JobStatusResponse>(
    ["platform-job-status", tenantId],
    "/platform/jobs/status",
    { enabled: canAccess }
  );

  const updateTenant = useApiMutation<{ id: number; name: string; updated: boolean }, TenantUpdatePayload>(
    `/platform/tenants/${tenantId}`,
    "PATCH"
  );
  const assignAdmin = useApiMutation<{ user_id: number; tenant_id: number; role: string }, { user_id: number }>(
    `/platform/tenants/${tenantId}/admins`,
    "POST"
  );
  const updateSelfRegistration = useApiMutation<SelfRegistrationConfig, SelfRegistrationConfig>(
    "/platform/config/self-registration",
    "PATCH"
  );

  useEffect(() => {
    if (!tenant) return;
    setForm({
      name: tenant.name,
      country: tenant.country ?? "",
      industry: tenant.industry ?? "",
      status: tenant.status,
    });
  }, [tenant]);

  const selectableUsers = useMemo(() => {
    return (users?.items ?? []).filter((user) => user.is_active);
  }, [users?.items]);

  async function saveTenant() {
    setTenantMessage("");
    const payload = {
      name: form.name,
      country: form.country || null,
      industry: form.industry || null,
      status: form.status,
    };
    await updateTenant.mutateAsync(payload);
    await refetch();
    setTenantMessage("Tenant settings saved.");
  }

  async function saveStatus(status: TenantDetail["status"]) {
    setTenantMessage("");
    if (status === "active") {
      await api.post(`/platform/tenants/${tenantId}/reactivate`);
    } else if (status === "suspended") {
      await api.post(`/platform/tenants/${tenantId}/suspend`);
    } else {
      await api.patch(`/platform/tenants/${tenantId}/archive`);
    }
    await refetch();
    setForm((current) => ({ ...current, status }));
    setTenantMessage(`Tenant moved to ${status}.`);
  }

  async function submitAdminAssignment() {
    if (!selectedUserId) return;
    setAssignmentMessage("");
    const selectedUser = selectableUsers.find((user) => user.id === Number(selectedUserId));
    await assignAdmin.mutateAsync({ user_id: Number(selectedUserId) });
    setAssignmentMessage(
      selectedUser
        ? `${selectedUser.full_name} assigned as tenant admin.`
        : "Tenant admin assigned."
    );
  }

  async function toggleSelfRegistration(value: boolean) {
    await updateSelfRegistration.mutateAsync({ allow_self_registration: value });
    await refetchSelfRegistration();
  }

  async function runJob(kind: "sla-check" | "project-deadlines" | "webhook-retries" | "export-jobs" | "all") {
    setJobMessage("");
    const path =
      kind === "sla-check"
        ? "/platform/jobs/sla-check"
        : kind === "project-deadlines"
          ? "/platform/jobs/project-deadlines"
          : kind === "webhook-retries"
            ? "/platform/jobs/webhook-retries"
            : kind === "export-jobs"
              ? "/platform/jobs/exports"
              : "/platform/jobs/run-all";
    await api.post(path);
    await refetchJobStatus();
    setJobMessage(kind === "all" ? "All scheduled jobs triggered." : `Job '${kind}' triggered.`);
  }

  if (meLoading || (canAccess && isLoading)) {
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
          <h2 className="text-2xl font-bold text-slate-900">Tenant Details</h2>
          <p className="mt-1 text-sm text-slate-500">
            Inspect tenant status, assign admins, and run platform jobs.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only platform admins can access tenant details.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!tenant) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/platform/tenants")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Tenant Details</h2>
          <p className="mt-1 text-sm text-slate-500">{tenant.name}</p>
        </div>
        <Badge variant={statusVariant(tenant.status)}>{tenant.status}</Badge>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Tenant Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="tenant-detail-name">Name</Label>
              <Input
                id="tenant-detail-name"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="tenant-detail-country">Country</Label>
                <Input
                  id="tenant-detail-country"
                  value={form.country}
                  onChange={(event) => setForm((current) => ({ ...current, country: event.target.value }))}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="tenant-detail-industry">Industry</Label>
                <Input
                  id="tenant-detail-industry"
                  value={form.industry}
                  onChange={(event) => setForm((current) => ({ ...current, industry: event.target.value }))}
                />
              </div>
            </div>
            <Select
              label="Lifecycle Status"
              value={form.status}
              onChange={(value) => setForm((current) => ({ ...current, status: value as TenantDetail["status"] }))}
              options={[
                { value: "active", label: "Active" },
                { value: "suspended", label: "Suspended" },
                { value: "archived", label: "Archived" },
              ]}
            />
            <div className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <p>Default currency: {tenant.default_currency ?? "-"}</p>
              <p>Setup completed: {tenant.setup_completed ? "Yes" : "No"}</p>
            </div>
            {tenantMessage && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                {tenantMessage}
              </div>
            )}
            <div className="flex flex-wrap items-center justify-end gap-3">
              <Button variant="outline" onClick={() => void saveStatus(form.status)}>
                Apply Status
              </Button>
              <Button onClick={() => void saveTenant()} disabled={updateTenant.isPending || !form.name.trim()}>
                {updateTenant.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Changes
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Admin Assignment</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              label="Assign Organization Admin"
              value={selectedUserId}
              onChange={setSelectedUserId}
              options={[
                { value: "", label: "Select active platform user" },
                ...selectableUsers.map((user) => ({
                  value: String(user.id),
                  label: `${user.full_name} (${user.email})`,
                })),
              ]}
            />
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              Assigning a tenant admin creates an organization-scoped admin binding for this tenant.
            </div>
            {assignmentMessage && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                {assignmentMessage}
              </div>
            )}
            <div className="flex justify-end">
              <Button
                variant="outline"
                onClick={() => void submitAdminAssignment()}
                disabled={assignAdmin.isPending || !selectedUserId}
              >
                {assignAdmin.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Assign Admin
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Platform Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-slate-200 p-4">
              <Switch
                checked={selfRegistration?.allow_self_registration ?? false}
                onCheckedChange={(value) => void toggleSelfRegistration(value)}
                label="Allow self registration"
              />
              <p className="mt-2 text-xs text-slate-500">
                This is a platform-wide switch affecting public registration availability.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Queue Status</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 text-sm text-slate-600">
            <div className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p>Export queue depth: {jobStatus?.queues.exports.queue_depth ?? 0}</p>
              <p>Export due retries: {jobStatus?.queues.exports.due_retries ?? 0}</p>
              <p>Webhook queue depth: {jobStatus?.queues.webhooks.queue_depth ?? 0}</p>
              <p>Webhook due retries: {jobStatus?.queues.webhooks.due_retries ?? 0}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="font-medium text-slate-900">Worker leases</p>
              {(jobStatus?.worker.active_leases ?? []).length === 0 ? (
                <p className="mt-2">No active worker leases.</p>
              ) : (
                <ul className="mt-2 space-y-1">
                  {jobStatus?.worker.active_leases.map((lease) => (
                    <li key={`${lease.name}-${lease.owner_id}`}>
                      {lease.name}: {lease.owner_id} ({lease.last_status ?? "unknown"})
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Job Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => void runJob("sla-check")}>
              <PlayCircle className="mr-2 h-4 w-4" />
              Run SLA Check
            </Button>
            <Button variant="outline" onClick={() => void runJob("project-deadlines")}>
              <PlayCircle className="mr-2 h-4 w-4" />
              Run Project Deadlines
            </Button>
            <Button variant="outline" onClick={() => void runJob("webhook-retries")}>
              <PlayCircle className="mr-2 h-4 w-4" />
              Retry Webhooks
            </Button>
            <Button variant="outline" onClick={() => void runJob("export-jobs")}>
              <PlayCircle className="mr-2 h-4 w-4" />
              Run Export Jobs
            </Button>
            <Button onClick={() => void runJob("all")}>
              <PlayCircle className="mr-2 h-4 w-4" />
              Run All Jobs
            </Button>
          </div>
          {jobMessage && (
            <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              {jobMessage}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
