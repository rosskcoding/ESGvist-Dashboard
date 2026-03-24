"use client";

import { Fragment, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Download,
  Loader2,
  Search,
  ShieldAlert,
} from "lucide-react";

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
import { useApiQuery } from "@/lib/hooks/use-api";

type AuditEntry = {
  id: number;
  organization_id: number | null;
  user_id: number | null;
  entity_type: string;
  entity_id: number | null;
  action: string;
  changes: Record<string, unknown> | null;
  request_id: string | null;
  performed_by_platform_admin: boolean;
  created_at: string | null;
};

type AuditResponse = {
  items: AuditEntry[];
  total: number;
};

const actionOptions = [
  { value: "", label: "All Actions" },
  { value: "login", label: "Login" },
  { value: "create", label: "Create" },
  { value: "update", label: "Update" },
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
  { value: "publish", label: "Publish" },
  { value: "gate_check", label: "Gate Check" },
];

export default function AuditPage() {
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [entityId, setEntityId] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");

  const role = me?.roles?.[0]?.role ?? "";
  const canAccess = role === "admin" || role === "auditor";
  const accessDenied = Boolean(role) && !canAccess;

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", "1");
    params.set("page_size", "50");
    if (entityType) params.set("entity_type", entityType);
    if (action) params.set("action", action);
    if (entityId) params.set("entity_id", entityId);
    return `/audit-log?${params.toString()}`;
  }, [action, entityId, entityType]);

  const { data, isLoading, error } = useApiQuery<AuditResponse>(
    ["audit-log", action, entityType, entityId],
    query,
    { enabled: canAccess }
  );

  const items = data?.items ?? [];

  function exportAudit(format: "csv" | "json") {
    const params = new URLSearchParams();
    params.set("format", format);
    if (entityType) params.set("entity_type", entityType);
    if (action) params.set("action", action);
    if (entityId) params.set("entity_id", entityId);
    window.open(`/api/audit-log/export?${params.toString()}`, "_blank");
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
          <h2 className="text-2xl font-bold text-slate-900">Audit Log</h2>
          <p className="mt-1 text-sm text-slate-500">
            Track changes, approvals, exports, and operational actions.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only admin and auditor roles can access audit logs.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Audit Log</h2>
          <p className="mt-1 text-sm text-slate-500">
            Track changes, approvals, exports, and operational actions.
          </p>
        </div>
        <Card>
          <CardContent className="flex items-center justify-center py-12 text-amber-700">
            <AlertTriangle className="mr-3 h-5 w-5" />
            Unable to load audit log entries.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Audit Log</h2>
          <p className="mt-1 text-sm text-slate-500">
            Track changes, approvals, exports, and operational actions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => exportAudit("csv")}>
            <Download className="mr-2 h-4 w-4" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportAudit("json")}>
            <Download className="mr-2 h-4 w-4" />
            JSON
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <Input
              label="Entity ID"
              placeholder="Filter by entity id"
              value={entityId}
              onChange={(event) => setEntityId(event.target.value)}
            />
            <Input
              label="Entity Type"
              placeholder="e.g. ReportingProject"
              value={entityType}
              onChange={(event) => setEntityType(event.target.value)}
            />
            <Select
              label="Action"
              value={action}
              onChange={setAction}
              options={actionOptions}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-slate-500">
              <Search className="mb-3 h-10 w-10 text-slate-300" />
              <p>No audit log entries found.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity Type</TableHead>
                  <TableHead>Entity ID</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Platform Admin</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((entry) => (
                  <Fragment key={entry.id}>
                    <TableRow
                      className="cursor-pointer hover:bg-slate-50"
                      onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                    >
                      <TableCell>
                        {expandedId === entry.id ? (
                          <ChevronDown className="h-4 w-4 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-slate-400" />
                        )}
                      </TableCell>
                      <TableCell className="text-sm">{entry.created_at ? new Date(entry.created_at).toLocaleString() : "-"}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{entry.action}</Badge>
                      </TableCell>
                      <TableCell className="text-sm">{entry.entity_type}</TableCell>
                      <TableCell className="text-sm">{entry.entity_id ?? "-"}</TableCell>
                      <TableCell className="text-sm">{entry.user_id ?? "-"}</TableCell>
                      <TableCell>
                        <Badge variant={entry.performed_by_platform_admin ? "warning" : "outline"}>
                          {entry.performed_by_platform_admin ? "Yes" : "No"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                    {expandedId === entry.id && (
                      <TableRow>
                        <TableCell colSpan={7} className="bg-slate-50 p-4">
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div>
                              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Request ID</p>
                              <p className="mt-1 font-mono text-sm text-slate-700">{entry.request_id ?? "-"}</p>
                            </div>
                            <div>
                              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Organization ID</p>
                              <p className="mt-1 font-mono text-sm text-slate-700">{entry.organization_id ?? "-"}</p>
                            </div>
                          </div>
                          <div className="mt-4">
                            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Changes</p>
                            <pre className="mt-2 overflow-auto rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700">
                              {entry.changes ? JSON.stringify(entry.changes, null, 2) : "No field-level changes recorded."}
                            </pre>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
