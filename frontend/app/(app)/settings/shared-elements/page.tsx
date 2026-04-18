"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { Layers, Link2, Loader2, Plus, ShieldAlert } from "lucide-react";

import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Dimension = {
  id: number;
  shared_element_id: number;
  dimension_type: string;
  is_required: boolean;
};

type SharedElement = {
  id: number;
  code: string;
  name: string;
  concept_domain: string | null;
  default_value_type: string | null;
  default_unit_code: string | null;
  dimensions: Dimension[];
};

type SharedElementListResponse = {
  items: SharedElement[];
  total: number;
};

type CrossStandardElement = {
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  standards: string[];
  mapping_count: number;
};

type Standard = { id: number; code: string; name: string };
type StandardListResponse = { items: Standard[]; total: number };
type Disclosure = { id: number; code: string; title: string };
type DisclosureListResponse = { items: Disclosure[]; total: number };
type RequirementItem = { id: number; item_code: string | null; name: string };
type RequirementItemListResponse = { items: RequirementItem[]; total: number };

type RequirementItemOption = { value: string; label: string };

const DIMENSION_OPTIONS = [
  { value: "scope", label: "Scope" },
  { value: "category", label: "Category" },
  { value: "gas", label: "Gas" },
  { value: "geography", label: "Geography" },
  { value: "facility", label: "Facility" },
] as const;

function dimensionLabel(value: string) {
  return (
    DIMENSION_OPTIONS.find((option) => option.value === value)?.label ??
    value.replace(/_/g, " ")
  );
}

function AddSharedElementDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    code: "",
    name: "",
    concept_domain: "emissions",
    default_value_type: "number",
    default_unit_code: "",
  });
  const mutation = useApiMutation("/shared-elements", "POST", {
    onSuccess: (element) => {
      queryClient.setQueryData<SharedElementListResponse>(
        ["shared-elements-admin"],
        (current) =>
          current
            ? {
                ...current,
                items: [element as SharedElement, ...current.items.filter((item) => item.id !== (element as SharedElement).id)],
                total: current.total + (current.items.some((item) => item.id === (element as SharedElement).id) ? 0 : 1),
              }
            : { items: [element as SharedElement], total: 1 }
      );
      onOpenChange(false);
      setForm({
        code: "",
        name: "",
        concept_domain: "emissions",
        default_value_type: "number",
        default_unit_code: "",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Shared Element</DialogTitle>
          <DialogDescription>Create a reusable cross-standard data element.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="shared-element-code">Code</Label>
            <Input
              id="shared-element-code"
              value={form.code}
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
              placeholder="e.g. DEMO_SCOPE1"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="shared-element-name">Name</Label>
            <Input
              id="shared-element-name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Scope 1 Demonstration Metric"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Concept Domain"
              value={form.concept_domain}
              onChange={(value) => setForm((current) => ({ ...current, concept_domain: value }))}
              options={[
                { value: "emissions", label: "Emissions" },
                { value: "energy", label: "Energy" },
                { value: "water", label: "Water" },
                { value: "governance", label: "Governance" },
              ]}
            />
            <Select
              label="Default Value Type"
              value={form.default_value_type}
              onChange={(value) => setForm((current) => ({ ...current, default_value_type: value }))}
              options={[
                { value: "number", label: "Number" },
                { value: "text", label: "Text" },
                { value: "boolean", label: "Boolean" },
              ]}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="shared-element-unit">Default Unit</Label>
            <Input
              id="shared-element-unit"
              value={form.default_unit_code}
              onChange={(event) =>
                setForm((current) => ({ ...current, default_unit_code: event.target.value }))
              }
              placeholder="e.g. tCO2e"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate(form)} disabled={mutation.isPending || !form.code || !form.name}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Element
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LinkMappingDialog({
  sharedElementId,
  open,
  onOpenChange,
}: {
  sharedElementId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [options, setOptions] = useState<RequirementItemOption[]>([]);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [selectedItemId, setSelectedItemId] = useState("");
  const [mappingType, setMappingType] = useState("full");

  useEffect(() => {
    let cancelled = false;
    async function loadOptions() {
      if (!open) return;
      setLoadingOptions(true);
      try {
        const standards = await api.get<StandardListResponse>("/standards?page_size=500");
        const disclosureResults = await Promise.all(
          standards.items.map((standard) =>
            api.get<DisclosureListResponse>(`/standards/${standard.id}/disclosures?page_size=100`).then((result) => ({
              standard,
              disclosures: result.items,
            }))
          )
        );
        const itemsByDisclosure = await Promise.all(
          disclosureResults.flatMap(({ standard, disclosures }) =>
            disclosures.map((disclosure) =>
              api
                .get<RequirementItemListResponse>(`/disclosures/${disclosure.id}/items?page_size=100`)
                .then((result) => ({ standard, disclosure, items: result.items }))
            )
          )
        );
        if (!cancelled) {
          setOptions(
            itemsByDisclosure.flatMap(({ standard, disclosure, items }) =>
              items.map((item) => ({
                value: String(item.id),
                label: `${standard.code} / ${disclosure.code} / ${item.item_code ?? item.id} - ${item.name}`,
              }))
            )
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingOptions(false);
        }
      }
    }
    loadOptions();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const mutation = useApiMutation("/mappings", "POST", {
    onSuccess: () => {
      const selectedOption = options.find((option) => option.value === selectedItemId);
      const standardCode = selectedOption?.label.split(" / ")[0]?.trim();
      const elements = queryClient.getQueryData<SharedElementListResponse>(["shared-elements-admin"]);
      const sharedElement = elements?.items.find((item) => item.id === sharedElementId);
      if (!sharedElement || !standardCode) {
        queryClient.invalidateQueries({ queryKey: ["cross-standard-mappings"] });
      } else {
        queryClient.setQueryData<CrossStandardElement[]>(
          ["cross-standard-mappings"],
          (current) => {
            if (!current) {
              return [
                {
                  shared_element_id: sharedElement.id,
                  shared_element_code: sharedElement.code,
                  shared_element_name: sharedElement.name,
                  standards: [standardCode],
                  mapping_count: 1,
                },
              ];
            }
            const existingIndex = current.findIndex(
              (item) => item.shared_element_id === sharedElementId
            );
            if (existingIndex === -1) {
              return [
                {
                  shared_element_id: sharedElement.id,
                  shared_element_code: sharedElement.code,
                  shared_element_name: sharedElement.name,
                  standards: [standardCode],
                  mapping_count: 1,
                },
                ...current,
              ];
            }
            const existing = current[existingIndex];
            const standards = existing.standards.includes(standardCode)
              ? existing.standards
              : [...existing.standards, standardCode].sort();
            const next = [...current];
            next[existingIndex] = {
              ...existing,
              standards,
              mapping_count: existing.mapping_count + 1,
            };
            return next;
          }
        );
      }
      onOpenChange(false);
      setSelectedItemId("");
      setMappingType("full");
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link Requirement Item</DialogTitle>
          <DialogDescription>Bind the selected shared element to a requirement item.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          {loadingOptions ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading requirement items...
            </div>
          ) : (
            <Select
              label="Requirement Item"
              value={selectedItemId}
              onChange={setSelectedItemId}
              options={options}
              placeholder="Select requirement item"
            />
          )}
          <Select
            label="Mapping Type"
            value={mappingType}
            onChange={setMappingType}
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
              mutation.mutate({
                shared_element_id: sharedElementId,
                requirement_item_id: Number(selectedItemId),
                mapping_type: mappingType,
              })
            }
            disabled={mutation.isPending || !selectedItemId}
          >
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Link Mapping
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AddDimensionDialog({
  sharedElementId,
  open,
  onOpenChange,
}: {
  sharedElementId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [dimensionType, setDimensionType] = useState("scope");
  const [isRequired, setIsRequired] = useState(false);

  useEffect(() => {
    if (!open) {
      const resetDimensionDialog = () => {
        setDimensionType("scope");
        setIsRequired(false);
      };
      resetDimensionDialog();
    }
  }, [open]);

  const mutation = useApiMutation<Dimension, { dimension_type: string; is_required: boolean }>(
    `/shared-elements/${sharedElementId}/dimensions`,
    "POST",
    {
      onSuccess: (dimension) => {
        queryClient.setQueryData<SharedElementListResponse>(
          ["shared-elements-admin"],
          (current) => {
            if (!current) return current;
            return {
              ...current,
              items: current.items.map((item) => {
                if (item.id !== sharedElementId) return item;
                const exists = item.dimensions.some(
                  (entry) => entry.dimension_type === dimension.dimension_type
                );
                return {
                  ...item,
                  dimensions: exists
                    ? item.dimensions.map((entry) =>
                        entry.dimension_type === dimension.dimension_type
                          ? (dimension as Dimension)
                          : entry
                      )
                    : [...item.dimensions, dimension as Dimension],
                };
              }),
            };
          }
        );
        onOpenChange(false);
      },
    }
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Dimension</DialogTitle>
          <DialogDescription>
            Define an allowed reporting breakdown for the selected shared element.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <Select
            label="Dimension Type"
            value={dimensionType}
            onChange={setDimensionType}
            options={DIMENSION_OPTIONS.map((option) => ({
              value: option.value,
              label: option.label,
            }))}
          />
          <div className="rounded-lg border border-slate-200 p-4">
            <Switch
              checked={isRequired}
              onCheckedChange={setIsRequired}
              label="Required for data entry"
            />
            <p className="mt-2 text-xs text-slate-500">
              Required dimensions must be supplied before the data point can pass gate checks.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              mutation.mutate({
                dimension_type: dimensionType,
                is_required: isRequired,
              })
            }
            disabled={mutation.isPending}
          >
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Dimension
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function SharedElementsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [dimensionDialogOpen, setDimensionDialogOpen] = useState(false);
  const [linkElementId, setLinkElementId] = useState<number | null>(null);
  const [dimensionElementId, setDimensionElementId] = useState<number | null>(null);

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");

  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) => role === "framework_admin" || role === "platform_admin");
  const accessDenied = Boolean(me) && !canAccess;

  const { data: elementsData, isLoading: elementsLoading } = useApiQuery<SharedElementListResponse>(
    ["shared-elements-admin"],
    "/shared-elements?page_size=100",
    { enabled: canAccess }
  );
  const elements = elementsData?.items ?? [];

  const { data: mappings = [], isLoading: mappingsLoading } = useApiQuery<CrossStandardElement[]>(
    ["cross-standard-mappings"],
    "/mappings/cross-standard",
    { enabled: canAccess }
  );

  const mappedElementIds = useMemo(() => new Set(mappings.map((item) => item.shared_element_id)), [mappings]);

  if (meLoading || (canAccess && (elementsLoading || mappingsLoading))) {
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
          <h2 className="text-2xl font-bold text-slate-900">Shared Elements & Mappings</h2>
          <p className="mt-1 text-sm text-slate-500">Manage reusable data elements and bind them to requirement items.</p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only framework admin and platform admin roles can manage shared elements.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Shared Elements & Mappings</h2>
          <p className="mt-1 text-sm text-slate-500">Manage reusable data elements and bind them to requirement items.</p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Element
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-slate-500" />
            Shared Elements
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Domain</TableHead>
                <TableHead>Value Type</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead>Dimensions</TableHead>
                <TableHead>Mapped</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {elements.map((element) => (
                <TableRow key={element.id}>
                  <TableCell className="font-mono text-xs">{element.code}</TableCell>
                  <TableCell>{element.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{element.concept_domain ?? "general"}</Badge>
                  </TableCell>
                  <TableCell>{element.default_value_type ?? "-"}</TableCell>
                  <TableCell>{element.default_unit_code ?? "-"}</TableCell>
                  <TableCell>
                    {element.dimensions.length === 0 ? (
                      <span className="text-sm text-slate-400">None</span>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {element.dimensions.map((dimension) => (
                          <Badge
                            key={dimension.id}
                            variant={dimension.is_required ? "warning" : "outline"}
                          >
                            {dimensionLabel(dimension.dimension_type)}
                            {dimension.is_required ? " required" : ""}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </TableCell>
                  <TableCell>{mappedElementIds.has(element.id) ? "Yes" : "No"}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setDimensionElementId(element.id);
                          setDimensionDialogOpen(true);
                        }}
                      >
                        <Plus className="mr-2 h-4 w-4" />
                        Add Dimension
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setLinkElementId(element.id);
                          setLinkDialogOpen(true);
                        }}
                      >
                        <Link2 className="mr-2 h-4 w-4" />
                        Link Mapping
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Cross-Standard Mapping Coverage</CardTitle>
        </CardHeader>
        <CardContent>
          {mappings.length === 0 ? (
            <p className="text-sm text-slate-500">No mappings defined yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Shared Element</TableHead>
                  <TableHead>Standards</TableHead>
                  <TableHead>Mapping Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mappings.map((mapping) => (
                  <TableRow key={mapping.shared_element_id}>
                    <TableCell>
                      <div>
                        <p className="font-mono text-xs">{mapping.shared_element_code}</p>
                        <p className="text-sm text-slate-900">{mapping.shared_element_name}</p>
                      </div>
                    </TableCell>
                    <TableCell>{mapping.standards.join(", ") || "-"}</TableCell>
                    <TableCell>{mapping.mapping_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AddSharedElementDialog open={dialogOpen} onOpenChange={setDialogOpen} />
      {linkElementId && (
        <LinkMappingDialog
          sharedElementId={linkElementId}
          open={linkDialogOpen}
          onOpenChange={setLinkDialogOpen}
        />
      )}
      {dimensionElementId && (
        <AddDimensionDialog
          sharedElementId={dimensionElementId}
          open={dimensionDialogOpen}
          onOpenChange={setDimensionDialogOpen}
        />
      )}
    </div>
  );
}
