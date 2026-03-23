"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, Plus, Send, ShieldAlert, Trash2, Webhook, XCircle } from "lucide-react";

import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

type RoleBinding = { role: string };

type WebhookEndpoint = {
  id: number;
  url: string;
  events: string[];
  is_active: boolean;
  secret_last4: string;
  created_at: string | null;
  updated_at: string | null;
};

type WebhookListResponse = {
  items: WebhookEndpoint[];
  total: number;
};

type WebhookDelivery = {
  id: number;
  event_type: string;
  status: string;
  http_status: number | null;
  attempt: number;
  max_attempts: number;
  delivered_at: string | null;
  created_at: string | null;
};

type WebhookDeliveryResponse = {
  items: WebhookDelivery[];
  total: number;
};

const supportedEvents = [
  "data_point.submitted",
  "data_point.approved",
  "data_point.rejected",
  "data_point.needs_revision",
  "data_point.rolled_back",
  "project.started",
  "project.in_review",
  "project.published",
  "evidence.created",
  "boundary.changed",
  "completeness.updated",
];

export default function WebhooksPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editing, setEditing] = useState<WebhookEndpoint | null>(null);
  const [formUrl, setFormUrl] = useState("");
  const [formSecret, setFormSecret] = useState("");
  const [formEvents, setFormEvents] = useState<string[]>([]);
  const [formIsActive, setFormIsActive] = useState(true);
  const [generatedSecret, setGeneratedSecret] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState("");
  const [actionError, setActionError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me", "webhooks-settings"],
    "/auth/me"
  );
  const canAccess = (me?.roles ?? []).some((binding) => ["admin", "platform_admin"].includes(binding.role));
  const accessDenied = Boolean(me) && !canAccess;

  const { data, isLoading, refetch } = useApiQuery<WebhookListResponse>(["webhooks"], "/webhooks", {
    enabled: canAccess,
  });

  useEffect(() => {
    const firstId = data?.items?.[0]?.id ?? null;
    setSelectedId((current) => (current && data?.items?.some((item) => item.id === current) ? current : firstId));
  }, [data?.items]);

  const selectedEndpoint = useMemo(
    () => data?.items?.find((item) => item.id === selectedId) ?? null,
    [data?.items, selectedId]
  );

  const { data: deliveries, refetch: refetchDeliveries } = useApiQuery<WebhookDeliveryResponse>(
    ["webhook-deliveries", selectedId],
    selectedId ? `/webhooks/${selectedId}/deliveries?page_size=20` : "/webhooks/0/deliveries",
    { enabled: Boolean(selectedId) && canAccess }
  );

  function openCreateDialog() {
    setEditing(null);
    setFormUrl("");
    setFormSecret("");
    setFormEvents([]);
    setFormIsActive(true);
    setGeneratedSecret(null);
    setActionError("");
    setDialogOpen(true);
  }

  function openEditDialog(endpoint: WebhookEndpoint) {
    setEditing(endpoint);
    setFormUrl(endpoint.url);
    setFormSecret("");
    setFormEvents(endpoint.events);
    setFormIsActive(endpoint.is_active);
    setGeneratedSecret(null);
    setActionError("");
    setDialogOpen(true);
  }

  function toggleEvent(eventType: string) {
    setFormEvents((current) =>
      current.includes(eventType)
        ? current.filter((value) => value !== eventType)
        : [...current, eventType]
    );
  }

  async function submitWebhook() {
    if (!formUrl.trim() || formEvents.length === 0) return;
    setActionError("");
    setActionMessage("");
    setIsSubmitting(true);
    try {
      if (editing) {
        await api.patch(`/webhooks/${editing.id}`, {
          url: formUrl,
          secret: formSecret || undefined,
          events: formEvents,
          is_active: formIsActive,
        });
        setActionMessage("Webhook updated.");
      } else {
        const created = await api.post<{ secret: string }>("/webhooks", {
          url: formUrl,
          secret: formSecret || undefined,
          events: formEvents,
          is_active: formIsActive,
        });
        setGeneratedSecret(created.secret);
        setActionMessage("Webhook created.");
      }
      setDialogOpen(false);
      await refetch();
      if (selectedId) {
        await refetchDeliveries();
      }
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to save webhook.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function triggerTest(endpointId: number) {
    setActionError("");
    setActionMessage("");
    try {
      await api.post(`/webhooks/${endpointId}/test`);
      await refetchDeliveries();
      setActionMessage("Webhook test delivery queued.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to test webhook.");
    }
  }

  async function deleteEndpoint(endpointId: number) {
    setActionError("");
    setActionMessage("");
    try {
      await api.delete(`/webhooks/${endpointId}`);
      await refetch();
      setActionMessage("Webhook deleted.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to delete webhook.");
    }
  }

  if (meLoading || (canAccess && isLoading)) {
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
          <h2 className="text-2xl font-bold text-slate-900">Webhooks</h2>
          <p className="mt-1 text-sm text-slate-500">Manage outbound webhook endpoints for workflow events.</p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only admin and platform admin roles can manage webhooks.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Webhooks</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage outbound webhook endpoints for workflow, boundary, evidence, and completeness events.
          </p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Add Webhook
        </Button>
      </div>

      {actionError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</div>
      )}
      {actionMessage && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">{actionMessage}</div>
      )}
      {generatedSecret && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
          Save this webhook secret now: <span className="font-mono">{generatedSecret}</span>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1fr_1.35fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Webhook className="h-4 w-4" />
              Endpoints
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(data?.items ?? []).length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
                No webhooks configured yet.
              </div>
            ) : (
              data?.items.map((endpoint) => (
                <button
                  key={endpoint.id}
                  className={`w-full rounded-lg border px-4 py-3 text-left transition-colors ${
                    selectedId === endpoint.id ? "border-blue-200 bg-blue-50" : "border-slate-200 hover:bg-slate-50"
                  }`}
                  onClick={() => setSelectedId(endpoint.id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{endpoint.url}</p>
                      <p className="mt-1 text-xs text-slate-500">Events: {endpoint.events.length}</p>
                      <p className="mt-1 text-xs text-slate-400">Secret ending: {endpoint.secret_last4}</p>
                    </div>
                    <Badge variant={endpoint.is_active ? "success" : "secondary"}>
                      {endpoint.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Endpoint Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {selectedEndpoint ? (
                <>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <p className="text-xs font-medium uppercase text-slate-400">URL</p>
                      <p className="mt-1 break-all text-sm text-slate-700">{selectedEndpoint.url}</p>
                    </div>
                    <div>
                      <p className="text-xs font-medium uppercase text-slate-400">Created</p>
                      <p className="mt-1 text-sm text-slate-700">
                        {selectedEndpoint.created_at ? new Date(selectedEndpoint.created_at).toLocaleString() : "-"}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase text-slate-400">Subscribed Events</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedEndpoint.events.map((eventType) => (
                        <Badge key={eventType} variant="secondary">{eventType}</Badge>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Button variant="outline" onClick={() => openEditDialog(selectedEndpoint)}>
                      Edit Endpoint
                    </Button>
                    <Button variant="outline" onClick={() => void triggerTest(selectedEndpoint.id)}>
                      <Send className="mr-2 h-4 w-4" />
                      Send Test Event
                    </Button>
                    <Button variant="destructive" onClick={() => void deleteEndpoint(selectedEndpoint.id)}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete Endpoint
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
                  Select a webhook endpoint to inspect deliveries and actions.
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Delivery History</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {selectedEndpoint == null ? (
                <p className="text-sm text-slate-500">Choose an endpoint to load its deliveries.</p>
              ) : (deliveries?.items ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">No deliveries recorded for this endpoint yet.</p>
              ) : (
                deliveries?.items.map((delivery) => (
                  <div key={delivery.id} className="rounded-lg border border-slate-200 px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-slate-900">{delivery.event_type}</p>
                        <p className="mt-1 text-xs text-slate-500">
                          Attempt {delivery.attempt} / {delivery.max_attempts}
                        </p>
                      </div>
                      {delivery.status === "success" ? (
                        <Badge variant="success">
                          <CheckCircle2 className="mr-1 h-3 w-3" />
                          Success
                        </Badge>
                      ) : (
                        <Badge variant="destructive">
                          <XCircle className="mr-1 h-3 w-3" />
                          {delivery.status}
                        </Badge>
                      )}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
                      <span>HTTP: {delivery.http_status ?? "-"}</span>
                      <span>
                        Created: {delivery.created_at ? new Date(delivery.created_at).toLocaleString() : "-"}
                      </span>
                      <span>
                        Delivered: {delivery.delivered_at ? new Date(delivery.delivered_at).toLocaleString() : "-"}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Webhook" : "Add Webhook"}</DialogTitle>
            <DialogDescription>
              Configure endpoint URL, secret rotation, active state, and subscribed events.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid gap-1.5">
              <Label htmlFor="webhook-url">URL</Label>
              <Input
                id="webhook-url"
                value={formUrl}
                onChange={(event) => setFormUrl(event.target.value)}
                placeholder="https://example.com/hooks/esg"
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="webhook-secret">Secret</Label>
              <Input
                id="webhook-secret"
                value={formSecret}
                onChange={(event) => setFormSecret(event.target.value)}
                placeholder={editing ? "Leave blank to keep existing secret" : "Optional secret override"}
              />
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <Switch checked={formIsActive} onCheckedChange={setFormIsActive} label="Endpoint active" />
            </div>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="grid max-h-64 gap-2 overflow-y-auto rounded-lg border border-slate-200 p-3">
                {supportedEvents.map((eventType) => {
                  const checked = formEvents.includes(eventType);
                  return (
                    <label key={eventType} className="flex items-center gap-2 text-sm text-slate-700">
                      <input type="checkbox" checked={checked} onChange={() => toggleEvent(eventType)} />
                      <span>{eventType}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void submitWebhook()} disabled={isSubmitting || !formUrl.trim() || formEvents.length === 0}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editing ? "Save Changes" : "Create Webhook"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
