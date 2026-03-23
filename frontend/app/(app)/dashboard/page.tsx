"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import {
  BarChart3,
  CheckCircle2,
  Clock,
  AlertTriangle,
  FileText,
  Activity,
  Globe,
  Loader2,
} from "lucide-react";

interface StandardProgress {
  standard_id: number;
  standard_name: string;
  code: string;
  total_disclosures: number;
  completed_disclosures: number;
  completion_percentage: number;
}

interface BoundarySummary {
  boundary_id: number | null;
  boundary_name: string;
  entities_in_scope: number;
  excluded_entities: number;
  snapshot_status: "locked" | "draft" | "not_created";
}

interface AuditLogEntry {
  id: number;
  action: string;
  user_name: string;
  created_at: string;
  details: string;
}

interface PriorityTask {
  id: number;
  title: string;
  due_date: string;
  status: "overdue" | "upcoming";
  assignee: string;
  disclosure_code: string;
}

interface DashboardProgress {
  overall_completion: number;
  data_points_submitted: number;
  data_points_total: number;
  overdue_assignments: number;
  pending_reviews: number;
  standards: StandardProgress[];
  boundary: BoundarySummary;
  recent_activity: AuditLogEntry[];
  priority_tasks: PriorityTask[];
}

export default function DashboardPage() {
  const [projectId] = useState(1);

  const { data, isLoading, error } = useApiQuery<DashboardProgress>(
    ["dashboard", "progress", projectId],
    `/dashboard/projects/${projectId}/progress`
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Dashboard</h2>
          <p className="mt-1 text-sm text-slate-500">
            ESGvist reporting overview
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load dashboard data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const progress = data ?? {
    overall_completion: 0,
    data_points_submitted: 0,
    data_points_total: 0,
    overdue_assignments: 0,
    pending_reviews: 0,
    standards: [],
    boundary: {
      boundary_id: null,
      boundary_name: "No boundary selected",
      entities_in_scope: 0,
      excluded_entities: 0,
      snapshot_status: "not_created" as const,
    },
    recent_activity: [],
    priority_tasks: [],
  };

  const overdueTasks = progress.priority_tasks.filter(
    (t) => t.status === "overdue"
  );
  const upcomingTasks = progress.priority_tasks.filter(
    (t) => t.status === "upcoming"
  );

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Dashboard</h2>
        <p className="mt-1 text-sm text-slate-500">
          ESGvist reporting overview for Project #{projectId}
        </p>
      </div>

      {/* Top metric cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Overall Completion */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Overall Completion
            </CardDescription>
            <BarChart3 className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {Math.round(progress.overall_completion)}%
            </div>
            <Progress
              value={progress.overall_completion}
              className="mt-3"
              indicatorClassName="bg-blue-600"
            />
          </CardContent>
        </Card>

        {/* Data Points */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Data Points
            </CardDescription>
            <CheckCircle2 className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {progress.data_points_submitted}
              <span className="text-lg font-normal text-slate-400">
                {" "}
                / {progress.data_points_total}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">submitted</p>
          </CardContent>
        </Card>

        {/* Overdue Assignments */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Overdue Assignments
            </CardDescription>
            <AlertTriangle
              className={cn(
                "h-4 w-4",
                progress.overdue_assignments > 0
                  ? "text-red-500"
                  : "text-slate-500"
              )}
            />
          </CardHeader>
          <CardContent>
            <div
              className={cn(
                "text-3xl font-bold",
                progress.overdue_assignments > 0
                  ? "text-red-600"
                  : "text-slate-900"
              )}
            >
              {progress.overdue_assignments}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {progress.overdue_assignments > 0
                ? "require attention"
                : "all on track"}
            </p>
          </CardContent>
        </Card>

        {/* Pending Reviews */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Pending Reviews
            </CardDescription>
            <FileText className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {progress.pending_reviews}
            </div>
            <p className="mt-1 text-xs text-slate-500">awaiting review</p>
          </CardContent>
        </Card>
      </div>

      {/* Completion by Standard + Boundary Summary */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Completion by Standard */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Completion by Standard</CardTitle>
            <CardDescription>
              Progress across reporting frameworks
            </CardDescription>
          </CardHeader>
          <CardContent>
            {progress.standards.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-400">
                No standards attached to this project yet.
              </p>
            ) : (
              <div className="space-y-5">
                {progress.standards.map((std) => (
                  <div key={std.standard_id} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {std.code}
                        </span>
                        <span className="text-sm text-slate-500">
                          {std.standard_name}
                        </span>
                      </div>
                      <span className="text-sm font-semibold">
                        {Math.round(std.completion_percentage)}%
                      </span>
                    </div>
                    <Progress
                      value={std.completion_percentage}
                      indicatorClassName={cn(
                        std.completion_percentage >= 80
                          ? "bg-green-500"
                          : std.completion_percentage >= 50
                            ? "bg-amber-500"
                            : "bg-blue-600"
                      )}
                    />
                    <p className="text-xs text-slate-400">
                      {std.completed_disclosures} / {std.total_disclosures}{" "}
                      disclosures complete
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Boundary Summary */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe className="h-4 w-4" />
              Boundary Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm text-slate-500">Selected Boundary</p>
              <div className="mt-1 flex items-center gap-2">
                <span className="font-medium">
                  {progress.boundary.boundary_name}
                </span>
                <Badge
                  variant={
                    progress.boundary.snapshot_status === "locked"
                      ? "default"
                      : progress.boundary.snapshot_status === "draft"
                        ? "warning"
                        : "secondary"
                  }
                >
                  {progress.boundary.snapshot_status === "not_created"
                    ? "No Snapshot"
                    : progress.boundary.snapshot_status}
                </Badge>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border border-slate-100 p-3">
                <p className="text-2xl font-bold">
                  {progress.boundary.entities_in_scope}
                </p>
                <p className="text-xs text-slate-500">In scope</p>
              </div>
              <div className="rounded-lg border border-slate-100 p-3">
                <p className="text-2xl font-bold">
                  {progress.boundary.excluded_entities}
                </p>
                <p className="text-xs text-slate-500">Excluded</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Activity + Priority Tasks */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Recent Activity
            </CardTitle>
            <CardDescription>Last 5 audit log entries</CardDescription>
          </CardHeader>
          <CardContent>
            {progress.recent_activity.length === 0 ? (
              <p className="py-4 text-center text-sm text-slate-400">
                No recent activity.
              </p>
            ) : (
              <div className="space-y-3">
                {progress.recent_activity.slice(0, 5).map((entry) => (
                  <div
                    key={entry.id}
                    className="flex items-start gap-3 rounded-lg border border-slate-100 p-3"
                  >
                    <div className="mt-0.5 rounded-full bg-slate-100 p-1.5">
                      <Activity className="h-3 w-3 text-slate-600" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <p className="text-sm">
                        <span className="font-medium">{entry.user_name}</span>{" "}
                        {entry.action}
                      </p>
                      {entry.details && (
                        <p className="text-xs text-slate-500">
                          {entry.details}
                        </p>
                      )}
                      <p className="text-xs text-slate-400">
                        {new Date(entry.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Priority Tasks */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Priority Tasks
            </CardTitle>
            <CardDescription>Overdue and upcoming deadlines</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Overdue */}
            {overdueTasks.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant="destructive">{overdueTasks.length}</Badge>
                  <span className="text-sm font-medium text-red-600">
                    Overdue
                  </span>
                </div>
                <div className="space-y-2">
                  {overdueTasks.map((task) => (
                    <div
                      key={task.id}
                      className="rounded-lg border border-red-200 bg-red-50 p-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">
                          {task.disclosure_code}
                        </span>
                        <span className="text-xs text-red-600">
                          Due {new Date(task.due_date).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">
                        {task.title}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        Assigned to {task.assignee}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Upcoming */}
            {upcomingTasks.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <Badge variant="secondary">{upcomingTasks.length}</Badge>
                  <span className="text-sm font-medium">Upcoming</span>
                </div>
                <div className="space-y-2">
                  {upcomingTasks.map((task) => (
                    <div
                      key={task.id}
                      className="rounded-lg border border-slate-200 p-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">
                          {task.disclosure_code}
                        </span>
                        <span className="text-xs text-slate-500">
                          Due {new Date(task.due_date).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-600">
                        {task.title}
                      </p>
                      <p className="mt-0.5 text-xs text-slate-400">
                        Assigned to {task.assignee}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {overdueTasks.length === 0 && upcomingTasks.length === 0 && (
              <p className="py-4 text-center text-sm text-slate-400">
                No priority tasks at this time.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
