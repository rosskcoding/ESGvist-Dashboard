"use client";

import { useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Upload,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  FileText,
  Info,
  Loader2,
} from "lucide-react";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/* ---------- Types ---------- */

interface DataPointDetail {
  id: string;
  element_code: string;
  element_name: string;
  element_type: "numeric" | "text" | "boolean";
  entity_name: string;
  facility_name: string;
  boundary_status: string;
  consolidation_method: string;
  standards: { code: string; name: string }[];
  evidence_required: boolean;
  dimensions: { scope?: boolean; gas_type?: boolean; category?: boolean };
  previous_value?: string;
  previous_unit?: string;
  unit_options: string[];
  methodology_options: string[];
}

interface GateCheckResult {
  passed: boolean;
  blockers: { message: string; code: string }[];
  warnings: { message: string; code: string }[];
}

interface FormData {
  value: string;
  unit: string;
  methodology: string;
  narrative: string;
  scope: string;
  gas_type: string;
  category: string;
  files: File[];
}

/* ---------- Step indicator ---------- */

const STEPS = ["Context", "Data Entry", "Preview", "Submit"] as const;

function StepIndicator({ current }: { current: number }) {
  return (
    <nav className="flex items-center justify-center gap-2">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={label} className="flex items-center gap-2">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                done && "bg-green-500 text-white",
                active && "bg-blue-600 text-white",
                !done && !active && "bg-slate-100 text-slate-400"
              )}
            >
              {done ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            <span
              className={cn(
                "text-sm font-medium",
                active ? "text-slate-900" : "text-slate-400"
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <div className="mx-2 h-px w-8 bg-slate-200" />
            )}
          </div>
        );
      })}
    </nav>
  );
}

/* ---------- Component ---------- */

