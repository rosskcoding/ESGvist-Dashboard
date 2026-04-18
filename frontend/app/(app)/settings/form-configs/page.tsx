"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ClipboardList,
  Loader2,
  Plus,
  RefreshCcw,
  Save,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";

type RoleBinding = { role: string; scope_type?: string; scope_id?: number | null };

type Project = {
  id: number;
  name: string;
  status: "draft" | "active" | "review" | "published";
  reporting_year?: number | null;
};

type ProjectsResponse = {
  items: Project[];
  total: number;
};

type FormFieldConfig = {
  shared_element_id: number;
  requirement_item_id?: number | null;
  assignment_id?: number | null;
  entity_id?: number | null;
  facility_id?: number | null;
  visible: boolean;
  required: boolean;
  help_text?: string | null;
  tooltip?: string | null;
  order: number;
};

type FormStepConfig = {
  id: string;
  title: string;
  fields: FormFieldConfig[];
};

type FormConfigBody = {
  steps: FormStepConfig[];
};

type FormConfigHealthIssue = {
  code: string;
  message: string;
  affected_fields: number;
};

type FormConfigHealth = {
  status: string;
  is_stale: boolean;
  target_project_id?: number | null;
  field_count: number;
  assignment_scoped_fields: number;
  context_scoped_fields: number;
  issue_count: number;
  issues: FormConfigHealthIssue[];
  latest_assignment_updated_at?: string | null;
  latest_boundary_updated_at?: string | null;
};

type FormConfig = {
  id: number;
  organization_id: number;
  project_id: number | null;
  name: string;
  description: string | null;
  config: FormConfigBody;
  is_active: boolean;
  created_by: number | null;
  created_at: string;
  updated_at?: string | null;
  resolved_for_project_id?: number | null;
  resolution_scope?: string | null;
  health?: FormConfigHealth | null;
};

type FormConfigListResponse = {
  items: FormConfig[];
  total: number;
};

type FormConfigPayload = {
  project_id: number | null;
  name: string;
  description: string | null;
  config: FormConfigBody;
  is_active: boolean;
};

const EMPTY_CONFIG_TEMPLATE: FormConfigBody = {
  steps: [
    {
      id: "step-1",
      title: "General",
      fields: [],
    },
  ],
};

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getHealthBadgeVariant(status?: string | null): "outline" | "secondary" | "success" | "warning" {
  switch (status) {
    case "healthy":
      return "success";
    case "stale":
      return "warning";
    case "not_applicable":
      return "outline";
    default:
      return "secondary";
  }
}

function getHealthLabel(config: FormConfig) {
  if (config.project_id === null) {
    return "Org default";
  }
  switch (config.health?.status) {
    case "healthy":
      return "Healthy";
    case "stale":
      return "Stale";
    default:
      return "Unchecked";
  }
}

function prettyConfig(value: FormConfigBody) {
  return JSON.stringify(value, null, 2);
}

function isOrgContextError(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "ORG_HEADER_REQUIRED" || /organization context|x-organization-id/i.test(error?.message ?? "");
}

