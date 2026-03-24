"use client";

import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AIFieldExplain } from "@/components/ai-inline-explain";
import { ChevronLeft, ChevronRight, HelpCircle } from "lucide-react";

interface FormField {
  shared_element_id: number;
  requirement_item_id?: number;
  assignment_id?: number | null;
  entity_id?: number | null;
  facility_id?: number | null;
  visible: boolean;
  required: boolean;
  help_text?: string | null;
  tooltip?: string | null;
  order: number;
}

interface FormStep {
  id: string;
  title: string;
  fields: FormField[];
}

interface FormConfig {
  steps: FormStep[];
}

interface WizardRendererProps {
  config: FormConfig;
  values?: Record<number, string>;
  onChange?: (elementId: number, value: string) => void;
  onSubmit?: () => void;
  isSubmitting?: boolean;
  elementNames?: Record<number, string>;
  submitLabel?: string;
  renderField?: (field: FormField) => ReactNode;
}

export function WizardRenderer({
  config,
  values = {},
  onChange = () => undefined,
  onSubmit = () => undefined,
  isSubmitting = false,
  elementNames = {},
  submitLabel = "Submit",
  renderField,
}: WizardRendererProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const steps = config.steps ?? [];

  if (steps.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-slate-400">
          No form configuration available.
        </CardContent>
      </Card>
    );
  }

  const step = steps[currentStep];
  const visibleFields = (step?.fields ?? [])
    .filter((f) => f.visible)
    .sort((a, b) => a.order - b.order);
  const isFirst = currentStep === 0;
  const isLast = currentStep === steps.length - 1;
  const fieldKey = (field: FormField) =>
    [
      field.shared_element_id,
      field.assignment_id ?? "na",
      field.entity_id ?? "na",
      field.facility_id ?? "na",
      field.order,
    ].join(":");

  return (
    <div className="space-y-4">
      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => (
          <button
            key={s.id}
            onClick={() => setCurrentStep(i)}
            className={cn(
              "flex h-8 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors",
              i === currentStep
                ? "bg-blue-100 text-blue-700"
                : i < currentStep
                  ? "bg-green-50 text-green-700"
                  : "bg-slate-100 text-slate-500"
            )}
          >
            <span className="font-bold">{i + 1}</span>
            <span className="hidden sm:inline">{s.title}</span>
          </button>
        ))}
      </div>

      {/* Step content */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{step.title}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {visibleFields.map((field) =>
            renderField ? (
              <div key={fieldKey(field)}>{renderField(field)}</div>
            ) : (
              <div key={fieldKey(field)}>
                <div className="flex items-center gap-2">
                  <label className="block text-sm font-medium text-slate-700">
                    {elementNames[field.shared_element_id] ??
                      `Element #${field.shared_element_id}`}
                  </label>
                  {field.required && (
                    <Badge variant="outline" className="text-[10px]">
                      Required
                    </Badge>
                  )}
                  {field.requirement_item_id ? (
                    <AIFieldExplain requirementItemId={field.requirement_item_id} />
                  ) : field.tooltip ? (
                    <span title={field.tooltip}>
                      <HelpCircle className="h-3.5 w-3.5 text-slate-400" />
                    </span>
                  ) : null}
                </div>
                {field.help_text && (
                  <p className="mt-0.5 text-xs text-slate-400">
                    {field.help_text}
                  </p>
                )}
                <Input
                  className="mt-1"
                  value={values[field.shared_element_id] ?? ""}
                  onChange={(e) =>
                    onChange(field.shared_element_id, e.target.value)
                  }
                  placeholder={`Enter value for ${elementNames[field.shared_element_id] ?? `element #${field.shared_element_id}`}`}
                />
              </div>
            )
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={() => setCurrentStep((s) => s - 1)}
          disabled={isFirst}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Previous
        </Button>
        {isLast ? (
          <Button onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Submitting..." : submitLabel}
          </Button>
        ) : (
          <Button onClick={() => setCurrentStep((s) => s + 1)}>
            Next
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
