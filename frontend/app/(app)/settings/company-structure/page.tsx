"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Search,
  Plus,
  Building2,
  ChevronRight,
  ChevronDown,
  Pencil,
  Save,
  X,
  Loader2,
  AlertTriangle,
  Link2,
  GitBranch,
  Eye,
  Network,
  CircleDot,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type EntityType =
  | "parent_company"
  | "legal_entity"
  | "branch"
  | "joint_venture"
  | "associate"
  | "facility"
  | "business_unit";

type EntityStatus = "active" | "inactive" | "disposed";

interface Entity {
  id: number;
  name: string;
  code: string;
  entity_type: EntityType;
  country: string;
  jurisdiction: string;
  status: EntityStatus;
  created_at: string;
  valid_from: string | null;
  valid_to: string | null;
  parent_id: number | null;
  ownership_percentage: number | null;
}

interface OwnershipLink {
  id: number;
  parent_entity_id: number;
  child_entity_id: number;
  ownership_percentage: number;
  ownership_type: string;
  parent_name?: string;
  child_name?: string;
}

interface ControlLink {
  id: number;
  controlling_entity_id: number;
  controlled_entity_id: number;
  control_type: string;
  controlling_name?: string;
  controlled_name?: string;
}

interface BoundaryMembership {
  boundary_id: number;
  boundary_name: string;
  included: boolean;
}

interface EntityTreeNode extends Entity {
  children: EntityTreeNode[];
}

interface EntitiesResponse {
  entities: Entity[];
  ownership_links: OwnershipLink[];
  control_links: ControlLink[];
  boundary_memberships: Record<number, BoundaryMembership[]>;
}

interface EntityTreeResponse {
  tree: EntityTreeNode[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ENTITY_TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All types" },
  { value: "parent_company", label: "Parent Company" },
  { value: "legal_entity", label: "Legal Entity" },
  { value: "branch", label: "Branch" },
  { value: "joint_venture", label: "Joint Venture" },
  { value: "associate", label: "Associate" },
  { value: "facility", label: "Facility" },
  { value: "business_unit", label: "Business Unit" },
];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "disposed", label: "Disposed" },
];

const ENTITY_TYPE_COLORS: Record<EntityType, string> = {
  parent_company: "bg-blue-100 text-blue-800",
  legal_entity: "bg-purple-100 text-purple-800",
  branch: "bg-cyan-100 text-cyan-800",
  joint_venture: "bg-amber-100 text-amber-800",
  associate: "bg-rose-100 text-rose-800",
  facility: "bg-green-100 text-green-800",
  business_unit: "bg-slate-100 text-slate-800",
};

const STATUS_COLORS: Record<EntityStatus, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-slate-100 text-slate-600",
  disposed: "bg-red-100 text-red-800",
};

type ViewMode = "structure" | "control" | "boundary";

// ---------------------------------------------------------------------------
// Custom Node
// ---------------------------------------------------------------------------

interface EntityNodeData {
  entity: Entity;
  viewMode: ViewMode;
  boundaryMemberships: BoundaryMembership[];
  isSelected: boolean;
  [key: string]: unknown;
}

function EntityNode({ data }: NodeProps<Node<EntityNodeData>>) {
  const { entity, viewMode, boundaryMemberships, isSelected } = data;

  let borderColor = "border-slate-200";
  let bgColor = "bg-white";

  if (viewMode === "boundary") {
    const included = boundaryMemberships.some((b) => b.included);
    const partial =
      boundaryMemberships.length > 0 &&
      boundaryMemberships.some((b) => b.included) &&
      boundaryMemberships.some((b) => !b.included);
    if (partial) {
      bgColor = "bg-yellow-50";
      borderColor = "border-yellow-400";
    } else if (included) {
      bgColor = "bg-green-50";
      borderColor = "border-green-400";
    } else {
      bgColor = "bg-slate-50";
      borderColor = "border-slate-300";
    }
  }

  if (isSelected) {
    borderColor = "border-blue-500 ring-2 ring-blue-200";
  }

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />
      <div
        className={cn(
          "rounded-lg border-2 px-4 py-3 shadow-sm min-w-[180px] max-w-[220px]",
          bgColor,
          borderColor
        )}
      >
        <div className="flex items-center gap-2 mb-1">
          <Building2 className="h-3.5 w-3.5 text-slate-500 shrink-0" />
          <span className="text-sm font-semibold text-slate-900 truncate">
            {entity.name}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-1 mt-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium",
              ENTITY_TYPE_COLORS[entity.entity_type]
            )}
          >
            {entity.entity_type.replace(/_/g, " ")}
          </span>
          {entity.country && (
            <span className="text-[10px] text-slate-500">{entity.country}</span>
          )}
        </div>
        {entity.ownership_percentage != null && (
          <div className="mt-1.5 text-[11px] text-slate-600">
            Ownership: {entity.ownership_percentage}%
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-slate-400"
      />
    </>
  );
}

