"use client";

import { useState, useMemo, useCallback, useId } from "react";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Search,
  Plus,
  ChevronDown,
  Loader2,
  AlertTriangle,
  Users,
  Clock,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AssignmentStatus = "assigned" | "in_progress" | "completed" | "overdue";

interface Assignment {
  id: number;
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  entity_id: number;
  entity_name: string;
  facility_id: number | null;
  facility_name: string | null;
  boundary_included: boolean;
  consolidation_method: string;
  collector_id: number | null;
  collector_name: string | null;
  reviewer_id: number | null;
  reviewer_name: string | null;
  deadline: string | null;
  status: AssignmentStatus;
  created_at: string;
}

interface User {
  id: number;
  name: string;
  email: string;
}

interface Entity {
  id: number;
  name: string;
  code: string;
}

interface AssignmentsResponse {
  assignments: Assignment[];
  users: User[];
  entities: Entity[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStatusBadgeVariant(
  status: AssignmentStatus
): "default" | "secondary" | "success" | "destructive" | "warning" {
  switch (status) {
    case "assigned":
      return "secondary";
    case "in_progress":
      return "warning";
    case "completed":
      return "success";
    case "overdue":
      return "destructive";
    default:
      return "secondary";
  }
}

function getSLAColor(deadline: string | null): {
  color: string;
  label: string;
} {
  if (!deadline) return { color: "bg-slate-100 text-slate-500", label: "N/A" };
  const now = new Date();
  const due = new Date(deadline);
  const diffDays = Math.ceil(
    (due.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (diffDays < 0)
    return { color: "bg-red-100 text-red-700", label: `${Math.abs(diffDays)}d overdue` };
  if (diffDays <= 3)
    return { color: "bg-orange-100 text-orange-700", label: `${diffDays}d left` };
  if (diffDays <= 7)
    return { color: "bg-yellow-100 text-yellow-700", label: `${diffDays}d left` };
  return { color: "bg-green-100 text-green-700", label: `${diffDays}d left` };
}

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

// ---------------------------------------------------------------------------
// Inline Editable Cell Components
// ---------------------------------------------------------------------------

function InlineSelectCell({
  value,
  options,
  onSave,
  disabled = false,
}: {
  value: string;
  options: { value: string; label: string }[];
  onSave: (value: string) => void;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        disabled={disabled}
        className="text-left text-sm hover:bg-slate-50 rounded px-1 py-0.5 -mx-1 w-full transition-colors"
      >
        {options.find((o) => o.value === value)?.label || value || (
          <span className="text-slate-300 italic">Unassigned</span>
        )}
      </button>
    );
  }

  return (
    <Select
      options={options}
      value={value}
      onChange={(v) => {
        onSave(v);
        setEditing(false);
      }}
      disabled={disabled}
      className="h-7 text-xs w-full"
      placeholder="Select..."
    />
  );
}

function InlineDateCell({
  value,
  onSave,
  disabled = false,
}: {
  value: string | null;
  onSave: (value: string) => void;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);

  if (!editing) {
    return (
      <button
        type="button"
        onClick={() => setEditing(true)}
        disabled={disabled}
        className="text-left text-sm hover:bg-slate-50 rounded px-1 py-0.5 -mx-1 w-full transition-colors"
      >
        {value ? new Date(value).toLocaleDateString() : (
          <span className="text-slate-300 italic">No date</span>
        )}
      </button>
    );
  }

  return (
    <Input
      type="date"
      defaultValue={value ? value.split("T")[0] : ""}
      disabled={disabled}
      className="h-7 text-xs w-full"
      onBlur={(e) => {
        if (e.target.value) onSave(e.target.value);
        setEditing(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          const target = e.target as HTMLInputElement;
          if (target.value) onSave(target.value);
          setEditing(false);
        }
        if (e.key === "Escape") setEditing(false);
      }}
      autoFocus
    />
  );
}

// ---------------------------------------------------------------------------
// Add Assignment Dialog
// ---------------------------------------------------------------------------

function AddAssignmentDialog({
  open,
  onOpenChange,
  users,
  entities,
  projectId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  users: User[];
  entities: Entity[];
  projectId: number;
}) {
  const queryClient = useQueryClient();
  const elementCodeId = useId();
  const elementNameId = useId();
  const deadlineId = useId();
  const [form, setForm] = useState({
    shared_element_code: "",
    shared_element_name: "",
    entity_id: "",
    consolidation_method: "full",
    collector_id: "",
    reviewer_id: "",
    deadline: "",
  });

  const mutation = useApiMutation<Assignment, typeof form>(
    `/projects/${projectId}/assignments`,
    "POST",
    {
      onSuccess: (assignment) => {
        queryClient.setQueryData<AssignmentsResponse>(
          ["assignments", projectId],
          (current) =>
            current
              ? {
                  ...current,
                  assignments: current.assignments.filter((item) => item.id !== assignment.id),
                }
              : current
        );
        const entity = entities.find((item) => String(item.id) === form.entity_id);
        const collector = users.find((item) => String(item.id) === form.collector_id);
        const reviewer = users.find((item) => String(item.id) === form.reviewer_id);
        const matrixRow: Assignment = {
          ...assignment,
          shared_element_code: form.shared_element_code,
          shared_element_name: form.shared_element_name,
          entity_id: entity?.id ?? assignment.entity_id ?? 0,
          entity_name: entity?.name ?? "",
          facility_id: null,
          facility_name: null,
          boundary_included: true,
          consolidation_method: form.consolidation_method,
          collector_id: collector?.id ?? assignment.collector_id ?? null,
          collector_name: collector?.name ?? null,
          reviewer_id: reviewer?.id ?? assignment.reviewer_id ?? null,
          reviewer_name: reviewer?.name ?? null,
          deadline: assignment.deadline ?? form.deadline ?? null,
          created_at: new Date().toISOString(),
        };
        queryClient.setQueryData<AssignmentsResponse>(
          ["assignments", projectId],
          (current) =>
            current
              ? {
                  ...current,
                  assignments: [
                    matrixRow,
                    ...current.assignments.filter((item) => item.id !== assignment.id),
                  ],
                }
              : current
        );
        void queryClient.invalidateQueries({
          queryKey: ["dashboard", "progress", projectId],
        });
        void queryClient.invalidateQueries({ queryKey: ["projects"] });
        onOpenChange(false);
        setForm({
          shared_element_code: "",
          shared_element_name: "",
          entity_id: "",
          consolidation_method: "full",
          collector_id: "",
          reviewer_id: "",
          deadline: "",
        });
      },
      onError: () => {
        queryClient.invalidateQueries({ queryKey: ["assignments", projectId] });
      },
    }
  );

  const collectorReviewerWarning =
    form.collector_id &&
    form.reviewer_id &&
    form.collector_id === form.reviewer_id;

  const userOptions = users.map((u) => ({
    value: String(u.id),
    label: u.name,
  }));

  const entityOptions = entities.map((e) => ({
    value: String(e.id),
    label: `${e.code} - ${e.name}`,
  }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Assignment</DialogTitle>
          <DialogDescription>
            Create a new data collection assignment.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor={elementCodeId}>Element Code</Label>
              <Input
                id={elementCodeId}
                value={form.shared_element_code}
                onChange={(e) =>
                  setForm({ ...form, shared_element_code: e.target.value })
                }
                placeholder="E1-1"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={elementNameId}>Element Name</Label>
              <Input
                id={elementNameId}
                value={form.shared_element_name}
                onChange={(e) =>
                  setForm({ ...form, shared_element_name: e.target.value })
                }
                placeholder="GHG Emissions"
              />
            </div>
          </div>
          <Select
            label="Entity"
            options={entityOptions}
            value={form.entity_id}
            onChange={(v) => setForm({ ...form, entity_id: v })}
            placeholder="Select entity"
          />
          <Select
            label="Consolidation Method"
            options={[
              { value: "full", label: "Full Consolidation" },
              { value: "proportional", label: "Proportional" },
              { value: "equity", label: "Equity Method" },
            ]}
            value={form.consolidation_method}
            onChange={(v) => setForm({ ...form, consolidation_method: v })}
          />
          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Collector"
              options={[{ value: "", label: "Unassigned" }, ...userOptions]}
              value={form.collector_id}
              onChange={(v) => setForm({ ...form, collector_id: v })}
              placeholder="Select collector"
            />
            <Select
              label="Reviewer"
              options={[{ value: "", label: "Unassigned" }, ...userOptions]}
              value={form.reviewer_id}
              onChange={(v) => setForm({ ...form, reviewer_id: v })}
              placeholder="Select reviewer"
            />
          </div>
          {collectorReviewerWarning && (
            <div className="flex items-center gap-2 rounded bg-amber-50 border border-amber-200 p-2.5 text-xs text-amber-800">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              Collector and reviewer should not be the same person.
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor={deadlineId}>Deadline</Label>
            <Input
              id={deadlineId}
              type="date"
              value={form.deadline}
              onChange={(e) => setForm({ ...form, deadline: e.target.value })}
            />
          </div>
        </div>
        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate(form)}
            disabled={
              mutation.isPending ||
              !form.shared_element_code ||
              !form.entity_id
            }
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Assignment
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Bulk Action Dialog
// ---------------------------------------------------------------------------

function BulkActionDialog({
  open,
  onOpenChange,
  action,
  selectedCount,
  users,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  action: "collector" | "reviewer" | "deadline";
  selectedCount: number;
  users: User[];
  onConfirm: (value: string) => void;
}) {
  const [value, setValue] = useState("");

  const userOptions = users.map((u) => ({
    value: String(u.id),
    label: u.name,
  }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {action === "collector"
              ? "Assign Collector"
              : action === "reviewer"
                ? "Assign Reviewer"
                : "Set Deadline"}
          </DialogTitle>
          <DialogDescription>
            Apply to {selectedCount} selected assignment
            {selectedCount !== 1 ? "s" : ""}.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4">
          {action === "deadline" ? (
            <div className="space-y-1.5">
              <Label>Deadline</Label>
              <Input
                type="date"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </div>
          ) : (
            <Select
              label={action === "collector" ? "Collector" : "Reviewer"}
              options={userOptions}
              value={value}
              onChange={setValue}
              placeholder={`Select ${action}`}
            />
          )}
        </div>
        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              onConfirm(value);
              setValue("");
              onOpenChange(false);
            }}
            disabled={!value}
          >
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AssignmentsPage() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const projectId = useMemo(() => {
    const raw = searchParams.get("projectId");
    const parsed = Number(raw ?? "1");
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  }, [searchParams]);
  const [searchTerm, setSearchTerm] = useState("");
  const [collectorFilter, setCollectorFilter] = useState("");
  const [reviewerFilter, setReviewerFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [entityFilter, setEntityFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [bulkAction, setBulkAction] = useState<
    "collector" | "reviewer" | "deadline" | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");
  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) =>
    ["admin", "esg_manager", "platform_admin"].includes(role)
  );

  const { data, isLoading, error } = useApiQuery<AssignmentsResponse>(
    ["assignments", projectId],
    `/projects/${projectId}/assignments`,
    { enabled: canAccess }
  );

  const assignments = useMemo(() => data?.assignments ?? [], [data]);
  const users = useMemo(() => data?.users ?? [], [data]);
  const entities = useMemo(() => data?.entities ?? [], [data]);

  const patchAssignments = useCallback(
    (updater: (assignment: Assignment) => Assignment) => {
      queryClient.setQueryData<AssignmentsResponse>(
        ["assignments", projectId],
        (current) =>
          current
            ? {
                ...current,
                assignments: current.assignments.map(updater),
              }
            : current
      );
    },
    [projectId, queryClient]
  );

  const resolveUserName = useCallback(
    (userId: string) => {
      const match = users.find((user) => String(user.id) === userId);
      return match?.name ?? null;
    },
    [users]
  );

  const updateMutation = useApiMutation<
    Assignment,
    { id: number; field: string; value: string }
  >(`/projects/${projectId}/assignments/inline-update`, "PATCH", {
    onSuccess: (updated) => {
      setActionError(null);
      patchAssignments((assignment) =>
        assignment.id === updated.id ? { ...assignment, ...updated } : assignment
      );
      void queryClient.invalidateQueries({
        queryKey: ["dashboard", "progress", projectId],
      });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => {
      setActionError(error.message);
    },
  });

  const bulkMutation = useApiMutation<
    { updated_count: number; assignment_ids: number[] },
    { ids: number[]; field: string; value: string }
  >(`/projects/${projectId}/assignments/bulk-update`, "PATCH", {
    onSuccess: (_result, variables) => {
      setActionError(null);
      const affectedIds = new Set(variables.ids);
      patchAssignments((assignment) => {
        if (!affectedIds.has(assignment.id)) {
          return assignment;
        }
        if (variables.field === "collector_id") {
          return {
            ...assignment,
            collector_id: variables.value ? Number(variables.value) : null,
            collector_name: variables.value ? resolveUserName(variables.value) : null,
          };
        }
        if (variables.field === "reviewer_id") {
          return {
            ...assignment,
            reviewer_id: variables.value ? Number(variables.value) : null,
            reviewer_name: variables.value ? resolveUserName(variables.value) : null,
          };
        }
        if (variables.field === "deadline") {
          return {
            ...assignment,
            deadline: variables.value || null,
          };
        }
        return assignment;
      });
      void queryClient.invalidateQueries({
        queryKey: ["dashboard", "progress", projectId],
      });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      setSelectedIds(new Set());
    },
    onError: (error) => {
      setActionError(error.message);
    },
  });

  const userOptions = useMemo(
    () => [
      { value: "", label: "All" },
      ...users.map((u) => ({ value: String(u.id), label: u.name })),
    ],
    [users]
  );

  const entityOptions = useMemo(
    () => [
      { value: "", label: "All entities" },
      ...entities.map((e) => ({
        value: String(e.id),
        label: `${e.code} - ${e.name}`,
      })),
    ],
    [entities]
  );

  const statusOptions = [
    { value: "", label: "All statuses" },
    { value: "assigned", label: "Assigned" },
    { value: "in_progress", label: "In Progress" },
    { value: "completed", label: "Completed" },
    { value: "overdue", label: "Overdue" },
  ];

  // Filter assignments
  const filtered = useMemo(() => {
    return assignments.filter((a) => {
      if (
        searchTerm &&
        !a.shared_element_code
          .toLowerCase()
          .includes(searchTerm.toLowerCase()) &&
        !a.shared_element_name
          .toLowerCase()
          .includes(searchTerm.toLowerCase()) &&
        !a.entity_name.toLowerCase().includes(searchTerm.toLowerCase())
      )
        return false;
      if (
        collectorFilter &&
        String(a.collector_id) !== collectorFilter
      )
        return false;
      if (
        reviewerFilter &&
        String(a.reviewer_id) !== reviewerFilter
      )
        return false;
      if (statusFilter && a.status !== statusFilter) return false;
      if (entityFilter && String(a.entity_id) !== entityFilter) return false;
      return true;
    });
  }, [
    assignments,
    searchTerm,
    collectorFilter,
    reviewerFilter,
    statusFilter,
    entityFilter,
  ]);

  // Summary stats
  const stats = useMemo(() => {
    return {
      total: assignments.length,
      overdue: assignments.filter((a) => a.status === "overdue").length,
      completed: assignments.filter((a) => a.status === "completed").length,
      unassigned: assignments.filter((a) => !a.collector_id).length,
    };
  }, [assignments]);

  // Selection handlers
  const allSelected =
    filtered.length > 0 && filtered.every((a) => selectedIds.has(a.id));

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map((a) => a.id)));
    }
  }, [allSelected, filtered]);

  const toggleOne = useCallback((id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Inline update handler
  const handleInlineUpdate = useCallback(
    (id: number, field: string, value: string) => {
      updateMutation.mutate({ id, field, value });
    },
    [updateMutation]
  );

  // Bulk confirm
  const handleBulkConfirm = useCallback(
    (value: string) => {
      if (!bulkAction || selectedIds.size === 0) return;
      const fieldMap = {
        collector: "collector_id",
        reviewer: "reviewer_id",
        deadline: "deadline",
      };
      bulkMutation.mutate({
        ids: Array.from(selectedIds),
        field: fieldMap[bulkAction],
        value,
      });
    },
    [bulkAction, selectedIds, bulkMutation]
  );

  const collectorUserOptions = useMemo(
    () =>
      users.map((u) => ({
        value: String(u.id),
        label: u.name,
      })),
    [users]
  );

  if (meLoading || isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if ((Boolean(me) && !canAccess) || (error && isForbidden(error))) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Assignments</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage data collection assignments
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-12 text-center">
          <ShieldAlert className="mx-auto mb-3 h-10 w-10 text-red-500" />
          <p className="text-sm font-medium text-slate-900">Access denied</p>
          <p className="mt-1 text-sm text-slate-500">
            Only admin and ESG manager roles can manage assignments.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Assignments</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage data collection assignments
          </p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-12 text-center">
          <AlertTriangle className="mx-auto mb-3 h-10 w-10 text-amber-500" />
          <p className="text-sm text-slate-500">
            Unable to load assignments. Please try again later.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">
          Assignments Matrix
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage data collection assignments, collectors, and reviewers
        </p>
      </div>

      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </div>
      )}

      {/* Top bar: search, filters, actions */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-[300px]">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <Input
            placeholder="Search elements, entities..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-8 h-9"
          />
        </div>
        <Select
          options={userOptions}
          value={collectorFilter}
          onChange={setCollectorFilter}
          placeholder="Collector"
          className="h-9 w-[160px]"
        />
        <Select
          options={userOptions}
          value={reviewerFilter}
          onChange={setReviewerFilter}
          placeholder="Reviewer"
          className="h-9 w-[160px]"
        />
        <Select
          options={statusOptions}
          value={statusFilter}
          onChange={setStatusFilter}
          className="h-9 w-[150px]"
        />
        <Select
          options={entityOptions}
          value={entityFilter}
          onChange={setEntityFilter}
          className="h-9 w-[200px]"
        />

        <div className="ml-auto flex items-center gap-2">
          {selectedIds.size > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm">
                  Bulk Actions ({selectedIds.size})
                  <ChevronDown className="ml-1 h-3.5 w-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setBulkAction("collector")}>
                  <Users className="mr-2 h-3.5 w-3.5" />
                  Assign Collector
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setBulkAction("reviewer")}>
                  <Users className="mr-2 h-3.5 w-3.5" />
                  Assign Reviewer
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setBulkAction("deadline")}>
                  <Clock className="mr-2 h-3.5 w-3.5" />
                  Set Deadline
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button onClick={() => setAddDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Add Assignment
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-slate-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]">
                <Checkbox
                  checked={allSelected}
                  onCheckedChange={toggleAll}
                />
              </TableHead>
              <TableHead>Shared Element</TableHead>
              <TableHead>Entity</TableHead>
              <TableHead>Facility</TableHead>
              <TableHead className="text-center">Boundary</TableHead>
              <TableHead>Consolidation</TableHead>
              <TableHead>Collector</TableHead>
              <TableHead>Reviewer</TableHead>
              <TableHead>Deadline</TableHead>
              <TableHead className="text-center">Status</TableHead>
              <TableHead className="text-center">SLA</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={11} className="text-center py-12">
                  <p className="text-sm text-slate-400">
                    {assignments.length === 0
                      ? "No assignments yet. Click Add Assignment to create one."
                      : "No assignments match the current filters."}
                  </p>
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((assignment) => {
                const sla = getSLAColor(assignment.deadline);
                const collectorReviewerConflict =
                  assignment.collector_id &&
                  assignment.reviewer_id &&
                  assignment.collector_id === assignment.reviewer_id;

                return (
                  <TableRow
                    key={assignment.id}
                    data-state={
                      selectedIds.has(assignment.id) ? "selected" : undefined
                    }
                  >
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.has(assignment.id)}
                        onCheckedChange={() => toggleOne(assignment.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-mono text-xs text-slate-500">
                          {assignment.shared_element_code}
                        </span>
                        <span className="text-sm font-medium">
                          {assignment.shared_element_name}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {assignment.entity_name}
                    </TableCell>
                    <TableCell className="text-sm text-slate-600">
                      {assignment.facility_name || "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={
                          assignment.boundary_included ? "success" : "secondary"
                        }
                        className="text-[10px]"
                      >
                        {assignment.boundary_included ? "In" : "Out"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-slate-600">
                      {assignment.consolidation_method}
                    </TableCell>
                    <TableCell className="min-w-[140px]">
                      <div className="flex items-center gap-1">
                        <InlineSelectCell
                          value={
                            assignment.collector_id
                              ? String(assignment.collector_id)
                              : ""
                          }
                          options={collectorUserOptions}
                          disabled={updateMutation.isPending || bulkMutation.isPending}
                          onSave={(v) =>
                            handleInlineUpdate(
                              assignment.id,
                              "collector_id",
                              v
                            )
                          }
                        />
                        {collectorReviewerConflict && (
                          <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="min-w-[140px]">
                      <div className="flex items-center gap-1">
                        <InlineSelectCell
                          value={
                            assignment.reviewer_id
                              ? String(assignment.reviewer_id)
                              : ""
                          }
                          options={collectorUserOptions}
                          disabled={updateMutation.isPending || bulkMutation.isPending}
                          onSave={(v) =>
                            handleInlineUpdate(
                              assignment.id,
                              "reviewer_id",
                              v
                            )
                          }
                        />
                        {collectorReviewerConflict && (
                          <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="min-w-[130px]">
                      <InlineDateCell
                        value={assignment.deadline}
                        disabled={updateMutation.isPending || bulkMutation.isPending}
                        onSave={(v) =>
                          handleInlineUpdate(assignment.id, "deadline", v)
                        }
                      />
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={getStatusBadgeVariant(assignment.status)}
                        className="text-[10px]"
                      >
                        {assignment.status.replace(/_/g, " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <span
                        className={cn(
                          "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-medium",
                          sla.color
                        )}
                      >
                        {sla.label}
                      </span>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Summary Stats */}
      <div className="flex items-center gap-6 rounded-lg border border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-500">Total assignments:</span>
          <span className="font-semibold">{stats.total}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
          <span className="text-slate-500">Overdue:</span>
          <span className="font-semibold text-red-600">{stats.overdue}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
          <span className="text-slate-500">Completed:</span>
          <span className="font-semibold text-green-600">
            {stats.completed}
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <AlertCircle className="h-3.5 w-3.5 text-yellow-500" />
          <span className="text-slate-500">Unassigned:</span>
          <span className="font-semibold text-yellow-600">
            {stats.unassigned}
          </span>
        </div>
      </div>

      {/* Dialogs */}
      <AddAssignmentDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        users={users}
        entities={entities}
        projectId={projectId}
      />
      {bulkAction && (
        <BulkActionDialog
          open={!!bulkAction}
          onOpenChange={(v) => {
            if (!v) setBulkAction(null);
          }}
          action={bulkAction}
          selectedCount={selectedIds.size}
          users={users}
          onConfirm={handleBulkConfirm}
        />
      )}
    </div>
  );
}
