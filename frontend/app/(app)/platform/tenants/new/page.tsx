"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  ArrowLeft,
  ArrowRight,
  Check,
  Building2,
  Network,
  UserPlus,
} from "lucide-react";

interface TenantForm {
  name: string;
  country: string;
  industry: string;
  root_entity_name: string;
  root_entity_type: string;
  admin_email: string;
}

const steps = [
  { title: "Tenant Info", icon: Building2, description: "Organization details" },
  { title: "Key Organization", icon: Network, description: "Root entity setup" },
  { title: "First Admin", icon: UserPlus, description: "Admin user invitation" },
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

export default function CreateTenantPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [form, setForm] = useState<TenantForm>({
    name: "",
    country: "",
    industry: "",
    root_entity_name: "",
    root_entity_type: "parent_company",
    admin_email: "",
  });

  const createMutation = useApiMutation(
    "/platform/tenants",
    "POST"
  );

  const updateField = (field: keyof TenantForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const canProceed = () => {
    switch (currentStep) {
      case 0:
        return form.name.trim() && form.country && form.industry;
      case 1:
        return form.root_entity_name.trim();
      case 2:
        return form.admin_email.trim() && form.admin_email.includes("@");
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep((s) => s + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep((s) => s - 1);
    }
  };

  const handleCreate = async () => {
    await createMutation.mutateAsync({
      name: form.name,
      country: form.country,
      industry: form.industry,
      root_entity: {
        name: form.root_entity_name,
        type: form.root_entity_type,
      },
      admin_email: form.admin_email,
    } as never);
    router.push("/platform/tenants");
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold text-slate-900">
            Create Organization
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Set up a new tenant on the platform
          </p>
        </div>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center justify-between">
        {steps.map((step, index) => {
          const StepIcon = step.icon;
          const isActive = index === currentStep;
          const isComplete = index < currentStep;

          return (
            <div key={step.title} className="flex flex-1 items-center">
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                    isComplete
                      ? "border-green-500 bg-green-500 text-white"
                      : isActive
                        ? "border-blue-500 bg-blue-50 text-blue-600"
                        : "border-slate-200 bg-white text-slate-400"
                  )}
                >
                  {isComplete ? (
                    <Check className="h-5 w-5" />
                  ) : (
                    <StepIcon className="h-5 w-5" />
                  )}
                </div>
                <div className="hidden sm:block">
                  <p
                    className={cn(
                      "text-sm font-medium",
                      isActive ? "text-slate-900" : "text-slate-500"
                    )}
                  >
                    {step.title}
                  </p>
                  <p className="text-xs text-slate-400">{step.description}</p>
                </div>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    "mx-4 h-0.5 flex-1",
                    isComplete ? "bg-green-500" : "bg-slate-200"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{steps[currentStep].title}</CardTitle>
          <CardDescription>{steps[currentStep].description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {currentStep === 0 && (
            <>
              <div className="space-y-2">
                <Label htmlFor="name">Organization Name</Label>
                <Input
                  id="name"
                  value={form.name}
                  onChange={(e) => updateField("name", e.target.value)}
                  placeholder="Enter organization name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="country">Country</Label>
                <Select
                  id="country"
                  options={countryOptions}
                  value={form.country}
                  onChange={(val) => updateField("country", val)}
                  placeholder="Select country"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="industry">Industry</Label>
                <Select
                  id="industry"
                  options={industryOptions}
                  value={form.industry}
                  onChange={(val) => updateField("industry", val)}
                  placeholder="Select industry"
                />
              </div>
            </>
          )}

          {currentStep === 1 && (
            <>
              <div className="space-y-2">
                <Label htmlFor="root_entity_name">Root Entity Name</Label>
                <Input
                  id="root_entity_name"
                  value={form.root_entity_name}
                  onChange={(e) =>
                    updateField("root_entity_name", e.target.value)
                  }
                  placeholder="e.g., Acme Corporation"
                />
              </div>
              <div className="space-y-2">
                <Label>Entity Type</Label>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">Parent Company</Badge>
                  <span className="text-xs text-slate-400">
                    Root entity is always a parent company
                  </span>
                </div>
              </div>
            </>
          )}

          {currentStep === 2 && (
            <>
              <div className="space-y-2">
                <Label htmlFor="admin_email">Admin Email</Label>
                <Input
                  id="admin_email"
                  type="email"
                  value={form.admin_email}
                  onChange={(e) => updateField("admin_email", e.target.value)}
                  placeholder="admin@company.com"
                />
                <p className="text-xs text-slate-500">
                  An invitation will be sent to this email address
                </p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Review (shown at last step) */}
      {currentStep === 2 && form.admin_email && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Organization</span>
                <span className="font-medium">{form.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Country</span>
                <span className="font-medium">{form.country}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Industry</span>
                <span className="font-medium">{form.industry}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Root Entity</span>
                <span className="font-medium">{form.root_entity_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Admin Email</span>
                <span className="font-medium">{form.admin_email}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentStep === 0}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>
        {currentStep < steps.length - 1 ? (
          <Button onClick={handleNext} disabled={!canProceed()}>
            Next
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        ) : (
          <Button
            onClick={handleCreate}
            disabled={!canProceed() || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Check className="mr-2 h-4 w-4" />
            )}
            Review &amp; Create
          </Button>
        )}
      </div>
    </div>
  );
}
