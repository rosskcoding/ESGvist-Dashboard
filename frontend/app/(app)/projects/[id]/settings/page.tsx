"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
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
import { Select } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  Play,
  Eye,
  Send,
  Plus,
  Shield,
  Globe,
  Users,
  Settings,
  Lock,
  FileText,
  CheckCircle2,
  XCircle,
  Camera,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/lib/api";

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

interface AssignmentSummary {
  id: number;
  user_name: string;
  email: string;
  role: string;
  assigned_disclosures: number;
  completed: number;
}

interface GateCheckResult {
  passed: boolean;
  blockers: string[];
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

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

export default function ProjectSettingsPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [addStandardDialogOpen, setAddStandardDialogOpen] = useState(false);
  const [selectedStandardId, setSelectedStandardId] = useState("");
  const [gateBlockers, setGateBlockers] = useState<string[]>([]);
  const [gateDialogOpen, setGateDialogOpen] = useState(false);

  // Queries
  const {
    data: project,
    isLoading: projectLoading,
    error: projectError,
    refetch: refetchProject,
  } = useApiQuery<ProjectDetail>(
    ["project", projectId],
    `/projects/${projectId}`
  );

  const {
    data: standardsData,
    isLoading: standardsLoading,
    refetch: refetchStandards,
  } = useApiQuery<{ items: ProjectStandard[] }>(
    ["project-standards", projectId],
    `/projects/${projectId}/standards`
  );

