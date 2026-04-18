"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, type SelectOptionItem } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  Plus,
  Shield,
  Globe,
  Users,
  Lock,
  FileText,
  Camera,
  ShieldAlert,
} from "lucide-react";
import { StandardLaunchDialog } from "@/components/projects/standard-launch-dialog";
import { WorkflowStrip } from "@/components/projects/workflow-strip";
import { TeamMatrix } from "@/components/projects/team-matrix";
import { CustomDatasheetBuilder } from "@/components/projects/custom-datasheet-builder";

interface ProjectDetail {
  id: number;
  name: string;
  status: "draft" | "active" | "review" | "published";
  reporting_period_start: string | null;
  reporting_period_end: string | null;
  created_at: string;
  updated_at: string;
}

interface ProjectStandard {
  id: number;
  standard_id: number;
  standard_name: string;
  code: string;
  disclosure_count: number;
  completion_percentage: number;
}

interface AvailableStandard {
  id: number;
  name: string;
  code: string;
  family_code: string;
  family_name: string;
  catalog_group_code: string;
  catalog_group_name: string;
  is_attachable: boolean;
}

interface ProjectStandardAttachPreview {
  standard_id: number;
  standard_code: string;
  standard_name: string;
  total_mapped_elements: number;
  auto_reuse_count: number;
  needs_review_count: number;
  new_metric_count: number;
  already_in_collection_count: number;
}

interface BoundaryOption {
  id: number;
  name: string;
  entity_count?: number;
}

interface ProjectBoundary {
  boundary_id: number | null;
  boundary_name: string | null;
  boundary_type?: string | null;
  entities_in_scope: number;
  excluded_entities: number;
  snapshot_status: "locked" | "draft" | "not_created";
  snapshot_created_at: string | null;
  snapshot_locked?: boolean;
  snapshot_date?: string | null;
}

interface AssignmentOptionUser {
  id: number;
  name: string;
  email: string;
}

interface AssignmentOptionEntity {
  id: number;
  name: string;
  code: string | null;
}

interface AssignmentOptionsData {
  users: AssignmentOptionUser[];
  entities: AssignmentOptionEntity[];
}

const statusConfig: Record<
  ProjectDetail["status"],
  { label: string; variant: "secondary" | "default" | "warning" | "success" }
> = {
  draft: { label: "Draft", variant: "secondary" },
  active: { label: "Active", variant: "default" },
  review: { label: "In Review", variant: "warning" },
  published: { label: "Published", variant: "success" },
};

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
  if (!trimmedName) return code;

  if (trimmedName === code) return code;

  if (trimmedName.startsWith(code)) {
    const remainder = trimmedName.slice(code.length).replace(/^[:\-\s]+/, "").trim();
    if (remainder) return remainder;
  }

  return trimmedName;
}

function formatStandardLabel(standard: Pick<AvailableStandard, "code" | "name">) {
  const displayName = getStandardDisplayName(standard.code, standard.name);
  return displayName === standard.code ? standard.code : `${standard.code} - ${displayName}`;
}

function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function getStandardCardTone(familyCode?: string) {
  switch (familyCode) {
    case "GRI":
      return {
        border: "border-l-emerald-500",
        icon: "bg-emerald-100 text-emerald-700",
        chip: "border-emerald-200 bg-emerald-50 text-emerald-700",
      };
    case "IFRS":
      return {
        border: "border-l-blue-500",
        icon: "bg-blue-100 text-blue-700",
        chip: "border-blue-200 bg-blue-50 text-blue-700",
      };
    case "SASB":
      return {
        border: "border-l-amber-500",
        icon: "bg-amber-100 text-amber-700",
        chip: "border-amber-200 bg-amber-50 text-amber-700",
      };
    case "ESRS":
      return {
        border: "border-l-cyan-500",
        icon: "bg-cyan-100 text-cyan-700",
        chip: "border-cyan-200 bg-cyan-50 text-cyan-700",
      };
    default:
      return {
        border: "border-l-slate-400",
        icon: "bg-slate-100 text-slate-700",
        chip: "border-slate-200 bg-slate-50 text-slate-700",
      };
  }
}

