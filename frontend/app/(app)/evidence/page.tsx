"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { triggerFileDownload } from "@/lib/download";
import { AIEvidenceGuidance } from "@/components/ai-inline-explain";
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
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Loader2,
  AlertTriangle,
  FileText,
  Link2,
  Upload,
  Trash2,
  Eye,
  Download,
  Plus,
  FileUp,
  Search,
  ExternalLink,
  ShieldAlert,
} from "lucide-react";

const EVIDENCE_FILE_ACCEPT =
  ".pdf,.json,.xlsx,.docx,.csv,.png,.jpg,.jpeg,application/pdf,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/csv,image/png,image/jpeg";

// ---------- Types ----------

interface LinkedDataPoint {
  data_point_id: number;
  code: string;
  label: string;
}

interface LinkedRequirement {
  requirement_item_id: number;
  code: string;
  description: string;
}

interface EvidenceItem {
  id: number;
  type: "file" | "link";
  title: string;
  description: string | null;
  url?: string;
  file_name?: string;
  file_size?: number;
  mime_type?: string;
  upload_date: string;
  created_by?: number | null;
  created_by_name?: string | null;
  binding_status: "bound" | "unbound";
  linked_data_points: LinkedDataPoint[];
  linked_requirement_items: LinkedRequirement[];
}

interface EvidenceResponse {
  items: EvidenceItem[];
  total: number;
}

interface ProjectItem {
  id: number;
  name: string;
}

interface ProjectsResponse {
  items: ProjectItem[];
  total: number;
}

interface AssignmentRow {
  id: number;
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  entity_id: number | null;
  entity_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
}

interface AssignmentMatrixResponse {
  assignments: AssignmentRow[];
}

interface ProjectDataPoint {
  id: number;
  shared_element_id: number;
  entity_id: number | null;
  facility_id: number | null;
}

interface ProjectDataPointsResponse {
  items: ProjectDataPoint[];
  total: number;
}

interface LinkCandidate {
  key: string;
  shared_element_id: number;
  entity_id: number | null;
  facility_id: number | null;
  data_point_id: number | null;
  metric_code: string;
  metric_name: string;
  entity_name: string | null;
  facility_name: string | null;
}

// ---------- Helpers ----------

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function getBindingLabel(status: EvidenceItem["binding_status"]): string {
  return status === "bound" ? "Linked" : "Not linked";
}

function buildAssignmentContextKey(
  sharedElementId: number,
  entityId: number | null,
  facilityId: number | null
) {
  return `${sharedElementId}:${entityId ?? 0}:${facilityId ?? 0}`;
}

async function fetchAllProjectDataPoints(projectId: number) {
  const pageSize = 100;
  let page = 1;
  const items: ProjectDataPoint[] = [];

  while (true) {
    const response = await api.get<ProjectDataPointsResponse>(
      `/projects/${projectId}/data-points?page=${page}&page_size=${pageSize}`
    );
    items.push(...response.items);
    if (response.items.length < pageSize || items.length >= response.total) {
      break;
    }
    page += 1;
  }

  return items;
}

// ---------- Component ----------

