"use client";

import { useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { useApiQuery } from "@/lib/hooks/use-api";
import {
  parseProjectId,
  resolveActiveProject,
  withProjectId,
  type ProjectSummary,
  type ProjectsResponse,
} from "@/lib/project-routing";

export function useActiveProject(queryScope: string, enabled = true) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsString = searchParams.toString();
  const requestedProjectId = parseProjectId(searchParams.get("projectId"));

  const {
    data: projectsData,
    isLoading,
    error,
  } = useApiQuery<ProjectsResponse>(["projects", queryScope], "/projects?page_size=100", { enabled });

  const projects = projectsData?.items ?? [];
  const activeProject = useMemo(
    () => resolveActiveProject(projects, requestedProjectId),
    [projects, requestedProjectId]
  );
  const projectId = activeProject?.id ?? null;

  useEffect(() => {
    if (!enabled || isLoading || !pathname || projectId == null) return;
    if (requestedProjectId === projectId) return;

    router.replace(
      withProjectId(`${pathname}${searchParamsString ? `?${searchParamsString}` : ""}`, projectId)
    );
  }, [enabled, isLoading, pathname, projectId, requestedProjectId, router, searchParamsString]);

  return {
    projects,
    activeProject: activeProject as ProjectSummary | null,
    projectId,
    isLoading,
    error,
  };
}
