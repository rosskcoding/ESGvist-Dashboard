"use client";

import { useEffect, useEffectEvent, useId, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Loader2,
  ShieldAlert,
  Upload,
  XCircle,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

interface GuidedRow {
  id: number;
  data_point_id?: number | null;
  assignment_id?: number | null;
  shared_element_id?: number | null;
  entity_id?: number | null;
  facility_id?: number | null;
  element_code: string;
  element_name: string;
  collection_status: "missing" | "partial" | "complete";
  entity_name: string;
  facility_name: string | null;
  boundary_status: "included" | "excluded" | "partial";
  consolidation_method: string;
  reused_across_standards: boolean;
  standards: string[];
}

interface FormConfigField {
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

interface DataPointDetail {
  id: number;
  reporting_project_id: number;
  status: string;
  element_code: string;
  element_name: string;
  element_type: "numeric" | "text" | "boolean";
  numeric_value?: number | null;
  text_value?: string | null;
  unit_code?: string | null;
  methodology?: string | null;
  entity_name?: string | null;
  facility_name?: string | null;
  boundary_status: string;
  consolidation_method: string;
  related_standards: { code: string; name: string }[];
  evidence_required: boolean;
  evidence_count: number;
  dimensions: { scope?: boolean; gas_type?: boolean; category?: boolean };
  unit_options: string[];
  methodology_options: string[];
}

interface GateCheckResult {
  allowed: boolean;
  failedGates: { message: string; code: string }[];
  warnings: { message: string; code: string }[];
}

interface GuidedEntryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: number;
  row: GuidedRow | null;
  field: FormConfigField | null;
  rowKey: string | null;
  onDataPointResolved: (rowKey: string, dataPointId: number) => void;
}

interface GuidedEntryForm {
  value: string;
  unit: string;
  methodology: string;
  scope: string;
  gas_type: string;
  category: string;
  files: File[];
}

const EMPTY_FORM: GuidedEntryForm = {
  value: "",
  unit: "",
  methodology: "",
  scope: "",
  gas_type: "",
  category: "",
  files: [],
};

function isEditableStatus(status: string | undefined) {
  return status ? ["draft", "needs_revision", "rejected"].includes(status) : false;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function GuidedEntryDialog({
  open,
  onOpenChange,
  projectId,
  row,
  field,
  rowKey,
  onDataPointResolved,
}: GuidedEntryDialogProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const scopeSelectId = useId();
  const gasTypeSelectId = useId();
  const categoryInputId = useId();

  const [detail, setDetail] = useState<DataPointDetail | null>(null);
  const [form, setForm] = useState<GuidedEntryForm>(EMPTY_FORM);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [gateResult, setGateResult] = useState<GateCheckResult | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionTone, setActionTone] = useState<"success" | "error" | "info">("info");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const notifyDataPointResolved = useEffectEvent((currentRowKey: string, dataPointId: number) => {
    onDataPointResolved(currentRowKey, dataPointId);
  });

  const isEditable = isEditableStatus(detail?.status);
  const fullWizardUrl = useMemo(() => {
    if (!detail?.id) return null;
    return `/collection/${detail.id}?projectId=${projectId}`;
  }, [detail?.id, projectId]);

  useEffect(() => {
    if (!open || !row || !rowKey || !row.shared_element_id) {
      if (!open) {
        setDetail(null);
        setForm(EMPTY_FORM);
        setValidationErrors({});
        setGateResult(null);
        setLoadError(null);
        setActionMessage(null);
        setActionTone("info");
        setIsLoading(false);
        setIsSaving(false);
        setIsChecking(false);
        setIsSubmitting(false);
      }
      return;
    }

    let cancelled = false;
    const currentRow = row;
    const currentRowKey = rowKey;

    async function loadOrCreateDataPoint() {
      setIsLoading(true);
      setLoadError(null);
      setActionMessage(null);
      setGateResult(null);
      setValidationErrors({});

      try {
        const payload = currentRow.data_point_id
          ? await api.get<DataPointDetail>(`/data-points/${currentRow.data_point_id}`)
          : await api.post<DataPointDetail>(`/projects/${projectId}/data-points`, {
              shared_element_id: currentRow.shared_element_id,
              entity_id: currentRow.entity_id ?? undefined,
              facility_id: currentRow.facility_id ?? undefined,
            });

        if (cancelled) return;
        setDetail(payload);
        setForm({
          value:
            payload.element_type === "numeric"
              ? (payload.numeric_value ?? "").toString()
              : payload.text_value ?? "",
          unit: payload.unit_code ?? "",
          methodology: payload.methodology ?? "",
          scope: "",
          gas_type: "",
          category: "",
          files: [],
        });
        notifyDataPointResolved(currentRowKey, payload.id);
      } catch (error) {
        if (cancelled) return;
        setLoadError(errorMessage(error, "Unable to prepare guided entry for this field."));
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadOrCreateDataPoint();

    return () => {
      cancelled = true;
    };
  }, [open, projectId, rowKey]);

  function updateField<K extends keyof GuidedEntryForm>(key: K, value: GuidedEntryForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setActionMessage(null);
    setActionTone("info");
    setGateResult(null);
    setValidationErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function validateForSubmission() {
    if (!detail) return false;

    const errors: Record<string, string> = {};
    if (!form.value.trim()) {
      errors.value = "Value is required";
    }
    if (detail.element_type === "numeric" && Number.isNaN(Number(form.value))) {
      errors.value = "Must be a valid number";
    }
    if (detail.element_type === "numeric" && !form.unit) {
      errors.unit = "Unit is required";
    }
    if (!form.methodology) {
      errors.methodology = "Methodology is required";
    }
    if (detail.evidence_required && form.files.length === 0 && detail.evidence_count === 0) {
      errors.files = "Evidence is required before submission";
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function uploadSelectedEvidence(dataPointId: number) {
    if (!detail || form.files.length === 0) return;

    const createdCount = form.files.length;
    for (const file of form.files) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name);
      formData.append("description", `Uploaded from guided collection for ${detail.element_name}`);
      const evidence = await api.upload<{ id: number }>("/evidences/upload", formData);
      await api.post(`/data-points/${dataPointId}/evidences`, { evidence_id: evidence.id });
    }

    setDetail((current) =>
      current ? { ...current, evidence_count: current.evidence_count + createdCount } : current
    );
    setForm((current) => ({ ...current, files: [] }));
  }

  async function persistDraft() {
    if (!detail) return null;
    if (detail.element_type === "numeric" && form.value.trim() && Number.isNaN(Number(form.value))) {
      setValidationErrors({ value: "Must be a valid number" });
      return null;
    }

    const dimensions = [
      detail.dimensions.scope && form.scope
        ? { dimension_type: "scope", dimension_value: form.scope }
        : null,
      detail.dimensions.gas_type && form.gas_type
        ? { dimension_type: "gas_type", dimension_value: form.gas_type }
        : null,
      detail.dimensions.category && form.category
        ? { dimension_type: "category", dimension_value: form.category }
        : null,
    ].filter(Boolean);

    const updated = await api.patch<DataPointDetail>(`/data-points/${detail.id}`, {
      numeric_value:
        detail.element_type === "numeric" && form.value.trim()
          ? Number(form.value)
          : undefined,
      text_value:
        detail.element_type !== "numeric" && form.value.trim()
          ? form.value
          : undefined,
      unit_code: form.unit || undefined,
      methodology: form.methodology || undefined,
      dimensions,
    });

    setDetail(updated);
    await uploadSelectedEvidence(updated.id);
    await queryClient.invalidateQueries({ queryKey: ["data-points", projectId] });
    await queryClient.invalidateQueries({ queryKey: ["collection-assignments", projectId] });
    return updated;
  }

  async function handleSaveDraft() {
    if (!detail || !isEditable) return;
    setIsSaving(true);
    setActionMessage(null);
    setActionTone("info");
    try {
      const updated = await persistDraft();
      if (!updated) return;
      setActionMessage("Draft saved in guided collection.");
      setActionTone("success");
    } catch (error) {
      setActionMessage(errorMessage(error, "Unable to save this draft."));
      setActionTone("error");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGateCheck() {
    if (!detail || !isEditable) return;
    if (!validateForSubmission()) return;

    setIsChecking(true);
    setActionMessage(null);
    setActionTone("info");
    try {
      const updated = await persistDraft();
      if (!updated) return;
      const result = await api.post<GateCheckResult>("/gate-check", {
        action: "submit_data_point",
        data_point_id: updated.id,
      });
      setGateResult(result);
      if (result.allowed) {
        setActionMessage("Gate checks passed. Field is ready to submit.");
        setActionTone("success");
      }
    } catch (error) {
      setActionMessage(errorMessage(error, "Gate check could not be completed."));
      setActionTone("error");
      setGateResult({
        allowed: false,
        failedGates: [{ code: "GATE_CHECK_ERROR", message: errorMessage(error, "Gate check failed.") }],
        warnings: [],
      });
    } finally {
      setIsChecking(false);
    }
  }

  async function handleSubmit() {
    if (!detail || !isEditable) return;
    if (!validateForSubmission()) return;

    setIsSubmitting(true);
    setActionMessage(null);
    setActionTone("info");
    try {
      const updated = await persistDraft();
      if (!updated) return;

      const result = await api.post<GateCheckResult>("/gate-check", {
        action: "submit_data_point",
        data_point_id: updated.id,
      });
      setGateResult(result);
      if (!result.allowed) {
        return;
      }

      const submitted = await api.post<{ id: number; status: string }>(`/data-points/${updated.id}/submit`);
      setDetail((current) => (current ? { ...current, status: submitted.status } : current));
      setActionMessage(
        submitted.status === "in_review"
          ? "Data point submitted and moved into review."
          : "Data point submitted successfully."
      );
      setActionTone("success");
      await queryClient.invalidateQueries({ queryKey: ["data-points", projectId] });
      await queryClient.invalidateQueries({ queryKey: ["collection-assignments", projectId] });
    } catch (error) {
      setActionMessage(errorMessage(error, "Submission failed. Please try again."));
      setActionTone("error");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Guided Quick Entry</DialogTitle>
          <DialogDescription>
            Save or submit this configured field without leaving the collection screen.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex min-h-[240px] items-center justify-center text-slate-500">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Preparing entry...
          </div>
        ) : loadError ? (
          <div className="flex min-h-[180px] flex-col items-center justify-center rounded-lg border border-red-200 bg-red-50 px-6 py-8 text-center text-red-700">
            <AlertTriangle className="mb-3 h-6 w-6" />
            <p>{loadError}</p>
          </div>
        ) : !detail || !row ? (
          <div className="flex min-h-[180px] items-center justify-center text-slate-500">
            No guided field selected.
          </div>
        ) : (
          <div className="space-y-5">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-white px-2 py-1 font-mono text-[11px] text-slate-600">
                      {detail.element_code}
                    </span>
                    <p className="font-medium text-slate-900">{detail.element_name}</p>
                    {field?.required && (
                      <Badge variant="outline" className="text-[10px]">
                        Required
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                    <span>Entity: {detail.entity_name ?? row.entity_name}</span>
                    {(detail.facility_name ?? row.facility_name) && (
                      <span>Facility: {detail.facility_name ?? row.facility_name}</span>
                    )}
                    <span>Boundary: {detail.boundary_status}</span>
                    <span>Consolidation: {detail.consolidation_method}</span>
                    {row.assignment_id && <span>Assignment #{row.assignment_id}</span>}
                  </div>
                  {field?.help_text && (
                    <p className="whitespace-pre-line text-xs text-slate-500">
                      {field.help_text}
                    </p>
                  )}
                </div>

                <div className="flex flex-col items-end gap-2">
                  <Badge
                    variant={
                      detail.status === "approved"
                        ? "success"
                        : detail.status === "submitted" || detail.status === "in_review"
                          ? "warning"
                          : "secondary"
                    }
                  >
                    {detail.status}
                  </Badge>
                  {detail.evidence_required && (
                    <Badge variant="outline" className="text-[10px]">
                      Evidence required
                    </Badge>
                  )}
                </div>
              </div>

              {(detail.related_standards ?? []).length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {detail.related_standards.map((standard) => (
                    <Badge key={standard.code} variant="outline" className="text-[10px]">
                      {standard.code}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {!isEditable && (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  This data point is read-only while it is in the <span className="font-medium">{detail.status}</span> status.
                </div>
              </div>
            )}

            {actionMessage && (
              <div
                className={cn(
                  "rounded-lg px-4 py-3 text-sm",
                  actionTone === "error" || (gateResult && !gateResult.allowed)
                    ? "border border-red-200 bg-red-50 text-red-800"
                    : actionTone === "success"
                      ? "border border-green-200 bg-green-50 text-green-800"
                      : "border border-slate-200 bg-slate-50 text-slate-700"
                )}
              >
                {actionMessage}
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Value"
                type={detail.element_type === "numeric" ? "number" : "text"}
                value={form.value}
                onChange={(event) => updateField("value", event.target.value)}
                error={validationErrors.value}
                placeholder={
                  detail.element_type === "numeric"
                    ? "Enter numeric value"
                    : "Enter value"
                }
                disabled={!isEditable}
              />

              {detail.element_type === "numeric" ? (
                <Select
                  label="Unit"
                  value={form.unit}
                  onChange={(value) => updateField("unit", value)}
                  options={[
                    { value: "", label: "Select unit" },
                    ...detail.unit_options.map((unit) => ({ value: unit, label: unit })),
                  ]}
                  error={validationErrors.unit}
                  disabled={!isEditable}
                />
              ) : (
                <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
                  This field stores text content. Unit selection is not required.
                </div>
              )}
            </div>

            <Select
              label="Methodology"
              value={form.methodology}
              onChange={(value) => updateField("methodology", value)}
              options={[
                { value: "", label: "Select methodology" },
                ...detail.methodology_options.map((methodology) => ({
                  value: methodology,
                  label: methodology,
                })),
              ]}
              error={validationErrors.methodology}
              disabled={!isEditable}
            />

            {(detail.dimensions.scope || detail.dimensions.gas_type || detail.dimensions.category) && (
              <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <h4 className="text-sm font-semibold text-slate-700">Dimensions</h4>
                <div className="grid gap-4 md:grid-cols-3">
                  {detail.dimensions.scope && (
                    <div className="grid gap-1.5">
                      <label htmlFor={scopeSelectId} className="text-sm font-medium text-slate-700">
                        Scope
                      </label>
                      <select
                        id={scopeSelectId}
                        value={form.scope}
                        onChange={(event) => updateField("scope", event.target.value)}
                        className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        disabled={!isEditable}
                      >
                        <option value="">Select...</option>
                        <option value="scope_1">Scope 1</option>
                        <option value="scope_2">Scope 2</option>
                        <option value="scope_3">Scope 3</option>
                      </select>
                    </div>
                  )}
                  {detail.dimensions.gas_type && (
                    <div className="grid gap-1.5">
                      <label htmlFor={gasTypeSelectId} className="text-sm font-medium text-slate-700">
                        Gas Type
                      </label>
                      <select
                        id={gasTypeSelectId}
                        value={form.gas_type}
                        onChange={(event) => updateField("gas_type", event.target.value)}
                        className="h-9 rounded-md border border-slate-200 bg-white px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-slate-950"
                        disabled={!isEditable}
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
                  {detail.dimensions.category && (
                    <Input
                      id={categoryInputId}
                      label="Category"
                      value={form.category}
                      onChange={(event) => updateField("category", event.target.value)}
                      placeholder="e.g. Energy, Transport"
                      disabled={!isEditable}
                    />
                  )}
                </div>
              </div>
            )}

            <div className="space-y-3 rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-900">Evidence</p>
                  <p className="text-xs text-slate-500">
                    Linked evidence: {detail.evidence_count}
                    {detail.evidence_required ? " (required before submission)" : ""}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={!isEditable}
                >
                  <Upload className="mr-2 h-4 w-4" />
                  Add Files
                </Button>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(event) => {
                  const selected = Array.from(event.target.files ?? []);
                  if (selected.length > 0) {
                    updateField("files", [...form.files, ...selected]);
                  }
                  event.target.value = "";
                }}
              />
              {validationErrors.files && (
                <p className="text-xs text-red-500">{validationErrors.files}</p>
              )}
              {form.files.length > 0 && (
                <ul className="space-y-1">
                  {form.files.map((file, index) => (
                    <li
                      key={`${file.name}-${index}`}
                      className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-sm"
                    >
                      <span className="flex items-center gap-2 text-slate-700">
                        <FileText className="h-4 w-4 text-slate-400" />
                        {file.name}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          updateField(
                            "files",
                            form.files.filter((_, fileIndex) => fileIndex !== index)
                          )
                        }
                        className="text-slate-400 hover:text-red-500"
                        disabled={!isEditable}
                      >
                        <XCircle className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {gateResult && (
              <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <h4 className="text-sm font-semibold text-slate-700">Gate Check Results</h4>
                {gateResult.allowed && gateResult.failedGates.length === 0 && (
                  <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    All checks passed. Ready to submit.
                  </div>
                )}
                {gateResult.failedGates.map((failure) => (
                  <div
                    key={failure.code}
                    className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
                  >
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>{failure.message}</div>
                  </div>
                ))}
                {gateResult.warnings.map((warning) => (
                  <div
                    key={warning.code}
                    className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
                  >
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>{warning.message}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <div className="flex w-full flex-col gap-2 sm:flex-row sm:justify-between">
            <Button
              variant="outline"
              onClick={() => {
                if (!fullWizardUrl) return;
                onOpenChange(false);
                router.push(fullWizardUrl);
              }}
              disabled={!fullWizardUrl}
            >
              Open Full Wizard
            </Button>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Close
              </Button>
              <Button
                variant="outline"
                onClick={() => void handleSaveDraft()}
                disabled={!isEditable || isLoading || isSaving || isChecking || isSubmitting}
              >
                {isSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save Draft"
                )}
              </Button>
              <Button
                variant="outline"
                onClick={() => void handleGateCheck()}
                disabled={!isEditable || isLoading || isSaving || isChecking || isSubmitting}
              >
                {isChecking ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Checking...
                  </>
                ) : (
                  "Check Readiness"
                )}
              </Button>
              <Button
                onClick={() => void handleSubmit()}
                disabled={!isEditable || isLoading || isSaving || isChecking || isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Submitting...
                  </>
                ) : (
                  "Submit"
                )}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
