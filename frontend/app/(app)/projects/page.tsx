"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Plus,
  Loader2,
  AlertTriangle,
  FolderOpen,
  ShieldAlert,
  Check,
  Circle,
  CalendarDays,
  Users,
  ClipboardList,
  ChevronRight,
  Clock,
  Search,
  MoreHorizontal,
} from "lucide-react";

type ProjectStatus = "draft" | "active" | "review" | "published" | "archived";

interface ProjectSetupHealth {
  standards_count: number;
  boundary_configured: boolean;
  boundary_entities_count: number;
  team_size: number;
  assignments_total: number;
  assignments_assigned: number;
  deadline_set: boolean;
  steps_completed: number;
  steps_total: number;
}

interface Project {
  id: number;
  name: string;
  status: ProjectStatus;
  standard_codes?: string[];
  completion_percentage?: number;
  deadline?: string | null;
  reporting_year?: number | null;
  setup_health?: ProjectSetupHealth;
}

interface ProjectsResponse {
  items: Project[];
  total: number;
}

interface CreateProjectPayload {
  name: string;
}

const ARCHIVED_STATUSES = new Set<ProjectStatus>(["published", "archived"]);

const statusBadge: Record<ProjectStatus, { label: string; classes: string }> = {
  draft: { label: "Draft", classes: "bg-slate-200 text-slate-700" },
  active: { label: "Active", classes: "bg-cyan-700 text-white" },
  review: { label: "In review", classes: "bg-amber-100 text-amber-800" },
  published: { label: "Published", classes: "bg-emerald-100 text-emerald-800" },
  archived: { label: "Archived", classes: "bg-slate-100 text-slate-500" },
};

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return (
    code === "FORBIDDEN" ||
    /not allowed|access denied|forbidden/i.test(error?.message || "")
  );
}

