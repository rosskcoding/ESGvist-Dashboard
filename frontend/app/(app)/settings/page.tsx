"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  Building2,
  Save,
  Upload,
  CheckCircle2,
  Globe,
} from "lucide-react";

interface OrgSettings {
  id: number;
  name: string;
  country: string;
  industry: string;
  currency: string;
  reporting_year: number;
  logo_url: string | null;
  default_boundary_id: number | null;
}

interface Boundary {
  id: number;
  name: string;
}

const currencyOptions = [
  { value: "USD", label: "USD - US Dollar" },
  { value: "EUR", label: "EUR - Euro" },
  { value: "GBP", label: "GBP - British Pound" },
  { value: "CHF", label: "CHF - Swiss Franc" },
  { value: "JPY", label: "JPY - Japanese Yen" },
  { value: "AUD", label: "AUD - Australian Dollar" },
  { value: "CAD", label: "CAD - Canadian Dollar" },
  { value: "SGD", label: "SGD - Singapore Dollar" },
];

const countryOptions = [
  { value: "", label: "Select country" },
  { value: "US", label: "United States" },
  { value: "GB", label: "United Kingdom" },
  { value: "DE", label: "Germany" },
  { value: "FR", label: "France" },
  { value: "NL", label: "Netherlands" },
  { value: "CH", label: "Switzerland" },
  { value: "AU", label: "Australia" },
  { value: "CA", label: "Canada" },
  { value: "JP", label: "Japan" },
  { value: "SG", label: "Singapore" },
];

const industryOptions = [
  { value: "", label: "Select industry" },
  { value: "technology", label: "Technology" },
  { value: "finance", label: "Financial Services" },
  { value: "healthcare", label: "Healthcare" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "energy", label: "Energy" },
  { value: "retail", label: "Retail" },
  { value: "real_estate", label: "Real Estate" },
  { value: "transportation", label: "Transportation" },
  { value: "agriculture", label: "Agriculture" },
  { value: "other", label: "Other" },
];

const currentYear = new Date().getFullYear();
const yearOptions = Array.from({ length: 5 }, (_, i) => ({
  value: String(currentYear - i),
  label: String(currentYear - i),
}));

export default function OrganizationSettingsPage() {
  const [form, setForm] = useState({
    name: "",
    country: "",
    industry: "",
    currency: "USD",
    reporting_year: String(currentYear),
    default_boundary_id: "",
  });
  const [saved, setSaved] = useState(false);

  const { data, isLoading } = useApiQuery<OrgSettings>(
    ["org-settings"],
    "/auth/me/organization"
  );

  const { data: boundaries } = useApiQuery<Boundary[]>(
    ["boundaries-list"],
    "/boundaries"
  );

  const saveMutation = useApiMutation("/auth/me/organization", "PATCH");

  useEffect(() => {
    if (data) {
      setForm({
        name: data.name,
        country: data.country,
        industry: data.industry,
        currency: data.currency,
        reporting_year: String(data.reporting_year),
        default_boundary_id: data.default_boundary_id
          ? String(data.default_boundary_id)
          : "",
      });
    }
  }, [data]);

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaved(false);
    await saveMutation.mutateAsync({
      name: form.name,
      country: form.country,
      industry: form.industry,
      currency: form.currency,
      reporting_year: parseInt(form.reporting_year, 10),
      default_boundary_id: form.default_boundary_id
        ? parseInt(form.default_boundary_id, 10)
        : null,
    } as never);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const boundaryOptions = [
    { value: "", label: "No default boundary" },
    ...(boundaries ?? []).map((b) => ({
      value: String(b.id),
      label: b.name,
    })),
  ];

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">
          Organization Settings
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage your organization&apos;s configuration
        </p>
      </div>

      {/* Organization Details */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Organization Details
          </CardTitle>
          <CardDescription>
            Basic information about your organization
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="orgName">Organization Name</Label>
            <Input
              id="orgName"
              value={form.name}
              onChange={(e) => updateField("name", e.target.value)}
              placeholder="Organization name"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="country">Country</Label>
              <Select
                id="country"
                options={countryOptions}
                value={form.country}
                onChange={(val) => updateField("country", val)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="industry">Industry</Label>
              <Select
                id="industry"
                options={industryOptions}
                value={form.industry}
                onChange={(val) => updateField("industry", val)}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="currency">Currency</Label>
              <Select
                id="currency"
                options={currencyOptions}
                value={form.currency}
                onChange={(val) => updateField("currency", val)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="reportingYear">Reporting Year</Label>
              <Select
                id="reportingYear"
                options={yearOptions}
                value={form.reporting_year}
                onChange={(val) => updateField("reporting_year", val)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Logo */}
      <Card>
        <CardHeader>
          <CardTitle>Logo</CardTitle>
          <CardDescription>
            Upload your organization&apos;s logo for reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex h-20 w-20 items-center justify-center rounded-lg border-2 border-dashed border-slate-200 bg-slate-50">
              {data?.logo_url ? (
                <img
                  src={data.logo_url}
                  alt="Logo"
                  className="h-full w-full rounded-lg object-contain p-2"
                />
              ) : (
                <Building2 className="h-8 w-8 text-slate-300" />
              )}
            </div>
            <div>
              <Button variant="outline" size="sm" disabled>
                <Upload className="mr-2 h-4 w-4" />
                Upload Logo
              </Button>
              <p className="mt-1 text-xs text-slate-400">
                PNG, JPG up to 2MB. Recommended 200x200px.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Default Boundary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-4 w-4" />
            Default Boundary
          </CardTitle>
          <CardDescription>
            Set the default boundary for new projects
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="defaultBoundary">Default Boundary</Label>
            <Select
              id="defaultBoundary"
              options={boundaryOptions}
              value={form.default_boundary_id}
              onChange={(val) => updateField("default_boundary_id", val)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Save */}
      {saved && (
        <Alert variant="success">
          <CheckCircle2 className="h-4 w-4" />
          <AlertDescription>Settings saved successfully</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={saveMutation.isPending}
        >
          {saveMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Settings
        </Button>
      </div>
    </div>
  );
}