export default function FormConfigsPage() {
  const queryClient = useQueryClient();
  const [selectedConfigId, setSelectedConfigId] = useState<number | "new" | null>(null);
  const [generateProjectId, setGenerateProjectId] = useState("");
  const [form, setForm] = useState({
    name: "",
    description: "",
    project_id: "",
    is_active: true,
    configText: prettyConfig(EMPTY_CONFIG_TEMPLATE),
  });
  const [formError, setFormError] = useState("");
  const [message, setMessage] = useState("");

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me"],
    "/auth/me"
  );
  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) =>
    ["admin", "esg_manager", "platform_admin"].includes(role)
  );
  const accessDenied = Boolean(me) && !canAccess;

  const {
    data: configsData,
    isLoading: configsLoading,
    error: configsError,
  } = useApiQuery<FormConfigListResponse>(
    ["form-configs"],
    "/form-configs?page_size=100",
    { enabled: canAccess }
  );
  const {
    data: projectsData,
    isLoading: projectsLoading,
    error: projectsError,
  } = useApiQuery<ProjectsResponse>(
    ["projects", "form-configs"],
    "/projects?page_size=100",
    { enabled: canAccess }
  );

  const configs = useMemo(() => configsData?.items ?? [], [configsData]);
  const projects = useMemo(() => projectsData?.items ?? [], [projectsData]);
  const projectsById = useMemo(
    () => new Map(projects.map((project) => [project.id, project])),
    [projects]
  );
  const selectedConfig = useMemo(
    () =>
      typeof selectedConfigId === "number"
        ? configs.find((config) => config.id === selectedConfigId) ?? null
        : null,
    [configs, selectedConfigId]
  );

  useEffect(() => {
    if (selectedConfigId === null && configs.length > 0) {
      const selectFirstConfig = () => {
        setSelectedConfigId(configs[0].id);
      };
      selectFirstConfig();
    }
  }, [configs, selectedConfigId]);

  useEffect(() => {
    if (selectedConfigId === "new") {
      const resetFormForNewConfig = () => {
        setForm({
          name: "",
          description: "",
          project_id: "",
          is_active: true,
          configText: prettyConfig(EMPTY_CONFIG_TEMPLATE),
        });
      };
      resetFormForNewConfig();
      return;
    }

    if (!selectedConfig) return;
    const syncConfigForm = () => {
      setForm({
        name: selectedConfig.name,
        description: selectedConfig.description ?? "",
        project_id: selectedConfig.project_id ? String(selectedConfig.project_id) : "",
        is_active: selectedConfig.is_active,
        configText: prettyConfig(selectedConfig.config),
      });
    };
    syncConfigForm();
  }, [selectedConfig, selectedConfigId]);

  function upsertConfig(config: FormConfig) {
    queryClient.setQueryData<FormConfigListResponse>(["form-configs"], (current) =>
      current
        ? {
            ...current,
            items: [
              config,
              ...current.items
                .filter((item) => item.id !== config.id)
                .map((item) =>
                  config.is_active && item.project_id === config.project_id
                    ? { ...item, is_active: false }
                    : item
                ),
            ],
            total: current.total + (current.items.some((item) => item.id === config.id) ? 0 : 1),
          }
        : { items: [config], total: 1 }
    );
  }

  const createMutation = useApiMutation<FormConfig, FormConfigPayload>(
    "/form-configs",
    "POST",
    {
      onSuccess: (config) => {
        upsertConfig(config);
        setSelectedConfigId(config.id);
        setMessage("Form configuration created.");
      },
    }
  );

  const updateMutation = useApiMutation<FormConfig, FormConfigPayload>(
    selectedConfig ? `/form-configs/${selectedConfig.id}` : "/form-configs/0",
    "PATCH",
    {
      onSuccess: (config) => {
        upsertConfig(config);
        setSelectedConfigId(config.id);
        setMessage("Form configuration updated.");
      },
    }
  );

  const generateMutation = useApiMutation<FormConfig, undefined>(
    generateProjectId
      ? `/form-configs/projects/${generateProjectId}/generate`
      : "/form-configs/projects/0/generate",
    "POST",
    {
      onSuccess: (config) => {
        upsertConfig(config);
        setSelectedConfigId(config.id);
        setGenerateProjectId(config.project_id ? String(config.project_id) : "");
        setMessage("Default configuration generated from the selected project.");
      },
    }
  );
  const resyncMutation = useApiMutation<FormConfig, undefined>(
    selectedConfig?.project_id
      ? `/form-configs/projects/${selectedConfig.project_id}/resync`
      : "/form-configs/projects/0/resync",
    "POST",
    {
      onSuccess: async (config) => {
        upsertConfig(config);
        setSelectedConfigId(config.id);
        setMessage("Project configuration re-synced from live assignments.");
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: ["form-configs"] }),
          queryClient.invalidateQueries({ queryKey: ["active-form-config", config.project_id] }),
          queryClient.invalidateQueries({ queryKey: ["collection-assignments", config.project_id] }),
        ]);
      },
    }
  );

  const orgContextMissing =
    isOrgContextError(configsError) || isOrgContextError(projectsError);
  const pageError = configsError ?? projectsError ?? null;

  function buildPayload(): FormConfigPayload | null {
    setFormError("");

    let parsedConfig: FormConfigBody;
    try {
      parsedConfig = JSON.parse(form.configText) as FormConfigBody;
    } catch {
      setFormError("Config JSON is invalid.");
      return null;
    }

    if (!parsedConfig.steps || !Array.isArray(parsedConfig.steps)) {
      setFormError("Config must contain a top-level 'steps' array.");
      return null;
    }

    if (!form.name.trim()) {
      setFormError("Configuration name is required.");
      return null;
    }

    return {
      project_id: form.project_id ? Number(form.project_id) : null,
      name: form.name.trim(),
      description: form.description.trim() || null,
      config: parsedConfig,
      is_active: form.is_active,
    };
  }

  async function saveConfig() {
    setMessage("");
    const payload = buildPayload();
    if (!payload) return;

    if (selectedConfigId === "new" || selectedConfigId === null) {
      await createMutation.mutateAsync(payload);
      return;
    }

    await updateMutation.mutateAsync(payload);
  }

  if (meLoading || (canAccess && (configsLoading || projectsLoading))) {
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
          <h2 className="text-2xl font-bold text-slate-900">Form Configurations</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage guided collection wizard steps and project-specific form layouts.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only ESG managers, admins, and platform admins can manage form configurations.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (orgContextMissing) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Form Configurations</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage guided collection wizard steps and project-specific form layouts.
          </p>
        </div>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 text-sm text-amber-800">
            Select an organization context first. If you are a platform admin, enter support mode
            for a tenant and then reopen this page.
          </CardContent>
        </Card>
      </div>
    );
  }

  if (pageError) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Form Configurations</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage guided collection wizard steps and project-specific form layouts.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6 text-sm text-red-700">{pageError.message}</CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Form Configurations</h2>
          <p className="mt-1 text-sm text-slate-500">
            Build wizard steps manually or generate a baseline from project assignments and mappings.
          </p>
        </div>
        <Button
          onClick={() => {
            setMessage("");
            setFormError("");
            setSelectedConfigId("new");
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          New Config
        </Button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_1.4fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-slate-500" />
                Generate From Project
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Select
                label="Project"
                value={generateProjectId}
                onChange={setGenerateProjectId}
                options={[
                  { value: "", label: "Select project" },
                  ...projects.map((project) => ({
                    value: String(project.id),
                    label: `${project.name} (${project.status})`,
                  })),
                ]}
              />
              <p className="text-xs text-slate-500">
                Recommended path: auto-build the initial wizard from requirement items and then tune
                the JSON for ordering, help text, and visibility.
              </p>
              <Button
                variant="outline"
                onClick={() => {
                  setMessage("");
                  void generateMutation.mutateAsync(undefined);
                }}
                disabled={generateMutation.isPending || !generateProjectId}
              >
                {generateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Generate Default Config
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-4 w-4 text-slate-500" />
                Existing Configs
              </CardTitle>
            </CardHeader>
            <CardContent>
              {configs.length === 0 ? (
                <p className="text-sm text-slate-500">No configurations yet.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Project</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Health</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {configs.map((config) => (
                      <TableRow key={config.id}>
                        <TableCell>
                          <div className="space-y-1">
                            <p className="font-medium text-slate-900">{config.name}</p>
                            {config.description && (
                              <p className="line-clamp-2 text-xs text-slate-500">{config.description}</p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {config.project_id
                            ? projectsById.get(config.project_id)?.name ?? `Project #${config.project_id}`
                            : "Organization default"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={config.is_active ? "success" : "secondary"}>
                            {config.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="space-y-1">
                            <Badge variant={getHealthBadgeVariant(config.health?.status)}>
                              {getHealthLabel(config)}
                            </Badge>
                            {config.health?.issue_count ? (
                              <p className="text-xs text-amber-700">
                                {config.health.issue_count} issue
                                {config.health.issue_count === 1 ? "" : "s"}
                              </p>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="text-sm text-slate-500">
                          {formatTimestamp(config.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant={selectedConfigId === config.id ? "default" : "outline"}
                            size="sm"
                            onClick={() => {
                              setMessage("");
                              setFormError("");
                              setSelectedConfigId(config.id);
                            }}
                          >
                            Edit
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

        <Card>
          <CardHeader>
            <CardTitle>
              {selectedConfigId === "new" || selectedConfigId === null
                ? "New Configuration"
                : `Editing Config #${selectedConfigId}`}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="form-config-name">Name</Label>
                <Input
                  id="form-config-name"
                  value={form.name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, name: event.target.value }))
                  }
                  placeholder="Collection wizard for FY2026"
                />
              </div>
              <Select
                label="Project Scope"
                value={form.project_id}
                onChange={(value) =>
                  setForm((current) => ({ ...current, project_id: value }))
                }
                options={[
                  { value: "", label: "Organization default" },
                  ...projects.map((project) => ({
                    value: String(project.id),
                    label: project.name,
                  })),
                ]}
              />
            </div>

            {selectedConfig && (
              <div className="rounded-lg border border-slate-200 bg-slate-50/80 p-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-2">
                      <Badge variant={selectedConfig.is_active ? "success" : "secondary"}>
                        {selectedConfig.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <Badge variant={getHealthBadgeVariant(selectedConfig.health?.status)}>
                        {getHealthLabel(selectedConfig)}
                      </Badge>
                      {selectedConfig.project_id !== null && (
                        <Badge variant="outline">
                          {projectsById.get(selectedConfig.project_id)?.name
                            ?? `Project #${selectedConfig.project_id}`}
                        </Badge>
                      )}
                    </div>
                    <div className="space-y-1 text-xs text-slate-500">
                      <p>Created {formatTimestamp(selectedConfig.created_at)}</p>
                      <p>
                        Updated{" "}
                        {formatTimestamp(selectedConfig.updated_at ?? selectedConfig.created_at)}
                      </p>
                      {selectedConfig.health && selectedConfig.project_id !== null && (
                        <p>
                          {selectedConfig.health.assignment_scoped_fields} assignment-aware field
                          {selectedConfig.health.assignment_scoped_fields === 1 ? "" : "s"},{" "}
                          {selectedConfig.health.context_scoped_fields} context-aware field
                          {selectedConfig.health.context_scoped_fields === 1 ? "" : "s"}
                        </p>
                      )}
                    </div>
                  </div>

                  {selectedConfig.project_id !== null && (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={resyncMutation.isPending}
                      onClick={() => {
                        setMessage("");
                        void resyncMutation.mutateAsync(undefined);
                      }}
                    >
                      {resyncMutation.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCcw className="mr-2 h-4 w-4" />
                      )}
                      Re-sync Project Config
                    </Button>
                  )}
                </div>

                {selectedConfig.health?.issues.length ? (
                  <div className="mt-4 space-y-2">
                    {selectedConfig.health.issues.map((issue) => (
                      <div
                        key={issue.code}
                        className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
                      >
                        <div className="flex items-start gap-2">
                          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                          <div>
                            <p className="font-medium">{issue.code}</p>
                            <p className="mt-1">
                              {issue.message}
                              {issue.affected_fields > 0 ? ` (${issue.affected_fields})` : ""}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : selectedConfig.project_id === null ? (
                  <p className="mt-4 text-sm text-slate-600">
                    Organization defaults are evaluated per project at runtime, so they do not carry
                    a fixed health status on their own.
                  </p>
                ) : (
                  <p className="mt-4 text-sm text-green-700">
                    This config matches the current project assignments and boundary.
                  </p>
                )}
              </div>
            )}

            <div className="grid gap-1.5">
              <Label htmlFor="form-config-description">Description</Label>
              <Textarea
                id="form-config-description"
                value={form.description}
                onChange={(event) =>
                  setForm((current) => ({ ...current, description: event.target.value }))
                }
                rows={3}
                placeholder="When should this wizard be used, and what collection flow does it support?"
              />
            </div>

            <div className="rounded-lg border border-slate-200 p-4">
              <Switch
                checked={form.is_active}
                onCheckedChange={(checked) =>
                  setForm((current) => ({ ...current, is_active: checked }))
                }
                label="Mark as active"
              />
              <p className="mt-2 text-xs text-slate-500">
                Active configs can be resolved by project and used as the live collection form.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    configText: prettyConfig(EMPTY_CONFIG_TEMPLATE),
                  }))
                }
              >
                <RefreshCcw className="mr-2 h-4 w-4" />
                Load Blank Template
              </Button>
              <p className="text-xs text-slate-500">
                Backend expects a `steps` array with ordered `fields` containing `shared_element_id`
                and, when needed, optional row context like `assignment_id`, `entity_id`, or
                `facility_id`.
              </p>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="form-config-json">Config JSON</Label>
              <Textarea
                id="form-config-json"
                value={form.configText}
                onChange={(event) =>
                  setForm((current) => ({ ...current, configText: event.target.value }))
                }
                rows={22}
                className="font-mono text-xs"
              />
            </div>

            {formError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {formError}
              </div>
            )}
            {message && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                {message}
              </div>
            )}

            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => {
                  setMessage("");
                  setFormError("");
                  if (configs.length > 0) {
                    setSelectedConfigId(configs[0].id);
                  } else {
                    setSelectedConfigId("new");
                  }
                }}
              >
                Reset
              </Button>
              <Button
                onClick={() => void saveConfig()}
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {(createMutation.isPending || updateMutation.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                <Save className="mr-2 h-4 w-4" />
                Save Configuration
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
