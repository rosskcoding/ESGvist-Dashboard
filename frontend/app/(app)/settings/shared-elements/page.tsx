"use client";

import { useState, useMemo } from "react";
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
  Trash2,
  Loader2,
  Link2,
  Layers,
  ArrowRight,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ConceptDomain =
  | "emissions"
  | "energy"
  | "water"
  | "waste"
  | "workforce"
  | "governance";

type BindingType = "full" | "partial" | "derived";

interface SharedElement {
  id: number;
  code: string;
  name: string;
  concept_domain: ConceptDomain;
  default_value_type: string;
  default_unit: string;
  description: string;
  standards_count: number;
  created_at: string;
  updated_at: string;
}

interface Mapping {
  id: number;
  shared_element_id: number;
  requirement_item_id: number;
  binding_type: BindingType;
  shared_element_code: string;
  shared_element_name: string;
  requirement_item_code: string;
  requirement_item_name: string;
  standard_name: string;
}

interface RequirementItemOption {
  id: number;
  code: string;
  name: string;
  standard_name: string;
}

const DOMAIN_OPTIONS = [
  { value: "emissions", label: "Emissions" },
  { value: "energy", label: "Energy" },
  { value: "water", label: "Water" },
  { value: "waste", label: "Waste" },
  { value: "workforce", label: "Workforce" },
  { value: "governance", label: "Governance" },
];

const DOMAIN_VARIANT: Record<ConceptDomain, "default" | "secondary" | "warning" | "success" | "destructive" | "outline"> = {
  emissions: "destructive",
  energy: "warning",
  water: "default",
  waste: "secondary",
  workforce: "success",
  governance: "outline",
};

const BINDING_VARIANT: Record<BindingType, "default" | "secondary" | "warning"> = {
  full: "success" as "default",
  partial: "warning",
  derived: "secondary",
};

// ---------------------------------------------------------------------------
// Shared Element Dialog
// ---------------------------------------------------------------------------

