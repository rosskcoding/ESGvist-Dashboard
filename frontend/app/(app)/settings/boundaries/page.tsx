"use client";

import { useEffect, useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { AIBoundaryWhy } from "@/components/ai-inline-explain";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Plus,
  Loader2,
  MapPin,
  Building2,
  Calendar,
  RefreshCw,
  History,
  Pencil,
  ShieldAlert,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BoundaryType =
  | "financial_reporting_default"
  | "operational_control"
  | "equity_share"
  | "custom";

type ConsolidationMethod = "full" | "proportional" | "equity_share";

interface Boundary {
  id: number;
  name: string;
  type?: BoundaryType;
  boundary_type?: BoundaryType;
  description: string;
  is_default: boolean;
  entity_count: number;
  created_at: string;
  updated_at: string;
}

interface Membership {
  id: number;
  entity_id: number;
  entity_name: string;
  entity_code?: string | null;
  entity_type: string;
  included: boolean;
  inclusion_source?: string | null;
  consolidation_method: ConsolidationMethod | null;
  inclusion_reason?: string | null;
  explicit: boolean;
}

interface Snapshot {
  id: number;
  boundary_id: number;
  snapshot_date: string;
  created_by: string;
  entity_count: number;
}

interface BoundaryMembershipResponse {
  boundary_id: number;
  boundary_name: string;
  memberships: Membership[];
}

interface CurrentUser {
  roles: Array<{
    role: string;
  }>;
}

const BOUNDARY_TYPE_OPTIONS = [
  { value: "financial_reporting_default", label: "Financial Reporting Default" },
  { value: "operational_control", label: "Operational Control" },
  { value: "equity_share", label: "Equity Share" },
  { value: "custom", label: "Custom" },
];

const CONSOLIDATION_OPTIONS = [
  { value: "full", label: "Full" },
  { value: "proportional", label: "Proportional" },
  { value: "equity_share", label: "Equity Share" },
];

const BOUNDARY_TYPE_VARIANT: Record<
  BoundaryType,
  "default" | "secondary" | "warning" | "success"
> = {
  financial_reporting_default: "default",
  operational_control: "success",
  equity_share: "warning",
  custom: "secondary",
};

function upsertBoundaryList(
  current: Boundary[] | undefined,
  nextBoundary: Boundary
): Boundary[] {
  const existing = current ?? [];
  const existingIndex = existing.findIndex((boundary) => boundary.id === nextBoundary.id);
  const nextList =
    existingIndex === -1
      ? [nextBoundary, ...existing]
      : existing.map((boundary, index) => (index === existingIndex ? nextBoundary : boundary));
  if (!nextBoundary.is_default) {
    return nextList;
  }
  return nextList.map((boundary) =>
    boundary.id === nextBoundary.id ? boundary : { ...boundary, is_default: false }
  );
}

function patchBoundaryCount(
  current: Boundary[] | undefined,
  boundaryId: number,
  entityCount: number
): Boundary[] | undefined {
  if (!current) return current;
  return current.map((boundary) =>
    boundary.id === boundaryId ? { ...boundary, entity_count: entityCount } : boundary
  );
}

// ---------------------------------------------------------------------------
// Add / Edit Boundary Dialog
// ---------------------------------------------------------------------------

function BoundaryDialog({
  open,
  onOpenChange,
  boundary,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  boundary: Boundary | null;
}) {
  const queryClient = useQueryClient();
  const isEdit = boundary !== null;

  const [form, setForm] = useState({
    name: boundary?.name ?? "",
    boundary_type:
      (boundary?.boundary_type ?? boundary?.type ?? "financial_reporting_default") as BoundaryType,
    description: boundary?.description ?? "",
    is_default: boundary?.is_default ?? false,
  });

  useEffect(() => {
    const syncBoundaryForm = () => {
      setForm({
        name: boundary?.name ?? "",
        boundary_type:
          (boundary?.boundary_type ?? boundary?.type ?? "financial_reporting_default") as BoundaryType,
        description: boundary?.description ?? "",
        is_default: boundary?.is_default ?? false,
      });
    };
    syncBoundaryForm();
  }, [boundary, open]);

  const createMutation = useApiMutation<Boundary, typeof form>(
    "/boundaries",
    "POST",
    {
      onSuccess: (createdBoundary) => {
        queryClient.setQueryData<Boundary[]>(
          ["boundaries"],
          (current) => upsertBoundaryList(current, createdBoundary)
        );
        onOpenChange(false);
      },
    }
  );

  const updateMutation = useApiMutation<Boundary, typeof form>(
    `/boundaries/${boundary?.id}`,
    "PATCH",
    {
      onSuccess: (updatedBoundary) => {
        queryClient.setQueryData<Boundary[]>(
          ["boundaries"],
          (current) => upsertBoundaryList(current, updatedBoundary)
        );
        onOpenChange(false);
      },
    }
  );

  const mutation = isEdit ? updateMutation : createMutation;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit Boundary" : "Add Boundary"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Modify the boundary definition."
              : "Define a new reporting boundary."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="bd-name">Name</Label>
            <Input
              id="bd-name"
              placeholder="Boundary name"
              value={form.name}
              onChange={(e) =>
                setForm((f) => ({ ...f, name: e.target.value }))
              }
            />
          </div>

          <Select
            label="Type"
            value={form.boundary_type}
            onChange={(v) =>
              setForm((f) => ({ ...f, boundary_type: v as BoundaryType }))
            }
            options={BOUNDARY_TYPE_OPTIONS}
          />

          <div className="grid gap-1.5">
            <Label htmlFor="bd-desc">Description</Label>
            <Textarea
              id="bd-desc"
              placeholder="Describe this boundary..."
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
              rows={3}
            />
          </div>

          <Switch
            checked={form.is_default}
            onCheckedChange={(checked) =>
              setForm((f) => ({ ...f, is_default: checked }))
            }
            label="Set as Default Boundary"
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate(form)}
            disabled={mutation.isPending || !form.name}
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {isEdit ? "Save Changes" : "Create Boundary"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Membership Toggle
// ---------------------------------------------------------------------------

function MembershipIncludedToggle({
  checked,
  onCheckedChange,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <Switch
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
    />
  );
}

// ---------------------------------------------------------------------------
// Membership Consolidation Method Select
// ---------------------------------------------------------------------------

function MembershipMethodSelect({
  value,
  onChange,
  disabled,
}: {
  value: ConsolidationMethod | null;
  onChange: (value: ConsolidationMethod) => void;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value ?? "full"}
      onChange={(v) => onChange(v as ConsolidationMethod)}
      options={CONSOLIDATION_OPTIONS}
      disabled={disabled}
    />
  );
}

// ---------------------------------------------------------------------------
// Boundary Detail Panel
// ---------------------------------------------------------------------------

function BoundaryDetail({ boundary }: { boundary: Boundary }) {
  const queryClient = useQueryClient();

  const { data: membershipData, isLoading: membershipsLoading } = useApiQuery<
    BoundaryMembershipResponse
  >(
    ["boundary-memberships", boundary.id],
    `/boundaries/${boundary.id}/memberships`
  );

  const calculateMutation = useApiMutation<void, void>(
    `/boundaries/${boundary.id}/recalculate`,
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["boundary-memberships", boundary.id],
        });
        queryClient.invalidateQueries({ queryKey: ["boundaries"] });
      },
    }
  );

  const replaceMembershipsMutation = useApiMutation<
    BoundaryMembershipResponse,
    { memberships: Array<{
      entity_id: number;
      included: boolean;
      inclusion_source: string;
      consolidation_method: ConsolidationMethod | null;
      inclusion_reason?: string | null;
    }> }
  >(`/boundaries/${boundary.id}/memberships`, "PUT", {
    onSuccess: (result) => {
      const includedCount = result.memberships.filter((membership) => membership.included).length;
      queryClient.setQueryData<BoundaryMembershipResponse>(
        ["boundary-memberships", boundary.id],
        result
      );
      queryClient.setQueryData<Boundary[]>(
        ["boundaries"],
        (current) => patchBoundaryCount(current, boundary.id, includedCount)
      );
    },
  });

  const memberships = membershipData?.memberships ?? [];
  const snapshots: Snapshot[] = [];
  const snapshotsLoading = false;

  const buildMembershipPayload = (
    membership: Membership,
    patch: Partial<Pick<Membership, "included" | "consolidation_method">>
  ) => ({
    entity_id: membership.entity_id,
    included: patch.included ?? membership.included,
    inclusion_source: membership.explicit
      ? membership.inclusion_source ?? "override"
      : "override",
    consolidation_method: patch.consolidation_method ?? membership.consolidation_method ?? "full",
    inclusion_reason: membership.inclusion_reason ?? null,
  });

  const handleMembershipChange = (
    entityId: number,
    patch: Partial<Pick<Membership, "included" | "consolidation_method">>
  ) => {
    replaceMembershipsMutation.mutate({
      memberships: memberships.map((membership) =>
        membership.entity_id === entityId
          ? buildMembershipPayload(membership, patch)
          : buildMembershipPayload(membership, {})
      ),
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <h3 className="text-lg font-semibold">{boundary.name}</h3>
          <Badge variant={BOUNDARY_TYPE_VARIANT[(boundary.boundary_type ?? boundary.type ?? "custom")]}>
            {(boundary.boundary_type ?? boundary.type ?? "custom").replace(/_/g, " ")}
          </Badge>
          {boundary.is_default && (
            <Badge variant="success">default</Badge>
          )}
        </div>
        {boundary.description && (
          <p className="text-sm text-slate-500">{boundary.description}</p>
        )}
      </div>

      <Separator />

      {/* Membership List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-medium">Entity Membership</h4>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              calculateMutation.mutate(undefined as unknown as void)
            }
            disabled={calculateMutation.isPending}
          >
            {calculateMutation.isPending ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
            )}
            Calculate Membership
          </Button>
        </div>

        {membershipsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : !memberships || memberships.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-slate-400">
            <Building2 className="mb-2 h-8 w-8" />
            <p className="text-sm">No entity memberships defined.</p>
            <p className="text-xs">
              Use &quot;Calculate Membership&quot; to auto-populate from rules.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Entity</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Included</TableHead>
                <TableHead>Consolidation Method</TableHead>
                <TableHead>Override</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {memberships.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{m.entity_name}</span>
                      <span className="font-mono text-xs text-slate-400">
                        {m.entity_code}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{m.entity_type}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <MembershipIncludedToggle
                        checked={m.included}
                        disabled={replaceMembershipsMutation.isPending}
                        onCheckedChange={(checked) =>
                          handleMembershipChange(m.entity_id, { included: checked })
                        }
                      />
                      <AIBoundaryWhy
                        entityId={m.entity_id}
                        included={m.included}
                      />
                    </div>
                  </TableCell>
                  <TableCell>
                    <MembershipMethodSelect
                      value={m.consolidation_method}
                      disabled={replaceMembershipsMutation.isPending}
                      onChange={(value) =>
                        handleMembershipChange(m.entity_id, { consolidation_method: value })
                      }
                    />
                  </TableCell>
                  <TableCell>
                    {m.explicit && m.inclusion_source === "override" ? (
                      <Badge variant="warning">override</Badge>
                    ) : (
                      <span className="text-sm text-slate-400">--</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      <Separator />

      {/* Snapshot History */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-slate-500" />
          <h4 className="font-medium">Snapshot History</h4>
        </div>

        {snapshotsLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
          </div>
        ) : !snapshots || snapshots.length === 0 ? (
          <p className="text-sm text-slate-400 py-4 text-center">
            No snapshots have been taken yet.
          </p>
        ) : (
          <div className="space-y-2">
            {snapshots.map((snap) => (
              <div
                key={snap.id}
                className="flex items-center justify-between rounded-md border border-slate-200 px-4 py-2.5 dark:border-slate-800"
              >
                <div className="flex items-center gap-3">
                  <Calendar className="h-4 w-4 text-slate-400" />
                  <div>
                    <span className="text-sm font-medium">
                      {new Date(snap.snapshot_date).toLocaleDateString(
                        undefined,
                        {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        }
                      )}
                    </span>
                    <span className="ml-2 text-xs text-slate-400">
                      by {snap.created_by}
                    </span>
                  </div>
                </div>
                <Badge variant="secondary">
                  {snap.entity_count} entities
                </Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default Switch per row
// ---------------------------------------------------------------------------

function DefaultSwitch({
  boundary,
}: {
  boundary: Boundary;
}) {
  const queryClient = useQueryClient();
  const toggleMutation = useApiMutation<Boundary, { is_default: boolean }>(
    `/boundaries/${boundary.id}`,
    "PATCH",
    {
      onSuccess: (updatedBoundary) => {
        queryClient.setQueryData<Boundary[]>(
          ["boundaries"],
          (current) => upsertBoundaryList(current, updatedBoundary)
        );
      },
    }
  );

  return (
    <Switch
      checked={boundary.is_default}
      onCheckedChange={(checked) =>
        toggleMutation.mutate({ is_default: checked })
      }
      disabled={toggleMutation.isPending}
    />
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function BoundariesPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editBoundary, setEditBoundary] = useState<Boundary | null>(null);

  const { data: currentUser } = useApiQuery<CurrentUser>(
    ["auth-me"],
    "/auth/me"
  );
  const { data: boundaries, isLoading } = useApiQuery<Boundary[]>(
    ["boundaries"],
    "/boundaries"
  );

  const currentRoles = currentUser?.roles?.map((entry) => entry.role) ?? [];
  const canManageBoundaries = currentRoles.some((role) =>
    ["admin", "platform_admin"].includes(role)
  );

  const selectedBoundary = useMemo(
    () => boundaries?.find((b) => b.id === selectedId) ?? null,
    [boundaries, selectedId]
  );

  function openAdd() {
    setEditBoundary(null);
    setDialogOpen(true);
  }

  function openEdit(b: Boundary) {
    setEditBoundary(b);
    setDialogOpen(true);
  }

  if (currentUser && !canManageBoundaries) {
    return (
      <div className="space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold">Boundaries</h1>
          <p className="mt-1 text-sm text-slate-500">
            Define and manage reporting boundaries
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Only admin roles can manage boundaries.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex h-full gap-6 p-6">
      {/* Left: Boundary List */}
      <div className="w-[480px] shrink-0 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Boundaries</h1>
          <Button onClick={openAdd}>
            <Plus className="mr-2 h-4 w-4" />
            Add Boundary
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        ) : !boundaries || boundaries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <MapPin className="mb-3 h-10 w-10" />
            <p className="font-medium">No boundaries defined</p>
            <p className="text-sm">
              Add your first boundary to define reporting scope.
            </p>
          </div>
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Default</TableHead>
                    <TableHead>Entities</TableHead>
                    <TableHead className="w-[60px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {boundaries.map((b) => (
                    <TableRow
                      key={b.id}
                      className={cn(
                        "cursor-pointer",
                        selectedId === b.id && "bg-slate-50 dark:bg-slate-800"
                      )}
                      onClick={() => setSelectedId(b.id)}
                    >
                      <TableCell className="font-medium">{b.name}</TableCell>
                      <TableCell>
                        <Badge variant={BOUNDARY_TYPE_VARIANT[(b.boundary_type ?? b.type ?? "custom")]}>
                          {(b.boundary_type ?? b.type ?? "custom").replace(/_/g, " ")}
                        </Badge>
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <DefaultSwitch boundary={b} />
                      </TableCell>
                      <TableCell className="text-center">
                        {b.entity_count ?? 0}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            openEdit(b);
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Right: Detail Panel */}
      <div className="flex-1 overflow-y-auto">
        {selectedBoundary ? (
          <Card>
            <CardContent className="p-6">
              <BoundaryDetail boundary={selectedBoundary} />
            </CardContent>
          </Card>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-slate-400">
            <MapPin className="mb-3 h-12 w-12" />
            <p className="text-lg font-medium">Select a boundary</p>
            <p className="text-sm">
              Click a boundary from the list to view its details and membership.
            </p>
          </div>
        )}
      </div>

      <BoundaryDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        boundary={editBoundary}
      />
    </div>
  );
}