export default function DataEntryWizardPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormData>({
    value: "",
    unit: "",
    methodology: "",
    narrative: "",
    scope: "",
    gas_type: "",
    category: "",
    files: [],
  });
  const [validationErrors, setValidationErrors] = useState<
    Record<string, string>
  >({});
  const [gateResult, setGateResult] = useState<GateCheckResult | null>(null);
  const [submitted, setSubmitted] = useState(false);

  /* Fetch data point detail */
  const { data: dp, isLoading } = useApiQuery<DataPointDetail>(
    ["data-point", id],
    `/api/data-points/${id}`
  );

  /* Gate check mutation */
  const gateCheck = useApiMutation<GateCheckResult>(
    "/api/gate-check",
    "POST"
  );

  /* Submit mutation */
  const submitMutation = useApiMutation(
    `/api/data-points/${id}`,
    "PATCH"
  );

  const updateField = useCallback(
    <K extends keyof FormData>(field: K, value: FormData[K]) => {
      setForm((prev) => ({ ...prev, [field]: value }));
      setValidationErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    },
    []
  );

  /* Drag-drop handlers */
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const droppedFiles = Array.from(e.dataTransfer.files);
      updateField("files", [...form.files, ...droppedFiles]);
    },
    [form.files, updateField]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        const selected = Array.from(e.target.files);
        updateField("files", [...form.files, ...selected]);
      }
    },
    [form.files, updateField]
  );

  const removeFile = useCallback(
    (index: number) => {
      updateField(
        "files",
        form.files.filter((_, i) => i !== index)
      );
    },
    [form.files, updateField]
  );

  /* Validate step 2 */
  const validateDataEntry = (): boolean => {
    const errors: Record<string, string> = {};

    if (!form.value.trim()) {
      errors.value = "Value is required";
    }
    if (dp?.element_type === "numeric" && isNaN(Number(form.value))) {
      errors.value = "Must be a valid number";
    }
    if (!form.unit) {
      errors.unit = "Unit is required";
    }
    if (!form.methodology) {
      errors.methodology = "Methodology is required";
    }
    if (dp?.evidence_required && form.files.length === 0) {
      errors.files = "Evidence is required for this data point";
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  /* Navigation */
  const goNext = async () => {
    if (step === 1) {
      if (!validateDataEntry()) return;
    }

    if (step === 2 && !gateResult) {
      // Run gate check
      try {
        const result = await gateCheck.mutateAsync({
          action: "submit_data_point",
          data_point_id: id,
          value: form.value,
          unit: form.unit,
          methodology: form.methodology,
        });
        setGateResult(result);
      } catch {
        setGateResult({
          passed: false,
          blockers: [
            {
              message: "Gate check could not be completed",
              code: "GATE_CHECK_ERROR",
            },
          ],
          warnings: [],
        });
      }
      return;
    }

    if (step < STEPS.length - 1) {
      setStep(step + 1);
    }
  };

  const goBack = () => {
    if (step > 0) {
      if (step === 2) setGateResult(null);
      setStep(step - 1);
    }
  };

  const handleSubmit = async () => {
    try {
      await submitMutation.mutateAsync({
        status: "submitted",
        value: form.value,
        unit: form.unit,
        methodology: form.methodology,
        narrative: form.narrative,
        scope: form.scope || undefined,
        gas_type: form.gas_type || undefined,
        category: form.category || undefined,
      });
      setSubmitted(true);
    } catch {
      // Error handled by mutation state
    }
  };

  /* ---------- Loading / Not found ---------- */

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-16 text-gray-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading data point...
      </div>
    );
  }

  if (!dp) {
    return (
      <div className="flex flex-col items-center justify-center p-16 text-gray-400">
        <p>Data point not found.</p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push("/collection")}
        >
          Back to Collection
        </Button>
      </div>
    );
  }

  /* ---------- Steps ---------- */

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Back link */}
      <button
        onClick={() => router.push("/collection")}
        className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Collection
      </button>

      {/* Step indicator */}
      <StepIndicator current={step} />

      {/* ---------- Step 0: Context ---------- */}
      {step === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Context</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs font-medium uppercase text-slate-400">
                  Element Name
                </p>
                <p className="mt-1 text-sm font-semibold text-slate-900">
                  {dp.element_name}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase text-slate-400">
                  Element Code
                </p>
                <p className="mt-1 font-mono text-sm text-slate-700">
                  {dp.element_code}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase text-slate-400">
                  Entity
                </p>
                <p className="mt-1 text-sm text-slate-700">{dp.entity_name}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase text-slate-400">
                  Facility
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  {dp.facility_name}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase text-slate-400">
                  Boundary Status
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  {dp.boundary_status}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase text-slate-400">
                  Consolidation Method
                </p>
                <p className="mt-1 text-sm text-slate-700">
                  {dp.consolidation_method}
                </p>
              </div>
            </div>

            {/* Standards */}
            <div>
              <p className="text-xs font-medium uppercase text-slate-400">
                Required by Standards
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(dp.standards ?? []).map((s) => (
                  <Badge key={s.code} variant="secondary">
                    {s.code} &mdash; {s.name}
                  </Badge>
                ))}
              </div>
            </div>

            {/* Evidence indicator */}
            {dp.evidence_required && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <Info className="h-4 w-4 shrink-0" />
                Evidence upload is required for this data point.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ---------- Step 1: Data Entry ---------- */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Data Entry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Value */}
            <Input
              label="Value"
              type={dp.element_type === "numeric" ? "number" : "text"}
              placeholder={
                dp.element_type === "numeric"
                  ? "Enter numeric value"
                  : "Enter value"
              }
              value={form.value}
              onChange={(e) => updateField("value", e.target.value)}
              error={validationErrors.value}
            />

            {/* Unit selector */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">
                Unit
              </label>
              <select
                value={form.unit}
                onChange={(e) => updateField("unit", e.target.value)}
                className={cn(
                  "h-9 w-full rounded-md border bg-transparent px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950",
                  validationErrors.unit
                    ? "border-red-500 focus:ring-red-500"
                    : "border-slate-200"
                )}
              >
                <option value="">Select unit...</option>
                {(dp.unit_options ?? []).map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
              {validationErrors.unit && (
                <p className="text-xs text-red-500">{validationErrors.unit}</p>
              )}
            </div>

            {/* Methodology */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">
                Methodology
              </label>
              <select
                value={form.methodology}
                onChange={(e) => updateField("methodology", e.target.value)}
                className={cn(
                  "h-9 w-full rounded-md border bg-transparent px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950",
                  validationErrors.methodology
                    ? "border-red-500 focus:ring-red-500"
                    : "border-slate-200"
                )}
              >
                <option value="">Select methodology...</option>
                {(dp.methodology_options ?? []).map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              {validationErrors.methodology && (
                <p className="text-xs text-red-500">
                  {validationErrors.methodology}
                </p>
              )}
            </div>

            {/* Narrative */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">
                Narrative / Notes
              </label>
              <textarea
                rows={3}
                value={form.narrative}
                onChange={(e) => updateField("narrative", e.target.value)}
                placeholder="Add any notes or explanations..."
                className="w-full rounded-md border border-slate-200 bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-950"
              />
            </div>

            {/* Dimensions */}
            {(dp.dimensions?.scope ||
              dp.dimensions?.gas_type ||
              dp.dimensions?.category) && (
              <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <h4 className="text-sm font-semibold text-slate-700">
                  Dimensions
                </h4>
                <div className="grid grid-cols-3 gap-4">
                  {dp.dimensions.scope && (
                    <div className="grid gap-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        Scope
                      </label>
                      <select
                        value={form.scope}
                        onChange={(e) => updateField("scope", e.target.value)}
                        className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                      >
                        <option value="">Select...</option>
                        <option value="scope_1">Scope 1</option>
                        <option value="scope_2">Scope 2</option>
                        <option value="scope_3">Scope 3</option>
                      </select>
                    </div>
                  )}
                  {dp.dimensions.gas_type && (
                    <div className="grid gap-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        Gas Type
                      </label>
                      <select
                        value={form.gas_type}
                        onChange={(e) =>
                          updateField("gas_type", e.target.value)
                        }
                        className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                      >
                        <option value="">Select...</option>
                        <option value="co2">CO2</option>
                        <option value="ch4">CH4</option>
                        <option value="n2o">N2O</option>
                        <option value="hfcs">HFCs</option>
                        <option value="pfcs">PFCs</option>
                        <option value="sf6">SF6</option>
                        <option value="nf3">NF3</option>
                      </select>
                    </div>
                  )}
                  {dp.dimensions.category && (
                    <div className="grid gap-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        Category
                      </label>
                      <Input
                        value={form.category}
                        onChange={(e) =>
                          updateField("category", e.target.value)
                        }
                        placeholder="e.g. Energy, Transport"
                      />
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Evidence upload */}
            <div className="grid gap-1.5">
              <label className="text-sm font-medium text-slate-700">
                Evidence
                {dp.evidence_required && (
                  <span className="ml-1 text-red-500">*</span>
                )}
              </label>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
                  dragOver
                    ? "border-blue-400 bg-blue-50"
                    : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                )}
              >
                <Upload className="h-8 w-8 text-slate-300" />
                <p className="mt-2 text-sm text-slate-500">
                  Drag and drop files here, or click to browse
                </p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={handleFileSelect}
                />
              </div>
              {validationErrors.files && (
                <p className="text-xs text-red-500">
                  {validationErrors.files}
                </p>
              )}

              {/* File list */}
              {form.files.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {form.files.map((f, i) => (
                    <li
                      key={i}
                      className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-sm"
                    >
                      <span className="flex items-center gap-2 text-slate-700">
                        <FileText className="h-4 w-4 text-slate-400" />
                        {f.name}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeFile(i)}
                        className="text-slate-400 hover:text-red-500"
                      >
                        <XCircle className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ---------- Step 2: Preview ---------- */}
      {step === 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Preview &amp; Gate Check</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Summary */}
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <h4 className="mb-3 text-sm font-semibold text-slate-700">
                Data Summary
              </h4>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <div>
                  <dt className="text-slate-400">Element</dt>
                  <dd className="font-medium text-slate-900">
                    {dp.element_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-400">Value</dt>
                  <dd className="font-medium text-slate-900">
                    {form.value} {form.unit}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-400">Methodology</dt>
                  <dd className="text-slate-700">{form.methodology}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Evidence</dt>
                  <dd className="text-slate-700">
                    {form.files.length} file(s) attached
                  </dd>
                </div>
                {form.narrative && (
                  <div className="col-span-2">
                    <dt className="text-slate-400">Narrative</dt>
                    <dd className="text-slate-700">{form.narrative}</dd>
                  </div>
                )}
                {form.scope && (
                  <div>
                    <dt className="text-slate-400">Scope</dt>
                    <dd className="text-slate-700">{form.scope}</dd>
                  </div>
                )}
                {form.gas_type && (
                  <div>
                    <dt className="text-slate-400">Gas Type</dt>
                    <dd className="text-slate-700">{form.gas_type}</dd>
                  </div>
                )}
                {form.category && (
                  <div>
                    <dt className="text-slate-400">Category</dt>
                    <dd className="text-slate-700">{form.category}</dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Gate check results */}
            {gateCheck.isPending && (
              <div className="flex items-center justify-center gap-2 py-8 text-slate-400">
                <Loader2 className="h-5 w-5 animate-spin" />
                Running gate checks...
              </div>
            )}

            {gateResult && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-700">
                  Gate Check Results
                </h4>

                {gateResult.blockers.length === 0 &&
                  gateResult.warnings.length === 0 && (
                    <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      All checks passed. Ready to submit.
                    </div>
                  )}

                {gateResult.blockers.map((b, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                  >
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <span className="font-medium">Blocker:</span>{" "}
                      {b.message}
                    </div>
                  </div>
                ))}

                {gateResult.warnings.map((w, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                  >
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <span className="font-medium">Warning:</span>{" "}
                      {w.message}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ---------- Step 3: Submit ---------- */}
      {step === 3 && (
        <Card>
          <CardHeader>
            <CardTitle>
              {submitted ? "Submitted!" : "Confirm Submission"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {submitted ? (
              <div className="flex flex-col items-center gap-4 py-8">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                </div>
                <p className="text-lg font-semibold text-slate-900">
                  Data point submitted successfully
                </p>
                <p className="text-sm text-slate-500">
                  Your data has been submitted for review.
                </p>
                <Button onClick={() => router.push("/collection")}>
                  Back to Collection
                </Button>
              </div>
            ) : (
              <>
                <p className="text-sm text-slate-600">
                  You are about to submit{" "}
                  <span className="font-semibold">{dp.element_name}</span> with
                  value{" "}
                  <span className="font-semibold">
                    {form.value} {form.unit}
                  </span>
                  . This will move the data point into review.
                </p>

                {submitMutation.isError && (
                  <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    <XCircle className="h-4 w-4 shrink-0" />
                    Submission failed. Please try again.
                  </div>
                )}

                <Button
                  onClick={handleSubmit}
                  disabled={submitMutation.isPending}
                  className="w-full"
                >
                  {submitMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Check className="h-4 w-4" />
                      Submit Data Point
                    </>
                  )}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* ---------- Navigation ---------- */}
      {!submitted && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={goBack}
            disabled={step === 0}
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>

          {step < 3 && (
            <Button
              onClick={goNext}
              disabled={
                (step === 2 && gateCheck.isPending) ||
                (step === 2 &&
                  gateResult !== null &&
                  gateResult.blockers.length > 0)
              }
            >
              {step === 2 && !gateResult ? (
                "Run Gate Check"
              ) : (
                <>
                  Next
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