  const { data: boundaryData, refetch: refetchBoundary } =
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
  }>(["available-standards"], "/standards");

  const { data: teamData } = useApiQuery<{ items: AssignmentSummary[] }>(
    ["project-team", projectId],
    `/projects/${projectId}/assignments/summary`
  );

  // Mutations
  const activateMutation = useApiMutation<ProjectDetail, void>(
    `/projects/${projectId}/activate`,
    "POST",
    { onSuccess: () => refetchProject() }
  );

  const reviewMutation = useApiMutation<ProjectDetail, void>(
    `/projects/${projectId}/start-review`,
    "POST",
    { onSuccess: () => refetchProject() }
  );

  const publishMutation = useApiMutation<ProjectDetail, void>(
    `/projects/${projectId}/publish`,
    "POST",
    { onSuccess: () => refetchProject() }
  );

  const addStandardMutation = useApiMutation<
    ProjectStandard,
    { standard_id: number }
  >(`/projects/${projectId}/standards`, "POST", {
    onSuccess: () => {
      setAddStandardDialogOpen(false);
      setSelectedStandardId("");
      refetchStandards();
    },
  });

  const setBoundaryMutation = useApiMutation<
    ProjectBoundary,
    { boundary_id: number }
  >(`/projects/${projectId}/boundary`, "PUT", {
    onSuccess: () => refetchBoundary(),
  });

  const snapshotMutation = useApiMutation<unknown, void>(
    `/projects/${projectId}/boundary/snapshot`,
    "POST",
    { onSuccess: () => refetchBoundary() }
  );

  const handleWorkflowAction = async (
    action: "activate" | "start-review" | "publish"
  ) => {
    try {
      const workflowAction =
        action === "activate"
          ? "start_project"
          : action === "start-review"
            ? "review_project"
            : "publish_project";
      const result = await api.post<GateCheckResult & { failed_gates?: Array<{ message?: string }> }>(
        "/gate-check",
        { project_id: Number(projectId), action: workflowAction }
      );
      if (result && !result.passed) {
        const blockers =
          result.blockers?.length
            ? result.blockers
            : (result.failed_gates || [])
                .map((gate) => gate.message)
                .filter((message): message is string => !!message);
        setGateBlockers(blockers);
        setGateDialogOpen(true);
        return;
      }
    } catch {
      // Preserve workflow action even if the pre-flight check is temporarily unavailable.
    }

    switch (action) {
      case "activate":
        activateMutation.mutate(undefined);
        break;
      case "start-review":
        reviewMutation.mutate(undefined);
        break;
      case "publish":
        publishMutation.mutate(undefined);
        break;
    }
  };

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
  const standards = standardsData?.items ?? [];
  const boundary = boundaryData ?? {
    boundary_id: null,
    boundary_name: "Not selected",
    entities_in_scope: 0,
    excluded_entities: 0,
    snapshot_status: "not_created" as const,
    snapshot_created_at: null,
  };
  const team = teamData?.items ?? [];
  const boundaries = Array.isArray(boundaryOptionsData)
    ? boundaryOptionsData
    : (boundaryOptionsData?.items ?? []);
  const allStandards = availableStandards?.items ?? [];

  const isWorkflowBusy =
    activateMutation.isPending ||
    reviewMutation.isPending ||
    publishMutation.isPending;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-slate-900">
              {project.name}
            </h2>
            <Badge variant={status.variant}>{status.label}</Badge>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Project Settings &middot; ID #{project.id}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">
            <Settings className="mr-1.5 h-3.5 w-3.5" />
            General
          </TabsTrigger>
          <TabsTrigger value="standards">
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            Standards
          </TabsTrigger>
          <TabsTrigger value="boundary">
            <Globe className="mr-1.5 h-3.5 w-3.5" />
            Boundary
          </TabsTrigger>
          <TabsTrigger value="team">
            <Users className="mr-1.5 h-3.5 w-3.5" />
            Team
          </TabsTrigger>
        </TabsList>

        {/* General Tab */}
        <TabsContent value="general">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Project Information</CardTitle>
                <CardDescription>
                  Basic project details and metadata
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm font-medium text-slate-700">Name</p>
                  <p className="mt-1 text-sm">{project.name}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">
                    Reporting Period
                  </p>
                  <p className="mt-1 text-sm">
                    {project.reporting_period_start && project.reporting_period_end
                      ? `${new Date(project.reporting_period_start).toLocaleDateString()} - ${new Date(project.reporting_period_end).toLocaleDateString()}`
                      : "Not set"}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">Status</p>
                  <Badge className="mt-1" variant={status.variant}>
                    {status.label}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-700">Created</p>
                  <p className="mt-1 text-sm">
                    {project.created_at
                      ? new Date(project.created_at).toLocaleString()
                      : "Not available"}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Workflow</CardTitle>
                <CardDescription>
                  Advance the project through its lifecycle
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-bold">
                    1
                  </div>
                  <span className="text-sm">Draft</span>
                  <div className="h-px flex-1 bg-slate-200" />
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-bold">
                    2
                  </div>
                  <span className="text-sm">Active</span>
                  <div className="h-px flex-1 bg-slate-200" />
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-bold">
                    3
                  </div>
                  <span className="text-sm">Review</span>
                  <div className="h-px flex-1 bg-slate-200" />
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-bold">
                    4
                  </div>
                  <span className="text-sm">Published</span>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  {project.status === "draft" && (
                    <Button
                      onClick={() => handleWorkflowAction("activate")}
                      disabled={isWorkflowBusy}
                    >
                      {activateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                      Activate
                    </Button>
                  )}
                  {project.status === "active" && (
                    <Button
                      onClick={() => handleWorkflowAction("start-review")}
                      disabled={isWorkflowBusy}
                    >
                      {reviewMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                      Start Review
                    </Button>
                  )}
                  {project.status === "review" && (
                    <Button
                      onClick={() => handleWorkflowAction("publish")}
                      disabled={isWorkflowBusy}
                    >
                      {publishMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                      Publish
                    </Button>
                  )}
                  {project.status === "published" && (
                    <div className="flex items-center gap-2 text-sm text-green-600">
                      <CheckCircle2 className="h-4 w-4" />
                      Project has been published
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

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
            <CardContent>
              {standardsLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : standards.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-400">
                  No standards attached yet. Add a standard to begin.
                </p>
              ) : (
                <div className="space-y-4">
                  {standards.map((std) => (
                    <div
                      key={std.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 p-4"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Shield className="h-4 w-4 text-slate-500" />
                          <span className="font-medium">{std.code}</span>
                          <span className="text-sm text-slate-500">
                            {std.standard_name}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400">
                          {std.disclosure_count} disclosures
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Progress
                          value={std.completion_percentage}
                          className="w-24"
                          indicatorClassName={
                            std.completion_percentage >= 80
                              ? "bg-green-500"
                              : std.completion_percentage >= 50
                                ? "bg-amber-500"
                                : "bg-blue-600"
                          }
                        />
                        <span className="text-sm font-semibold">
                          {Math.round(std.completion_percentage)}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
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
          <Card>
            <CardHeader>
              <CardTitle>Team Assignments</CardTitle>
              <CardDescription>
                Summary of team member assignments and progress
              </CardDescription>
            </CardHeader>
            <CardContent>
              {team.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-400">
                  No team members assigned yet.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Assigned</TableHead>
                      <TableHead>Completed</TableHead>
                      <TableHead>Progress</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {team.map((member) => {
                      const pct =
                        member.assigned_disclosures > 0
                          ? (member.completed / member.assigned_disclosures) *
                            100
                          : 0;
                      return (
                        <TableRow key={member.id}>
                          <TableCell className="font-medium">
                            {member.user_name}
                          </TableCell>
                          <TableCell className="text-slate-500">
                            {member.email}
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline">{member.role}</Badge>
                          </TableCell>
                          <TableCell>{member.assigned_disclosures}</TableCell>
                          <TableCell>{member.completed}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Progress
                                value={pct}
                                className="w-20"
                                indicatorClassName={
                                  pct >= 80
                                    ? "bg-green-500"
                                    : pct >= 50
                                      ? "bg-amber-500"
                                      : "bg-blue-600"
                                }
                              />
                              <span className="text-xs text-slate-500">
                                {Math.round(pct)}%
                              </span>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Add Standard Dialog */}
      <Dialog open={addStandardDialogOpen} onOpenChange={setAddStandardDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Standard</DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <Select
              label="Standard"
              options={allStandards
                .filter(
                  (s) => !standards.some((ps) => ps.standard_id === s.id)
                )
                .map((s) => ({
                  value: String(s.id),
                  label: `${s.code} - ${s.name}`,
                }))}
              placeholder="Select a standard..."
              value={selectedStandardId}
              onChange={(val) => setSelectedStandardId(val)}
            />
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

      {/* Gate Check Blockers Dialog */}
      <Dialog open={gateDialogOpen} onOpenChange={setGateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <XCircle className="h-5 w-5" />
              Cannot Proceed
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-3">
            <p className="text-sm text-slate-600">
              The following issues must be resolved before advancing:
            </p>
            <ul className="space-y-2">
              {gateBlockers.map((blocker, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700"
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                  {blocker}
                </li>
              ))}
            </ul>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setGateDialogOpen(false)}
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
