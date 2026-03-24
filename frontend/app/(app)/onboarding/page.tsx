"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";

import { api } from "@/lib/api";
import { useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

type RoleBinding = {
  role: string;
  scope_type: string;
  scope_id: number | null;
};

type CurrentUser = {
  email: string;
  full_name: string;
  roles: RoleBinding[];
};

type SetupResponse = {
  organization_id: number;
  root_entity_id: number;
  boundary_id: number;
  created_entities: number;
  invited_users: number;
  next_step: string;
};

type InviteRole = "esg_manager" | "admin";

type SubsidiaryDraft = {
  name: string;
  country: string;
  entity_type: "legal_entity" | "branch" | "joint_venture";
  ownership_percent: number;
};

type InviteDraft = {
  email: string;
  role: InviteRole;
};

const STEP_TITLES = [
  "Organization Basics",
  "Reporting Setup",
  "Company Structure",
  "Team Setup",
  "Review & Create",
] as const;

const COUNTRY_OPTIONS = [
  { value: "US", label: "United States" },
  { value: "GB", label: "United Kingdom" },
  { value: "DE", label: "Germany" },
  { value: "FR", label: "France" },
  { value: "KZ", label: "Kazakhstan" },
  { value: "AE", label: "United Arab Emirates" },
  { value: "JP", label: "Japan" },
] as const;

const INDUSTRY_OPTIONS = [
  { value: "oil_gas", label: "Oil & Gas" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "finance", label: "Finance" },
  { value: "technology", label: "Technology" },
  { value: "utilities", label: "Utilities" },
  { value: "transport", label: "Transport" },
] as const;

const STANDARD_OPTIONS = [
  { value: "GRI", label: "GRI 2021" },
  { value: "IFRS_S2", label: "IFRS S2" },
  { value: "ESRS_E1", label: "ESRS E1" },
  { value: "SASB", label: "SASB" },
] as const;

const CURRENCY_BY_COUNTRY: Record<string, string> = {
  US: "USD",
  GB: "GBP",
  DE: "EUR",
  FR: "EUR",
  KZ: "KZT",
  AE: "AED",
  JP: "JPY",
};

const CURRENT_YEAR = new Date().getFullYear();

function saveOnboardingSummary(summary: {
  organizationName: string;
  plannedStandards: string[];
  warnings: string[];
}) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem("onboarding-summary", JSON.stringify(summary));
}

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export default function OnboardingPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    organizationName: "",
    legalName: "",
    registrationNumber: "",
    country: "US",
    jurisdiction: "",
    industry: "technology",
    currency: CURRENCY_BY_COUNTRY.US,
    reportingYear: String(CURRENT_YEAR),
    consolidationApproach: "financial_control",
    ghgScopeApproach: "location_based",
    structureLater: false,
    inviteLater: false,
  });
  const [selectedStandards, setSelectedStandards] = useState<string[]>(["GRI"]);
  const [subsidiaries, setSubsidiaries] = useState<SubsidiaryDraft[]>([]);
  const [inviteUsers, setInviteUsers] = useState<InviteDraft[]>([
    { email: "", role: "esg_manager" },
  ]);

  const { data: me, isLoading: meLoading } = useApiQuery<CurrentUser>(
    ["auth-me"],
    "/auth/me"
  );

  const hasOrganizationRole = useMemo(
    () =>
      (me?.roles ?? []).some(
        (role) => role.scope_type === "organization" && role.scope_id
      ),
    [me?.roles]
  );
  const isPlatformAdmin = useMemo(
    () => (me?.roles ?? []).some((role) => role.role === "platform_admin"),
    [me?.roles]
  );

  useEffect(() => {
    setForm((current) => ({
      ...current,
      currency: CURRENCY_BY_COUNTRY[current.country] ?? "USD",
    }));
  }, [form.country]);

  const plannedStandards = selectedStandards.map(
    (value) => STANDARD_OPTIONS.find((option) => option.value === value)?.label ?? value
  );

  function addSubsidiary() {
    setSubsidiaries((current) => [
      ...current,
      {
        name: "",
        country: form.country,
        entity_type: "legal_entity",
        ownership_percent: 100,
      },
    ]);
  }

  function addInvite() {
    setInviteUsers((current) => [...current, { email: "", role: "esg_manager" }]);
  }

  function validateCurrentStep() {
    if (step === 0) {
      if (!form.organizationName.trim()) {
        return "Organization name is required.";
      }
      if (!form.country) {
        return "Country is required.";
      }
      if (!form.industry) {
        return "Industry is required.";
      }
    }

    if (step === 2 && !form.structureLater) {
      for (const subsidiary of subsidiaries) {
        if (!subsidiary.name.trim()) {
          return "Every subsidiary row must have a name, or remove the empty row.";
        }
      }
    }

    if (step === 3 && !form.inviteLater) {
      for (const invite of inviteUsers) {
        if (!invite.email.trim()) continue;
        if (!isValidEmail(invite.email.trim())) {
          return `Invitation email '${invite.email}' is invalid.`;
        }
      }
    }

    return "";
  }

  async function completeOnboarding() {
    setError("");
    setLoading(true);

    try {
      const setup = await api.post<SetupResponse>("/organizations/setup", {
        name: form.organizationName.trim(),
        legal_name: form.legalName.trim() || null,
        registration_number: form.registrationNumber.trim() || null,
        country: form.country,
        jurisdiction: form.jurisdiction.trim() || null,
        industry: form.industry,
        default_currency: form.currency,
        reporting_year: Number(form.reportingYear),
        standards: selectedStandards,
        consolidation_approach: form.consolidationApproach,
        ghg_scope_approach: form.ghgScopeApproach,
        subsidiaries: form.structureLater
          ? []
          : subsidiaries
              .filter((item) => item.name.trim())
              .map((item) => ({
                name: item.name.trim(),
                entity_type: item.entity_type,
                country: item.country || form.country,
                ownership_percent: item.ownership_percent,
              })),
        invite_users: form.inviteLater
          ? []
          : inviteUsers
              .filter((item) => item.email.trim())
              .map((item) => ({
                email: item.email.trim(),
                role: item.role,
              })),
      });

      await api.post("/auth/context/organization", {
        organization_id: setup.organization_id,
      });

      await queryClient.invalidateQueries({ queryKey: ["auth-me"] });

      saveOnboardingSummary({
        organizationName: form.organizationName.trim(),
        plannedStandards,
        warnings: [],
      });

      await queryClient.invalidateQueries({ queryKey: ["org-settings"] });
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      await queryClient.invalidateQueries({ queryKey: ["entities"] });
      router.push(setup.next_step || "/dashboard");
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : "Unable to complete onboarding."
      );
    } finally {
      setLoading(false);
    }
  }

  if (meLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (isPlatformAdmin) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Organization Setup</h2>
          <p className="mt-1 text-sm text-slate-500">
            Platform admins should use tenant creation and support mode instead of onboarding.
          </p>
        </div>
        <Card>
          <CardContent className="p-6">
            <Button onClick={() => router.push("/platform/tenants")}>
              Go to Tenant Management
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (hasOrganizationRole) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Organization Setup</h2>
          <p className="mt-1 text-sm text-slate-500">
            Your account is already attached to an organization.
          </p>
        </div>
        <Card>
          <CardContent className="flex items-center justify-between gap-4 p-6">
            <p className="text-sm text-slate-600">
              Open the dashboard to continue working in ESGvist.
            </p>
            <Button onClick={() => router.push("/dashboard")}>Go to Dashboard</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const nextError = validateCurrentStep();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-900">Organization Setup</h2>
          <p className="mt-1 text-sm text-slate-500">
            Create your tenant, establish the root organization, and prepare the first reporting workspace.
          </p>
        </div>
        <Badge variant="outline">Step {step + 1} of {STEP_TITLES.length}</Badge>
      </div>

      <div className="grid gap-3 md:grid-cols-5">
        {STEP_TITLES.map((title, index) => (
          <button
            key={title}
            type="button"
            onClick={() => index <= step && setStep(index)}
            className={
              index === step
                ? "rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-left"
                : index < step
                  ? "rounded-2xl border border-green-200 bg-green-50 px-4 py-3 text-left"
                  : "rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left"
            }
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Step {index + 1}
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">{title}</p>
          </button>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.55fr_0.95fr]">
        <Card>
          <CardHeader>
            <CardTitle>{STEP_TITLES[step]}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {step === 0 && (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-1.5 md:col-span-2">
                    <Label htmlFor="organization-name">Organization name</Label>
                    <Input
                      id="organization-name"
                      value={form.organizationName}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          organizationName: event.target.value,
                        }))
                      }
                      placeholder="Green Horizon Group"
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="legal-name">Legal name</Label>
                    <Input
                      id="legal-name"
                      value={form.legalName}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          legalName: event.target.value,
                        }))
                      }
                      placeholder="Green Horizon Holdings Ltd."
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="registration-number">Registration number</Label>
                    <Input
                      id="registration-number"
                      value={form.registrationNumber}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          registrationNumber: event.target.value,
                        }))
                      }
                      placeholder="Optional"
                    />
                  </div>
                  <Select
                    label="Country"
                    value={form.country}
                    onChange={(value) =>
                      setForm((current) => ({ ...current, country: value }))
                    }
                    options={COUNTRY_OPTIONS.map((option) => ({
                      value: option.value,
                      label: option.label,
                    }))}
                  />
                  <Select
                    label="Industry"
                    value={form.industry}
                    onChange={(value) =>
                      setForm((current) => ({ ...current, industry: value }))
                    }
                    options={INDUSTRY_OPTIONS.map((option) => ({
                      value: option.value,
                      label: option.label,
                    }))}
                  />
                  <div className="grid gap-1.5">
                    <Label htmlFor="jurisdiction">Jurisdiction</Label>
                    <Input
                      id="jurisdiction"
                      value={form.jurisdiction}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          jurisdiction: event.target.value,
                        }))
                      }
                      placeholder="Optional"
                    />
                  </div>
                </div>
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm font-medium text-slate-900">Smart defaults</p>
                  <p className="mt-2 text-sm text-slate-600">
                    Currency is inferred from country and can be adjusted now or later in Organization Settings.
                  </p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div className="rounded-xl border border-white bg-white px-3 py-2">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Currency</p>
                      <p className="mt-1 font-medium text-slate-900">{form.currency}</p>
                    </div>
                    <div className="rounded-xl border border-white bg-white px-3 py-2">
                      <p className="text-xs uppercase tracking-wide text-slate-500">Reporting year</p>
                      <p className="mt-1 font-medium text-slate-900">{CURRENT_YEAR}</p>
                    </div>
                  </div>
                </div>
              </>
            )}

            {step === 1 && (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <Select
                    label="Reporting year"
                    value={form.reportingYear}
                    onChange={(value) =>
                      setForm((current) => ({ ...current, reportingYear: value }))
                    }
                    options={Array.from({ length: 4 }).map((_, index) => ({
                      value: String(CURRENT_YEAR + index - 1),
                      label: String(CURRENT_YEAR + index - 1),
                    }))}
                  />
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-sm font-medium text-slate-900">Default boundary</p>
                    <p className="mt-1 text-sm text-slate-600">
                      Financial Reporting Default is created automatically during setup.
                    </p>
                  </div>
                  <Select
                    label="Consolidation approach"
                    value={form.consolidationApproach}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        consolidationApproach: value,
                      }))
                    }
                    options={[
                      { value: "financial_control", label: "Financial control" },
                      { value: "operational_control", label: "Operational control" },
                      { value: "equity_share", label: "Equity share" },
                    ]}
                  />
                  <Select
                    label="GHG scope approach"
                    value={form.ghgScopeApproach}
                    onChange={(value) =>
                      setForm((current) => ({
                        ...current,
                        ghgScopeApproach: value,
                      }))
                    }
                    options={[
                      { value: "location_based", label: "Location based" },
                      { value: "market_based", label: "Market based" },
                    ]}
                  />
                </div>

                <div className="space-y-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      Which standards do you expect to report against?
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      Selected standards are saved as organization defaults and will prefill the first project setup.
                    </p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {STANDARD_OPTIONS.map((option) => {
                      const checked = selectedStandards.includes(option.value);
                      return (
                        <label
                          key={option.value}
                          className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3"
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={(value) =>
                              setSelectedStandards((current) =>
                                value === true
                                  ? [...current, option.value]
                                  : current.filter((item) => item !== option.value)
                              )
                            }
                          />
                          <span className="text-sm text-slate-700">{option.label}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </>
            )}

            {step === 2 && (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-900">Subsidiaries and key entities</p>
                    <p className="mt-1 text-sm text-slate-500">
                      The root entity is created automatically from your organization name.
                    </p>
                  </div>
                  <Button variant="outline" onClick={addSubsidiary}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add subsidiary
                  </Button>
                </div>
                {subsidiaries.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
                    No subsidiaries added yet.
                  </div>
                ) : (
                  <div className="space-y-4">
                    {subsidiaries.map((subsidiary, index) => (
                      <div
                        key={`${subsidiary.name}-${index}`}
                        className="grid gap-4 rounded-2xl border border-slate-200 p-4 md:grid-cols-[1.6fr_1fr_1fr_120px_auto]"
                      >
                        <Input
                          value={subsidiary.name}
                          onChange={(event) =>
                            setSubsidiaries((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, name: event.target.value }
                                  : item
                              )
                            )
                          }
                          placeholder="Subsidiary name"
                        />
                        <Select
                          value={subsidiary.country}
                          onChange={(value) =>
                            setSubsidiaries((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, country: value }
                                  : item
                              )
                            )
                          }
                          options={COUNTRY_OPTIONS.map((option) => ({
                            value: option.value,
                            label: option.label,
                          }))}
                        />
                        <Select
                          value={subsidiary.entity_type}
                          onChange={(value) =>
                            setSubsidiaries((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? {
                                      ...item,
                                      entity_type: value as SubsidiaryDraft["entity_type"],
                                    }
                                  : item
                              )
                            )
                          }
                          options={[
                            { value: "legal_entity", label: "Legal entity" },
                            { value: "branch", label: "Branch" },
                            { value: "joint_venture", label: "Joint venture" },
                          ]}
                        />
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          step="0.1"
                          value={String(subsidiary.ownership_percent)}
                          onChange={(event) =>
                            setSubsidiaries((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? {
                                      ...item,
                                      ownership_percent: Number(event.target.value || 0),
                                    }
                                  : item
                              )
                            )
                          }
                          placeholder="100"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            setSubsidiaries((current) =>
                              current.filter((_, itemIndex) => itemIndex !== index)
                            )
                          }
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
                  <Checkbox
                    checked={form.structureLater}
                    onCheckedChange={(checked) =>
                      setForm((current) => ({
                        ...current,
                        structureLater: checked === true,
                      }))
                    }
                  />
                  <span className="text-sm text-slate-700">I&apos;ll set up the full structure later</span>
                </label>
              </>
            )}

            {step === 3 && (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-900">Invite your team</p>
                    <p className="mt-1 text-sm text-slate-500">
                      You will be created as admin automatically.
                    </p>
                  </div>
                  <Button variant="outline" onClick={addInvite}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add invite
                  </Button>
                </div>
                <div className="space-y-4">
                  {inviteUsers.map((invite, index) => (
                    <div
                      key={`${invite.email}-${index}`}
                      className="grid gap-4 rounded-2xl border border-slate-200 p-4 md:grid-cols-[1.6fr_1fr_auto]"
                    >
                      <Input
                        value={invite.email}
                        onChange={(event) =>
                          setInviteUsers((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, email: event.target.value }
                                : item
                            )
                          )
                        }
                        type="email"
                        placeholder="teammate@company.com"
                      />
                      <Select
                        value={invite.role}
                        onChange={(value) =>
                          setInviteUsers((current) =>
                            current.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, role: value as InviteRole }
                                : item
                            )
                          )
                        }
                        options={[
                          { value: "esg_manager", label: "ESG Manager" },
                          { value: "admin", label: "Admin" },
                        ]}
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() =>
                          setInviteUsers((current) =>
                            current.filter((_, itemIndex) => itemIndex !== index)
                          )
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3">
                  <Checkbox
                    checked={form.inviteLater}
                    onCheckedChange={(checked) =>
                      setForm((current) => ({
                        ...current,
                        inviteLater: checked === true,
                      }))
                    }
                  />
                  <span className="text-sm text-slate-700">I&apos;ll invite users later</span>
                </label>
              </>
            )}

            {step === 4 && (
              <div className="space-y-5">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
                  <p className="text-sm text-slate-500">Organization</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">{form.organizationName || "New organization"}</p>
                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    {form.legalName && (
                      <div>
                        <p className="text-xs uppercase tracking-wide text-slate-500">Legal name</p>
                        <p className="mt-1 text-sm text-slate-900">{form.legalName}</p>
                      </div>
                    )}
                    {form.registrationNumber && (
                      <div>
                        <p className="text-xs uppercase tracking-wide text-slate-500">Registration number</p>
                        <p className="mt-1 text-sm text-slate-900">{form.registrationNumber}</p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Country</p>
                      <p className="mt-1 text-sm text-slate-900">
                        {COUNTRY_OPTIONS.find((option) => option.value === form.country)?.label}
                      </p>
                    </div>
                    {form.jurisdiction && (
                      <div>
                        <p className="text-xs uppercase tracking-wide text-slate-500">Jurisdiction</p>
                        <p className="mt-1 text-sm text-slate-900">{form.jurisdiction}</p>
                      </div>
                    )}
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Industry</p>
                      <p className="mt-1 text-sm text-slate-900">
                        {INDUSTRY_OPTIONS.find((option) => option.value === form.industry)?.label}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Currency</p>
                      <p className="mt-1 text-sm text-slate-900">{form.currency}</p>
                    </div>
                    <div>
                      <p className="text-xs uppercase tracking-wide text-slate-500">Reporting year</p>
                      <p className="mt-1 text-sm text-slate-900">{form.reportingYear}</p>
                    </div>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-sm font-medium text-slate-900">Planned standards</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {plannedStandards.length === 0 ? (
                        <span className="text-sm text-slate-500">No standards selected yet.</span>
                      ) : (
                        plannedStandards.map((standard) => (
                          <Badge key={standard} variant="outline">
                            {standard}
                          </Badge>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-sm font-medium text-slate-900">Team setup</p>
                    <p className="mt-3 text-sm text-slate-600">
                      {form.inviteLater
                        ? "Invitations will be handled later."
                        : `${inviteUsers.filter((item) => item.email.trim()).length} invitation(s) will be attempted.`}
                    </p>
                  </div>
                </div>

                <div className="grid gap-4 lg:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-sm font-medium text-slate-900">Consolidation approach</p>
                    <p className="mt-3 text-sm text-slate-600">{form.consolidationApproach.replace(/_/g, " ")}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 p-4">
                    <p className="text-sm font-medium text-slate-900">GHG scope approach</p>
                    <p className="mt-3 text-sm text-slate-600">{form.ghgScopeApproach.replace(/_/g, " ")}</p>
                  </div>
                </div>

                <div className="rounded-2xl border border-slate-200 p-4">
                  <p className="text-sm font-medium text-slate-900">Structure</p>
                  <p className="mt-3 text-sm text-slate-600">
                    {form.structureLater
                      ? "Only the root organization will be created for now."
                      : `${subsidiaries.filter((item) => item.name.trim()).length} subsidiary entries will be created.`}
                  </p>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button
                variant="outline"
                onClick={() => setStep((current) => Math.max(0, current - 1))}
                disabled={step === 0 || loading}
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              {step === STEP_TITLES.length - 1 ? (
                <Button onClick={() => void completeOnboarding()} disabled={loading}>
                  {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create Organization
                </Button>
              ) : (
                <Button
                  onClick={() => {
                    const validationError = validateCurrentStep();
                    setError(validationError);
                    if (!validationError) {
                      setStep((current) => current + 1);
                    }
                  }}
                  disabled={loading}
                >
                  Next
                  <ChevronRight className="ml-2 h-4 w-4" />
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {step === 0 && <Building2 className="h-4 w-4 text-slate-500" />}
                {step === 1 && <Sparkles className="h-4 w-4 text-slate-500" />}
                {step === 2 && <GitBranch className="h-4 w-4 text-slate-500" />}
                {step === 3 && <Users className="h-4 w-4 text-slate-500" />}
                {step === 4 && <CheckCircle2 className="h-4 w-4 text-slate-500" />}
                AI Hint
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              {step === 0 && "Industry selection influences which ESG metrics and standards are usually introduced first."}
              {step === 1 && "Most teams start with GRI and add IFRS S2 later. The first project can attach whichever standards you choose next."}
              {step === 2 && "You can keep structure minimal today and expand it later in Company Structure without blocking the setup."}
              {step === 3 && "An ESG Manager is usually the best first invite because they can create projects and coordinate assignments."}
              {step === 4 && "This setup creates the tenant, root entity, and default boundary first. Follow-up guidance appears on the dashboard."}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Minimal Path</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              You can complete onboarding with only organization name, country, and industry. Reporting details,
              structure, and invitations can all be finished later.
            </CardContent>
          </Card>

          {nextError && step < STEP_TITLES.length - 1 && (
            <Card className="border-amber-200 bg-amber-50">
              <CardHeader>
                <CardTitle className="text-amber-900">Before you continue</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-amber-800">{nextError}</CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
