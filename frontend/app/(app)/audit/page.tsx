"use client";

import { useState, useCallback } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import {
  Loader2,
  Download,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Search,
  Filter,
} from "lucide-react";

interface AuditEntry {
  id: number;
  timestamp: string;
  user_name: string;
  user_id: number;
  action: string;
  entity_type: string;
  entity_id: string;
  description: string;
  changes: Record<string, { before: unknown; after: unknown }> | null;
  outcome: "success" | "failure";
}

interface AuditLogResponse {
  items: AuditEntry[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

const actionOptions = [
  { value: "", label: "All Actions" },
  { value: "create", label: "Create" },
  { value: "update", label: "Update" },
  { value: "delete", label: "Delete" },
  { value: "approve", label: "Approve" },
  { value: "reject", label: "Reject" },
  { value: "login", label: "Login" },
  { value: "export", label: "Export" },
];

const entityTypeOptions = [
  { value: "", label: "All Entity Types" },
  { value: "project", label: "Project" },
  { value: "disclosure", label: "Disclosure" },
  { value: "data_point", label: "Data Point" },
  { value: "boundary", label: "Boundary" },
  { value: "entity", label: "Entity" },
  { value: "user", label: "User" },
  { value: "assignment", label: "Assignment" },
];

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const buildQuery = useCallback(() => {
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("per_page", "20");
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (entityType) params.set("entity_type", entityType);
    if (action) params.set("action", action);
    if (resourceId) params.set("resource_id", resourceId);
    return `/audit-log?${params.toString()}`;
  }, [page, dateFrom, dateTo, entityType, action, resourceId]);

  const { data, isLoading } = useApiQuery<AuditLogResponse>(
    ["audit-log", page, dateFrom, dateTo, entityType, action, resourceId],
    buildQuery()
  );

  const auditLog = data ?? {
    items: [],
    total: 0,
    page: 1,
    per_page: 20,
    total_pages: 0,
  };

  const handleExport = (format: "csv" | "json") => {
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (entityType) params.set("entity_type", entityType);
    if (action) params.set("action", action);
    params.set("format", format);
    window.open(`/api/audit-log/export?${params.toString()}`, "_blank");
  };

  const getActionBadgeVariant = (act: string) => {
    switch (act) {
      case "create":
        return "default";
      case "update":
        return "secondary";
      case "delete":
        return "destructive";
      case "approve":
        return "default";
      case "reject":
        return "destructive";
      default:
        return "secondary";
    }
  };

  const renderJsonDiff = (changes: Record<string, { before: unknown; after: unknown }>) => {
    return (
      <div className="space-y-2">
        {Object.entries(changes).map(([field, { before, after }]) => (
          <div key={field} className="rounded border border-slate-200 p-2">
            <p className="mb-1 text-xs font-medium text-slate-600">{field}</p>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded bg-red-50 p-2">
                <p className="mb-1 text-xs font-medium text-red-600">Before</p>
                <pre className="text-xs text-red-800">
                  {JSON.stringify(before, null, 2)}
                </pre>
              </div>
              <div className="rounded bg-green-50 p-2">
                <p className="mb-1 text-xs font-medium text-green-600">After</p>
                <pre className="text-xs text-green-800">
                  {JSON.stringify(after, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Audit Log</h2>
          <p className="mt-1 text-sm text-slate-500">
            Track all changes and actions across the platform
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => handleExport("csv")}>
            <Download className="mr-2 h-4 w-4" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport("json")}>
            <Download className="mr-2 h-4 w-4" />
            JSON
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setPage(1);
              }}
              placeholder="From date"
            />
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setPage(1);
              }}
              placeholder="To date"
            />
            <Select
              options={entityTypeOptions}
              value={entityType}
              onChange={(val) => {
                setEntityType(val);
                setPage(1);
              }}
              placeholder="Entity Type"
            />
            <Select
              options={actionOptions}
              value={action}
              onChange={(val) => {
                setAction(val);
                setPage(1);
              }}
              placeholder="Action"
            />
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <Input
                className="pl-9"
                placeholder="Search resource ID..."
                value={resourceId}
                onChange={(e) => {
                  setResourceId(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : auditLog.items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Search className="mb-3 h-10 w-10 text-slate-300" />
              <p className="text-sm text-slate-500">No audit log entries found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Timestamp</TableHead>
                  <TableHead>User</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Entity Type</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {auditLog.items.map((entry) => (
                  <>
                    <TableRow
                      key={entry.id}
                      className="cursor-pointer hover:bg-slate-50"
                      onClick={() =>
                        setExpandedRow(
                          expandedRow === entry.id ? null : entry.id
                        )
                      }
                    >
                      <TableCell>
                        {expandedRow === entry.id ? (
                          <ChevronDown className="h-4 w-4 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-slate-400" />
                        )}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-sm">
                        {new Date(entry.timestamp).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-sm font-medium">
                        {entry.user_name}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={getActionBadgeVariant(entry.action) as "default" | "secondary" | "destructive"}
                        >
                          {entry.action}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-slate-600">
                        {entry.entity_type}
                      </TableCell>
                      <TableCell className="max-w-[300px] truncate text-sm text-slate-600">
                        {entry.description}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            entry.outcome === "success"
                              ? "default"
                              : "destructive"
                          }
                          className={
                            entry.outcome === "success"
                              ? "bg-green-100 text-green-700"
                              : ""
                          }
                        >
                          {entry.outcome}
                        </Badge>
                      </TableCell>
                    </TableRow>
                    {expandedRow === entry.id && (
                      <TableRow key={`${entry.id}-expanded`}>
                        <TableCell colSpan={7} className="bg-slate-50 p-4">
                          <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <p className="text-xs font-medium text-slate-500">
                                  Entity ID
                                </p>
                                <p className="font-mono">{entry.entity_id}</p>
                              </div>
                              <div>
                                <p className="text-xs font-medium text-slate-500">
                                  User ID
                                </p>
                                <p className="font-mono">{entry.user_id}</p>
                              </div>
                            </div>
                            {entry.changes && (
                              <div>
                                <p className="mb-2 text-xs font-medium text-slate-500">
                                  Changes
                                </p>
                                {renderJsonDiff(entry.changes)}
                              </div>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {auditLog.total_pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-500">
            Showing {(auditLog.page - 1) * auditLog.per_page + 1} to{" "}
            {Math.min(auditLog.page * auditLog.per_page, auditLog.total)} of{" "}
            {auditLog.total} entries
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <span className="text-sm text-slate-600">
              Page {auditLog.page} of {auditLog.total_pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(auditLog.total_pages, p + 1))}
              disabled={page === auditLog.total_pages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
