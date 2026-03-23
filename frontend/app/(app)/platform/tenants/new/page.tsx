"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Loader2, ShieldAlert } from "lucide-react";

import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type RoleBinding = { role: string };

type TenantCreateResponse = {
  id: number;
  name: string;
  created: boolean;
};

export default function CreateTenantPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", country: "", industry: "" });

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me", "tenant-create"],
    "/auth/me"
  );

  const canAccess = (me?.roles ?? []).some((binding) => binding.role === "platform_admin");
  const accessDenied = Boolean(me) && !canAccess;

  const mutation = useApiMutation<TenantCreateResponse, typeof form>("/platform/tenants", "POST");

  async function createTenant() {
    const created = await mutation.mutateAsync(form);
    router.push(`/platform/tenants/${created.id}`);
  }

  if (meLoading) {
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
          <h2 className="text-2xl font-bold text-slate-900">Create Tenant</h2>
          <p className="mt-1 text-sm text-slate-500">Register a new organization on the platform.</p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only platform admins can create tenants.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/platform/tenants")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Create Tenant</h2>
          <p className="mt-1 text-sm text-slate-500">
            Register a new organization and continue to the detail view for lifecycle controls.
          </p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tenant Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-1.5">
            <Label htmlFor="tenant-name">Name</Label>
            <Input
              id="tenant-name"
              value={form.name}
              onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="Northwind Europe"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="tenant-country">Country</Label>
            <Input
              id="tenant-country"
              value={form.country}
              onChange={(event) => setForm((current) => ({ ...current, country: event.target.value }))}
              placeholder="United Kingdom"
            />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="tenant-industry">Industry</Label>
            <Input
              id="tenant-industry"
              value={form.industry}
              onChange={(event) => setForm((current) => ({ ...current, industry: event.target.value }))}
              placeholder="Renewable Energy"
            />
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            The backend creates the tenant in <strong>active</strong> status. Additional admin assignment and
            self-registration controls are managed from the detail page.
          </div>
          <div className="flex justify-end">
            <Button onClick={() => void createTenant()} disabled={mutation.isPending || !form.name.trim()}>
              {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Tenant
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
