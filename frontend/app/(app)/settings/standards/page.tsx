"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArchiveX,
  BookOpen,
  FileText,
  Layers,
  Loader2,
  Pencil,
  Plus,
  ShieldAlert,
} from "lucide-react";

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
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

type Standard = {
  id: number;
  code: string;
  name: string;
  version: string | null;
  is_active: boolean;
  family_code: string;
  family_name: string;
  catalog_group_code: string;
  catalog_group_name: string;
  is_attachable: boolean;
};

type Section = {
  id: number;
  code: string | null;
  title: string;
  sort_order: number;
};

type Disclosure = {
  id: number;
  section_id: number | null;
  code: string;
  title: string;
  description?: string | null;
  requirement_type: "quantitative" | "qualitative" | "mixed";
  mandatory_level: "mandatory" | "conditional" | "optional";
  sort_order: number;
};

type StandardListResponse = { items: Standard[]; total: number };
type DisclosureListResponse = { items: Disclosure[]; total: number };

const familyDisplayPriority: Record<string, number> = {
  GRI: 0,
  SASB: 1,
  IFRS: 2,
  ESRS: 3,
};

const groupDisplayPriority: Record<string, number> = {
  universal: 0,
  topic: 1,
  sector: 2,
  family: 99,
};

function getStandardDisplayName(code: string, name: string) {
  const trimmedName = name.trim();
  if (!trimmedName || trimmedName === code) return code;
  if (trimmedName.startsWith(code)) {
    const remainder = trimmedName.slice(code.length).replace(/^[:\-\s]+/, "").trim();
    if (remainder) return remainder;
  }
  return trimmedName;
}

function AddStandardDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (standardId: number) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ code: "", name: "", version: "2026" });
  const mutation = useApiMutation<Standard, typeof form>("/standards", "POST", {
    onSuccess: (standard) => {
      queryClient.setQueryData<StandardListResponse>(["standards-admin"], (current) =>
        current
          ? {
              ...current,
              items: [standard, ...current.items.filter((item) => item.id !== standard.id)],
              total: current.total + (current.items.some((item) => item.id === standard.id) ? 0 : 1),
            }
          : { items: [standard], total: 1 }
      );
      onOpenChange(false);
      onCreated(standard.id);
      setForm({ code: "", name: "", version: "2026" });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Standard</DialogTitle>
          <DialogDescription>Create a reporting standard and open it for configuration.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="standard-code">Code</Label>
            <Input
              id="standard-code"
              value={form.code}
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
              placeholder="e.g. DEMO-ESG"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="standard-name">Name</Label>
            <Input
              id="standard-name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Demo ESG Standard"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="standard-version">Version</Label>
            <Input
              id="standard-version"
              value={form.version}
              onChange={(event) => setForm((current) => ({ ...current, version: event.target.value }))}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate(form)} disabled={mutation.isPending || !form.code || !form.name}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Standard
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EditStandardDialog({
  standard,
  open,
  onOpenChange,
}: {
  standard: Standard;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ name: standard.name, version: standard.version ?? "" });

  useEffect(() => {
    if (!open) return;
    setForm({ name: standard.name, version: standard.version ?? "" });
  }, [open, standard]);

  const mutation = useApiMutation<Standard, typeof form>(`/standards/${standard.id}`, "PATCH", {
    onSuccess: (updated) => {
      queryClient.setQueryData<StandardListResponse>(["standards-admin"], (current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) => (item.id === updated.id ? updated : item)),
            }
          : current
      );
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Standard</DialogTitle>
          <DialogDescription>Update the standard metadata without changing its code.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="standard-edit-code">Code</Label>
            <Input id="standard-edit-code" value={standard.code} disabled />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="standard-edit-name">Name</Label>
            <Input
              id="standard-edit-name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="standard-edit-version">Version</Label>
            <Input
              id="standard-edit-version"
              value={form.version}
              onChange={(event) => setForm((current) => ({ ...current, version: event.target.value }))}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              mutation.mutate({
                name: form.name,
                version: form.version,
              })
            }
            disabled={mutation.isPending || !form.name}
          >
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Standard
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AddSectionDialog({
  standardId,
  open,
  onOpenChange,
}: {
  standardId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ code: "", title: "", sort_order: 0 });
  const mutation = useApiMutation<Section, typeof form>(`/standards/${standardId}/sections`, "POST", {
    onSuccess: (section) => {
      queryClient.setQueryData<Section[]>(["standard-sections", standardId], (current) =>
        current ? [...current, section] : [section]
      );
      onOpenChange(false);
      setForm({ code: "", title: "", sort_order: 0 });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Section</DialogTitle>
          <DialogDescription>Create a section bucket for disclosures in this standard.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="section-code">Code</Label>
            <Input
              id="section-code"
              value={form.code}
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
              placeholder="e.g. GOV"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="section-title">Title</Label>
            <Input
              id="section-title"
              value={form.title}
              onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="Governance"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => mutation.mutate(form)} disabled={mutation.isPending || !form.title}>
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Section
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AddDisclosureDialog({
  standardId,
  sections,
  open,
  onOpenChange,
}: {
  standardId: number;
  sections: Section[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  type DisclosureCreatePayload = {
    section_id: number | null;
    code: string;
    title: string;
    description: string;
    requirement_type: "quantitative" | "qualitative" | "mixed";
    mandatory_level: "mandatory" | "conditional" | "optional";
    sort_order: number;
  };
  const [form, setForm] = useState({
    section_id: "",
    code: "",
    title: "",
    description: "",
    requirement_type: "quantitative",
    mandatory_level: "mandatory",
    sort_order: 0,
  });
  const mutation = useApiMutation<Disclosure, DisclosureCreatePayload>(`/standards/${standardId}/disclosures`, "POST", {
    onSuccess: (disclosure) => {
      queryClient.setQueryData<DisclosureListResponse>(
        ["standard-disclosures", standardId],
        (current) =>
          current
            ? {
                ...current,
                items: [...current.items, disclosure],
                total: current.total + 1,
              }
            : { items: [disclosure], total: 1 }
      );
      onOpenChange(false);
      setForm({
        section_id: "",
        code: "",
        title: "",
        description: "",
        requirement_type: "quantitative",
        mandatory_level: "mandatory",
        sort_order: 0,
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Disclosure</DialogTitle>
          <DialogDescription>Create a disclosure requirement under the selected standard.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <Select
            label="Section"
            value={form.section_id}
            onChange={(value) => setForm((current) => ({ ...current, section_id: value }))}
            options={[
              { value: "", label: "No section" },
              ...sections.map((section) => ({
                value: String(section.id),
                label: `${section.code ?? "SEC"} - ${section.title}`,
              })),
            ]}
          />
          <div className="grid gap-1.5">
            <Label htmlFor="disclosure-code">Code</Label>
            <Input
              id="disclosure-code"
              value={form.code}
              onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
              placeholder="e.g. GOV-1"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="disclosure-title">Title</Label>
            <Input
              id="disclosure-title"
              value={form.title}
              onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="Describe board oversight"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="disclosure-description">Description</Label>
            <Textarea
              id="disclosure-description"
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="Paste the disclosure requirement or reporting explanation"
              rows={6}
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="Requirement Type"
              value={form.requirement_type}
              onChange={(value) => setForm((current) => ({ ...current, requirement_type: value }))}
              options={[
                { value: "quantitative", label: "Quantitative" },
                { value: "qualitative", label: "Qualitative" },
                { value: "mixed", label: "Mixed" },
              ]}
            />
            <Select
              label="Mandatory Level"
              value={form.mandatory_level}
              onChange={(value) => setForm((current) => ({ ...current, mandatory_level: value }))}
              options={[
                { value: "mandatory", label: "Mandatory" },
                { value: "conditional", label: "Conditional" },
                { value: "optional", label: "Optional" },
              ]}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() =>
              mutation.mutate({
                ...form,
                section_id: form.section_id ? Number(form.section_id) : null,
                requirement_type: form.requirement_type as DisclosureCreatePayload["requirement_type"],
                mandatory_level: form.mandatory_level as DisclosureCreatePayload["mandatory_level"],
              })
            }
            disabled={mutation.isPending || !form.code || !form.title}
          >
            {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Disclosure
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function StandardsPage() {
  const pathname = usePathname();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [standardDialogOpen, setStandardDialogOpen] = useState(false);
  const [editStandardOpen, setEditStandardOpen] = useState(false);
  const [sectionDialogOpen, setSectionDialogOpen] = useState(false);
  const [disclosureDialogOpen, setDisclosureDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");

  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) => role === "framework_admin" || role === "platform_admin");
  const accessDenied = Boolean(me) && !canAccess;
  const basePath = pathname.startsWith("/platform/framework")
    ? "/platform/framework"
    : "/settings";

  const { data: standardsData, isLoading: standardsLoading } = useApiQuery<StandardListResponse>(
    ["standards-admin"],
    "/standards?page_size=500",
    { enabled: canAccess }
  );
  const standards = useMemo(
    () =>
      [...(standardsData?.items ?? [])].sort((left, right) => {
        const leftFamilyPriority = familyDisplayPriority[left.family_code] ?? 100;
        const rightFamilyPriority = familyDisplayPriority[right.family_code] ?? 100;
        if (leftFamilyPriority !== rightFamilyPriority) return leftFamilyPriority - rightFamilyPriority;

        const leftGroupPriority = groupDisplayPriority[left.catalog_group_code] ?? 100;
        const rightGroupPriority = groupDisplayPriority[right.catalog_group_code] ?? 100;
        if (leftGroupPriority !== rightGroupPriority) return leftGroupPriority - rightGroupPriority;

        return left.code.localeCompare(right.code);
      }),
    [standardsData]
  );

  useEffect(() => {
    if (!selectedId && standards.length > 0) {
      setSelectedId(standards[0].id);
    }
  }, [selectedId, standards]);

  const selectedStandard = useMemo(
    () => standards.find((standard) => standard.id === selectedId) ?? null,
    [selectedId, standards]
  );

  const deactivateStandard = useApiMutation<Standard, void>(
    selectedStandard ? `/standards/${selectedStandard.id}/deactivate` : "/standards/0/deactivate",
    "POST",
    {
      onSuccess: (updated) => {
        queryClient.setQueryData<StandardListResponse>(["standards-admin"], (current) =>
          current
            ? {
                ...current,
                items: current.items.map((item) => (item.id === updated.id ? updated : item)),
              }
            : current
        );
      },
    }
  );

  const { data: sections = [], isLoading: sectionsLoading } = useApiQuery<Section[]>(
    ["standard-sections", selectedId],
    selectedId ? `/standards/${selectedId}/sections` : "/standards/0/sections",
    { enabled: canAccess && Boolean(selectedId) }
  );

  const { data: disclosuresData, isLoading: disclosuresLoading } = useApiQuery<DisclosureListResponse>(
    ["standard-disclosures", selectedId],
    selectedId ? `/standards/${selectedId}/disclosures?page_size=100` : "/standards/0/disclosures",
    { enabled: canAccess && Boolean(selectedId) }
  );
  const disclosures = disclosuresData?.items ?? [];

  if (meLoading || (canAccess && standardsLoading)) {
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
          <h2 className="text-2xl font-bold text-slate-900">Standards Management</h2>
          <p className="mt-1 text-sm text-slate-500">
            Configure standards, disclosures, and requirement-item entry points.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only framework admin and platform admin roles can manage standards.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Standards Management</h2>
        <p className="mt-1 text-sm text-slate-500">Configure standards, disclosures, and requirement-item entry points.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>Standards</CardTitle>
          <Button size="sm" onClick={() => setStandardDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Standard
          </Button>
        </CardHeader>
        <CardContent className="space-y-2">
          {standards.length === 0 ? (
            <p className="text-sm text-slate-500">No standards configured yet.</p>
          ) : (
            standards.map((standard) => (
              <button
                key={standard.id}
                type="button"
                className={cn(
                  "w-full rounded-lg border px-3 py-3 text-left transition-colors",
                  selectedId === standard.id
                    ? "border-slate-900 bg-slate-50"
                    : "border-slate-200 hover:bg-slate-50"
                )}
                onClick={() => setSelectedId(standard.id)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-600">{standard.code}</span>
                  <Badge variant={standard.is_active ? "success" : "secondary"}>
                    {standard.is_active ? "active" : "inactive"}
                  </Badge>
                </div>
                <p className="mt-2 font-medium text-slate-900">
                  {getStandardDisplayName(standard.code, standard.name)}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge variant="outline">{standard.family_name}</Badge>
                  <Badge variant="outline">{standard.catalog_group_name}</Badge>
                  {!standard.is_attachable && <Badge variant="secondary">catalog family</Badge>}
                </div>
                <p className="mt-2 text-sm text-slate-500">Version {standard.version ?? "n/a"}</p>
              </button>
            ))
          )}
        </CardContent>
      </Card>

      <div className="space-y-6">
        {selectedStandard ? (
          <>
            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <BookOpen className="h-5 w-5 text-slate-500" />
                    {getStandardDisplayName(selectedStandard.code, selectedStandard.name)}
                  </CardTitle>
                  <p className="mt-1 text-sm text-slate-500">
                    {selectedStandard.code} • Version {selectedStandard.version ?? "n/a"}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge variant="outline">{selectedStandard.family_name}</Badge>
                    <Badge variant="outline">{selectedStandard.catalog_group_name}</Badge>
                    {!selectedStandard.is_attachable && <Badge variant="secondary">catalog family</Badge>}
                  </div>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <Button variant="outline" onClick={() => setEditStandardOpen(true)}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit Standard
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => deactivateStandard.mutate()}
                    disabled={deactivateStandard.isPending || !selectedStandard.is_active}
                  >
                    <ArchiveX className="mr-2 h-4 w-4" />
                    {selectedStandard.is_active ? "Deactivate Standard" : "Standard Inactive"}
                  </Button>
                  <Button variant="outline" asChild>
                    <Link href={`${basePath}/standards/${selectedStandard.id}/requirements`}>
                      Open Requirement Items
                    </Link>
                  </Button>
                </div>
              </CardHeader>
            </Card>

            <div className="grid gap-6 xl:grid-cols-2">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-5 w-5 text-slate-500" />
                    Sections
                  </CardTitle>
                  <Button size="sm" variant="outline" onClick={() => setSectionDialogOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Section
                  </Button>
                </CardHeader>
                <CardContent>
                  {sectionsLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                    </div>
                  ) : sections.length === 0 ? (
                    <p className="text-sm text-slate-500">No sections defined yet.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Code</TableHead>
                          <TableHead>Title</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {sections.map((section) => (
                          <TableRow key={section.id}>
                            <TableCell className="font-mono text-xs">{section.code ?? "-"}</TableCell>
                            <TableCell>{section.title}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-row items-center justify-between space-y-0">
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-slate-500" />
                    Disclosures
                  </CardTitle>
                  <Button size="sm" variant="outline" onClick={() => setDisclosureDialogOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Disclosure
                  </Button>
                </CardHeader>
                <CardContent>
                  {disclosuresLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                    </div>
                  ) : disclosures.length === 0 ? (
                    <p className="text-sm text-slate-500">No disclosures configured yet.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Code</TableHead>
                          <TableHead>Title</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Items</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {disclosures.map((disclosure) => (
                        <TableRow key={disclosure.id}>
                          <TableCell className="font-mono text-xs">{disclosure.code}</TableCell>
                          <TableCell>
                            <div className="space-y-1">
                              <div>{disclosure.title}</div>
                              {disclosure.description && (
                                <p className="line-clamp-3 text-xs text-slate-500">{disclosure.description}</p>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">{disclosure.requirement_type}</Badge>
                          </TableCell>
                            <TableCell>
                              <Button variant="ghost" size="sm" asChild>
                                <Link href={`${basePath}/standards/${selectedStandard.id}/requirements?disclosureId=${disclosure.id}`}>
                                  Manage Items
                                </Link>
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        ) : (
          <Card>
            <CardContent className="flex min-h-[300px] items-center justify-center text-slate-500">
              Select a standard to configure sections and disclosures.
            </CardContent>
          </Card>
        )}
      </div>
      </div>

      <AddStandardDialog
        open={standardDialogOpen}
        onOpenChange={setStandardDialogOpen}
        onCreated={(standardId) => setSelectedId(standardId)}
      />
      {selectedStandard && (
        <>
          <EditStandardDialog
            standard={selectedStandard}
            open={editStandardOpen}
            onOpenChange={setEditStandardOpen}
          />
          <AddSectionDialog
            standardId={selectedStandard.id}
            open={sectionDialogOpen}
            onOpenChange={setSectionDialogOpen}
          />
          <AddDisclosureDialog
            standardId={selectedStandard.id}
            sections={sections}
            open={disclosureDialogOpen}
            onOpenChange={setDisclosureDialogOpen}
          />
        </>
      )}
    </div>
  );
}
