"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Building2, Globe, Loader2, LockKeyhole, Save, ShieldAlert } from "lucide-react";

import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

type RoleBinding = { role: string };

type OrgSettings = {
  id: number;
  name: string;
  country: string | null;
  industry: string | null;
  currency: string;
  reporting_year: number | null;
  logo_url: string | null;
  default_boundary_id: number | null;
};

type Boundary = {
  id: number;
  name: string;
  is_default?: boolean;
};

type OrgAuthSettings = {
  organization_id: number;
  allow_password_login: boolean;
  allow_sso_login: boolean;
  enforce_sso: boolean;
  active_sso_provider_count: number;
  sso_available: boolean;
};

const currentYear = new Date().getFullYear();

export default function OrganizationSettingsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    country: "",
    industry: "",
    currency: "USD",
    reporting_year: String(currentYear),
    default_boundary_id: "",
  });
  const [authForm, setAuthForm] = useState({
    allow_password_login: true,
    allow_sso_login: true,
    enforce_sso: false,
  });
  const [saved, setSaved] = useState(false);
  const [authSaved, setAuthSaved] = useState(false);
  const [authError, setAuthError] = useState("");

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me"],
    "/auth/me"
  );
  const canAccess = (me?.roles ?? []).some((binding) =>
    ["admin", "platform_admin"].includes(binding.role)
  );
  const accessDenied = Boolean(me) && !canAccess;

  const { data, isLoading } = useApiQuery<OrgSettings>(
    ["org-settings"],
    "/auth/me/organization",
    { enabled: canAccess }
  );

  const { data: boundaries = [] } = useApiQuery<Boundary[]>(
    ["boundaries-list", "org-settings"],
    "/boundaries",
    { enabled: canAccess }
  );

  const { data: authSettings } = useApiQuery<OrgAuthSettings>(
    ["organization-auth-settings"],
    "/auth/organization/auth-settings",
    { enabled: canAccess }
  );

  const saveMutation = useApiMutation<OrgSettings, Record<string, string | number | null>>(
    "/auth/me/organization",
    "PATCH"
  );
  const authSettingsMutation = useApiMutation<OrgAuthSettings, Partial<OrgAuthSettings>>(
    "/auth/organization/auth-settings",
    "PATCH"
  );

  useEffect(() => {
    if (!data) return;
    const syncOrganizationForm = () => {
      setForm({
        name: data.name,
        country: data.country ?? "",
        industry: data.industry ?? "",
        currency: data.currency,
        reporting_year: String(data.reporting_year ?? currentYear),
        default_boundary_id: data.default_boundary_id ? String(data.default_boundary_id) : "",
      });
    };
    syncOrganizationForm();
  }, [data]);

  useEffect(() => {
    if (!authSettings) return;
    const syncAuthForm = () => {
      setAuthForm({
        allow_password_login: authSettings.allow_password_login,
        allow_sso_login: authSettings.allow_sso_login,
        enforce_sso: authSettings.enforce_sso,
      });
    };
    syncAuthForm();
  }, [authSettings]);

  async function saveOrganizationSettings() {
    setSaved(false);
    const updated = await saveMutation.mutateAsync({
      name: form.name,
      country: form.country || null,
      industry: form.industry || null,
      currency: form.currency,
      reporting_year: Number(form.reporting_year),
      default_boundary_id: form.default_boundary_id ? Number(form.default_boundary_id) : null,
    });
    queryClient.setQueryData(["org-settings"], updated);
    setSaved(true);
  }

  async function saveAuthSettings() {
    setAuthError("");
    setAuthSaved(false);
    try {
      const updated = await authSettingsMutation.mutateAsync(authForm);
      queryClient.setQueryData(["organization-auth-settings"], updated);
      setAuthSaved(true);
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Failed to save auth settings.");
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
          <h2 className="text-2xl font-bold text-slate-900">Organization Settings</h2>
          <p className="mt-1 text-sm text-slate-500">Manage organization metadata, boundaries, and login policy.</p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">Only organization admins can manage organization settings.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Organization Settings</h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage organization metadata, default boundary selection, and authentication policy.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              Organization Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="orgName">Organization Name</Label>
              <Input
                id="orgName"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="country">Country</Label>
                <Input
                  id="country"
                  value={form.country}
                  onChange={(event) => setForm((current) => ({ ...current, country: event.target.value }))}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="industry">Industry</Label>
                <Input
                  id="industry"
                  value={form.industry}
                  onChange={(event) => setForm((current) => ({ ...current, industry: event.target.value }))}
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="currency">Currency</Label>
                <Input
                  id="currency"
                  value={form.currency}
                  onChange={(event) => setForm((current) => ({ ...current, currency: event.target.value.toUpperCase() }))}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="reportingYear">Reporting Year</Label>
                <Input
                  id="reportingYear"
                  type="number"
                  value={form.reporting_year}
                  onChange={(event) => setForm((current) => ({ ...current, reporting_year: event.target.value }))}
                />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="defaultBoundary">Default Boundary</Label>
              <Select
                id="defaultBoundary"
                value={form.default_boundary_id}
                onChange={(value) => setForm((current) => ({ ...current, default_boundary_id: value }))}
                options={[
                  { value: "", label: "No default boundary" },
                  ...boundaries.map((boundary) => ({ value: String(boundary.id), label: boundary.name })),
                ]}
              />
            </div>
            {saved && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                Settings saved successfully.
              </div>
            )}
            <div className="flex justify-end">
              <Button onClick={() => void saveOrganizationSettings()} disabled={saveMutation.isPending || !form.name.trim()}>
                {saveMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Settings
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-4 w-4" />
                Boundary Context
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              <p>Available boundaries: {boundaries.length}</p>
              <p>
                Current default: {boundaries.find((boundary) => String(boundary.id) === form.default_boundary_id)?.name ?? "None"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LockKeyhole className="h-4 w-4" />
                Authentication Policy
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border border-slate-200 p-4">
                <Switch
                  checked={authForm.allow_password_login}
                  onCheckedChange={(value) => setAuthForm((current) => ({ ...current, allow_password_login: value }))}
                  label="Allow password login"
                />
              </div>
              <div className="rounded-lg border border-slate-200 p-4">
                <Switch
                  checked={authForm.allow_sso_login}
                  onCheckedChange={(value) => setAuthForm((current) => ({ ...current, allow_sso_login: value }))}
                  label="Allow SSO login"
                />
              </div>
              <div className="rounded-lg border border-slate-200 p-4">
                <Switch
                  checked={authForm.enforce_sso}
                  onCheckedChange={(value) => setAuthForm((current) => ({ ...current, enforce_sso: value }))}
                  label="Enforce SSO"
                />
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
                <p>Active SSO providers: {authSettings?.active_sso_provider_count ?? 0}</p>
                <p className="mt-1">SSO available: {authSettings?.sso_available ? "Yes" : "No"}</p>
              </div>
              {authError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {authError}
                </div>
              )}
              {authSaved && (
                <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                  Authentication policy saved.
                </div>
              )}
              <div className="flex justify-end">
                <Button variant="outline" onClick={() => void saveAuthSettings()} disabled={authSettingsMutation.isPending}>
                  {authSettingsMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Auth Policy
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