function getCompletionTone(percentage: number) {
  if (percentage >= 80) {
    return {
      label: "Ready",
      variant: "success" as const,
      progress: "bg-green-500",
    };
  }

  if (percentage >= 50) {
    return {
      label: "In progress",
      variant: "warning" as const,
      progress: "bg-amber-500",
    };
  }

  return {
    label: "Starting",
    variant: "secondary" as const,
    progress: "bg-cyan-600",
  };
}

function isFixtureStandard(standard: AvailableStandard) {
  return /^PAG_/i.test(standard.code) || /^JOURNEY_/i.test(standard.code);
}

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

const TAB_VALUES = ["standards", "custom-datasheet", "boundary", "team"] as const;
type TabValue = (typeof TAB_VALUES)[number];
const DEFAULT_TAB: TabValue = "team";

function isTabValue(value: string | null): value is TabValue {
  return !!value && (TAB_VALUES as readonly string[]).includes(value);
}

export default function ProjectSettingsPage() {
  const params = useParams();
  const projectId = params.id as string;
  const numericProjectId = Number(projectId);
  const queryClient = useQueryClient();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTab = searchParams?.get("tab");
  const activeTab: TabValue = isTabValue(initialTab) ? initialTab : DEFAULT_TAB;
  const handleTabChange = (next: string) => {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    if (next === DEFAULT_TAB) {
      params.delete("tab");
    } else {
      params.set("tab", next);
    }
    const query = params.toString();
    router.replace(
      `/projects/${projectId}/settings${query ? `?${query}` : ""}`
    );
  };

  const [addStandardDialogOpen, setAddStandardDialogOpen] = useState(false);
  const [selectedStandardId, setSelectedStandardId] = useState("");
  const [selectedFamilyCode, setSelectedFamilyCode] = useState("");
  const [selectedGroupCode, setSelectedGroupCode] = useState("");
  const [standardSearch, setStandardSearch] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [launchStandard, setLaunchStandard] = useState<ProjectStandard | null>(null);

  const syncProjectsList = (updates: Partial<ProjectDetail> & { id?: number; standard_code?: string }) => {
    queryClient.setQueryData<{
      items: Array<{
        id: number;
        name: string;
        status: ProjectDetail["status"];
        standard_codes?: string[];
      }>;
      total: number;
    }>(
      ["projects"],
      (current) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.map((item) => {
            if (item.id !== Number(projectId)) return item;
            const nextStandardCodes = updates.standard_code
              ? Array.from(new Set([...(item.standard_codes ?? []), updates.standard_code]))
              : item.standard_codes;
            return {
              ...item,
              ...("name" in updates ? { name: updates.name ?? item.name } : {}),
              ...("status" in updates ? { status: updates.status as ProjectDetail["status"] } : {}),
              standard_codes: nextStandardCodes,
            };
          }),
        };
      }
    );
  };

  const invalidateDerivedProjectViews = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["dashboard", "progress", numericProjectId] }),
      queryClient.invalidateQueries({ queryKey: ["report", "readiness", numericProjectId] }),
      queryClient.invalidateQueries({ queryKey: ["project-team", projectId] }),
    ]);

  // Queries
  const {
    data: project,
    isLoading: projectLoading,
    error: projectError,
  } = useApiQuery<ProjectDetail>(
    ["project", projectId],
    `/projects/${projectId}`
  );

  const {
    data: standardsData,
    isLoading: standardsLoading,
  } = useApiQuery<{ items: ProjectStandard[] }>(
    ["project-standards", projectId],
    `/projects/${projectId}/standards`
  );

  const { data: boundaryData } =
    useApiQuery<ProjectBoundary>(
      ["project-boundary", projectId],
      `/projects/${projectId}/boundary`
    );

  const { data: boundaryOptionsData } = useApiQuery<
    { items: BoundaryOption[] } | BoundaryOption[]
  >(
    ["boundaries"],
    "/boundaries"
  );

  const { data: availableStandards } = useApiQuery<{
    items: AvailableStandard[];
  }>(["available-standards"], "/standards?page_size=500");
  const selectedAttachPreviewStandardId = selectedStandardId ? Number(selectedStandardId) : 0;
  const { data: attachPreview, isLoading: attachPreviewLoading } =
    useApiQuery<ProjectStandardAttachPreview>(
      ["project-standard-attach-preview", projectId, selectedAttachPreviewStandardId],
      `/projects/${projectId}/standards/${selectedAttachPreviewStandardId}/attach-preview`,
      {
        enabled: addStandardDialogOpen && Boolean(selectedStandardId),
      }
    );

  const { data: assignmentOptionsData } = useApiQuery<AssignmentOptionsData>(
    ["project-assignment-options", projectId],
    `/projects/${projectId}/assignments`
  );

  // Mutations
  const addStandardMutation = useApiMutation<
    ProjectStandard,
    { standard_id: number }
  >(`/projects/${projectId}/standards`, "POST", {
    onMutate: () => {
      setActionError(null);
    },
    onSuccess: async (result) => {
      const selectedStandard = allStandards.find((item) => item.id === result.standard_id);
      if (selectedStandard) {
        queryClient.setQueryData<{ items: ProjectStandard[] }>(
          ["project-standards", projectId],
          (current) => {
            const existing = current?.items ?? [];
            if (existing.some((item) => item.standard_id === result.standard_id)) {
              return current ?? { items: existing };
            }
            return {
              items: [
                ...existing,
                {
                  id: selectedStandard.id,
                  standard_id: selectedStandard.id,
                  standard_name: selectedStandard.name,
                  code: selectedStandard.code,
                  disclosure_count: 0,
                  completion_percentage: 0,
                },
              ],
            };
          }
        );
        syncProjectsList({ standard_code: selectedStandard.code });
      }
      setAddStandardDialogOpen(false);
      setSelectedStandardId("");
      setSelectedFamilyCode("");
      setSelectedGroupCode("");
      setStandardSearch("");
      await invalidateDerivedProjectViews();
    },
    onError: (error) => {
      setActionError(error.message || "Unable to attach standard to project.");
    },
  });

  const setBoundaryMutation = useApiMutation<
    ProjectBoundary,
    { boundary_id: number }
  >(`/projects/${projectId}/boundary`, "PUT", {
    onMutate: () => {
      setActionError(null);
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-boundary", projectId] }),
        invalidateDerivedProjectViews(),
      ]);
    },
    onError: (error) => {
      setActionError(error.message || "Unable to update project boundary.");
    },
  });

  const snapshotMutation = useApiMutation<unknown, void>(
    `/projects/${projectId}/boundary/snapshot`,
    "POST",
    {
      onMutate: () => {
        setActionError(null);
      },
      onSuccess: async () => {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["project-boundary", projectId] }),
          invalidateDerivedProjectViews(),
        ]);
      },
      onError: (error) => {
        setActionError(error.message || "Unable to save boundary snapshot.");
      },
    }
  );

  const standards = standardsData?.items ?? [];
  const allStandards = availableStandards?.items ?? [];
  const standardCatalogById = new Map(allStandards.map((standard) => [standard.id, standard]));
  const totalDisclosureCount = standards.reduce((sum, standard) => sum + standard.disclosure_count, 0);
  const averageCompletion = standards.length
    ? Math.round(
        standards.reduce((sum, standard) => sum + standard.completion_percentage, 0) / standards.length
      )
    : 0;
  const attachedFamilyCount = new Set(
    standards
      .map((standard) => standardCatalogById.get(standard.standard_id)?.family_code)
      .filter((familyCode): familyCode is string => Boolean(familyCode))
  ).size;
  const normalizedStandardSearch = standardSearch.trim().toLowerCase();
  const baseSelectableStandards = allStandards
    .filter((standard) => !standards.some((projectStandard) => projectStandard.standard_id === standard.id))
    .filter((standard) => standard.is_attachable)
    .filter((standard) => !isFixtureStandard(standard))
    .sort((left, right) => {
      const leftFamilyPriority = familyDisplayPriority[left.family_code] ?? 100;
      const rightFamilyPriority = familyDisplayPriority[right.family_code] ?? 100;
      if (leftFamilyPriority !== rightFamilyPriority) return leftFamilyPriority - rightFamilyPriority;

      const leftGroupPriority = groupDisplayPriority[left.catalog_group_code] ?? 100;
      const rightGroupPriority = groupDisplayPriority[right.catalog_group_code] ?? 100;
      if (leftGroupPriority !== rightGroupPriority) return leftGroupPriority - rightGroupPriority;

      return left.code.localeCompare(right.code);
    });
  const familyOptions = Array.from(
    new Map(
      baseSelectableStandards.map((standard) => [
        standard.family_code,
        { value: standard.family_code, label: standard.family_name },
      ])
    ).values()
  ).sort((left, right) => {
    const leftPriority = familyDisplayPriority[left.value] ?? 100;
    const rightPriority = familyDisplayPriority[right.value] ?? 100;
    if (leftPriority !== rightPriority) return leftPriority - rightPriority;
    return left.label.localeCompare(right.label);
  });
  const groupOptions = Array.from(
    new Map(
      baseSelectableStandards
        .filter((standard) => !selectedFamilyCode || standard.family_code === selectedFamilyCode)
        .map((standard) => [
          `${standard.family_code}:${standard.catalog_group_code}`,
          {
            value: standard.catalog_group_code,
            label: standard.catalog_group_name,
          },
        ])
    ).values()
  ).sort((left, right) => {
    const leftPriority = groupDisplayPriority[left.value] ?? 100;
    const rightPriority = groupDisplayPriority[right.value] ?? 100;
    if (leftPriority !== rightPriority) return leftPriority - rightPriority;
    return left.label.localeCompare(right.label);
  });
  const selectableStandards = baseSelectableStandards
    .filter((standard) => !selectedFamilyCode || standard.family_code === selectedFamilyCode)
    .filter((standard) => !selectedGroupCode || standard.catalog_group_code === selectedGroupCode)
    .filter((standard) => {
      if (!normalizedStandardSearch) return true;
      return `${standard.code} ${standard.name}`.toLowerCase().includes(normalizedStandardSearch);
    });
  const standardOptions: SelectOptionItem[] = selectedFamilyCode
    ? selectableStandards.map((standard) => ({
        value: String(standard.id),
        label: formatStandardLabel(standard),
      }))
    : familyOptions
        .map((family) => ({
          label: family.label,
          options: selectableStandards
            .filter((standard) => standard.family_code === family.value)
            .map((standard) => ({
              value: String(standard.id),
              label: formatStandardLabel(standard),
            })),
        }))
        .filter((family) => family.options.length > 0);

  useEffect(() => {
    if (selectedStandardId && !selectableStandards.some((standard) => String(standard.id) === selectedStandardId)) {
      const clearInvalidStandardSelection = () => {
        setSelectedStandardId("");
      };
      clearInvalidStandardSelection();
    }
  }, [selectedStandardId, selectableStandards]);

  if (projectLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (projectError && isForbidden(projectError)) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-slate-900">Project Settings</h2>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Only admin and ESG manager roles can access project settings.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-slate-900">Project Settings</h2>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load project details.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const status = statusConfig[project.status];
  const boundary = boundaryData ?? {
    boundary_id: null,
    boundary_name: "Not selected",
    entities_in_scope: 0,
    excluded_entities: 0,
    snapshot_status: "not_created" as const,
    snapshot_created_at: null,
  };
  const assignmentUsers = assignmentOptionsData?.users ?? [];
  const assignmentEntities = assignmentOptionsData?.entities ?? [];
  const boundaries = Array.isArray(boundaryOptionsData)
    ? boundaryOptionsData
    : (boundaryOptionsData?.items ?? []);
  const attachedStandardLabels = standards.map(
    (standard) => formatStandardLabel({ code: standard.code, name: standard.standard_name })
  );

  const boundaryConfigured = boundary.boundary_id !== null;
  const boundaryWarn =
    !boundaryConfigured || boundary.snapshot_status !== "locked";
  const totalDisclosures = totalDisclosureCount;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <div className="text-sm text-slate-500">
          <button
            type="button"
            onClick={() => router.push("/projects")}
            className="hover:text-slate-800"
          >
            Projects
          </button>
          <span className="mx-1.5 text-slate-300">&rsaquo;</span>
          <span className="text-slate-700">{project.name}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-2xl font-bold text-slate-900">{project.name}</h2>
          <Badge variant={status.variant}>{status.label}</Badge>
          {project.reporting_period_start && project.reporting_period_end && (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              {new Date(project.reporting_period_start).toLocaleDateString()}
              {" – "}
              {new Date(project.reporting_period_end).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>

      {/* Workflow strip */}
      <WorkflowStrip
        projectId={projectId}
        onBlockerClick={(tab) => tab && handleTabChange(tab)}
        onError={setActionError}
      />

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Tabs */}
      <Tabs
        defaultValue={DEFAULT_TAB}
        value={activeTab}
        onValueChange={handleTabChange}
      >
        <TabsList>
          <TabsTrigger value="standards">
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            Standards
            {standards.length > 0 && (
              <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
                {standards.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="custom-datasheet">
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Custom Datasheet
          </TabsTrigger>
          <TabsTrigger value="boundary">
            <Globe className="mr-1.5 h-3.5 w-3.5" />
            Boundary
            {boundaryWarn && (
              <span className="ml-1.5 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800">
                !
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="team">
            <Users className="mr-1.5 h-3.5 w-3.5" />
            Team
            {totalDisclosures > 0 && (
              <span className="ml-1.5 rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">
                {totalDisclosures}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Standards Tab */}
        <TabsContent value="standards">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Attached Standards</CardTitle>
                <CardDescription>
                  Reporting frameworks linked to this project
                </CardDescription>
              </div>
              <Button
                size="sm"
                onClick={() => setAddStandardDialogOpen(true)}
              >
                <Plus className="h-4 w-4" />
                Add Standard
              </Button>
            </CardHeader>
            <CardContent className="space-y-5">
              {standardsLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : standards.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-400">
                  No standards attached yet. Add a standard to begin.
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="secondary" className="rounded-full px-3 py-1 text-[11px] shadow-none">
                      {pluralize(standards.length, "standard")}
                    </Badge>
                    <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] text-slate-600">
                      {pluralize(totalDisclosureCount, "disclosure")}
                    </Badge>
                    <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] text-slate-600">
                      {attachedFamilyCount} families
                    </Badge>
                    <Badge variant="outline" className="rounded-full px-3 py-1 text-[11px] text-slate-600">
                      {averageCompletion}% avg completion
                    </Badge>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                    {standards.map((std) => {
                      const standardMeta = standardCatalogById.get(std.standard_id);
                      const tone = getStandardCardTone(standardMeta?.family_code);
                      const completionTone = getCompletionTone(std.completion_percentage);
                      const displayName = getStandardDisplayName(std.code, std.standard_name);

                      return (
                        <div
                          key={std.id}
                          className={`flex h-full flex-col rounded-2xl border border-slate-200 border-l-4 ${tone.border} bg-gradient-to-b from-white via-white to-slate-50/80 p-5 shadow-sm transition-transform duration-150 hover:-translate-y-0.5 hover:shadow-md`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex min-w-0 items-start gap-3">
                              <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${tone.icon}`}>
                                <Shield className="h-5 w-5" />
                              </div>
                              <div className="min-w-0">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                                  {standardMeta?.family_name ?? "Reporting standard"}
                                </p>
                                <h3 className="mt-1 text-lg font-extrabold tracking-tight text-slate-900">
                                  {std.code}
                                </h3>
                                {displayName !== std.code && (
                                  <p className="mt-1 line-clamp-2 text-sm leading-5 text-slate-600">
                                    {displayName}
                                  </p>
                                )}
                              </div>
                            </div>
                            <Badge
                              variant={completionTone.variant}
                              className="rounded-full px-2.5 py-1 text-[10px] shadow-none"
                            >
                              {completionTone.label}
                            </Badge>
                          </div>

                          <div className="mt-4 flex flex-wrap gap-2">
                            {standardMeta?.catalog_group_name && (
                              <span
                                className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${tone.chip}`}
                              >
                                {standardMeta.catalog_group_name}
                              </span>
                            )}
                            {standardMeta?.family_code && (
                              <span className="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600">
                                {standardMeta.family_code}
                              </span>
                            )}
                          </div>

                          <div className="mt-5 grid grid-cols-2 gap-3">
                            <div className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2.5">
                              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                <FileText className="h-3.5 w-3.5" />
                                Disclosures
                              </div>
                              <div className="mt-1 text-lg font-bold text-slate-900">
                                {std.disclosure_count}
                              </div>
                            </div>
                            <div className="rounded-xl border border-slate-200 bg-white/80 px-3 py-2.5">
                              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                <Globe className="h-3.5 w-3.5" />
                                Completion
                              </div>
                              <div className="mt-1 text-lg font-bold text-slate-900">
                                {Math.round(std.completion_percentage)}%
                              </div>
                            </div>
                          </div>

                          <div className="mt-5">
                            <div className="mb-2 flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                              <span>Readiness</span>
                              <span>{Math.round(std.completion_percentage)}%</span>
                            </div>
                            <Progress
                              value={std.completion_percentage}
                              className="h-2.5"
                              indicatorClassName={completionTone.progress}
                            />
                          </div>

                          <div className="mt-5 pt-1">
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full justify-center rounded-xl border-slate-300 bg-white/70"
                              onClick={() => {
                                setActionError(null);
                                setLaunchStandard(std);
                              }}
                            >
                              Launch Indicators
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="custom-datasheet">
          <CustomDatasheetBuilder projectId={projectId} />
        </TabsContent>

        {/* Boundary Tab */}
        <TabsContent value="boundary">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Boundary Selection
                </CardTitle>
                <CardDescription>
                  Choose the organizational boundary for this project
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select
                  label="Boundary"
                  options={boundaries.map((b) => ({
                    value: String(b.id),
                    label: `${b.name} (${b.entity_count ?? 0} entities)`,
                  }))}
                  placeholder="Select a boundary..."
                  value={
                    boundary.boundary_id
                      ? String(boundary.boundary_id)
                      : ""
                  }
                  onChange={(val) => {
                    if (val) {
                      setBoundaryMutation.mutate({
                        boundary_id: parseInt(val),
                      });
                    }
                  }}
                />
                {setBoundaryMutation.isPending && (
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Saving...
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Boundary Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-2xl font-bold">
                      {boundary.entities_in_scope}
                    </p>
                    <p className="text-xs text-slate-500">Entities in scope</p>
                  </div>
                  <div className="rounded-lg border border-slate-100 p-3">
                    <p className="text-2xl font-bold">
                      {boundary.excluded_entities}
                    </p>
                    <p className="text-xs text-slate-500">
                      Excluded entities
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      Snapshot Status
                    </span>
                    <Badge
                      variant={
                        boundary.snapshot_status === "locked"
                          ? "default"
                          : boundary.snapshot_status === "draft"
                            ? "warning"
                            : "secondary"
                      }
                    >
                      {boundary.snapshot_status === "locked" && (
                        <Lock className="mr-1 h-3 w-3" />
                      )}
                      {boundary.snapshot_status === "not_created"
                        ? "No Snapshot"
                        : boundary.snapshot_status}
                    </Badge>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => snapshotMutation.mutate(undefined)}
                    disabled={
                      snapshotMutation.isPending ||
                      !boundary.boundary_id ||
                      boundary.snapshot_status === "locked"
                    }
                  >
                    {snapshotMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Camera className="h-4 w-4" />
                    )}
                    Save Snapshot
                  </Button>
                </div>

                {boundary.snapshot_created_at && (
                  <p className="text-xs text-slate-400">
                    Last snapshot:{" "}
                    {new Date(
                      boundary.snapshot_created_at
                    ).toLocaleString()}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Team Tab */}
        <TabsContent value="team">
          <TeamMatrix projectId={projectId} onError={setActionError} />
        </TabsContent>
      </Tabs>

      {/* Add Standard Dialog */}
      <Dialog open={addStandardDialogOpen} onOpenChange={setAddStandardDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Standard</DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <div className="space-y-1 text-sm text-slate-500">
              <p>Only standards that are not yet attached to this project appear here.</p>
              {attachedStandardLabels.length > 0 && (
                <p>
                  Already attached: {attachedStandardLabels.join(", ")}.
                </p>
              )}
            </div>
            <Input
              label="Search"
              placeholder="Find standard by code or name"
              value={standardSearch}
              onChange={(e) => setStandardSearch(e.target.value)}
            />
            <Select
              label="Family"
              options={[{ value: "", label: "All families" }, ...familyOptions]}
              value={selectedFamilyCode}
              onChange={(val) => {
                setSelectedFamilyCode(val);
                setSelectedGroupCode("");
                setSelectedStandardId("");
              }}
            />
            {selectedFamilyCode ? (
              <Select
                label="Group"
                options={[{ value: "", label: "All groups" }, ...groupOptions]}
                value={selectedGroupCode}
                onChange={(val) => {
                  setSelectedGroupCode(val);
                  setSelectedStandardId("");
                }}
              />
            ) : (
              <p className="text-sm text-slate-500">
                Choose a family first if you want to narrow the list by group.
              </p>
            )}
            <Select
              label="Standard"
              options={standardOptions}
              placeholder="Select a standard..."
              value={selectedStandardId}
              onChange={(val) => setSelectedStandardId(val)}
            />
            {selectableStandards.length === 0 && (
              <p className="text-sm text-slate-500">
                No visible standards match the current filters.
              </p>
            )}
            {selectedStandardId && (
              <div className="rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3">
                <p className="text-sm font-medium text-cyan-950">Automatic reuse preview</p>
                <p className="mt-1 text-sm text-cyan-900">
                  Full-match links reuse one shared data point across standards. Editing from either linked card stays in sync.
                </p>
                {attachPreviewLoading ? (
                  <div className="mt-3 flex items-center gap-2 text-sm text-cyan-900">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Calculating reuse impact...
                  </div>
                ) : attachPreview ? (
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="rounded-lg border border-cyan-200 bg-white px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-cyan-700">
                        Auto-linked
                      </p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">
                        {attachPreview.auto_reuse_count}
                      </p>
                    </div>
                    <div className="rounded-lg border border-amber-200 bg-white px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-amber-700">
                        Needs Extra Input
                      </p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">
                        {attachPreview.needs_review_count}
                      </p>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                        New Metrics
                      </p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">
                        {attachPreview.new_metric_count}
                      </p>
                    </div>
                    <div className="rounded-lg border border-emerald-200 bg-white px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-700">
                        Already In Collection
                      </p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">
                        {attachPreview.already_in_collection_count}
                      </p>
                    </div>
                  </div>
                ) : null}
                <p className="mt-3 text-sm text-cyan-900">
                  After attaching the standard, launch only the missing metrics. Existing linked metrics will be reused automatically.
                </p>
              </div>
            )}
            {addStandardMutation.error && (
              <p className="text-sm text-red-500">
                {addStandardMutation.error.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setAddStandardDialogOpen(false);
                setSelectedStandardId("");
                setSelectedFamilyCode("");
                setSelectedGroupCode("");
                setStandardSearch("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={() =>
                addStandardMutation.mutate({
                  standard_id: parseInt(selectedStandardId),
                })
              }
              disabled={
                !selectedStandardId || addStandardMutation.isPending
              }
            >
              {addStandardMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <StandardLaunchDialog
        open={!!launchStandard}
        onOpenChange={(open) => {
          if (!open) {
            setLaunchStandard(null);
          }
        }}
        projectId={projectId}
        standard={
          launchStandard
            ? {
                standard_id: launchStandard.standard_id,
                code: launchStandard.code,
                standard_name: launchStandard.standard_name,
              }
            : null
        }
        users={assignmentUsers}
        entities={assignmentEntities}
        boundaryId={boundary.boundary_id}
        onError={setActionError}
      />

    </div>
  );
}
