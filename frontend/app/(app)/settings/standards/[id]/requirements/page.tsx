"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileText, Loader2, Plus, ShieldAlert } from "lucide-react";

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Standard = {
  id: number;
  code: string;
  name: string;
  version: string | null;
};

type Disclosure = {
  id: number;
  code: string;
  title: string;
  requirement_type: string;
};

type DisclosureListResponse = { items: Disclosure[]; total: number };

type RequirementItem = {
  id: number;
  item_code: string | null;
  name: string;
  item_type: string;
  value_type: string;
  unit_code: string | null;
  is_required: boolean;
  requires_evidence: boolean;
};

type RequirementItemListResponse = { items: RequirementItem[]; total: number };

function AddRequirementItemDialog({
  disclosureId,
  open,
  onOpenChange,
}: {
  disclosureId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    item_code: "",
    name: "",
    item_type: "metric",
    value_type: "number",
    unit_code: "",
    is_required: true,
    requires_evidence: false,
  });

  const mutation = useApiMutation(`/disclosures/${disclosureId}/items`, "POST", {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requirement-items", disclosureId] });
      onOpenChange(false);
      setForm({
        item_code: "",
        name: "",
        item_type: "metric",
        value_type: "number",
        unit_code: "",
        is_required: true,
        requires_evidence: false,
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Requirement Item</DialogTitle>
          <DialogDescription>Create a metric or narrative item inside the selected disclosure.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="item-code">Item Code</Label>
            <Input
              id="item-code"
              value={form.item_code}
              onChange={(event) => setForm((current) => ({ ...current, item_code: event.target.value }))}
              placeholder="e.g. ITEM-1"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="item-name">Name</Label>
            <Input
              id="item-name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Describe the requirement item"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Item Type"
              value={form.item_type}
              onChange={(value) => setForm((current) => ({ ...current, item_type: value }))}
              options={[
                { value: "metric", label: "Metric" },
                { value: "attribute", label: "Attribute" },
                { value: "narrative", label: "Narrative" },
                { value: "document", label: "Document" },
              ]}
            />
            <Select
              label="Value Type"
              value={form.value_type}
              onChange={(value) => setForm((current) => ({ ...current, value_type: value }))}
              options={[
                { value: "number", label: "Number" },
                { value: "text", label: "Text" },
                { value: "boolean", label: "Boolean" },
                { value: "date", label: "Date" },
              ]}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="item-unit">Unit Code</Label>
            <Input
              id="item-unit"
              value={form.unit_code}
              onChange={(event) => setForm((current) => ({ ...current, unit_code: event.target.value }))}
              placeholder="e.g. tCO2e"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate(form)} disabled={mutation.isPending || !form.name}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Item
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function RequirementItemsPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const standardId = Number(params.id);
  const initialDisclosureId = searchParams.get("disclosureId");
  const [selectedDisclosureId, setSelectedDisclosureId] = useState<number | null>(
    initialDisclosureId ? Number(initialDisclosureId) : null
  );
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me", "requirement-items"], "/auth/me");

  const role = me?.roles?.[0]?.role ?? "";
  const canAccess = role === "admin" || role === "platform_admin";
  const accessDenied = Boolean(role) && !canAccess;

  const { data: standard, isLoading: standardLoading } = useApiQuery<Standard>(
    ["standard", standardId],
    `/standards/${standardId}`,
    { enabled: canAccess && Boolean(standardId) }
  );

  const { data: disclosuresData, isLoading: disclosuresLoading } = useApiQuery<DisclosureListResponse>(
    ["standard-disclosures", standardId, "requirements"],
    `/standards/${standardId}/disclosures?page_size=100`,
    { enabled: canAccess && Boolean(standardId) }
  );
  const disclosures = disclosuresData?.items ?? [];

  useEffect(() => {
    if (!selectedDisclosureId && disclosures.length > 0) {
      setSelectedDisclosureId(disclosures[0].id);
    }
  }, [selectedDisclosureId, disclosures]);

  const selectedDisclosure = useMemo(
    () => disclosures.find((disclosure) => disclosure.id === selectedDisclosureId) ?? null,
    [disclosures, selectedDisclosureId]
  );

  const { data: itemsData, isLoading: itemsLoading } = useApiQuery<RequirementItemListResponse>(
    ["requirement-items", selectedDisclosureId],
    selectedDisclosureId ? `/disclosures/${selectedDisclosureId}/items?page_size=100` : "/disclosures/0/items",
    { enabled: canAccess && Boolean(selectedDisclosureId) }
  );
  const items = itemsData?.items ?? [];

  if (meLoading || (canAccess && (standardLoading || disclosuresLoading))) {
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
          <h2 className="text-2xl font-bold text-slate-900">Requirement Items</h2>
          <p className="mt-1 text-sm text-slate-500">Configure item-level metrics and narratives inside a disclosure.</p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only admin and platform admin roles can configure requirement items.</p>
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
          <h2 className="text-2xl font-bold text-slate-900">Requirement Items</h2>
          <p className="mt-1 text-sm text-slate-500">
            {standard ? `${standard.name} (${standard.code})` : "Configure requirement items for this standard."}
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/settings/standards">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to standards
          </Link>
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Disclosures</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {disclosures.map((disclosure) => (
              <button
                key={disclosure.id}
                type="button"
                className={
                  selectedDisclosureId === disclosure.id
                    ? "w-full rounded-lg border border-slate-900 bg-slate-50 px-3 py-3 text-left"
                    : "w-full rounded-lg border border-slate-200 px-3 py-3 text-left hover:bg-slate-50"
                }
                onClick={() => setSelectedDisclosureId(disclosure.id)}
              >
                <p className="font-mono text-xs font-semibold text-slate-600">{disclosure.code}</p>
                <p className="mt-1 font-medium text-slate-900">{disclosure.title}</p>
                <Badge variant="secondary" className="mt-2">
                  {disclosure.requirement_type}
                </Badge>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-slate-500" />
                {selectedDisclosure?.title ?? "Requirement Items"}
              </CardTitle>
              {selectedDisclosure && (
                <p className="mt-1 text-sm text-slate-500">{selectedDisclosure.code}</p>
              )}
            </div>
            {selectedDisclosure && (
              <Button size="sm" onClick={() => setDialogOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Item
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {itemsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              </div>
            ) : items.length === 0 ? (
              <p className="text-sm text-slate-500">No requirement items yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Item Type</TableHead>
                    <TableHead>Value Type</TableHead>
                    <TableHead>Evidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-mono text-xs">{item.item_code ?? "-"}</TableCell>
                      <TableCell>{item.name}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{item.item_type}</Badge>
                      </TableCell>
                      <TableCell>{item.value_type}</TableCell>
                      <TableCell>{item.requires_evidence ? "Required" : "Optional"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {selectedDisclosure && (
        <AddRequirementItemDialog
          disclosureId={selectedDisclosure.id}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      )}
    </div>
  );
}
