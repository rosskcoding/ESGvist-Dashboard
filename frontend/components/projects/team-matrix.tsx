"use client";

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Loader2,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";

interface User {
  id: number;
  name: string;
  email: string;
}

interface Entity {
  id: number;
  name: string;
  code: string | null;
}

interface MatrixRow {
  id: number;
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  entity_id: number | null;
  entity_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  boundary_included: boolean;
  consolidation_method: string;
  collector_id: number | null;
  collector_name: string | null;
  reviewer_id: number | null;
  reviewer_name: string | null;
  backup_collector_id: number | null;
  backup_collector_name: string | null;
  deadline: string | null;
  escalation_after_days: number;
  sla_status: string;
  days_overdue: number;
  days_until_deadline: number | null;
  status: string;
  created_at: string | null;
}

interface MatrixResponse {
  assignments: MatrixRow[];
  users: User[];
  entities: Entity[];
}

type QuickFilter = null | "overdue" | "unassigned" | "review";

interface TeamMatrixProps {
  projectId: string;
  onError?: (message: string | null) => void;
}

function avatarInitials(name: string | null): string {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function avatarColor(id: number | null): string {
  if (id == null) return "bg-slate-200 text-slate-600";
  const palette = [
    "bg-sky-200 text-sky-800",
    "bg-rose-200 text-rose-800",
    "bg-emerald-200 text-emerald-800",
    "bg-violet-200 text-violet-800",
    "bg-amber-200 text-amber-800",
    "bg-teal-200 text-teal-800",
    "bg-fuchsia-200 text-fuchsia-800",
  ];
  return palette[id % palette.length];
}

function daysFromDeadline(deadline: string | null): number | null {
  if (!deadline) return null;
  const target = new Date(deadline);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function slaChip(row: MatrixRow) {
  if (!row.collector_id) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
        Unassigned
      </span>
    );
  }
  if (row.status === "completed" || row.status === "approved") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
        <Check className="h-3 w-3" strokeWidth={3} />
        Submitted
      </span>
    );
  }
  if (row.status === "in_review") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-800">
        In review
      </span>
    );
  }
  if (row.days_overdue > 0) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-800">
        <span className="h-1.5 w-1.5 rounded-full bg-rose-500"></span>
        {row.days_overdue}d overdue
      </span>
    );
  }
  const days = row.days_until_deadline ?? daysFromDeadline(row.deadline);
  if (days !== null && days <= 5) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500"></span>
        Due in {days}d
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
      On track
    </span>
  );
}

function formatShortDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface UserPickerProps {
  value: number | null;
  users: User[];
  placeholder: string;
  onChange: (userId: number | null) => void;
  disabled?: boolean;
  tone?: "default" | "warn";
}

function UserPicker({
  value,
  users,
  placeholder,
  onChange,
  disabled,
  tone = "default",
}: UserPickerProps) {
  const current = value ? users.find((u) => u.id === value) ?? null : null;

  if (current) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger disabled={disabled} asChild>
          <button
            type="button"
            className="group/cell inline-flex items-center gap-2 rounded-md px-1.5 py-1 text-sm text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed"
            disabled={disabled}
          >
            <span
              className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold ${avatarColor(
                current.id
              )}`}
            >
              {avatarInitials(current.name)}
            </span>
            <span className="max-w-[120px] truncate">{current.name}</span>
            <ChevronDown className="h-3 w-3 opacity-0 group-hover/cell:opacity-60" />
          </button>
        </DropdownMenuTrigger>
        <UserPickerList users={users} value={value} onChange={onChange} />
      </DropdownMenu>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger disabled={disabled} asChild>
        <button
          type="button"
          className={`inline-flex items-center gap-1.5 rounded-md border border-dashed px-2 py-1 text-xs transition-colors disabled:cursor-not-allowed ${
            tone === "warn"
              ? "border-amber-300 bg-amber-50 font-medium text-amber-800 hover:bg-amber-100"
              : "border-slate-300 text-slate-500 hover:border-slate-400 hover:bg-slate-50"
          }`}
          disabled={disabled}
        >
          <Plus className="h-3 w-3" strokeWidth={tone === "warn" ? 2.5 : 2} />
          {placeholder}
        </button>
      </DropdownMenuTrigger>
      <UserPickerList users={users} value={value} onChange={onChange} />
    </DropdownMenu>
  );
}

function UserPickerList({
  users,
  value,
  onChange,
}: {
  users: User[];
  value: number | null;
  onChange: (userId: number | null) => void;
}) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return users;
    return users.filter(
      (u) =>
        u.name.toLowerCase().includes(needle) ||
        u.email.toLowerCase().includes(needle)
    );
  }, [q, users]);

  return (
    <DropdownMenuContent className="w-64 p-0">
      <div className="border-b border-slate-100 p-2">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search people..."
            className="w-full rounded-md border border-slate-200 bg-slate-50 py-1.5 pl-7 pr-2 text-xs focus:bg-white focus:outline-none"
          />
        </div>
      </div>
      <div className="max-h-64 overflow-y-auto p-1">
        {value !== null && (
          <DropdownMenuItem
            onClick={() => onChange(null)}
            className="flex items-center gap-2 text-rose-600"
          >
            <X className="h-3.5 w-3.5" />
            Clear assignment
          </DropdownMenuItem>
        )}
        {filtered.length === 0 ? (
          <DropdownMenuLabel className="text-xs text-slate-400">
            No matches
          </DropdownMenuLabel>
        ) : (
          filtered.map((user) => (
            <DropdownMenuItem
              key={user.id}
              onClick={() => onChange(user.id)}
              className="flex items-center gap-2"
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold ${avatarColor(
                  user.id
                )}`}
              >
                {avatarInitials(user.name)}
              </span>
              <div className="min-w-0">
                <div className="truncate text-sm">{user.name}</div>
                <div className="truncate text-xs text-slate-500">
                  {user.email}
                </div>
              </div>
              {value === user.id && (
                <Check className="ml-auto h-3.5 w-3.5 text-emerald-600" strokeWidth={3} />
              )}
            </DropdownMenuItem>
          ))
        )}
      </div>
    </DropdownMenuContent>
  );
}