function daysUntil(dateStr?: string | null): number | null {
  if (!dateStr) return null;
  const target = new Date(dateStr);
  if (Number.isNaN(target.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  target.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function formatDeadline(dateStr?: string | null): string | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

type StepTone = "done" | "warn" | "todo";

function stepIcon(tone: StepTone) {
  if (tone === "done") {
    return (
      <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
        <Check className="h-3.5 w-3.5" strokeWidth={3} />
      </span>
    );
  }
  if (tone === "warn") {
    return (
      <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-amber-50 text-amber-600">
        <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2.5} />
      </span>
    );
  }
  return (
    <span className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-slate-400">
      <Circle className="h-2.5 w-2.5 fill-current" />
    </span>
  );
}

interface SetupStep {
  key: string;
  label: string;
  subtitle: string;
  tone: StepTone;
  href: string;
  trailing?: React.ReactNode;
}

function buildSetupSteps(project: Project): SetupStep[] {
  const health = project.setup_health;
  const standardsCount =
    health?.standards_count ?? project.standard_codes?.length ?? 0;
  const boundaryConfigured = health?.boundary_configured ?? false;
  const boundaryEntities = health?.boundary_entities_count ?? 0;
  const teamSize = health?.team_size ?? 0;
  const assignmentsTotal = health?.assignments_total ?? 0;
  const assignmentsAssigned = health?.assignments_assigned ?? 0;
  const deadlineSet = health?.deadline_set ?? !!project.deadline;

  const base = `/projects/${project.id}/settings`;

  const standardsTone: StepTone = standardsCount > 0 ? "done" : "warn";
  const boundaryTone: StepTone = boundaryConfigured ? "done" : "warn";
  const deadlineTone: StepTone = deadlineSet ? "done" : "warn";

  let teamTone: StepTone = "todo";
  let teamSubtitle = "No assignments yet";
  if (assignmentsTotal > 0 && assignmentsAssigned === 0) {
    teamTone = "warn";
    teamSubtitle = `0 of ${assignmentsTotal} assignments staffed`;
  } else if (assignmentsTotal > 0 && assignmentsAssigned < assignmentsTotal) {
    teamTone = "warn";
    teamSubtitle = `${assignmentsAssigned} of ${assignmentsTotal} assignments staffed`;
  } else if (assignmentsTotal > 0 && assignmentsAssigned === assignmentsTotal) {
    teamTone = "done";
    teamSubtitle = `${teamSize} ${
      teamSize === 1 ? "member" : "members"
    } · all staffed`;
  } else if (teamSize > 0) {
    teamTone = "done";
    teamSubtitle = `${teamSize} ${teamSize === 1 ? "member" : "members"}`;
  }

  return [
    {
      key: "standards",
      label: "Standards",
      subtitle:
        standardsCount > 0 ? `${standardsCount} selected` : "No standards attached",
      tone: standardsTone,
      href: `${base}?tab=standards`,
    },
    {
      key: "boundary",
      label: "Reporting boundary",
      subtitle: boundaryConfigured
        ? boundaryEntities > 0
          ? `${boundaryEntities} ${
              boundaryEntities === 1 ? "entity" : "entities"
            } in scope`
          : "Boundary selected"
        : "Not configured",
      tone: boundaryTone,
      href: `${base}?tab=boundary`,
    },
    {
      key: "team",
      label: "Team & assignments",
      subtitle: teamSubtitle,
      tone: teamTone,
      href: `${base}?tab=team`,
      trailing:
        assignmentsTotal > 0 ? (
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full ${
                assignmentsAssigned === assignmentsTotal
                  ? "bg-emerald-500"
                  : assignmentsAssigned > 0
                    ? "bg-amber-500"
                    : "bg-slate-300"
              }`}
              style={{
                width: `${Math.round(
                  (assignmentsAssigned / Math.max(assignmentsTotal, 1)) * 100
                )}%`,
              }}
            />
          </div>
        ) : undefined,
    },
    {
      key: "deadline",
      label: "Deadline",
      subtitle: deadlineSet
        ? (formatDeadline(project.deadline) ?? "Set")
        : "Not set",
      tone: deadlineTone,
      href: `${base}`,
    },
  ];
}

function ProjectCard({ project }: { project: Project }) {
  const router = useRouter();
  const badge = statusBadge[project.status];
  const steps = buildSetupSteps(project);
  const stepsDone =
    project.setup_health?.steps_completed ??
    steps.filter((step) => step.tone === "done").length;
  const stepsTotal = project.setup_health?.steps_total ?? steps.length;
  const setupPct =
    stepsTotal > 0 ? Math.round((stepsDone / stepsTotal) * 100) : 0;
  const ringCircumference = 2 * Math.PI * 34;
  const ringOffset =
    ringCircumference * (1 - stepsDone / Math.max(stepsTotal, 1));
  const ringColor =
    stepsDone >= stepsTotal ? "#059669" : stepsDone > 0 ? "#0e7490" : "#94a3b8";

  const deadlineLabel = formatDeadline(project.deadline);
  const days = daysUntil(project.deadline);
  const deadlineIsActive =
    project.status === "active" || project.status === "review";
  let deadlineChip: React.ReactNode = null;
  if (deadlineLabel) {
    const tone =
      days !== null && days < 0
        ? "bg-rose-50 text-rose-800"
        : days !== null && days <= 14
          ? "bg-amber-50 text-amber-800"
          : "bg-slate-100 text-slate-700";
    const headline =
      days === null
        ? deadlineLabel
        : days < 0
          ? `Overdue by ${Math.abs(days)} ${
              Math.abs(days) === 1 ? "day" : "days"
            }`
          : days === 0
            ? "Due today"
            : `Due in ${days} ${days === 1 ? "day" : "days"}`;
    deadlineChip = (
      <div
        className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${tone}`}
      >
        <Clock className="h-3.5 w-3.5" />
        {headline}
        <span className="font-normal opacity-70">· {deadlineLabel}</span>
      </div>
    );
  } else if (deadlineIsActive) {
    deadlineChip = (
      <div className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
        No deadline set
      </div>
    );
  }

  const standards = project.standard_codes ?? [];
  const canCollect =
    project.status !== "draft" &&
    (project.setup_health?.assignments_total ?? 0) > 0;

  return (
    <Card className="overflow-hidden p-0">
      <CardContent className="p-0">
        {/* Header */}
        <div className="flex items-start justify-between gap-6 border-b border-slate-100 px-6 pt-5 pb-4">
          <div className="flex items-start gap-5">
            <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
              <svg className="h-20 w-20 -rotate-90" viewBox="0 0 80 80">
                <circle
                  cx="40"
                  cy="40"
                  r="34"
                  stroke="#e2e8f0"
                  strokeWidth="7"
                  fill="none"
                />
                <circle
                  cx="40"
                  cy="40"
                  r="34"
                  stroke={ringColor}
                  strokeWidth="7"
                  fill="none"
                  strokeLinecap="round"
                  strokeDasharray={ringCircumference}
                  strokeDashoffset={ringOffset}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-lg font-bold text-slate-900">
                  {stepsDone}
                </div>
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  of {stepsTotal}
                </div>
              </div>
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/projects/${project.id}/settings`}
                  className="text-xl font-bold text-slate-900 hover:underline"
                >
                  {project.name}
                </Link>
                <span
                  className={`rounded-md px-2 py-0.5 text-[11px] font-medium ${badge.classes}`}
                >
                  {badge.label}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-500">
                {project.reporting_year && (
                  <span className="inline-flex items-center gap-1">
                    <CalendarDays className="h-3.5 w-3.5" />
                    Reporting year {project.reporting_year}
                  </span>
                )}
                <span className="inline-flex items-center gap-1">
                  <span className="text-slate-300">#</span>ID {project.id}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                {deadlineChip}
                <div className="text-xs text-slate-500">
                  Setup{" "}
                  <span className="font-semibold text-slate-700">
                    {setupPct}%
                  </span>{" "}
                  complete
                </div>
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-slate-400 hover:text-slate-600"
            onClick={() => router.push(`/projects/${project.id}/settings`)}
            title="Project settings"
          >
            <MoreHorizontal className="h-5 w-5" />
          </Button>
        </div>

        {/* Setup health grid */}
        <div className="grid grid-cols-1 divide-y divide-slate-100 border-b border-slate-100 text-sm sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4">
          {steps.map((step, idx) => (
            <Link
              key={step.key}
              href={step.href}
              className={`group flex items-center justify-between px-6 py-4 hover:bg-slate-50 ${
                idx % 2 === 0 ? "sm:border-r sm:border-slate-100 lg:border-r" : ""
              } ${
                idx < 2 ? "sm:border-b sm:border-slate-100 lg:border-b-0" : ""
              } ${
                idx === 2 ? "lg:border-r lg:border-slate-100" : ""
              }`}
            >
              <div className="flex items-start gap-3">
                {stepIcon(step.tone)}
                <div>
                  <div className="font-medium text-slate-900">{step.label}</div>
                  <div
                    className={`mt-0.5 text-xs ${
                      step.tone === "warn"
                        ? "text-amber-700"
                        : step.tone === "done"
                          ? "text-slate-500"
                          : "text-slate-400"
                    }`}
                  >
                    {step.subtitle}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {step.trailing}
                <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-slate-600" />
              </div>
            </Link>
          ))}
        </div>

        {/* Standards chip row */}
        {standards.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-6 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Standards
            </div>
            {standards.slice(0, 10).map((code) => (
              <span
                key={code}
                className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700"
              >
                {code}
              </span>
            ))}
            {standards.length > 10 && (
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">
                +{standards.length - 10}
              </span>
            )}
          </div>
        )}

        {/* Entry points */}
        <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50/60 px-6 py-4">
          <div className="text-xs text-slate-500">
            {canCollect
              ? "Jump into work"
              : "Finish setup to start collecting data"}
          </div>
          <div className="flex flex-wrap gap-2">
            {canCollect && (
              <>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/collection?projectId=${project.id}`}>
                    <ClipboardList className="h-4 w-4" />
                    Collection
                  </Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/evidence?projectId=${project.id}`}>
                    <Search className="h-4 w-4" />
                    Evidence
                  </Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link href={`/projects/${project.id}/settings?tab=team`}>
                    <Users className="h-4 w-4" />
                    Assignments
                  </Link>
                </Button>
              </>
            )}
            <Button size="sm" asChild>
              <Link href={`/projects/${project.id}/settings`}>
                {canCollect ? "Open project" : "Continue setup"}
                <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [tab, setTab] = useState<"active" | "archived">("active");

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");
  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) =>
    ["admin", "esg_manager", "platform_admin"].includes(role)
  );

  const { data, isLoading, error } = useApiQuery<ProjectsResponse>(
    ["projects"],
    "/projects?page_size=100",
    { enabled: canAccess }
  );

  const createMutation = useApiMutation<Project, CreateProjectPayload>(
    "/projects",
    "POST",
    {
      onMutate: () => {
        setActionError(null);
      },
      onSuccess: (project) => {
        queryClient.setQueryData<ProjectsResponse>(["projects"], (current) =>
          current
            ? {
                ...current,
                items: [
                  project,
                  ...current.items.filter((item) => item.id !== project.id),
                ],
                total:
                  current.total +
                  (current.items.some((item) => item.id === project.id)
                    ? 0
                    : 1),
              }
            : { items: [project], total: 1 }
        );
        setDialogOpen(false);
        setNewProjectName("");
      },
      onError: (error) => {
        setActionError(
          error.message || "Unable to create project. Please try again."
        );
      },
    }
  );

  const handleCreate = () => {
    if (!newProjectName.trim() || createMutation.isPending) return;
    setActionError(null);
    createMutation.mutate({ name: newProjectName.trim() });
  };

  const projects = useMemo(() => data?.items ?? [], [data]);
  const { activeProjects, archivedProjects } = useMemo(() => {
    const active: Project[] = [];
    const archived: Project[] = [];
    for (const project of projects) {
      if (ARCHIVED_STATUSES.has(project.status)) archived.push(project);
      else active.push(project);
    }
    return { activeProjects: active, archivedProjects: archived };
  }, [projects]);

  const visibleProjects = tab === "active" ? activeProjects : archivedProjects;
  const accessDenied =
    (Boolean(me) && !canAccess) || (!!error && isForbidden(error));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Projects</h2>
          <p className="mt-1 text-sm text-slate-500">
            Configure your reporting projects and jump into the work.
          </p>
        </div>
        {!accessDenied && (
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Project
          </Button>
        )}
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Tabs */}
      {!accessDenied &&
        !meLoading &&
        !isLoading &&
        !error &&
        projects.length > 0 && (
          <div className="flex items-center gap-6 border-b border-slate-200">
            <button
              onClick={() => setTab("active")}
              className={`-mb-px border-b-2 px-1 py-2 text-sm font-medium transition-colors ${
                tab === "active"
                  ? "border-cyan-700 text-cyan-800"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              Active{" "}
              <span
                className={`ml-1 rounded-full px-1.5 py-0.5 text-[11px] ${
                  tab === "active"
                    ? "bg-cyan-50 text-cyan-800"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {activeProjects.length}
              </span>
            </button>
            <button
              onClick={() => setTab("archived")}
              className={`-mb-px border-b-2 px-1 py-2 text-sm font-medium transition-colors ${
                tab === "archived"
                  ? "border-cyan-700 text-cyan-800"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              Archived{" "}
              <span
                className={`ml-1 rounded-full px-1.5 py-0.5 text-[11px] ${
                  tab === "archived"
                    ? "bg-cyan-50 text-cyan-800"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {archivedProjects.length}
              </span>
            </button>
          </div>
        )}

      {/* Content */}
      {meLoading || isLoading ? (
        <div className="flex min-h-[300px] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
        </div>
      ) : accessDenied ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Only admin and ESG manager roles can access project management.
            </p>
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load projects. Please try again later.
            </p>
          </CardContent>
        </Card>
      ) : projects.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <FolderOpen className="mb-4 h-12 w-12 text-slate-300" />
            <p className="text-lg font-medium text-slate-600">
              No projects yet
            </p>
            <p className="mt-1 text-sm text-slate-400">
              Create your first project to get started with ESG reporting.
            </p>
            <Button className="mt-4" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4" />
              Create Project
            </Button>
          </CardContent>
        </Card>
      ) : visibleProjects.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <FolderOpen className="mb-4 h-10 w-10 text-slate-300" />
            <p className="text-sm text-slate-500">
              {tab === "active" ? "No active projects." : "No archived projects."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {visibleProjects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      {/* Create Project Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <Input
              label="Project Name"
              placeholder="e.g. 2025 Sustainability Report"
              value={newProjectName}
              onChange={(e) => setNewProjectName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
              }}
            />
            {createMutation.error && (
              <p className="text-sm text-red-500">
                {createMutation.error.message}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDialogOpen(false);
                setNewProjectName("");
                setActionError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!newProjectName.trim() || createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" />
              )}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
