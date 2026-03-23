"use client";

import { useState, useMemo, useEffect } from "react";
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Search,
  Plus,
  ChevronRight,
  ChevronDown,
  Save,
  Loader2,
  BookOpen,
  FileText,
  ListTree,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Standard {
  id: number;
  code: string;
  name: string;
  version: string;
  status: "active" | "inactive";
  description: string;
  created_at: string;
  updated_at: string;
}

interface Section {
  id: number;
  standard_id: number;
  parent_id: number | null;
  code: string;
  name: string;
  order: number;
  children: Section[];
  disclosure_requirements: DisclosureRequirement[];
}

interface DisclosureRequirement {
  id: number;
  code: string;
  name: string;
  type: "quantitative" | "qualitative" | "mixed";
  is_mandatory: boolean;
  section_id: number;
  section_name?: string;
}

// ---------------------------------------------------------------------------
// Add Standard Dialog
// ---------------------------------------------------------------------------

function AddStandardDialog({
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
    version: "",
    description: "",
    status: "active" as "active" | "inactive",
  });

  const createMutation = useApiMutation<Standard, typeof form>(
    "/standards",
    "POST",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["standards"] });
        onOpenChange(false);
        setForm({ code: "", name: "", version: "", description: "", status: "active" });
      },
    }
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Standard</DialogTitle>
          <DialogDescription>
            Create a new reporting standard for your organization.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-1.5">
            <Label htmlFor="std-code">Code</Label>
            <Input
              id="std-code"
              placeholder="e.g. ESRS, GRI, IFRS-S"
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="std-name">Name</Label>
            <Input
              id="std-name"
              placeholder="Standard name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="std-version">Version</Label>
              <Input
                id="std-version"
                placeholder="e.g. 2024"
                value={form.version}
                onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
              />
            </div>
            <Select
              label="Status"
              value={form.status}
              onChange={(v) => setForm((f) => ({ ...f, status: v as "active" | "inactive" }))}
              options={[
                { value: "active", label: "Active" },
                { value: "inactive", label: "Inactive" },
              ]}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="std-desc">Description</Label>
            <Textarea
              id="std-desc"
              placeholder="Describe this standard..."
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            onClick={() => createMutation.mutate(form)}
            disabled={createMutation.isPending || !form.code || !form.name}
          >
            {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Create Standard
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Section Tree Node
// ---------------------------------------------------------------------------

function SectionNode({
  section,
  depth = 0,
}: {
  section: Section;
  depth?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasChildren = (section.children ?? []).length > 0;
  const hasDisclosures = (section.disclosure_requirements ?? []).length > 0;

  return (
    <div>
      <button
        type="button"
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800",
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={() => setExpanded(!expanded)}
      >
        {(hasChildren || hasDisclosures) ? (
          expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-500" />
          )
        ) : (
          <span className="h-4 w-4 shrink-0" />
        )}
        <span className="font-medium text-slate-600 dark:text-slate-400">
          {section.code}
        </span>
        <span className="truncate">{section.name}</span>
      </button>

      {expanded && hasDisclosures && (
        <div
          className="border-l border-slate-200 ml-4 dark:border-slate-700"
          style={{ marginLeft: `${depth * 20 + 24}px` }}
        >
          {(section.disclosure_requirements ?? []).map((dr) => (
            <div
              key={dr.id}
              className="flex items-center gap-2 px-3 py-1.5 text-sm"
            >
              <FileText className="h-3.5 w-3.5 text-slate-400" />
              <span className="font-mono text-xs text-slate-500">{dr.code}</span>
              <span className="truncate text-slate-700 dark:text-slate-300">
                {dr.name}
              </span>
              <Badge
                variant={
                  dr.type === "quantitative"
                    ? "default"
                    : dr.type === "qualitative"
                    ? "secondary"
                    : "warning"
                }
                className="ml-auto text-[10px]"
              >
                {dr.type}
              </Badge>
              <Badge
                variant={dr.is_mandatory ? "destructive" : "outline"}
                className="text-[10px]"
              >
                {dr.is_mandatory ? "mandatory" : "optional"}
              </Badge>
            </div>
          ))}
        </div>
      )}

      {expanded &&
        hasChildren &&
        (section.children ?? []).map((child) => (
          <SectionNode key={child.id} section={child} depth={depth + 1} />
        ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Details Tab
// ---------------------------------------------------------------------------

function DetailsTab({ standard }: { standard: Standard }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: standard.name,
    code: standard.code,
    version: standard.version,
    description: standard.description,
    status: standard.status,
  });

  const updateMutation = useApiMutation<Standard, typeof form>(
    `/api/standards/${standard.id}`,
    "PUT",
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["standards"] });
        queryClient.invalidateQueries({ queryKey: ["standard", standard.id] });
      },
    }
  );

  // Reset form when standard changes
  // Note: intentionally not adding setForm to deps to avoid loops
  useEffect(() => {
    setForm({
      name: standard.name,
      code: standard.code,
      version: standard.version,
      description: standard.description,
      status: standard.status,
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [standard.id]);

  return (
    <div className="space-y-4">
      <div className="grid gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="detail-name">Name</Label>
            <Input
              id="detail-name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="detail-code">Code</Label>
            <Input
              id="detail-code"
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="detail-version">Version</Label>
            <Input
              id="detail-version"
              value={form.version}
              onChange={(e) => setForm((f) => ({ ...f, version: e.target.value }))}
            />
          </div>
          <div className="pt-6">
            <Switch
              checked={form.status === "active"}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, status: checked ? "active" : "inactive" }))
              }
              label={form.status === "active" ? "Active" : "Inactive"}
            />
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="detail-desc">Description</Label>
          <Textarea
            id="detail-desc"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            rows={4}
          />
        </div>
      </div>
      <div className="flex justify-end">
        <Button
          onClick={() => updateMutation.mutate(form)}
          disabled={updateMutation.isPending}
        >
          {updateMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Changes
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections Tab
// ---------------------------------------------------------------------------

function SectionsTab({ standardId }: { standardId: number }) {
  const { data: sections, isLoading } = useApiQuery<Section[]>(
    ["standard-sections", standardId],
    `/api/standards/${standardId}/sections`
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!sections || sections.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-500">
        <ListTree className="mb-2 h-8 w-8" />
        <p className="text-sm">No sections defined for this standard.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500">
          {sections.length} top-level section{sections.length !== 1 && "s"}
        </p>
        <Button size="sm" variant="outline">
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add Section
        </Button>
      </div>
      <Card>
        <CardContent className="p-2">
          {sections.map((section) => (
            <SectionNode key={section.id} section={section} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Disclosures Tab
// ---------------------------------------------------------------------------

function DisclosuresTab({ standardId }: { standardId: number }) {
  const { data: sections, isLoading } = useApiQuery<Section[]>(
    ["standard-sections", standardId],
    `/api/standards/${standardId}/sections`
  );

  const disclosures = useMemo(() => {
    if (!sections) return [];
    const result: (DisclosureRequirement & { section_name: string })[] = [];
    function walk(secs: Section[]) {
      for (const sec of secs) {
        if (sec.disclosure_requirements) {
          for (const dr of sec.disclosure_requirements) {
            result.push({ ...dr, section_name: sec.name });
          }
        }
        if (sec.children) walk(sec.children);
      }
    }
    walk(sections);
    return result;
  }, [sections]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (disclosures.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-500">
        <FileText className="mb-2 h-8 w-8" />
        <p className="text-sm">No disclosure requirements found.</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Code</TableHead>
          <TableHead>Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Section</TableHead>
          <TableHead>Required</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {disclosures.map((dr) => (
          <TableRow key={dr.id}>
            <TableCell className="font-mono text-xs">{dr.code}</TableCell>
            <TableCell>{dr.name}</TableCell>
            <TableCell>
              <Badge
                variant={
                  dr.type === "quantitative"
                    ? "default"
                    : dr.type === "qualitative"
                    ? "secondary"
                    : "warning"
                }
              >
                {dr.type}
              </Badge>
            </TableCell>
            <TableCell className="text-slate-500">{dr.section_name}</TableCell>
            <TableCell>
              <Badge variant={dr.is_mandatory ? "destructive" : "outline"}>
                {dr.is_mandatory ? "mandatory" : "optional"}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function StandardsPage() {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [addOpen, setAddOpen] = useState(false);

  const { data: standards, isLoading } = useApiQuery<Standard[]>(
    ["standards"],
    "/standards"
  );

  const selectedStandard = useMemo(
    () => standards?.find((s) => s.id === selectedId) ?? null,
    [standards, selectedId]
  );

  const filtered = useMemo(() => {
    if (!standards) return [];
    if (!search) return standards;
    const q = search.toLowerCase();
    return standards.filter(
      (s) =>
        s.code.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q) ||
        s.version.toLowerCase().includes(q)
    );
  }, [standards, search]);

  return (
    <div className="flex h-full gap-6 p-6">
      {/* Left Panel */}
      <div className="flex w-[300px] shrink-0 flex-col gap-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Standards</h2>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <Plus className="mr-1 h-3.5 w-3.5" />
            Add Standard
          </Button>
        </div>

        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="Search standards..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <div className="flex-1 space-y-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
            </div>
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-500">
              No standards found.
            </p>
          ) : (
            filtered.map((std) => (
              <button
                key={std.id}
                type="button"
                className={cn(
                  "flex w-full flex-col gap-0.5 rounded-md border px-3 py-2 text-left transition-colors",
                  selectedId === std.id
                    ? "border-slate-900 bg-slate-50 dark:border-slate-100 dark:bg-slate-800"
                    : "border-transparent hover:bg-slate-100 dark:hover:bg-slate-800"
                )}
                onClick={() => setSelectedId(std.id)}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-semibold text-slate-600 dark:text-slate-300">
                    {std.code}
                  </span>
                  <Badge
                    variant={std.status === "active" ? "success" : "secondary"}
                    className="text-[10px]"
                  >
                    {std.status}
                  </Badge>
                </div>
                <span className="text-sm">{std.name}</span>
                <span className="text-xs text-slate-400">v{std.version}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 overflow-y-auto">
        {selectedStandard ? (
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <BookOpen className="h-5 w-5 text-slate-500" />
                <div>
                  <CardTitle>
                    {selectedStandard.name}{" "}
                    <span className="text-sm font-normal text-slate-500">
                      ({selectedStandard.code} v{selectedStandard.version})
                    </span>
                  </CardTitle>
                </div>
                <Badge
                  variant={
                    selectedStandard.status === "active" ? "success" : "secondary"
                  }
                  className="ml-auto"
                >
                  {selectedStandard.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="details">
                <TabsList>
                  <TabsTrigger value="details">Details</TabsTrigger>
                  <TabsTrigger value="sections">Sections</TabsTrigger>
                  <TabsTrigger value="disclosures">Disclosures</TabsTrigger>
                </TabsList>

                <TabsContent value="details" className="pt-4">
                  <DetailsTab standard={selectedStandard} />
                </TabsContent>

                <TabsContent value="sections" className="pt-4">
                  <SectionsTab standardId={selectedStandard.id} />
                </TabsContent>

                <TabsContent value="disclosures" className="pt-4">
                  <DisclosuresTab standardId={selectedStandard.id} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        ) : (
          <div className="flex h-full flex-col items-center justify-center text-slate-400">
            <BookOpen className="mb-3 h-12 w-12" />
            <p className="text-lg font-medium">Select a standard</p>
            <p className="text-sm">
              Choose a standard from the left panel to view its details.
            </p>
          </div>
        )}
      </div>

      <AddStandardDialog open={addOpen} onOpenChange={setAddOpen} />
    </div>
  );
}