function DeadlineInput({
  value,
  onChange,
  disabled,
}: {
  value: string | null;
  onChange: (val: string | null) => void;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const label = formatShortDate(value);

  if (!editing) {
    return (
      <button
        type="button"
        className="rounded px-1 py-0.5 text-sm text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed"
        onClick={() => !disabled && setEditing(true)}
        disabled={disabled}
      >
        {label}
      </button>
    );
  }

  return (
    <input
      type="date"
      className="rounded border border-slate-300 px-1 py-0.5 text-sm"
      autoFocus
      defaultValue={value ?? ""}
      onBlur={(e) => {
        onChange(e.target.value || null);
        setEditing(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          onChange((e.target as HTMLInputElement).value || null);
          setEditing(false);
        } else if (e.key === "Escape") {
          setEditing(false);
        }
      }}
    />
  );
}

export function TeamMatrix({ projectId, onError }: TeamMatrixProps) {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useApiQuery<MatrixResponse>(
    ["project-assignments-matrix", projectId],
    `/projects/${projectId}/assignments`
  );

  const [quickFilter, setQuickFilter] = useState<QuickFilter>(null);
  const [entityFilter, setEntityFilter] = useState<number | null>(null);
  const [personFilter, setPersonFilter] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [teamLoadOpen, setTeamLoadOpen] = useState(false);

  const inlineMutation = useApiMutation<
    MatrixRow,
    { id: number; field: string; value: string }
  >(`/projects/${projectId}/assignments/inline-update`, "PATCH", {
    onMutate: () => onError?.(null),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["project-assignments-matrix", projectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["project-workflow-status", projectId],
      });
    },
    onError: (err) => onError?.(err.message || "Unable to update assignment."),
  });

  const bulkMutation = useApiMutation<
    unknown,
    { ids: number[]; field: string; value: string }
  >(`/projects/${projectId}/assignments/bulk-update`, "PATCH", {
    onMutate: () => onError?.(null),
    onSuccess: async () => {
      setSelected(new Set());
      await queryClient.invalidateQueries({
        queryKey: ["project-assignments-matrix", projectId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["project-workflow-status", projectId],
      });
    },
    onError: (err) => onError?.(err.message || "Unable to update assignments."),
  });

  const users = useMemo(() => data?.users ?? [], [data]);
  const entities = useMemo(() => data?.entities ?? [], [data]);
  const rows = useMemo(() => data?.assignments ?? [], [data]);

  const filteredRows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (quickFilter === "overdue" && row.days_overdue <= 0) return false;
      if (
        quickFilter === "unassigned" &&
        (row.collector_id !== null || row.status === "completed")
      )
        return false;
      if (
        quickFilter === "review" &&
        row.status !== "in_review" &&
        row.status !== "submitted"
      )
        return false;
      if (entityFilter !== null && row.entity_id !== entityFilter) return false;
      if (
        personFilter !== null &&
        row.collector_id !== personFilter &&
        row.reviewer_id !== personFilter &&
        row.backup_collector_id !== personFilter
      )
        return false;
      if (needle) {
        const hay = `${row.shared_element_code} ${row.shared_element_name} ${
          row.entity_name ?? ""
        } ${row.facility_name ?? ""}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [rows, quickFilter, entityFilter, personFilter, search]);

  // Counters
  const counts = useMemo(() => {
    let overdue = 0;
    let unassigned = 0;
    let review = 0;
    const loadByUser = new Map<
      number,
      { total: number; overdue: number; dueSoon: number; toReview: number }
    >();
    for (const row of rows) {
      if (row.days_overdue > 0) overdue++;
      if (!row.collector_id && row.status !== "completed") unassigned++;
      if (row.status === "in_review" || row.status === "submitted") review++;

      if (row.collector_id) {
        const entry = loadByUser.get(row.collector_id) ?? {
          total: 0,
          overdue: 0,
          dueSoon: 0,
          toReview: 0,
        };
        entry.total++;
        if (row.days_overdue > 0) entry.overdue++;
        const dus = row.days_until_deadline;
        if (dus !== null && dus <= 5 && dus >= 0) entry.dueSoon++;
        loadByUser.set(row.collector_id, entry);
      }
      if (
        row.reviewer_id &&
        (row.status === "in_review" || row.status === "submitted")
      ) {
        const entry = loadByUser.get(row.reviewer_id) ?? {
          total: 0,
          overdue: 0,
          dueSoon: 0,
          toReview: 0,
        };
        entry.toReview++;
        loadByUser.set(row.reviewer_id, entry);
      }
    }
    return { overdue, unassigned, review, loadByUser };
  }, [rows]);

  const sortedRows = useMemo(() => {
    return [...filteredRows].sort((a, b) => {
      // overdue first, then due soonest, unassigned last among others
      if (a.days_overdue !== b.days_overdue)
        return b.days_overdue - a.days_overdue;
      const aDue = a.days_until_deadline ?? 999;
      const bDue = b.days_until_deadline ?? 999;
      return aDue - bDue;
    });
  }, [filteredRows]);

  const allSelected =
    sortedRows.length > 0 && sortedRows.every((r) => selected.has(r.id));

  const toggleRow = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(sortedRows.map((r) => r.id)));
  };

  const bulkReassign = (userId: number | null) => {
    if (selected.size === 0) return;
    bulkMutation.mutate({
      ids: Array.from(selected),
      field: "collector_id",
      value: userId ? String(userId) : "",
    });
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[300px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-sm text-slate-500">
        <AlertTriangle className="mr-2 h-4 w-4 text-amber-500" />
        Unable to load assignments.
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex min-h-[260px] flex-col items-center justify-center rounded-xl border border-slate-200 bg-white py-12 text-center">
        <Users className="mb-3 h-10 w-10 text-slate-300" />
        <p className="text-sm font-medium text-slate-700">
          No assignments yet
        </p>
        <p className="mt-1 max-w-sm text-xs text-slate-500">
          Assignments are created when you launch indicators from the Standards
          tab. Go there and pick a standard to launch.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Collapsible Team load summary */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <button
          type="button"
          onClick={() => setTeamLoadOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-slate-50"
        >
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="inline-flex items-center gap-1.5 font-semibold text-slate-800">
              <Users className="h-4 w-4 text-slate-500" />
              {counts.loadByUser.size}{" "}
              {counts.loadByUser.size === 1 ? "member" : "members"}
            </span>
            {counts.overdue > 0 && (
              <span className="text-rose-700">
                · <span className="font-semibold">{counts.overdue}</span> overdue
              </span>
            )}
            {counts.unassigned > 0 && (
              <span className="text-amber-700">
                · <span className="font-semibold">{counts.unassigned}</span>{" "}
                unassigned
              </span>
            )}
            {counts.review > 0 && (
              <span className="text-sky-700">
                · <span className="font-semibold">{counts.review}</span> pending
                review
              </span>
            )}
          </div>
          <ChevronRight
            className={`h-4 w-4 text-slate-400 transition-transform ${
              teamLoadOpen ? "rotate-90" : ""
            }`}
          />
        </button>
        {teamLoadOpen && (
          <div className="grid gap-3 border-t border-slate-100 bg-slate-50/40 p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from(counts.loadByUser.entries()).map(([uid, load]) => {
              const user = users.find((u) => u.id === uid);
              if (!user) return null;
              const isActive = personFilter === uid;
              return (
                <button
                  key={uid}
                  type="button"
                  onClick={() => setPersonFilter(isActive ? null : uid)}
                  className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left transition-colors ${
                    isActive
                      ? "border-cyan-300 bg-cyan-50"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${avatarColor(
                        uid
                      )}`}
                    >
                      {avatarInitials(user.name)}
                    </span>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-slate-900">
                        {user.name}
                      </div>
                      <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                        <span>{load.total} assigned</span>
                        {load.toReview > 0 && (
                          <span className="text-sky-700">
                            · {load.toReview} to review
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-0.5 text-[11px]">
                    {load.overdue > 0 && (
                      <span className="rounded-full bg-rose-50 px-1.5 text-rose-800">
                        {load.overdue} overdue
                      </span>
                    )}
                    {load.dueSoon > 0 && (
                      <span className="rounded-full bg-amber-50 px-1.5 text-amber-800">
                        {load.dueSoon} due soon
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <FilterChip
            active={quickFilter === "overdue"}
            onClick={() =>
              setQuickFilter(quickFilter === "overdue" ? null : "overdue")
            }
            tone="rose"
            count={counts.overdue}
          >
            Overdue
          </FilterChip>
          <FilterChip
            active={quickFilter === "unassigned"}
            onClick={() =>
              setQuickFilter(quickFilter === "unassigned" ? null : "unassigned")
            }
            tone="amber"
            count={counts.unassigned}
          >
            Unassigned
          </FilterChip>
          <FilterChip
            active={quickFilter === "review"}
            onClick={() =>
              setQuickFilter(quickFilter === "review" ? null : "review")
            }
            tone="sky"
            count={counts.review}
          >
            Review pending
          </FilterChip>
          <span className="mx-1 h-4 w-px bg-slate-200"></span>
          <EntityFilter
            entities={entities}
            value={entityFilter}
            onChange={setEntityFilter}
          />
          <PersonFilter
            users={users}
            value={personFilter}
            onChange={setPersonFilter}
          />
        </div>
        <div className="relative w-60">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search element or entity"
            className="pl-8"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-2.5">
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="h-4 w-4 rounded border-slate-300"
            />
            <div className="text-xs text-slate-500">
              <span className="font-semibold text-slate-700">
                {sortedRows.length}
              </span>{" "}
              of {rows.length} assignments
            </div>
          </div>
        </div>

        {selected.size > 0 && (
          <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 bg-cyan-50 px-5 py-2 text-xs">
            <span className="font-medium text-cyan-900">
              {selected.size} selected
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="rounded border border-cyan-300 bg-white px-2 py-0.5 text-cyan-900 hover:bg-cyan-100">
                  Reassign collector
                </button>
              </DropdownMenuTrigger>
              <UserPickerList
                users={users}
                value={null}
                onChange={(uid) => bulkReassign(uid)}
              />
            </DropdownMenu>
            <button
              onClick={() => setSelected(new Set())}
              className="ml-auto text-cyan-900 hover:underline"
            >
              Clear selection
            </button>
          </div>
        )}

        {/* Header row */}
        <div className="grid grid-cols-[32px_minmax(240px,2fr)_minmax(140px,1.2fr)_minmax(160px,1.3fr)_minmax(160px,1.3fr)_minmax(110px,1fr)_minmax(110px,0.9fr)] items-center border-b border-slate-100 bg-slate-50 px-5 py-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          <div></div>
          <div>Element</div>
          <div>Entity</div>
          <div>Collector</div>
          <div>Reviewer</div>
          <div>Deadline</div>
          <div>SLA</div>
        </div>

        {sortedRows.length === 0 ? (
          <div className="px-5 py-12 text-center text-sm text-slate-500">
            No assignments match your filters.
          </div>
        ) : (
          sortedRows.map((row) => (
            <div
              key={row.id}
              className={`grid grid-cols-[32px_minmax(240px,2fr)_minmax(140px,1.2fr)_minmax(160px,1.3fr)_minmax(160px,1.3fr)_minmax(110px,1fr)_minmax(110px,0.9fr)] items-center border-b border-slate-100 px-5 py-2.5 text-sm transition-colors ${
                selected.has(row.id) ? "bg-cyan-50/50" : "hover:bg-slate-50"
              }`}
            >
              <input
                type="checkbox"
                checked={selected.has(row.id)}
                onChange={() => toggleRow(row.id)}
                className="h-4 w-4 rounded border-slate-300"
              />
              <div className="min-w-0 pr-3">
                <div className="truncate font-medium text-slate-900">
                  {row.shared_element_name || row.shared_element_code}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
                  <span className="rounded-sm bg-slate-100 px-1 py-0 text-[10px] font-medium text-slate-600">
                    {row.shared_element_code}
                  </span>
                  {row.facility_name && (
                    <span className="text-[10px]">· {row.facility_name}</span>
                  )}
                </div>
              </div>
              <div className="truncate pr-3 text-slate-700">
                {row.entity_name || <span className="text-slate-400">—</span>}
              </div>
              <div className="pr-2">
                <UserPicker
                  value={row.collector_id}
                  users={users}
                  placeholder="Assign collector"
                  tone={row.collector_id ? "default" : "warn"}
                  onChange={(uid) =>
                    inlineMutation.mutate({
                      id: row.id,
                      field: "collector_id",
                      value: uid ? String(uid) : "",
                    })
                  }
                />
              </div>
              <div className="pr-2">
                <UserPicker
                  value={row.reviewer_id}
                  users={users}
                  placeholder="Assign reviewer"
                  onChange={(uid) =>
                    inlineMutation.mutate({
                      id: row.id,
                      field: "reviewer_id",
                      value: uid ? String(uid) : "",
                    })
                  }
                />
              </div>
              <div>
                <DeadlineInput
                  value={row.deadline}
                  onChange={(val) =>
                    inlineMutation.mutate({
                      id: row.id,
                      field: "deadline",
                      value: val ?? "",
                    })
                  }
                />
              </div>
              <div>{slaChip(row)}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  tone,
  count,
  children,
}: {
  active: boolean;
  onClick: () => void;
  tone: "rose" | "amber" | "sky";
  count: number;
  children: React.ReactNode;
}) {
  const toneClasses =
    tone === "rose"
      ? active
        ? "border-rose-400 bg-rose-100 text-rose-900"
        : "border-rose-200 bg-rose-50 text-rose-800 hover:border-rose-300"
      : tone === "amber"
        ? active
          ? "border-amber-400 bg-amber-100 text-amber-900"
          : "border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-300"
        : active
          ? "border-sky-400 bg-sky-100 text-sky-900"
          : "border-sky-200 bg-sky-50 text-sky-800 hover:border-sky-300";
  const dotColor =
    tone === "rose"
      ? "bg-rose-500"
      : tone === "amber"
        ? "bg-amber-500"
        : "bg-sky-500";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${toneClasses}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`}></span>
      {children}
      <span className="rounded-full bg-white px-1.5 text-[11px]">{count}</span>
    </button>
  );
}

function EntityFilter({
  entities,
  value,
  onChange,
}: {
  entities: Entity[];
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const current = value ? entities.find((e) => e.id === value) : null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-slate-300">
          Entity: {current ? current.name : "All"}
          <ChevronDown className="h-3 w-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="max-h-72 w-56 overflow-y-auto">
        <DropdownMenuItem onClick={() => onChange(null)}>
          All entities
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {entities.map((entity) => (
          <DropdownMenuItem
            key={entity.id}
            onClick={() => onChange(entity.id)}
            className="flex items-center gap-2"
          >
            <span className="truncate">{entity.name}</span>
            {value === entity.id && (
              <Check
                className="ml-auto h-3.5 w-3.5 text-emerald-600"
                strokeWidth={3}
              />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function PersonFilter({
  users,
  value,
  onChange,
}: {
  users: User[];
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const current = value ? users.find((u) => u.id === value) : null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-slate-300">
          Person: {current ? current.name : "All"}
          <ChevronDown className="h-3 w-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="max-h-72 w-56 overflow-y-auto">
        <DropdownMenuItem onClick={() => onChange(null)}>
          All people
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {users.map((user) => (
          <DropdownMenuItem
            key={user.id}
            onClick={() => onChange(user.id)}
            className="flex items-center gap-2"
          >
            <span
              className={`flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-semibold ${avatarColor(
                user.id
              )}`}
            >
              {avatarInitials(user.name)}
            </span>
            <span className="truncate">{user.name}</span>
            {value === user.id && (
              <Check
                className="ml-auto h-3.5 w-3.5 text-emerald-600"
                strokeWidth={3}
              />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// Also export so settings page can show the "Launch" CTA from inside Standards tab
export { ClipboardList };