export default function EvidencePage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [typeFilter, setTypeFilter] = useState("");
  const [bindingFilter, setBindingFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<EvidenceItem | null>(null);
  const [detailTarget, setDetailTarget] = useState<EvidenceItem | null>(null);
  const [autoOpenedEvidenceId, setAutoOpenedEvidenceId] = useState<number | null>(null);
  const [addLinkOpen, setAddLinkOpen] = useState(false);
  const [linkTitle, setLinkTitle] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkDescription, setLinkDescription] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [linkProjectId, setLinkProjectId] = useState("");
  const [linkSearch, setLinkSearch] = useState("");
  const [isLinking, setIsLinking] = useState(false);
  const [unlinkingDataPointId, setUnlinkingDataPointId] = useState<number | null>(null);

  const { data: me, isLoading: meLoading } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me"], "/auth/me");
  const role = me?.roles?.[0]?.role ?? "";
  const isReviewer = role === "reviewer";
  const canManageEvidence = !["auditor", "reviewer"].includes(role);

  const { data, isLoading, error } = useApiQuery<EvidenceResponse>(
    ["evidence"],
    "/evidences",
    { enabled: !isReviewer }
  );
  const { data: projectsData } = useApiQuery<ProjectsResponse>(
    ["projects", "evidence-link"],
    "/projects?page_size=100",
    { enabled: !isReviewer }
  );
  const evidenceIdFromQuery = useMemo(() => {
    const value = searchParams.get("evidenceId");
    if (!value) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }, [searchParams]);
  const { data: requestedEvidence } = useApiQuery<EvidenceItem>(
    ["evidence-detail-direct", evidenceIdFromQuery],
    `/evidences/${evidenceIdFromQuery ?? 0}`,
    { enabled: !isReviewer && Boolean(evidenceIdFromQuery) }
  );
  const selectedProjectId = Number(linkProjectId) || null;
  const { data: assignmentsData, isLoading: assignmentsLoading } =
    useApiQuery<AssignmentMatrixResponse>(
      ["evidence-link-assignments", selectedProjectId],
      `/projects/${selectedProjectId ?? 0}/assignments`,
      {
        enabled:
          !isReviewer &&
          canManageEvidence &&
          Boolean(detailTarget) &&
          Boolean(selectedProjectId),
      }
    );
  const { data: projectDataPoints, isLoading: dataPointsLoading } = useQuery<
    ProjectDataPoint[],
    Error
  >({
    queryKey: ["evidence-link-data-points", selectedProjectId],
    queryFn: () => fetchAllProjectDataPoints(selectedProjectId as number),
    enabled:
      !isReviewer &&
      canManageEvidence &&
      Boolean(detailTarget) &&
      Boolean(selectedProjectId),
  });

  const syncEvidenceCache = useCallback(
    (updater: (current: EvidenceResponse | undefined) => EvidenceResponse | undefined) => {
      queryClient.setQueryData<EvidenceResponse>(["evidence"], updater);
    },
    [queryClient]
  );

  const upsertEvidenceCache = useCallback(
    (item: EvidenceItem) => {
      syncEvidenceCache((current) => {
        if (!current) {
          return { items: [item], total: 1 };
        }
        const existingIndex = current.items.findIndex((entry) => entry.id === item.id);
        if (existingIndex === -1) {
          return {
            ...current,
            items: [item, ...current.items],
            total: current.total + 1,
          };
        }
        const items = [...current.items];
        items[existingIndex] = { ...items[existingIndex], ...item };
        return { ...current, items };
      });
    },
    [syncEvidenceCache]
  );

  const removeEvidenceFromCache = useCallback(
    (evidenceId: number) => {
      syncEvidenceCache((current) => {
        if (!current) return current;
        const items = current.items.filter((item) => item.id !== evidenceId);
        if (items.length === current.items.length) {
          return current;
        }
        return {
          ...current,
          items,
          total: Math.max(0, current.total - 1),
        };
      });
      setDeleteTarget((current) => (current?.id === evidenceId ? null : current));
      setDetailTarget((current) => (current?.id === evidenceId ? null : current));
    },
    [syncEvidenceCache]
  );

  const uploadMutation = useMutation<EvidenceItem, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name);
      formData.append("description", "Uploaded from evidence repository");
      return api.upload<EvidenceItem>("/evidences/upload", formData);
    },
    onMutate: () => {
      setActionError(null);
    },
    onSuccess: (item) => {
      upsertEvidenceCache(item);
    },
    onError: (error) => {
      setActionError(error.message || "Failed to upload evidence. Please try again.");
    },
  });

  const addLinkMutation = useApiMutation<
    EvidenceItem,
    { title: string; url: string; description: string; type: "link" }
  >("/evidences", "POST", {
    onMutate: () => {
      setActionError(null);
    },
    onSuccess: (item) => {
      setAddLinkOpen(false);
      setLinkTitle("");
      setLinkUrl("");
      setLinkDescription("");
      upsertEvidenceCache(item);
    },
    onError: (error) => {
      setActionError(error.message || "Failed to add evidence link. Please try again.");
    },
  });

  const items = data?.items ?? [];
  const accessDenied =
    isReviewer ||
    ((error as Error & { code?: string } | null)?.code === "FORBIDDEN") ||
    /not allowed|access denied|forbidden/i.test((error as Error | null)?.message || "");

  const filteredItems = useMemo(() => {
    let result = items;

    if (typeFilter) {
      result = result.filter((i) => i.type === typeFilter);
    }

    if (bindingFilter) {
      result = result.filter((i) => i.binding_status === bindingFilter);
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          (i.description ?? "").toLowerCase().includes(q) ||
          (i.file_name && i.file_name.toLowerCase().includes(q))
      );
    }

    return result;
  }, [items, typeFilter, bindingFilter, searchQuery]);

  const projects = projectsData?.items ?? [];

  const clearEvidenceIdParam = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete("evidenceId");
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname, { scroll: false });
  }, [pathname, router, searchParams]);

  const closeDetailDrawer = useCallback(() => {
    setDetailTarget(null);
    setAutoOpenedEvidenceId(null);
    if (evidenceIdFromQuery) {
      clearEvidenceIdParam();
    }
  }, [clearEvidenceIdParam, evidenceIdFromQuery]);

  useEffect(() => {
    if (!detailTarget) return;
    if (linkProjectId) return;
    const requestedProjectId = Number(searchParams.get("projectId") ?? "");
    if (requestedProjectId) {
      setLinkProjectId(String(requestedProjectId));
      return;
    }
    if (projects.length > 0) {
      setLinkProjectId(String(projects[0].id));
    }
  }, [detailTarget, linkProjectId, projects, searchParams]);

  const linkedDataPointIdSet = useMemo(
    () => new Set((detailTarget?.linked_data_points ?? []).map((item) => item.data_point_id)),
    [detailTarget]
  );

  const linkCandidates = useMemo(() => {
    const assignments = assignmentsData?.assignments ?? [];
    const dataPoints = projectDataPoints ?? [];
    const dataPointsByContext = new Map<string, ProjectDataPoint>();

    for (const dataPoint of dataPoints) {
      dataPointsByContext.set(
        buildAssignmentContextKey(
          dataPoint.shared_element_id,
          dataPoint.entity_id,
          dataPoint.facility_id
        ),
        dataPoint
      );
    }

    const query = linkSearch.trim().toLowerCase();
    const candidates: LinkCandidate[] = assignments.map((assignment) => {
      const contextKey = buildAssignmentContextKey(
        assignment.shared_element_id,
        assignment.entity_id,
        assignment.facility_id
      );
      const existingDataPoint = dataPointsByContext.get(contextKey);
      return {
        key: contextKey,
        shared_element_id: assignment.shared_element_id,
        entity_id: assignment.entity_id,
        facility_id: assignment.facility_id,
        data_point_id: existingDataPoint?.id ?? null,
        metric_code: assignment.shared_element_code,
        metric_name: assignment.shared_element_name,
        entity_name: assignment.entity_name,
        facility_name: assignment.facility_name,
      };
    });

    return candidates
      .filter((candidate) => !linkedDataPointIdSet.has(candidate.data_point_id ?? -1))
      .filter((candidate) => {
        if (!query) return true;
        return [
          candidate.metric_code,
          candidate.metric_name,
          candidate.entity_name ?? "",
          candidate.facility_name ?? "",
        ]
          .join(" ")
          .toLowerCase()
          .includes(query);
      })
      .slice(0, 8);
  }, [assignmentsData?.assignments, linkSearch, linkedDataPointIdSet, projectDataPoints]);

  useEffect(() => {
    if (!evidenceIdFromQuery) return;
    if (autoOpenedEvidenceId === evidenceIdFromQuery) return;

    const existing = items.find((item) => item.id === evidenceIdFromQuery);
    if (existing) {
      setDetailTarget(existing);
      setAutoOpenedEvidenceId(evidenceIdFromQuery);
      return;
    }

    if (requestedEvidence) {
      setDetailTarget(requestedEvidence);
      setAutoOpenedEvidenceId(evidenceIdFromQuery);
    }
  }, [autoOpenedEvidenceId, evidenceIdFromQuery, items, requestedEvidence]);

  useEffect(() => {
    setLinkSearch("");
  }, [detailTarget?.id]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (!canManageEvidence) return;
      setActionError(null);
      const files = e.dataTransfer.files;
      for (let i = 0; i < files.length; i++) {
        uploadMutation.mutate(files[i]);
      }
    },
    [canManageEvidence, uploadMutation]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || !canManageEvidence) return;
      setActionError(null);
      for (let i = 0; i < files.length; i++) {
        uploadMutation.mutate(files[i]);
      }
      e.target.value = "";
    },
    [canManageEvidence, uploadMutation]
  );

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      setIsDeleting(true);
      setActionError(null);
      await api.delete(`/evidence/${deleteTarget.id}`);
      removeEvidenceFromCache(deleteTarget.id);
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : "Failed to delete evidence. Please try again."
      );
    } finally {
      setIsDeleting(false);
    }
  }, [deleteTarget, removeEvidenceFromCache]);

  const refreshEvidenceDetail = useCallback(
    async (evidenceId: number) => {
      const refreshed = await api.get<EvidenceItem>(`/evidences/${evidenceId}`);
      upsertEvidenceCache(refreshed);
      setDetailTarget(refreshed);
      return refreshed;
    },
    [upsertEvidenceCache]
  );

  const handleLinkToMetric = useCallback(
    async (candidate: LinkCandidate) => {
      if (!detailTarget || !selectedProjectId) return;

      try {
        setIsLinking(true);
        setActionError(null);
        let dataPointId = candidate.data_point_id;

        if (!dataPointId) {
          const created = await api.post<{ id: number }>(`/projects/${selectedProjectId}/data-points`, {
            shared_element_id: candidate.shared_element_id,
            entity_id: candidate.entity_id ?? undefined,
            facility_id: candidate.facility_id ?? undefined,
          });
          dataPointId = created.id;
        }

        await api.post(`/data-points/${dataPointId}/evidences`, {
          evidence_id: detailTarget.id,
        });

        await refreshEvidenceDetail(detailTarget.id);
        await queryClient.invalidateQueries({ queryKey: ["evidence"] });
        await queryClient.invalidateQueries({ queryKey: ["evidence-link-data-points", selectedProjectId] });
        await queryClient.invalidateQueries({ queryKey: ["data-points", selectedProjectId] });
        await queryClient.invalidateQueries({ queryKey: ["collection-assignments", selectedProjectId] });
      } catch (error) {
        setActionError(
          error instanceof Error ? error.message : "Unable to link this evidence to the selected metric."
        );
      } finally {
        setIsLinking(false);
      }
    },
    [detailTarget, queryClient, refreshEvidenceDetail, selectedProjectId]
  );

  const handleUnlinkFromMetric = useCallback(
    async (dataPointId: number) => {
      if (!detailTarget) return;

      try {
        setUnlinkingDataPointId(dataPointId);
        setActionError(null);
        await api.delete(`/data-points/${dataPointId}/evidences/${detailTarget.id}`);
        await refreshEvidenceDetail(detailTarget.id);
        if (selectedProjectId) {
          await queryClient.invalidateQueries({ queryKey: ["data-points", selectedProjectId] });
          await queryClient.invalidateQueries({ queryKey: ["collection-assignments", selectedProjectId] });
        }
        await queryClient.invalidateQueries({ queryKey: ["evidence"] });
      } catch (error) {
        setActionError(
          error instanceof Error ? error.message : "Unable to unlink this evidence from the selected metric."
        );
      } finally {
        setUnlinkingDataPointId(null);
      }
    },
    [detailTarget, queryClient, refreshEvidenceDetail, selectedProjectId]
  );

  // ---------- Render ----------

  if (meLoading || (!isReviewer && isLoading)) {
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
          <h2 className="text-2xl font-bold text-slate-900">
            Evidence Repository
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage supporting evidence for disclosures
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Reviewers cannot access the evidence repository.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">
            Evidence Repository
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage supporting evidence for disclosures
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load evidence data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
          <FileText className="h-6 w-6" />
          Evidence Repository
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage supporting evidence for disclosures
        </p>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {actionError}
        </div>
      )}

      {/* Upload section */}
      <Card>
        <CardContent className="py-4">
          {!canManageEvidence && (
            <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Auditor access is read-only. Upload, add link, and delete actions are disabled.
            </div>
          )}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
            {/* Drag and drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                "flex flex-1 flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors",
                isDragOver
                  ? "border-cyan-400 bg-cyan-50"
                  : "border-slate-300 bg-slate-50 hover:border-slate-400"
              )}
            >
              <FileUp className="mb-2 h-8 w-8 text-slate-400" />
              <p className="text-sm font-medium text-slate-600">
                Drag and drop files here
              </p>
              <p className="mt-1 text-xs text-slate-400">
                or click to browse files. Allowed: PDF, JSON, XLSX, DOCX, CSV, PNG, JPG.
              </p>
              <label className="mt-3 cursor-pointer">
                <input
                  type="file"
                  multiple
                  accept={EVIDENCE_FILE_ACCEPT}
                  className="hidden"
                  onChange={handleFileInput}
                  disabled={!canManageEvidence || uploadMutation.isPending}
                />
                <span className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
                  {uploadMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
                  ) : (
                    <Upload className="mr-1.5 h-3 w-3" />
                  )}
                  {uploadMutation.isPending ? "Uploading..." : "Browse Files"}
                </span>
              </label>
            </div>

            {/* Add link button */}
            <Button
              variant="outline"
              onClick={() => setAddLinkOpen(true)}
              className="shrink-0"
              disabled={!canManageEvidence || addLinkMutation.isPending || uploadMutation.isPending}
            >
              <Link2 className="mr-1.5 h-4 w-4" />
              Add Link
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 py-4">
          <div className="w-40">
            <Select
              label="Type"
              placeholder="All Types"
              value={typeFilter}
              onChange={setTypeFilter}
              options={[
                { value: "", label: "All Types" },
                { value: "file", label: "File" },
                { value: "link", label: "Link" },
              ]}
            />
          </div>
          <div className="w-44">
            <Select
              label="Link Status"
              placeholder="All"
              value={bindingFilter}
              onChange={setBindingFilter}
              options={[
                { value: "", label: "All" },
                { value: "bound", label: "Linked" },
                { value: "unbound", label: "Not linked" },
              ]}
            />
          </div>
          <div className="w-64">
            <Input
              label="Search"
              placeholder="Search evidence..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Evidence table */}
      <Card>
        <CardHeader>
          <CardTitle>Evidence Items</CardTitle>
          <CardDescription>
            {filteredItems.length} item{filteredItems.length !== 1 && "s"}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">Type</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="hidden md:table-cell">
                  Description
                </TableHead>
                <TableHead>Upload Date</TableHead>
                <TableHead className="hidden lg:table-cell">
                  Created By
                </TableHead>
                <TableHead className="text-center">Link status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredItems.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className="py-12 text-center text-sm text-slate-400"
                  >
                    No evidence records found.
                  </TableCell>
                </TableRow>
              ) : (
                filteredItems.map((item) => (
                  <TableRow
                    key={item.id}
                    className="cursor-pointer"
                    onClick={() => setDetailTarget(item)}
                  >
                    <TableCell>
                      {item.type === "file" ? (
                        <FileText className="h-4 w-4 text-cyan-500" />
                      ) : (
                        <Link2 className="h-4 w-4 text-emerald-500" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium">{item.title}</TableCell>
                    <TableCell className="hidden max-w-[200px] truncate text-sm text-slate-500 md:table-cell">
                      {item.description}
                    </TableCell>
                    <TableCell className="text-sm text-slate-500">
                      {formatDate(item.upload_date)}
                    </TableCell>
                    <TableCell className="hidden text-sm text-slate-500 lg:table-cell">
                      {item.created_by_name ?? "System"}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={
                          item.binding_status === "bound"
                            ? "success"
                            : "secondary"
                        }
                      >
                        {getBindingLabel(item.binding_status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div
                        className="flex items-center justify-end gap-1"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDetailTarget(item)}
                          title="View"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        {item.type === "file" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Download"
                            onClick={() => {
                              void triggerFileDownload(`/api/evidences/${item.id}/download`);
                            }}
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                        )}
                        {item.type === "link" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Open link"
                            onClick={() => {
                              if (item.url) window.open(item.url, "_blank");
                            }}
                          >
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteTarget(item)}
                          title="Delete"
                          disabled={!canManageEvidence || isDeleting}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Detail dialog */}
      <Dialog
        open={detailTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeDetailDrawer();
          }
        }}
      >
        <DialogContent
          className="inset-y-0 left-auto right-0 m-0 h-screen max-h-screen w-screen max-w-[min(1180px,100vw)] rounded-none border-y-0 border-r-0 border-l border-slate-200 bg-white shadow-2xl backdrop:bg-slate-950/35 backdrop:backdrop-blur-[2px]"
          contentClassName="flex h-full flex-col p-0"
          showCloseButton={false}
        >
          {detailTarget && (
            <>
              <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-5">
                <DialogHeader className="space-y-2">
                  <DialogTitle className="flex items-center gap-2 text-2xl font-semibold">
                    {detailTarget.type === "file" ? (
                      <FileText className="h-6 w-6 text-cyan-500" />
                    ) : (
                      <Link2 className="h-6 w-6 text-emerald-500" />
                    )}
                    <span className="truncate">{detailTarget.title}</span>
                  </DialogTitle>
                  <DialogDescription className="max-w-3xl text-base leading-7">
                    {detailTarget.description || "Review this evidence, manage links to metrics, and update supporting context."}
                  </DialogDescription>
                </DialogHeader>

                <div className="flex shrink-0 items-center gap-2">
                  {detailTarget.type === "file" ? (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        void triggerFileDownload(`/api/evidences/${detailTarget.id}/download`);
                      }}
                    >
                      <Download className="h-4 w-4" />
                      Download
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        if (detailTarget.url) window.open(detailTarget.url, "_blank");
                      }}
                    >
                      <ExternalLink className="h-4 w-4" />
                      Open link
                    </Button>
                  )}
                  <button
                    type="button"
                    className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
                    onClick={closeDetailDrawer}
                    aria-label="Close"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M18 6 6 18" />
                      <path d="m6 6 12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_320px]">
                <div className="min-h-0 overflow-y-auto px-6 py-5">
                  <div className="space-y-6">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Type
                        </div>
                        <div className="mt-2 text-base font-medium capitalize text-slate-900">
                          {detailTarget.type}
                        </div>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Link status
                        </div>
                        <div className="mt-2">
                          <Badge
                            variant={
                              detailTarget.binding_status === "bound"
                                ? "success"
                                : "secondary"
                            }
                            className="text-sm"
                          >
                            {getBindingLabel(detailTarget.binding_status)}
                          </Badge>
                        </div>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Upload date
                        </div>
                        <div className="mt-2 text-base font-medium text-slate-900">
                          {formatDate(detailTarget.upload_date)}
                        </div>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Created by
                        </div>
                        <div className="mt-2 text-base font-medium text-slate-900">
                          {detailTarget.created_by_name ?? "System"}
                        </div>
                      </div>
                    </div>

                    {detailTarget.binding_status === "unbound" && (
                      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                        This evidence is uploaded, but it is not linked to any metric yet.
                      </div>
                    )}

                    {detailTarget.type === "file" && detailTarget.file_name && (
                      <div className="rounded-xl border border-slate-200 bg-white p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          File
                        </div>
                        <div className="mt-2 text-base font-medium text-slate-900">
                          {detailTarget.file_name}
                        </div>
                        {detailTarget.file_size != null && (
                          <div className="mt-1 text-sm text-slate-500">
                            {formatFileSize(detailTarget.file_size)}
                          </div>
                        )}
                      </div>
                    )}

                    {detailTarget.type === "link" && detailTarget.url && (
                      <div className="rounded-xl border border-slate-200 bg-white p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Link
                        </div>
                        <a
                          href={detailTarget.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-2 inline-flex items-center gap-1 text-base font-medium text-cyan-700 hover:underline"
                        >
                          {detailTarget.url}
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </div>
                    )}

                    <section className="space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Linked Metrics
                          </h3>
                          <p className="mt-1 text-sm text-slate-500">
                            {(detailTarget.linked_data_points ?? []).length} linked metric contexts
                          </p>
                        </div>
                      </div>

                      {(detailTarget.linked_data_points ?? []).length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-200 px-4 py-5 text-sm text-slate-400">
                          No linked metrics yet.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {(detailTarget.linked_data_points ?? []).map((dp) => (
                            <div
                              key={dp.data_point_id}
                              className="grid gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 md:grid-cols-[minmax(0,1fr)_auto]"
                            >
                              <div className="min-w-0">
                                <div className="text-base font-medium text-slate-900">{dp.label}</div>
                                <div className="mt-1 break-all font-mono text-xs text-slate-500">
                                  {dp.code}
                                </div>
                              </div>
                              <div className="flex items-start justify-end">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-9 px-3 text-sm text-red-600 hover:bg-red-50 hover:text-red-700"
                                  onClick={() => void handleUnlinkFromMetric(dp.data_point_id)}
                                  disabled={!canManageEvidence || unlinkingDataPointId === dp.data_point_id}
                                >
                                  {unlinkingDataPointId === dp.data_point_id ? (
                                    <>
                                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                                      Unlinking...
                                    </>
                                  ) : (
                                    "Unlink"
                                  )}
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>

                    <section className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <div>
                        <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Link To Metric
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                          Attach this evidence to an existing project indicator. If the draft data point
                          does not exist yet, it will be created automatically for the selected context.
                        </p>
                      </div>

                      <div className="grid gap-3 lg:grid-cols-[260px_minmax(0,1fr)]">
                        <Select
                          label="Project"
                          placeholder="Select project"
                          value={linkProjectId}
                          onChange={setLinkProjectId}
                          options={projects.map((project) => ({
                            value: String(project.id),
                            label: project.name,
                          }))}
                        />
                        <Input
                          label="Search metric"
                          placeholder="Search by code, metric name, entity, facility..."
                          value={linkSearch}
                          onChange={(event) => setLinkSearch(event.target.value)}
                        />
                      </div>

                      {selectedProjectId == null ? (
                        <div className="text-sm text-slate-400">Choose a project to start linking.</div>
                      ) : assignmentsLoading || dataPointsLoading ? (
                        <div className="flex items-center gap-2 text-sm text-slate-500">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Loading metric contexts...
                        </div>
                      ) : linkCandidates.length === 0 ? (
                        <div className="text-sm text-slate-400">
                          No matching unlinked metrics found in this project.
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {linkCandidates.map((candidate) => (
                            <div
                              key={candidate.key}
                              className="grid gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 md:grid-cols-[minmax(0,1fr)_auto]"
                            >
                              <div className="min-w-0">
                                <div className="truncate text-base font-medium text-slate-900">
                                  {candidate.metric_name}
                                </div>
                                <div className="mt-1 break-all font-mono text-xs text-slate-500">
                                  {candidate.metric_code}
                                </div>
                                <div className="mt-1 truncate text-sm text-slate-500">
                                  {[candidate.entity_name, candidate.facility_name].filter(Boolean).join(" / ")}
                                </div>
                              </div>
                              <div className="flex items-start justify-end">
                                <Button
                                  size="sm"
                                  className="h-9 px-4 text-sm"
                                  onClick={() => void handleLinkToMetric(candidate)}
                                  disabled={!canManageEvidence || isLinking}
                                >
                                  {isLinking ? (
                                    <>
                                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                                      Linking...
                                    </>
                                  ) : (
                                    "Link"
                                  )}
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>

                    <section className="space-y-3">
                      <div>
                        <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Linked Requirement Items
                        </h3>
                        <p className="mt-1 text-sm text-slate-500">
                          {(detailTarget.linked_requirement_items ?? []).length} linked requirement items
                        </p>
                      </div>
                      {(detailTarget.linked_requirement_items ?? []).length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-200 px-4 py-5 text-sm text-slate-400">
                          No linked requirement items.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {(detailTarget.linked_requirement_items ?? []).map((ri) => (
                            <div
                              key={ri.requirement_item_id}
                              className="rounded-xl border border-slate-200 bg-white px-4 py-3"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="text-sm font-semibold text-slate-900">{ri.code}</div>
                                  <div className="mt-1 text-sm text-slate-500">{ri.description}</div>
                                </div>
                                <AIEvidenceGuidance requirementItemId={ri.requirement_item_id} />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </section>
                  </div>
                </div>

                <aside className="border-t border-slate-200 bg-slate-50/80 px-5 py-5 xl:border-l xl:border-t-0">
                  <div className="space-y-4">
                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Summary
                      </div>
                      <div className="mt-3 space-y-3 text-sm text-slate-600">
                        <div className="flex items-center justify-between gap-3">
                          <span>Type</span>
                          <span className="font-medium capitalize text-slate-900">{detailTarget.type}</span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>Status</span>
                          <Badge
                            variant={
                              detailTarget.binding_status === "bound" ? "success" : "secondary"
                            }
                          >
                            {getBindingLabel(detailTarget.binding_status)}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>Linked metrics</span>
                          <span className="font-medium text-slate-900">
                            {(detailTarget.linked_data_points ?? []).length}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-3">
                          <span>Requirements</span>
                          <span className="font-medium text-slate-900">
                            {(detailTarget.linked_requirement_items ?? []).length}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-xl border border-slate-200 bg-white p-4">
                      <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        Actions
                      </div>
                      <div className="mt-3 flex flex-col gap-2">
                        {detailTarget.type === "file" ? (
                          <Button
                            type="button"
                            onClick={() => {
                              void triggerFileDownload(`/api/evidences/${detailTarget.id}/download`);
                            }}
                          >
                            <Download className="h-4 w-4" />
                            Download file
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            onClick={() => {
                              if (detailTarget.url) window.open(detailTarget.url, "_blank");
                            }}
                          >
                            <ExternalLink className="h-4 w-4" />
                            Open link
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="outline"
                          onClick={closeDetailDrawer}
                        >
                          Close
                        </Button>
                      </div>
                    </div>
                  </div>
                </aside>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Evidence</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.title}
              &rdquo;? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium shadow-sm hover:bg-slate-50">
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting || !canManageEvidence}
            >
              {isDeleting ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-1.5 h-4 w-4" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add link dialog */}
      <Dialog open={addLinkOpen} onOpenChange={setAddLinkOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Link</DialogTitle>
            <DialogDescription>
              Add an external link as evidence.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <Input
              label="Title"
              placeholder="Evidence title"
              value={linkTitle}
              onChange={(e) => setLinkTitle(e.target.value)}
            />
            <Input
              label="URL"
              placeholder="https://..."
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
            />
            <Input
              label="Description"
              placeholder="Brief description (optional)"
              value={linkDescription}
              onChange={(e) => setLinkDescription(e.target.value)}
            />
          </div>
          <DialogFooter className="mt-4">
            <DialogClose className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium shadow-sm hover:bg-slate-50">
              Cancel
            </DialogClose>
            <Button
              disabled={
                !linkTitle.trim() ||
                !linkUrl.trim() ||
                addLinkMutation.isPending
              }
              onClick={() =>
                addLinkMutation.mutate({
                  title: linkTitle,
                  url: linkUrl,
                  description: linkDescription,
                  type: "link",
                })
              }
            >
              {addLinkMutation.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-1.5 h-4 w-4" />
              )}
              Add Link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
