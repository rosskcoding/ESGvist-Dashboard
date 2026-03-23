"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  Settings,
  ShieldAlert,
} from "lucide-react";

interface Project {
  id: number;
  name: string;
  status: "draft" | "active" | "review" | "published";
  standards?: string[];
  standard_codes?: string[];
  completion_percentage?: number;
  deadline?: string | null;
  created_at?: string;
  reporting_year?: number;
}

interface ProjectsResponse {
  items: Project[];
  total: number;
}

interface CreateProjectPayload {
  name: string;
  description?: string;
}

const statusConfig: Record<
  Project["status"],
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

export default function ProjectsPage() {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me", "projects"], "/auth/me");
  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) =>
    ["admin", "esg_manager", "platform_admin"].includes(role)
  );

  const { data, isLoading, error, refetch } = useApiQuery<ProjectsResponse>(
    ["projects"],
    "/projects?page_size=100",
    { enabled: canAccess }
  );

  const createMutation = useApiMutation<Project, CreateProjectPayload>(
    "/projects",
    "POST",
    {
      onSuccess: () => {
        setDialogOpen(false);
        setNewProjectName("");
        refetch();
      },
    }
  );

  const handleCreate = () => {
    if (!newProjectName.trim()) return;
    createMutation.mutate({ name: newProjectName.trim() });
  };

  const projects = data?.items ?? [];
  const accessDenied = (Boolean(me) && !canAccess) || (!!error && isForbidden(error));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Projects</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage your ESG reporting projects
          </p>
        </div>
        {!accessDenied && (
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Project
          </Button>
        )}
      </div>

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
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>All Projects</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Standards</TableHead>
                  <TableHead>Completion</TableHead>
                  <TableHead>Deadline</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((project) => {
                  const status = statusConfig[project.status];
                  return (
                    <TableRow
                      key={project.id}
                      className="cursor-pointer"
                      onClick={() =>
                        router.push(`/projects/${project.id}/settings`)
                      }
                    >
                      <TableCell className="font-medium">
                        {project.name}
                      </TableCell>
                      <TableCell>
                        <Badge variant={status.variant}>{status.label}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {(project.standards || project.standard_codes || []).length > 0 ? (
                            (project.standards || project.standard_codes || []).map((std: string) => (
                              <Badge
                                key={std}
                                variant="outline"
                                className="text-xs"
                              >
                                {std}
                              </Badge>
                            ))
                          ) : (
                            <span className="text-xs text-slate-400">
                              None
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress
                            value={(project.completion_percentage ?? 0)}
                            className="w-20"
                            indicatorClassName={
                              (project.completion_percentage ?? 0) >= 80
                                ? "bg-green-500"
                                : (project.completion_percentage ?? 0) >= 50
                                  ? "bg-amber-500"
                                  : "bg-blue-600"
                            }
                          />
                          <span className="text-sm text-slate-600">
                            {Math.round((project.completion_percentage ?? 0))}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {project.deadline ? (
                          <span className="text-sm">
                            {new Date(project.deadline).toLocaleDateString()}
                          </span>
                        ) : (
                          <span className="text-sm text-slate-400">--</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/projects/${project.id}/settings`);
                          }}
                        >
                          <Settings className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
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
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={
                !newProjectName.trim() || createMutation.isPending
              }
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