function ElementDialog({
  open,
  onOpenChange,
  element,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  element: SharedElement | null;
}) {
  const queryClient = useQueryClient();
  const isEdit = element !== null;

  const [form, setForm] = useState({
    code: element?.code ?? "",
    name: element?.name ?? "",
    concept_domain: element?.concept_domain ?? ("emissions" as ConceptDomain),
    default_value_type: element?.default_value_type ?? "number",
    default_unit: element?.default_unit ?? "",
    description: element?.description ?? "",
  });

  const createMutation = useApiMutation<SharedElement, typeof form>(
    "/shared-elements",
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["shared-elements"] });
        onOpenChange(false);
      },
    }
  );

  const updateMutation = useApiMutation<SharedElement, typeof form>(
    `/api/shared-elements/${element?.id}`,
    "PUT",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["shared-elements"] });
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
            {isEdit ? "Edit Shared Element" : "Add Shared Element"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Modify the shared data element configuration."
              : "Define a new shared data element that maps across standards."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="se-code">Code</Label>
              <Input
                id="se-code"
                placeholder="e.g. GHG_SCOPE1"
                value={form.code}
                onChange={(e) =>
                  setForm((f) => ({ ...f, code: e.target.value }))
                }
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="se-name">Name</Label>
              <Input
                id="se-name"
                placeholder="Element name"
                value={form.name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, name: e.target.value }))
                }
              />
            </div>
          </div>

          <Select
            label="Concept Domain"
            value={form.concept_domain}
            onChange={(v) =>
              setForm((f) => ({ ...f, concept_domain: v as ConceptDomain }))
            }
            options={DOMAIN_OPTIONS}
          />

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Default Value Type"
              value={form.default_value_type}
              onChange={(v) =>
                setForm((f) => ({ ...f, default_value_type: v }))
              }
              options={[
                { value: "number", label: "Number" },
                { value: "text", label: "Text" },
                { value: "boolean", label: "Boolean" },
                { value: "date", label: "Date" },
                { value: "enum", label: "Enum" },
              ]}
            />
            <div className="grid gap-1.5">
              <Label htmlFor="se-unit">Default Unit</Label>
              <Input
                id="se-unit"
                placeholder="e.g. tCO2e"
                value={form.default_unit}
                onChange={(e) =>
                  setForm((f) => ({ ...f, default_unit: e.target.value }))
                }
              />
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="se-desc">Description</Label>
            <Textarea
              id="se-desc"
              placeholder="Describe this shared element..."
              value={form.description}
              onChange={(e) =>
                setForm((f) => ({ ...f, description: e.target.value }))
              }
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate(form)}
            disabled={mutation.isPending || !form.code || !form.name}
          >
            {mutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            {isEdit ? "Save Changes" : "Create Element"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Link Requirement Dialog
// ---------------------------------------------------------------------------

function LinkRequirementDialog({
  open,
  onOpenChange,
  elementId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  elementId: number;
}) {
  const queryClient = useQueryClient();
  const [requirementItemId, setRequirementItemId] = useState("");
  const [bindingType, setBindingType] = useState<BindingType>("full");

  const { data: requirementItems } = useApiQuery<RequirementItemOption[]>(
    ["requirement-items-options"],
    "/requirement-items",
    { enabled: open }
  );

  const linkMutation = useApiMutation<
    Mapping,
    { shared_element_id: number; requirement_item_id: number; binding_type: BindingType }
  >("/mappings", "POST", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mappings"] });
      onOpenChange(false);
      setRequirementItemId("");
      setBindingType("full");
    },
  });

  const riOptions = useMemo(
    () =>
      (requirementItems ?? []).map((ri) => ({
        value: String(ri.id),
        label: `${ri.code} - ${ri.name} (${ri.standard_name})`,
      })),
    [requirementItems]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link Requirement Item</DialogTitle>
          <DialogDescription>
            Map a requirement item to this shared element.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <Select
            label="Requirement Item"
            value={requirementItemId}
            onChange={setRequirementItemId}
            options={riOptions}
            placeholder="Select a requirement item..."
          />
          <Select
            label="Binding Type"
            value={bindingType}
            onChange={(v) => setBindingType(v as BindingType)}
            options={[
              { value: "full", label: "Full" },
              { value: "partial", label: "Partial" },
              { value: "derived", label: "Derived" },
            ]}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              linkMutation.mutate({
                shared_element_id: elementId,
                requirement_item_id: Number(requirementItemId),
                binding_type: bindingType,
              })
            }
            disabled={linkMutation.isPending || !requirementItemId}
          >
            {linkMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Link Requirement
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Delete Element Button
// ---------------------------------------------------------------------------

function DeleteElementButton({ elementId }: { elementId: number }) {
  const queryClient = useQueryClient();
  const deleteMut = useApiMutation<void, void>(
    `/api/shared-elements/${elementId}`,
    "DELETE",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["shared-elements"] });
        queryClient.invalidateQueries({ queryKey: ["mappings"] });
      },
    }
  );

  return (
    <Button
      size="sm"
      variant="ghost"
      className="text-red-500 hover:text-red-700"
      onClick={() => {
        if (confirm("Delete this shared element?")) {
          deleteMut.mutate(undefined as unknown as void);
        }
      }}
      disabled={deleteMut.isPending}
      title="Delete"
    >
      {deleteMut.isPending ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Trash2 className="h-3.5 w-3.5" />
      )}
    </Button>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function SharedElementsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [filterDomain, setFilterDomain] = useState("all");
  const [elementDialogOpen, setElementDialogOpen] = useState(false);
  const [editElement, setEditElement] = useState<SharedElement | null>(null);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [linkElementId, setLinkElementId] = useState<number>(0);

  const { data: elements, isLoading: elementsLoading } = useApiQuery<
    SharedElement[]
  >(["shared-elements"], "/shared-elements");

  const { data: mappings, isLoading: mappingsLoading } = useApiQuery<Mapping[]>(
    ["mappings"],
    "/mappings"
  );

  const filteredElements = useMemo(() => {
    if (!elements) return [];
    let result = elements;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (e) =>
          e.code.toLowerCase().includes(q) ||
          e.name.toLowerCase().includes(q)
      );
    }
    if (filterDomain !== "all") {
      result = result.filter((e) => e.concept_domain === filterDomain);
    }
    return result;
  }, [elements, search, filterDomain]);

  // Group mappings by shared element
  const mappingsByElement = useMemo(() => {
    const map = new Map<number, Mapping[]>();
    const mappingList = Array.isArray(mappings) ? mappings : (mappings as any)?.items ?? [];
    if (mappingList.length > 0) {
      for (const m of mappingList) {
        const arr = map.get(m.shared_element_id) ?? [];
        arr.push(m);
        map.set(m.shared_element_id, arr);
      }
    }
    return map;
  }, [mappings]);

  function openEdit(el: SharedElement) {
    setEditElement(el);
    setElementDialogOpen(true);
  }

  function openAdd() {
    setEditElement(null);
    setElementDialogOpen(true);
  }

  function openLink(elementId: number) {
    setLinkElementId(elementId);
    setLinkDialogOpen(true);
  }

  return (
    <div className="space-y-8 p-6">
      <h1 className="text-2xl font-semibold">Shared Elements & Mappings</h1>

      {/* ------------------------------------------------------------------ */}
      {/* Shared Elements Section                                            */}
      {/* ------------------------------------------------------------------ */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Shared Elements</h2>
          <Button onClick={openAdd}>
            <Plus className="mr-2 h-4 w-4" />
            Add Element
          </Button>
        </div>

        <Card>
          <CardContent className="py-3">
            <div className="flex items-center gap-4 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Search elements..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select
                value={filterDomain}
                onChange={setFilterDomain}
                options={[
                  { value: "all", label: "All Domains" },
                  ...DOMAIN_OPTIONS,
                ]}
              />
            </div>

            {elementsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
              </div>
            ) : filteredElements.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                <Layers className="mb-3 h-10 w-10" />
                <p className="font-medium">No shared elements found</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Domain</TableHead>
                    <TableHead>Default Value Type</TableHead>
                    <TableHead>Default Unit</TableHead>
                    <TableHead>Standards Count</TableHead>
                    <TableHead className="w-[120px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredElements.map((el) => (
                    <TableRow key={el.id}>
                      <TableCell className="font-mono text-xs font-semibold">
                        {el.code}
                      </TableCell>
                      <TableCell>{el.name}</TableCell>
                      <TableCell>
                        <Badge variant={DOMAIN_VARIANT[el.concept_domain]}>
                          {el.concept_domain}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{el.default_value_type}</Badge>
                      </TableCell>
                      <TableCell className="text-slate-500">
                        {el.default_unit || "--"}
                      </TableCell>
                      <TableCell className="text-center">
                        {el.standards_count ?? 0}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => openEdit(el)}
                            title="Edit"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => openLink(el.id)}
                            title="Link Requirement"
                          >
                            <Link2 className="h-3.5 w-3.5" />
                          </Button>
                          <DeleteElementButton
                            elementId={el.id}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Mappings Section                                                   */}
      {/* ------------------------------------------------------------------ */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Mappings</h2>

        <Card>
          <CardContent className="py-3">
            {mappingsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
              </div>
            ) : !mappings || mappings.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                <Link2 className="mb-3 h-10 w-10" />
                <p className="font-medium">No mappings defined</p>
                <p className="text-sm">
                  Link requirement items to shared elements above.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Shared Element</TableHead>
                    <TableHead className="w-[40px]" />
                    <TableHead>Requirement Item</TableHead>
                    <TableHead>Standard</TableHead>
                    <TableHead>Binding Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mappings.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-mono text-xs font-semibold">
                            {m.shared_element_code}
                          </span>
                          <span className="text-sm text-slate-500">
                            {m.shared_element_name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <ArrowRight className="h-4 w-4 text-slate-400" />
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-mono text-xs font-semibold">
                            {m.requirement_item_code}
                          </span>
                          <span className="text-sm text-slate-500">
                            {m.requirement_item_name}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{m.standard_name}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            m.binding_type === "full"
                              ? "success"
                              : m.binding_type === "partial"
                              ? "warning"
                              : "secondary"
                          }
                        >
                          {m.binding_type}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Dialogs */}
      <ElementDialog
        open={elementDialogOpen}
        onOpenChange={setElementDialogOpen}
        element={editElement}
      />
      <LinkRequirementDialog
        open={linkDialogOpen}
        onOpenChange={setLinkDialogOpen}
        elementId={linkElementId}
      />
    </div>
  );
}
