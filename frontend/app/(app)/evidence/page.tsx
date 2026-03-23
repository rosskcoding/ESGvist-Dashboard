"use client";

import { useState, useMemo, useCallback } from "react";
import { api } from "@/lib/api";
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
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
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

// ---------- Component ----------

export default function EvidencePage() {
  const [typeFilter, setTypeFilter] = useState("");
  const [bindingFilter, setBindingFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<EvidenceItem | null>(null);
  const [detailTarget, setDetailTarget] = useState<EvidenceItem | null>(null);
  const [addLinkOpen, setAddLinkOpen] = useState(false);
  const [linkTitle, setLinkTitle] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [linkDescription, setLinkDescription] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data: me } = useApiQuery<{
    roles: Array<{ role: string }>;
  }>(["auth-me", "evidence"], "/auth/me");

  const { data, isLoading, error, refetch } = useApiQuery<EvidenceResponse>(
    ["evidence"],
    "/evidences"
  );

  const uploadMutation = useApiMutation<
    EvidenceItem,
    {
      type: "file";
      title: string;
      description: string;
      source_type: "manual";
      file_name: string;
      file_uri: string;
      mime_type: string;
      file_size: number;
    }
  >(
    "/evidences",
    "POST",
    {
      onSuccess: () => {
        refetch();
      },
    }
  );

  const addLinkMutation = useApiMutation<
    EvidenceItem,
    { title: string; url: string; description: string; type: "link" }
  >("/evidences", "POST", {
    onSuccess: () => {
      setAddLinkOpen(false);
      setLinkTitle("");
      setLinkUrl("");
      setLinkDescription("");
      refetch();
    },
  });

  const items = data?.items ?? [];
  const role = me?.roles?.[0]?.role ?? "";
  const canManageEvidence = !["auditor", "reviewer"].includes(role);
  const accessDenied =
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
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        for (let i = 0; i < files.length; i++) {
          uploadMutation.mutate({
            type: "file",
            title: files[i].name,
            description: `Uploaded from evidence repository`,
            source_type: "manual",
            file_name: files[i].name,
            file_uri: `file:///uploads/${encodeURIComponent(files[i].name)}`,
            mime_type: files[i].type || "application/pdf",
            file_size: files[i].size,
          });
        }
      }
    },
    [canManageEvidence, uploadMutation]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files) return;
      if (!canManageEvidence) return;
      for (let i = 0; i < files.length; i++) {
        uploadMutation.mutate({
          type: "file",
          title: files[i].name,
          description: `Uploaded from evidence repository`,
          source_type: "manual",
          file_name: files[i].name,
          file_uri: `file:///uploads/${encodeURIComponent(files[i].name)}`,
          mime_type: files[i].type || "application/pdf",
          file_size: files[i].size,
        });
      }
      e.target.value = "";
    },
    [canManageEvidence, uploadMutation]
  );

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      setIsDeleting(true);
      await api.delete(`/evidence/${deleteTarget.id}`);
      setDeleteTarget(null);
      refetch();
    } finally {
      setIsDeleting(false);
    }
  }, [deleteTarget, refetch]);

  // ---------- Render ----------

  if (isLoading) {
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
                  ? "border-blue-400 bg-blue-50"
                  : "border-slate-300 bg-slate-50 hover:border-slate-400"
              )}
            >
              <FileUp className="mb-2 h-8 w-8 text-slate-400" />
              <p className="text-sm font-medium text-slate-600">
                Drag and drop files here
              </p>
              <p className="mt-1 text-xs text-slate-400">
                or click to browse files
              </p>
              <label className="mt-3 cursor-pointer">
                <input
                  type="file"
                  multiple
                  className="hidden"
                  onChange={handleFileInput}
                  disabled={!canManageEvidence}
                />
                <span className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-3 text-xs font-medium shadow-sm hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
                  <Upload className="mr-1.5 h-3 w-3" />
                  Browse Files
                </span>
              </label>
            </div>

            {/* Add link button */}
            <Button
              variant="outline"
              onClick={() => setAddLinkOpen(true)}
              className="shrink-0"
              disabled={!canManageEvidence}
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
              label="Binding Status"
              placeholder="All"
              value={bindingFilter}
              onChange={setBindingFilter}
              options={[
                { value: "", label: "All" },
                { value: "bound", label: "Bound" },
                { value: "unbound", label: "Unbound" },
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
                <TableHead className="text-center">Binding</TableHead>
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
                        <FileText className="h-4 w-4 text-blue-500" />
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
                      {item.created_by_name ?? "Unknown"}
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={
                          item.binding_status === "bound"
                            ? "success"
                            : "secondary"
                        }
                      >
                        {item.binding_status}
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
                              if (item.url) window.open(item.url, "_blank");
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
                          disabled={!canManageEvidence}
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
          if (!open) setDetailTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {detailTarget?.type === "file" ? (
                <FileText className="h-5 w-5 text-blue-500" />
              ) : (
                <Link2 className="h-5 w-5 text-emerald-500" />
              )}
              {detailTarget?.title}
            </DialogTitle>
            <DialogDescription>{detailTarget?.description}</DialogDescription>
          </DialogHeader>

          {detailTarget && (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs font-medium text-slate-500">Type</p>
                  <p className="mt-1 text-sm capitalize">{detailTarget.type}</p>
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Binding Status
                  </p>
                  <Badge
                    variant={
                      detailTarget.binding_status === "bound"
                        ? "success"
                        : "secondary"
                    }
                    className="mt-1"
                  >
                    {detailTarget.binding_status}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Upload Date
                  </p>
                  <p className="mt-1 text-sm">
                    {formatDate(detailTarget.upload_date)}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-medium text-slate-500">
                    Created By
                  </p>
                  <p className="mt-1 text-sm">{detailTarget.created_by_name ?? "Unknown"}</p>
                </div>
              </div>

              {detailTarget.type === "file" && detailTarget.file_name && (
                <div>
                  <p className="text-xs font-medium text-slate-500">File</p>
                  <p className="mt-1 text-sm">
                    {detailTarget.file_name}
                    {detailTarget.file_size != null && (
                      <span className="ml-2 text-slate-400">
                        ({formatFileSize(detailTarget.file_size)})
                      </span>
                    )}
                  </p>
                </div>
              )}

              {detailTarget.type === "link" && detailTarget.url && (
                <div>
                  <p className="text-xs font-medium text-slate-500">URL</p>
                  <a
                    href={detailTarget.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
                  >
                    {detailTarget.url}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}

              {/* Linked data points */}
              <div>
                <p className="text-xs font-medium text-slate-500">
                  Linked Data Points ({(detailTarget.linked_data_points ?? []).length})
                </p>
                {(detailTarget.linked_data_points ?? []).length === 0 ? (
                  <p className="mt-1 text-xs text-slate-400">None</p>
                ) : (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {(detailTarget.linked_data_points ?? []).map((dp) => (
                      <Badge key={dp.data_point_id} variant="outline">
                        {dp.code} &mdash; {dp.label}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {/* Linked requirement items */}
              <div>
                <p className="text-xs font-medium text-slate-500">
                  Linked Requirement Items (
                  {(detailTarget.linked_requirement_items ?? []).length})
                </p>
                {(detailTarget.linked_requirement_items ?? []).length === 0 ? (
                  <p className="mt-1 text-xs text-slate-400">None</p>
                ) : (
                  <div className="mt-1.5 space-y-1">
                    {(detailTarget.linked_requirement_items ?? []).map((ri) => (
                      <div
                        key={ri.requirement_item_id}
                        className="rounded border border-slate-100 px-2 py-1 text-xs"
                      >
                        <span className="font-medium">{ri.code}</span>{" "}
                        <span className="text-slate-500">
                          {ri.description}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
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