const nodeTypes = { entity: EntityNode };

// ---------------------------------------------------------------------------
// Helpers — layout tree nodes for React Flow
// ---------------------------------------------------------------------------

const NODE_WIDTH = 200;
const NODE_HEIGHT = 100;
const H_GAP = 40;
const V_GAP = 80;

function layoutTree(
  treeNodes: EntityTreeNode[],
  allEntities: Entity[],
  viewMode: ViewMode,
  boundaryMemberships: Record<number, BoundaryMembership[]>,
  selectedId: number | null
): { nodes: Node<EntityNodeData>[]; edges: Edge[] } {
  const nodes: Node<EntityNodeData>[] = [];
  const edges: Edge[] = [];

  let xOffset = 0;

  function getSubtreeWidth(node: EntityTreeNode): number {
    if (node.children.length === 0) return NODE_WIDTH;
    const childrenWidth = node.children.reduce(
      (sum, c) => sum + getSubtreeWidth(c) + H_GAP,
      -H_GAP
    );
    return Math.max(NODE_WIDTH, childrenWidth);
  }

  function traverse(node: EntityTreeNode, x: number, y: number) {
    const entity =
      allEntities.find((e) => e.id === node.id) ?? (node as unknown as Entity);

    nodes.push({
      id: String(node.id),
      type: "entity",
      position: { x, y },
      data: {
        entity,
        viewMode,
        boundaryMemberships: boundaryMemberships[node.id] ?? [],
        isSelected: selectedId === node.id,
      },
    });

    if (node.children.length > 0) {
      const totalChildrenWidth =
        node.children.reduce((sum, c) => sum + getSubtreeWidth(c) + H_GAP, 0) -
        H_GAP;
      let childX = x + NODE_WIDTH / 2 - totalChildrenWidth / 2;

      for (const child of node.children) {
        const childWidth = getSubtreeWidth(child);
        const childCenterX = childX + childWidth / 2 - NODE_WIDTH / 2;

        edges.push({
          id: `e-${node.id}-${child.id}`,
          source: String(node.id),
          target: String(child.id),
          label:
            child.ownership_percentage != null
              ? `${child.ownership_percentage}%`
              : undefined,
          style: { stroke: "#94a3b8", strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
          type: "smoothstep",
        });

        traverse(child, childCenterX, y + NODE_HEIGHT + V_GAP);
        childX += childWidth + H_GAP;
      }
    }
  }

  for (const root of treeNodes) {
    const treeWidth = getSubtreeWidth(root);
    traverse(root, xOffset, 0);
    xOffset += treeWidth + H_GAP * 2;
  }

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Left Panel — Entity Tree
// ---------------------------------------------------------------------------

function EntityTreeItem({
  node,
  depth,
  selectedId,
  onSelect,
  searchTerm,
  typeFilter,
  statusFilter,
}: {
  node: EntityTreeNode;
  depth: number;
  selectedId: number | null;
  onSelect: (id: number) => void;
  searchTerm: string;
  typeFilter: string;
  statusFilter: string;
}) {
  const [expanded, setExpanded] = useState(true);

  const matchesSelf =
    (!searchTerm ||
      node.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      node.code.toLowerCase().includes(searchTerm.toLowerCase())) &&
    (!typeFilter || node.entity_type === typeFilter) &&
    (!statusFilter || node.status === statusFilter);

  const hasMatchingDescendant = (n: EntityTreeNode): boolean => {
    for (const child of n.children) {
      const childMatch =
        (!searchTerm ||
          child.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          child.code.toLowerCase().includes(searchTerm.toLowerCase())) &&
        (!typeFilter || child.entity_type === typeFilter) &&
        (!statusFilter || child.status === statusFilter);
      if (childMatch || hasMatchingDescendant(child)) return true;
    }
    return false;
  };

  if (!matchesSelf && !hasMatchingDescendant(node)) return null;

  return (
    <div>
      <button
        onClick={() => onSelect(node.id)}
        className={cn(
          "flex w-full items-center gap-1 rounded px-2 py-1.5 text-left text-sm hover:bg-slate-100 transition-colors",
          selectedId === node.id && "bg-blue-50 text-blue-700 font-medium"
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {node.children.length > 0 ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="shrink-0 p-0.5 hover:bg-slate-200 rounded"
          >
            {expanded ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>
        ) : (
          <span className="w-[18px]" />
        )}
        <Building2 className="h-3.5 w-3.5 text-slate-400 shrink-0" />
        <span className="truncate">{node.name}</span>
        <span
          className={cn(
            "ml-auto shrink-0 inline-flex items-center rounded px-1 py-0.5 text-[9px] font-medium",
            STATUS_COLORS[node.status]
          )}
        >
          {node.status}
        </span>
      </button>
      {expanded &&
        node.children.map((child) => (
          <EntityTreeItem
            key={child.id}
            node={child}
            depth={depth + 1}
            selectedId={selectedId}
            onSelect={onSelect}
            searchTerm={searchTerm}
            typeFilter={typeFilter}
            statusFilter={statusFilter}
          />
        ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add Entity Dialog
// ---------------------------------------------------------------------------

function AddEntityDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    code: "",
    entity_type: "legal_entity" as EntityType,
    country: "",
    jurisdiction: "",
    status: "active" as EntityStatus,
  });

  const mutation = useApiMutation<Entity, typeof form>(
    "/entities",
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["entities"] });
        queryClient.invalidateQueries({ queryKey: ["entities", "tree"] });
        onOpenChange(false);
        setForm({
          name: "",
          code: "",
          entity_type: "legal_entity",
          country: "",
          jurisdiction: "",
          status: "active",
        });
      },
    }
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Entity</DialogTitle>
          <DialogDescription>
            Create a new entity in the company structure.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="entity-name">Name</Label>
              <Input
                id="entity-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Entity name"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="entity-code">Code</Label>
              <Input
                id="entity-code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="ENT-001"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Type"
              options={ENTITY_TYPE_OPTIONS.filter((o) => o.value !== "")}
              value={form.entity_type}
              onChange={(v) => setForm({ ...form, entity_type: v as EntityType })}
            />
            <Select
              label="Status"
              options={STATUS_OPTIONS.filter((o) => o.value !== "")}
              value={form.status}
              onChange={(v) => setForm({ ...form, status: v as EntityStatus })}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="entity-country">Country</Label>
              <Input
                id="entity-country"
                value={form.country}
                onChange={(e) => setForm({ ...form, country: e.target.value })}
                placeholder="US"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="entity-jurisdiction">Jurisdiction</Label>
              <Input
                id="entity-jurisdiction"
                value={form.jurisdiction}
                onChange={(e) =>
                  setForm({ ...form, jurisdiction: e.target.value })
                }
                placeholder="Delaware"
              />
            </div>
          </div>
        </div>
        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate(form)}
            disabled={mutation.isPending || !form.name || !form.code}
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Entity
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Add Ownership Link Dialog
// ---------------------------------------------------------------------------

function AddOwnershipLinkDialog({
  open,
  onOpenChange,
  entities,
  selectedEntityId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  entities: Entity[];
  selectedEntityId: number | null;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    parent_entity_id: "",
    child_entity_id: selectedEntityId ? String(selectedEntityId) : "",
    ownership_percentage: "100",
    ownership_type: "direct",
  });

  useEffect(() => {
    if (selectedEntityId) {
      setForm((f) => ({ ...f, child_entity_id: String(selectedEntityId) }));
    }
  }, [selectedEntityId]);

  const mutation = useApiMutation<OwnershipLink, typeof form>(
    "/entities/ownership-links",
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["entities"] });
        queryClient.invalidateQueries({ queryKey: ["entities", "tree"] });
        onOpenChange(false);
      },
    }
  );

  const entityOptions = entities.map((e) => ({
    value: String(e.id),
    label: `${e.code} - ${e.name}`,
  }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Ownership Link</DialogTitle>
          <DialogDescription>
            Define an ownership relationship between two entities.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 space-y-4">
          <Select
            label="Parent Entity"
            options={entityOptions}
            value={form.parent_entity_id}
            onChange={(v) => setForm({ ...form, parent_entity_id: v })}
            placeholder="Select parent entity"
          />
          <Select
            label="Child Entity"
            options={entityOptions}
            value={form.child_entity_id}
            onChange={(v) => setForm({ ...form, child_entity_id: v })}
            placeholder="Select child entity"
          />
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="ownership-pct">Ownership %</Label>
              <Input
                id="ownership-pct"
                type="number"
                min="0"
                max="100"
                value={form.ownership_percentage}
                onChange={(e) =>
                  setForm({ ...form, ownership_percentage: e.target.value })
                }
              />
            </div>
            <Select
              label="Ownership Type"
              options={[
                { value: "direct", label: "Direct" },
                { value: "indirect", label: "Indirect" },
              ]}
              value={form.ownership_type}
              onChange={(v) => setForm({ ...form, ownership_type: v })}
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
              !form.parent_entity_id ||
              !form.child_entity_id
            }
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Add Link
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Add Control Link Dialog
// ---------------------------------------------------------------------------

function AddControlLinkDialog({
  open,
  onOpenChange,
  entities,
  selectedEntityId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  entities: Entity[];
  selectedEntityId: number | null;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    controlling_entity_id: "",
    controlled_entity_id: selectedEntityId ? String(selectedEntityId) : "",
    control_type: "operational",
  });

  useEffect(() => {
    if (selectedEntityId) {
      setForm((f) => ({
        ...f,
        controlled_entity_id: String(selectedEntityId),
      }));
    }
  }, [selectedEntityId]);

  const mutation = useApiMutation<ControlLink, typeof form>(
    "/entities/control-links",
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["entities"] });
        queryClient.invalidateQueries({ queryKey: ["entities", "tree"] });
        onOpenChange(false);
      },
    }
  );

  const entityOptions = entities.map((e) => ({
    value: String(e.id),
    label: `${e.code} - ${e.name}`,
  }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Control Link</DialogTitle>
          <DialogDescription>
            Define a control relationship between two entities.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 space-y-4">
          <Select
            label="Controlling Entity"
            options={entityOptions}
            value={form.controlling_entity_id}
            onChange={(v) => setForm({ ...form, controlling_entity_id: v })}
            placeholder="Select controlling entity"
          />
          <Select
            label="Controlled Entity"
            options={entityOptions}
            value={form.controlled_entity_id}
            onChange={(v) => setForm({ ...form, controlled_entity_id: v })}
            placeholder="Select controlled entity"
          />
          <Select
            label="Control Type"
            options={[
              { value: "operational", label: "Operational Control" },
              { value: "financial", label: "Financial Control" },
              { value: "joint", label: "Joint Control" },
              { value: "significant_influence", label: "Significant Influence" },
            ]}
            value={form.control_type}
            onChange={(v) => setForm({ ...form, control_type: v })}
          />
        </div>
        <DialogFooter className="mt-6">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate(form)}
            disabled={
              mutation.isPending ||
              !form.controlling_entity_id ||
              !form.controlled_entity_id
            }
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Add Link
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Right Panel — Entity Detail
// ---------------------------------------------------------------------------

function EntityDetailPanel({
  entity,
  ownershipLinks,
  controlLinks,
  boundaryMemberships,
  entities,
  onOwnershipAdd,
  onControlAdd,
}: {
  entity: Entity;
  ownershipLinks: OwnershipLink[];
  controlLinks: ControlLink[];
  boundaryMemberships: BoundaryMembership[];
  entities: Entity[];
  onOwnershipAdd: () => void;
  onControlAdd: () => void;
}) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ ...entity });

  const updateMutation = useApiMutation<Entity, Partial<Entity>>(
    `/entities/${entity.id}`,
    "PATCH",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["entities"] });
        queryClient.invalidateQueries({ queryKey: ["entities", "tree"] });
        setEditing(false);
      },
    }
  );

  useEffect(() => {
    setEditForm({ ...entity });
    setEditing(false);
  }, [entity]);

  const parentLinks = ownershipLinks.filter(
    (l) => l.child_entity_id === entity.id
  );
  const childLinks = ownershipLinks.filter(
    (l) => l.parent_entity_id === entity.id
  );

  const controllingLinks = controlLinks.filter(
    (l) => l.controlled_entity_id === entity.id
  );
  const controlledLinks = controlLinks.filter(
    (l) => l.controlling_entity_id === entity.id
  );

  const getEntityName = (id: number) => {
    const e = entities.find((en) => en.id === id);
    return e ? e.name : `Entity #${id}`;
  };

  // Calculate effective ownership from chain
  const effectiveOwnership = useMemo(() => {
    if (parentLinks.length === 0) return 100;
    // Simple: sum of direct ownership from parents
    // For chain: multiply up the chain
    const visited = new Set<number>();
    function calcChain(entityId: number): number {
      if (visited.has(entityId)) return 0;
      visited.add(entityId);
      const pLinks = ownershipLinks.filter(
        (l) => l.child_entity_id === entityId
      );
      if (pLinks.length === 0) return 100;
      let total = 0;
      for (const link of pLinks) {
        const parentPct = calcChain(link.parent_entity_id);
        total += (link.ownership_percentage / 100) * parentPct;
      }
      return total;
    }
    return Math.round(calcChain(entity.id) * 100) / 100;
  }, [entity.id, ownershipLinks, parentLinks.length]);

  return (
    <div className="space-y-4">
      {/* Entity Info */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Entity Details</CardTitle>
            {!editing ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setEditing(true)}
              >
                <Pencil className="h-3.5 w-3.5 mr-1" />
                Edit
              </Button>
            ) : (
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setEditing(false);
                    setEditForm({ ...entity });
                  }}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    updateMutation.mutate({
                      name: editForm.name,
                      code: editForm.code,
                      country: editForm.country,
                      jurisdiction: editForm.jurisdiction,
                      status: editForm.status,
                    })
                  }
                  disabled={updateMutation.isPending}
                >
                  <Save className="h-3.5 w-3.5 mr-1" />
                  Save
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {editing ? (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input
                  value={editForm.name}
                  onChange={(e) =>
                    setEditForm({ ...editForm, name: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label>Code</Label>
                <Input
                  value={editForm.code}
                  onChange={(e) =>
                    setEditForm({ ...editForm, code: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label>Country</Label>
                <Input
                  value={editForm.country}
                  onChange={(e) =>
                    setEditForm({ ...editForm, country: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label>Jurisdiction</Label>
                <Input
                  value={editForm.jurisdiction}
                  onChange={(e) =>
                    setEditForm({ ...editForm, jurisdiction: e.target.value })
                  }
                />
              </div>
              <Select
                label="Status"
                options={STATUS_OPTIONS.filter((o) => o.value !== "")}
                value={editForm.status}
                onChange={(v) =>
                  setEditForm({ ...editForm, status: v as EntityStatus })
                }
              />
            </div>
          ) : (
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Name</span>
                <span className="font-medium">{entity.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Code</span>
                <span className="font-mono text-xs">{entity.code}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Type</span>
                <Badge
                  className={cn(
                    "text-[10px]",
                    ENTITY_TYPE_COLORS[entity.entity_type]
                  )}
                >
                  {entity.entity_type.replace(/_/g, " ")}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Country</span>
                <span>{entity.country || "-"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Jurisdiction</span>
                <span>{entity.jurisdiction || "-"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Status</span>
                <Badge
                  className={cn("text-[10px]", STATUS_COLORS[entity.status])}
                >
                  {entity.status}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Effective Ownership</span>
                <span className="font-semibold text-blue-700">
                  {effectiveOwnership}%
                </span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ownership Links */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-1.5">
              <Link2 className="h-3.5 w-3.5" />
              Ownership Links
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={onOwnershipAdd}>
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {parentLinks.length === 0 && childLinks.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-2">
              No ownership links
            </p>
          ) : (
            <div className="space-y-2">
              {parentLinks.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between rounded bg-slate-50 px-2.5 py-1.5 text-xs"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Parent:</span>
                    <span className="font-medium">
                      {l.parent_name || getEntityName(l.parent_entity_id)}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    {l.ownership_percentage}%
                  </Badge>
                </div>
              ))}
              {childLinks.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between rounded bg-slate-50 px-2.5 py-1.5 text-xs"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Child:</span>
                    <span className="font-medium">
                      {l.child_name || getEntityName(l.child_entity_id)}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    {l.ownership_percentage}%
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Control Links */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-1.5">
              <GitBranch className="h-3.5 w-3.5" />
              Control Links
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={onControlAdd}>
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {controllingLinks.length === 0 && controlledLinks.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-2">
              No control links
            </p>
          ) : (
            <div className="space-y-2">
              {controllingLinks.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between rounded bg-slate-50 px-2.5 py-1.5 text-xs"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Controlled by:</span>
                    <span className="font-medium">
                      {l.controlling_name ||
                        getEntityName(l.controlling_entity_id)}
                    </span>
                  </div>
                  <Badge variant="secondary" className="text-[10px]">
                    {l.control_type.replace(/_/g, " ")}
                  </Badge>
                </div>
              ))}
              {controlledLinks.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between rounded bg-slate-50 px-2.5 py-1.5 text-xs"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">Controls:</span>
                    <span className="font-medium">
                      {l.controlled_name ||
                        getEntityName(l.controlled_entity_id)}
                    </span>
                  </div>
                  <Badge variant="secondary" className="text-[10px]">
                    {l.control_type.replace(/_/g, " ")}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Boundary Membership */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-1.5">
            <CircleDot className="h-3.5 w-3.5" />
            Boundary Membership
          </CardTitle>
        </CardHeader>
        <CardContent>
          {boundaryMemberships.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-2">
              No boundary memberships
            </p>
          ) : (
            <div className="space-y-2">
              {boundaryMemberships.map((bm) => (
                <div
                  key={bm.boundary_id}
                  className="flex items-center justify-between rounded bg-slate-50 px-2.5 py-1.5 text-xs"
                >
                  <span className="font-medium">{bm.boundary_name}</span>
                  <Badge
                    variant={bm.included ? "success" : "secondary"}
                    className="text-[10px]"
                  >
                    {bm.included ? "Included" : "Excluded"}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between">
              <span className="text-slate-500">Created</span>
              <span>
                {entity.created_at
                  ? new Date(entity.created_at).toLocaleDateString()
                  : "-"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Valid from</span>
              <span>
                {entity.valid_from
                  ? new Date(entity.valid_from).toLocaleDateString()
                  : "-"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Valid to</span>
              <span>
                {entity.valid_to
                  ? new Date(entity.valid_to).toLocaleDateString()
                  : "-"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CompanyStructurePage() {
  const [selectedEntityId, setSelectedEntityId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("structure");
  const [addEntityOpen, setAddEntityOpen] = useState(false);
  const [ownershipLinkOpen, setOwnershipLinkOpen] = useState(false);
  const [controlLinkOpen, setControlLinkOpen] = useState(false);

  // Fetch data
  const {
    data: entitiesData,
    isLoading: entitiesLoading,
    error: entitiesError,
  } = useApiQuery<EntitiesResponse>(["entities"], "/entities");

  const { data: treeData, isLoading: treeLoading } =
    useApiQuery<EntityTreeResponse>(["entities", "tree"], "/entities/tree");

  const entities = entitiesData?.entities ?? [];
  const ownershipLinks = entitiesData?.ownership_links ?? [];
  const controlLinks = entitiesData?.control_links ?? [];
  const boundaryMemberships = entitiesData?.boundary_memberships ?? {};
  const tree = treeData?.tree ?? [];

  // Build edges based on view mode
  const { flowNodes, flowEdges } = useMemo(() => {
    if (tree.length === 0) return { flowNodes: [], flowEdges: [] };

    const { nodes, edges } = layoutTree(
      tree,
      entities,
      viewMode,
      boundaryMemberships,
      selectedEntityId
    );

    // For control mode, replace edges with control links
    if (viewMode === "control") {
      const controlEdges: Edge[] = controlLinks.map((cl) => ({
        id: `ctrl-${cl.id}`,
        source: String(cl.controlling_entity_id),
        target: String(cl.controlled_entity_id),
        label: cl.control_type.replace(/_/g, " "),
        style: { stroke: "#f59e0b", strokeWidth: 2, strokeDasharray: "5 5" },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#f59e0b" },
        type: "smoothstep",
      }));
      return { flowNodes: nodes, flowEdges: controlEdges };
    }

    return { flowNodes: nodes, flowEdges: edges };
  }, [
    tree,
    entities,
    viewMode,
    boundaryMemberships,
    selectedEntityId,
    controlLinks,
  ]);

  const [nodes, , onNodesChange] = useNodesState(flowNodes);
  const [edges, , onEdgesChange] = useEdgesState(flowEdges);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedEntityId(Number(node.id));
    },
    []
  );

  const selectedEntity = useMemo(
    () => entities.find((e) => e.id === selectedEntityId) ?? null,
    [entities, selectedEntityId]
  );

  const isLoading = entitiesLoading || treeLoading;

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (entitiesError) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">
            Company Structure
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage your corporate entity hierarchy
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load entity data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">
          Company Structure
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage your corporate entity hierarchy, ownership, and control
          relationships
        </p>
      </div>

      {/* 3-panel layout */}
      <div className="flex gap-4 h-[calc(100vh-180px)]">
        {/* Left Panel — Entity Tree */}
        <div className="w-[250px] shrink-0 flex flex-col rounded-lg border border-slate-200 bg-white">
          <div className="p-3 space-y-2 border-b border-slate-100">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <Input
                placeholder="Search entities..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 h-8 text-xs"
              />
            </div>
            <Select
              options={ENTITY_TYPE_OPTIONS}
              value={typeFilter}
              onChange={setTypeFilter}
              className="h-8 text-xs"
            />
            <Select
              options={STATUS_OPTIONS}
              value={statusFilter}
              onChange={setStatusFilter}
              className="h-8 text-xs"
            />
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {tree.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">
                No entities found
              </p>
            ) : (
              tree.map((node) => (
                <EntityTreeItem
                  key={node.id}
                  node={node}
                  depth={0}
                  selectedId={selectedEntityId}
                  onSelect={setSelectedEntityId}
                  searchTerm={searchTerm}
                  typeFilter={typeFilter}
                  statusFilter={statusFilter}
                />
              ))
            )}
          </div>
          <div className="p-3 border-t border-slate-100">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setAddEntityOpen(true)}
            >
              <Plus className="h-3.5 w-3.5 mr-1" />
              Add Entity
            </Button>
          </div>
        </div>

        {/* Center Panel — React Flow Canvas */}
        <div className="flex-1 rounded-lg border border-slate-200 bg-white overflow-hidden flex flex-col">
          {/* View Mode Toggle */}
          <div className="flex items-center gap-2 p-3 border-b border-slate-100">
            <span className="text-xs font-medium text-slate-500 mr-1">
              View:
            </span>
            <Button
              variant={viewMode === "structure" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("structure")}
            >
              <Network className="h-3.5 w-3.5 mr-1" />
              Structure
            </Button>
            <Button
              variant={viewMode === "control" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("control")}
            >
              <GitBranch className="h-3.5 w-3.5 mr-1" />
              Control
            </Button>
            <Button
              variant={viewMode === "boundary" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("boundary")}
            >
              <Eye className="h-3.5 w-3.5 mr-1" />
              Boundary
            </Button>

            {viewMode === "boundary" && (
              <div className="ml-auto flex items-center gap-3 text-[10px]">
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2.5 w-2.5 rounded bg-green-400" />
                  Included
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2.5 w-2.5 rounded bg-yellow-400" />
                  Partial
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block h-2.5 w-2.5 rounded bg-slate-300" />
                  Excluded
                </span>
              </div>
            )}
          </div>
          <div className="flex-1">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onNodeClick={onNodeClick}
              nodeTypes={nodeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.1}
              maxZoom={2}
            >
              <Background gap={16} size={1} />
              <Controls position="bottom-left" />
              <MiniMap
                position="bottom-right"
                nodeStrokeWidth={3}
                pannable
                zoomable
                className="!bg-slate-50"
              />
            </ReactFlow>
          </div>
        </div>

        {/* Right Panel — Entity Detail */}
        <div className="w-[350px] shrink-0 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
          {selectedEntity ? (
            <EntityDetailPanel
              entity={selectedEntity}
              ownershipLinks={ownershipLinks}
              controlLinks={controlLinks}
              boundaryMemberships={boundaryMemberships[selectedEntity.id] ?? []}
              entities={entities}
              onOwnershipAdd={() => setOwnershipLinkOpen(true)}
              onControlAdd={() => setControlLinkOpen(true)}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Building2 className="h-12 w-12 text-slate-200 mb-3" />
              <p className="text-sm text-slate-400">
                Select an entity to view details
              </p>
              <p className="text-xs text-slate-300 mt-1">
                Click on a node in the graph or an item in the tree
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <AddEntityDialog open={addEntityOpen} onOpenChange={setAddEntityOpen} />
      <AddOwnershipLinkDialog
        open={ownershipLinkOpen}
        onOpenChange={setOwnershipLinkOpen}
        entities={entities}
        selectedEntityId={selectedEntityId}
      />
      <AddControlLinkDialog
        open={controlLinkOpen}
        onOpenChange={setControlLinkOpen}
        entities={entities}
        selectedEntityId={selectedEntityId}
      />
    </div>
  );
}
