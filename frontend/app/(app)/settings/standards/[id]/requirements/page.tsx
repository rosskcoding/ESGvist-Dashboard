"use client";

import { useState, useMemo } from "react";
import { useParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
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
  Search,
  Plus,
  Pencil,
  Loader2,
  Filter,
  ClipboardList,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ItemType = "metric" | "attribute" | "narrative" | "document";
type ValueType = "number" | "text" | "boolean" | "date" | "enum";

interface RequirementItem {
  id: number;
  standard_id: number;
  code: string;
  name: string;
  description: string;
  item_type: ItemType;
  value_type: ValueType;
  unit: string;
  is_required: boolean;
  requires_evidence: boolean;
  validation_rules: string;
  granularity_rules: string;
  created_at: string;
  updated_at: string;
}

interface RequirementFormData {
  code: string;
  name: string;
  description: string;
  item_type: ItemType;
  value_type: ValueType;
  unit: string;
  is_required: boolean;
  requires_evidence: boolean;
  validation_rules: string;
  granularity_rules: string;
}

const EMPTY_FORM: RequirementFormData = {
  code: "",
  name: "",
  description: "",
  item_type: "metric",
  value_type: "number",
  unit: "",
  is_required: false,
  requires_evidence: false,
  validation_rules: "{}",
  granularity_rules: "{}",
};

const ITEM_TYPE_OPTIONS = [
  { value: "metric", label: "Metric" },
  { value: "attribute", label: "Attribute" },
  { value: "narrative", label: "Narrative" },
  { value: "document", label: "Document" },
];

const VALUE_TYPE_OPTIONS = [
  { value: "number", label: "Number" },
  { value: "text", label: "Text" },
  { value: "boolean", label: "Boolean" },
  { value: "date", label: "Date" },
  { value: "enum", label: "Enum" },
];

const ITEM_TYPE_VARIANT: Record<ItemType, "default" | "secondary" | "warning" | "success"> = {
  metric: "default",
  attribute: "secondary",
  narrative: "warning",
  document: "success",
};

// ---------------------------------------------------------------------------
// Edit / Add Dialog
// ---------------------------------------------------------------------------

function RequirementDialog({
  open,
  onOpenChange,
  standardId,
  item,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  standardId: string;
  item: RequirementItem | null;
}) {
  const queryClient = useQueryClient();
  const isEdit = item !== null;

  const [form, setForm] = useState<RequirementFormData>(
    item
      ? {
          code: item.code,
          name: item.name,
          description: item.description,
          item_type: item.item_type,
          value_type: item.value_type,
          unit: item.unit,
          is_required: item.is_required,
          requires_evidence: item.requires_evidence,
          validation_rules:
            typeof item.validation_rules === "string"
              ? item.validation_rules
              : JSON.stringify(item.validation_rules, null, 2),
          granularity_rules:
            typeof item.granularity_rules === "string"
              ? item.granularity_rules
              : JSON.stringify(item.granularity_rules, null, 2),
        }
      : { ...EMPTY_FORM }
  );

  const createMutation = useApiMutation<RequirementItem, RequirementFormData>(
    "/api/requirement-items",
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["requirement-items", standardId],
        });
        onOpenChange(false);
      },
    }
  );

  const updateMutation = useApiMutation<RequirementItem, RequirementFormData>(
    `/api/requirement-items/${item?.id}`,
    "PUT",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: ["requirement-items", standardId],
        });
        onOpenChange(false);
      },
    }
  );

  const mutation = isEdit ? updateMutation : createMutation;

  function handleSave() {
    const payload = {
      ...form,
      standard_id: Number(standardId),
    } as RequirementFormData & { standard_id: number };
    mutation.mutate(payload as unknown as RequirementFormData);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit Requirement Item" : "Add Requirement Item"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Modify the requirement item configuration."
              : "Define a new requirement item for this standard."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto pr-2">
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="ri-code">Code</Label>
              <Input
                id="ri-code"
                placeholder="e.g. E1-1.01"
                value={form.code}
                onChange={(e) =>
                  setForm((f) => ({ ...f, code: e.target.value }))
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ri-name">Name</Label>
              <Input
                id="ri-name"
                placeholder="Requirement name"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="ri-desc">Description</Label>
            <Textarea
              id="ri-desc"
              placeholder="Describe what this requirement captures..."
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
              rows={3}
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Select
              label="Item Type"
              value={form.item_type}
              onChange={(v) =>
                setForm((f) => ({ ...f, item_type: v as ItemType }))
              }
              options={ITEM_TYPE_OPTIONS}
            />
            <Select
              label="Value Type"
              value={form.value_type}
              onChange={(v) =>
                setForm((f) => ({ ...f, value_type: v as ValueType }))
              }
              options={VALUE_TYPE_OPTIONS}
            />
            <div className="grid gap-1.5">
              <Label htmlFor="ri-unit">Unit</Label>
              <Input
                id="ri-unit"
                placeholder="e.g. tCO2e, MWh"
                value={form.unit}
                onChange={(e) =>
                  setForm((f) => ({ ...f, unit: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="flex items-center gap-8">
            <Switch
              checked={form.is_required}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, is_required: checked }))
              }
              label="Required"
            />
            <Switch
              checked={form.requires_evidence}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, requires_evidence: checked }))
              }
              label="Requires Evidence"
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="ri-validation">Validation Rules (JSON)</Label>
            <Textarea
              id="ri-validation"
              className="font-mono text-xs"
              value={form.validation_rules}
              onChange={(e) =>
                setForm((f) => ({ ...f, validation_rules: e.target.value }))
              }
              rows={4}
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="ri-granularity">Granularity Rules (JSON)</Label>
            <Textarea
              id="ri-granularity"
              className="font-mono text-xs"
              value={form.granularity_rules}
              onChange={(e) =>
                setForm((f) => ({ ...f, granularity_rules: e.target.value }))
              }
              rows={4}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={mutation.isPending || !form.code || !form.name}
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {isEdit ? "Save Changes" : "Create Item"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function RequirementItemsPage() {
  const params = useParams();
  const standardId = params.id as string;

  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterRequired, setFilterRequired] = useState<string>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editItem, setEditItem] = useState<RequirementItem | null>(null);

  const { data: items, isLoading } = useApiQuery<RequirementItem[]>(
    ["requirement-items", standardId],
    `/api/requirement-items?standard_id=${standardId}`
  );

  const filtered = useMemo(() => {
    if (!items) return [];
    let result = items;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (i) =>
          i.code.toLowerCase().includes(q) ||
          i.name.toLowerCase().includes(q)
      );
    }
    if (filterType !== "all") {
      result = result.filter((i) => i.item_type === filterType);
    }
    if (filterRequired === "required") {
      result = result.filter((i) => i.is_required);
    } else if (filterRequired === "optional") {
      result = result.filter((i) => !i.is_required);
    }
    return result;
  }, [items, search, filterType, filterRequired]);

  function openEdit(item: RequirementItem) {
    setEditItem(item);
    setDialogOpen(true);
  }

  function openAdd() {
    setEditItem(null);
    setDialogOpen(true);
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Requirement Items</h1>
          <p className="text-sm text-slate-500">
            Configure requirement items for standard #{standardId}
          </p>
        </div>
        <Button onClick={openAdd}>
          <Plus className="mr-2 h-4 w-4" />
          Add Requirement Item
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="flex items-center gap-4 py-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              placeholder="Search by code or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select
            value={filterType}
            onChange={setFilterType}
            options={[
              { value: "all", label: "All Types" },
              ...ITEM_TYPE_OPTIONS,
            ]}
          />
          <Select
            value={filterRequired}
            onChange={setFilterRequired}
            options={[
              { value: "all", label: "All" },
              { value: "required", label: "Required" },
              { value: "optional", label: "Optional" },
            ]}
          />
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400">
              <ClipboardList className="mb-3 h-10 w-10" />
              <p className="font-medium">No requirement items found</p>
              <p className="text-sm">
                {items?.length
                  ? "Try adjusting your filters."
                  : "Add your first requirement item to get started."}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Value Type</TableHead>
                  <TableHead>Unit</TableHead>
                  <TableHead>Required</TableHead>
                  <TableHead>Evidence</TableHead>
                  <TableHead className="w-[60px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer"
                    onClick={() => openEdit(item)}
                  >
                    <TableCell className="font-mono text-xs font-semibold">
                      {item.code}
                    </TableCell>
                    <TableCell>{item.name}</TableCell>
                    <TableCell>
                      <Badge variant={ITEM_TYPE_VARIANT[item.item_type]}>
                        {item.item_type}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{item.value_type}</Badge>
                    </TableCell>
                    <TableCell className="text-slate-500">
                      {item.unit || "--"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={item.is_required ? "destructive" : "secondary"}
                      >
                        {item.is_required ? "required" : "optional"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {item.requires_evidence ? (
                        <Badge variant="warning">yes</Badge>
                      ) : (
                        <span className="text-sm text-slate-400">no</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          openEdit(item);
                        }}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <RequirementDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        standardId={standardId}
        item={editItem}
      />
    </div>
  );
}
