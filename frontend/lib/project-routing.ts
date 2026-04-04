"use client";

export interface ProjectSummary {
  id: number;
  name: string;
  status: "draft" | "active" | "review" | "published";
  reporting_year?: number | null;
}

export interface ProjectsResponse {
  items: ProjectSummary[];
  total: number;
}

const PROJECT_SCOPED_PATHS = new Set([
  "/dashboard",
  "/collection",
  "/evidence",
  "/merge",
  "/completeness",
  "/report",
]);

export function parseProjectId(value: string | null): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function resolveActiveProject(
  projects: ProjectSummary[],
  requestedProjectId: number | null
): ProjectSummary | null {
  if (requestedProjectId != null) {
    const exactMatch = projects.find((project) => project.id === requestedProjectId);
    if (exactMatch) return exactMatch;
  }

  return projects[0] ?? null;
}

export function isProjectScopedPath(path: string): boolean {
  return PROJECT_SCOPED_PATHS.has(path);
}

export function withProjectId(path: string, projectId: number | null | undefined): string {
  if (!projectId) return path;

  const [pathname, queryString = ""] = path.split("?");
  const params = new URLSearchParams(queryString);
  params.set("projectId", String(projectId));

  const nextQuery = params.toString();
  return nextQuery ? `${pathname}?${nextQuery}` : pathname;
}
