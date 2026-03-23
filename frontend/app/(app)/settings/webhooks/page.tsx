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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
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
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  Plus,
  MoreHorizontal,
  Webhook,
  Pencil,
  Trash2,
  Zap,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Clock,
} from "lucide-react";

interface WebhookEntry {
  id: number;
  url: string;
  status: "active" | "inactive";
  events: string[];
  created_at: string;
}

interface DeliveryEntry {
  id: number;
  webhook_id: number;
  status: "success" | "failed";
  http_code: number | null;
  timestamp: string;
  retry_count: number;
  event_type: string;
}

interface WebhooksResponse {
  webhooks: WebhookEntry[];
  deliveries: DeliveryEntry[];
}

const allEvents = [
  { value: "data_point.created", label: "Data Point Created" },
  { value: "data_point.updated", label: "Data Point Updated" },
  { value: "data_point.approved", label: "Data Point Approved" },
  { value: "assignment.created", label: "Assignment Created" },
  { value: "assignment.completed", label: "Assignment Completed" },
  { value: "project.published", label: "Project Published" },
  { value: "boundary.locked", label: "Boundary Locked" },
  { value: "export.completed", label: "Export Completed" },
  { value: "user.invited", label: "User Invited" },
];

export default function WebhooksPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookEntry | null>(null);
  const [formUrl, setFormUrl] = useState("");
  const [formSecret, setFormSecret] = useState("");
  const [formEvents, setFormEvents] = useState<string[]>([]);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { data, isLoading, refetch } = useApiQuery<WebhooksResponse>(
    ["webhooks"],
    "/webhooks"
  );

  const createMutation = useApiMutation("/webhooks", "POST");
  const updateMutation = useApiMutation("", "PATCH");
  const deleteMutation = useApiMutation("", "DELETE");
  const testMutation = useApiMutation("", "POST");

  const webhooks = data?.webhooks ?? [];
  const deliveries = data?.deliveries ?? [];

  const openCreateDialog = () => {
    setEditingWebhook(null);
    setFormUrl("");
    setFormSecret("");
    setFormEvents([]);
    setDialogOpen(true);
  };

  const openEditDialog = (webhook: WebhookEntry) => {
    setEditingWebhook(webhook);
    setFormUrl(webhook.url);
    setFormSecret("");
    setFormEvents(webhook.events);
    setDialogOpen(true);
  };

  const toggleEvent = (event: string) => {
    setFormEvents((prev) =>
      prev.includes(event)
        ? prev.filter((e) => e !== event)
        : [...prev, event]
    );
  };

  const handleSave = async () => {
    const payload = {
      url: formUrl,
      secret: formSecret || undefined,
      events: formEvents,
    };

    if (editingWebhook) {
      await updateMutation.mutateAsync({
        ...payload,
        path: `/webhooks/${editingWebhook.id}`,
      } as never);
    } else {
      await createMutation.mutateAsync(payload as never);
    }

    setDialogOpen(false);
    refetch();
  };

  const handleTest = async (webhookId: number) => {
    await testMutation.mutateAsync({
      path: `/webhooks/${webhookId}/test`,
    } as never);
    refetch();
  };

  const handleDelete = async () => {
    if (deletingId) {
      await deleteMutation.mutateAsync({
        path: `/webhooks/${deletingId}`,
      } as never);
      setDeleteDialogOpen(false);
      setDeletingId(null);
      refetch();
    }
  };

  const confirmDelete = (id: number) => {
    setDeletingId(id);
    setDeleteDialogOpen(true);
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Webhooks</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage webhook endpoints for event notifications
          </p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Add Webhook
        </Button>
      </div>

      {/* Webhooks Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Webhook className="h-4 w-4" />
            Endpoints
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {webhooks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Webhook className="mb-3 h-10 w-10 text-slate-300" />
              <p className="text-sm text-slate-500">No webhooks configured</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={openCreateDialog}
              >
                Add your first webhook
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>URL</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {webhooks.map((webhook) => (
                  <TableRow key={webhook.id}>
                    <TableCell className="max-w-[300px] truncate font-mono text-sm">
                      {webhook.url}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          webhook.status === "active"
                            ? "bg-green-100 text-green-700"
                            : "bg-slate-100 text-slate-600"
                        }
                      >
                        {webhook.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-slate-600">
                        {(webhook.events ?? []).length} event
                        {(webhook.events ?? []).length !== 1 ? "s" : ""}
                      </span>
                    </TableCell>
                    <TableCell className="text-sm text-slate-600">
                      {new Date(webhook.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() => openEditDialog(webhook)}
                          >
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleTest(webhook.id)}
                          >
                            <Zap className="mr-2 h-4 w-4" />
                            Test
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => confirmDelete(webhook.id)}
                            className="text-red-600"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Delivery History */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Delivery History
          </CardTitle>
          <CardDescription>Recent webhook delivery attempts</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {deliveries.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Clock className="mb-3 h-10 w-10 text-slate-300" />
              <p className="text-sm text-slate-500">No deliveries yet</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>HTTP Code</TableHead>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Retries</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deliveries.map((delivery) => (
                  <TableRow key={delivery.id}>
                    <TableCell>
                      {delivery.status === "success" ? (
                        <Badge className="bg-green-100 text-green-700">
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Success
                        </Badge>
                      ) : (
                        <Badge variant="destructive">
                          <XCircle className="mr-1 h-3 w-3" />
                          Failed
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm font-mono">
                      {delivery.event_type}
                    </TableCell>
                    <TableCell className="text-sm">
                      {delivery.http_code ?? "N/A"}
                    </TableCell>
                    <TableCell className="text-sm text-slate-600">
                      {new Date(delivery.timestamp).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      {delivery.retry_count > 0 && (
                        <div className="flex items-center gap-1 text-sm text-slate-600">
                          <RotateCcw className="h-3 w-3" />
                          {delivery.retry_count}
                        </div>
                      )}
                      {delivery.retry_count === 0 && (
                        <span className="text-sm text-slate-400">-</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Webhook Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingWebhook ? "Edit Webhook" : "Add Webhook"}
            </DialogTitle>
            <DialogDescription>
              {editingWebhook
                ? "Update webhook endpoint configuration"
                : "Configure a new webhook endpoint"}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="webhook-url">URL</Label>
              <Input
                id="webhook-url"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                placeholder="https://example.com/webhook"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="webhook-secret">Secret</Label>
              <Input
                id="webhook-secret"
                type="password"
                value={formSecret}
                onChange={(e) => setFormSecret(e.target.value)}
                placeholder={
                  editingWebhook
                    ? "Leave blank to keep current"
                    : "Signing secret"
                }
              />
              <p className="text-xs text-slate-400">
                Used to sign webhook payloads for verification
              </p>
            </div>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-slate-200 p-3">
                {allEvents.map((event) => (
                  <div
                    key={event.value}
                    className="flex items-center gap-2"
                  >
                    <Checkbox
                      checked={formEvents.includes(event.value)}
                      onCheckedChange={() => toggleEvent(event.value)}
                    />
                    <span className="text-sm">{event.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={
                !formUrl.trim() ||
                formEvents.length === 0 ||
                createMutation.isPending ||
                updateMutation.isPending
              }
            >
              {(createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {editingWebhook ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Webhook</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this webhook? This action cannot
              be undone and all delivery history will be lost.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
