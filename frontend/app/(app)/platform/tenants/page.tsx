"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Loader2,
  Pause,
  Play,
  Plus,
  Search,
  ShieldAlert,
  TimerReset,
} from "lucide-react";

import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type RoleBinding = { role: string };

type Tenant = {
  id: number;
  name: string;
  country: string | null;
  industry: string | null;
  status: "active" | "suspended" | "archived";
  setup_completed: boolean;
  user_count: number;
};

type TenantListResponse = {
  items: Tenant[];
  total: number;
};

type JobStatusResponse = {
  queues: {
    exports: { queue_depth: number; due_retries: number };
    webhooks: { queue_depth: number; due_retries: number };
  };
};

function tenantStatusVariant(status: Tenant["status"]) {
  if (status === "active") return "success" as const;
  if (status === "suspended") return "warning" as const;
  return "secondary" as const;
}

export default function TenantsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [isRefreshingJobs, setIsRefreshingJobs] = useState(false);

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me", "platform-tenants"],
    "/auth/me"
  );

  const canAccess = (me?.roles ?? []).some((binding) => binding.role === "platform_admin");
  const accessDenied = Boolean(me) && !canAccess;

  const { data, isLoading, refetch } = useApiQuery<TenantListResponse>(
    ["platform-tenants"],
    "/platform/tenants?page_size=100",
    { enabled: canAccess }
  );

  const { data: jobStatus, refetch: refetchJobs } = useApiQuery<JobStatusResponse>(
    ["platform-job-status"],
    "/platform/jobs/status",
    { enabled: canAccess }
  );

  const tenants = useMemo(() => {
    const items = data?.items ?? [];
    return items.filter((tenant) => {
      const haystack = [tenant.name, tenant.country ?? "", tenant.industry ?? ""].join(" ").toLowerCase();
      const matchesSearch = !search || haystack.includes(search.toLowerCase());
      const matchesStatus = !statusFilter || tenant.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [data?.items, search, statusFilter]);

  const summary = useMemo(() => {
    return {
      active: (data?.items ?? []).filter((tenant) => tenant.status === "active").length,
      suspended: (data?.items ?? []).filter((tenant) => tenant.status === "suspended").length,
      archived: (data?.items ?? []).filter((tenant) => tenant.status === "archived").length,
    };
  }, [data?.items]);

  async function suspendTenant(id: number) {
    await api.post(`/platform/tenants/${id}/suspend`);
    await refetch();
  }

  async function reactivateTenant(id: number) {
    await api.post(`/platform/tenants/${id}/reactivate`);
    await refetch();
  }

  async function archiveTenant(id: number) {
    await api.patch(`/platform/tenants/${id}/archive`);
    await refetch();
  }

  async function refreshJobs() {
    setIsRefreshingJobs(true);
    await refetchJobs();
    setIsRefreshingJobs(false);
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
          <h2 className="text-2xl font-bold text-slate-900">Tenants</h2>
          <p className="mt-1 text-sm text-slate-500">Manage organizations registered on the platform.</p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only platform admins can access tenant management.</p>
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
          <h2 className="text-2xl font-bold text-slate-900">Tenants</h2>
          <p className="mt-1 text-sm text-slate-500">
            Register organizations, manage lifecycle state, and monitor queue health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => void refreshJobs()} disabled={isRefreshingJobs}>
            <TimerReset className="mr-2 h-4 w-4" />
            Refresh queues
          </Button>
          <Button asChild>
            <Link href="/platform/tenants/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Tenant
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Active</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{summary.active}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Suspended</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{summary.suspended}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Archived</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{summary.archived}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Export Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{jobStatus?.queues.exports.queue_depth ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Due retries: {jobStatus?.queues.exports.due_retries ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Webhook Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">{jobStatus?.queues.webhooks.queue_depth ?? 0}</p>
            <p className="mt-1 text-xs text-slate-500">Due retries: {jobStatus?.queues.webhooks.due_retries ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <CardTitle>Tenant Directory</CardTitle>
            <p className="mt-1 text-sm text-slate-500">
              Search tenants by name, geography, or lifecycle status.
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[420px]">
            <Input
              aria-label="Search tenants"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search tenants"
            />
            <Select
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "", label: "All statuses" },
                { value: "active", label: "Active" },
                { value: "suspended", label: "Suspended" },
                { value: "archived", label: "Archived" },
              ]}
            />
          </div>
        </CardHeader>
        <CardContent>
          {tenants.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Search className="mb-3 h-10 w-10 text-slate-300" />
              <p className="font-medium">No tenants found.</p>
              <p className="mt-1 text-sm">Adjust your filters or create a new tenant.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>Industry</TableHead>
                  <TableHead>Users</TableHead>
                  <TableHead>Setup</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map((tenant) => (
                  <TableRow key={tenant.id}>
                    <TableCell className="font-medium">{tenant.name}</TableCell>
                    <TableCell>{tenant.country ?? "-"}</TableCell>
                    <TableCell>{tenant.industry ?? "-"}</TableCell>
                    <TableCell>{tenant.user_count}</TableCell>
                    <TableCell>
                      <Badge variant={tenant.setup_completed ? "success" : "secondary"}>
                        {tenant.setup_completed ? "Complete" : "Pending"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={tenantStatusVariant(tenant.status)}>{tenant.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button variant="outline" size="sm" asChild>
                          <Link href={`/platform/tenants/${tenant.id}`}>Details</Link>
                        </Button>
                        {tenant.status === "active" ? (
                          <Button variant="outline" size="sm" onClick={() => void suspendTenant(tenant.id)}>
                            <Pause className="mr-2 h-4 w-4" />
                            Suspend
                          </Button>
                        ) : tenant.status === "suspended" ? (
                          <Button variant="outline" size="sm" onClick={() => void reactivateTenant(tenant.id)}>
                            <Play className="mr-2 h-4 w-4" />
                            Reactivate
                          </Button>
                        ) : null}
                        {tenant.status !== "archived" && (
                          <Button variant="outline" size="sm" onClick={() => void archiveTenant(tenant.id)}>
                            Archive
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
