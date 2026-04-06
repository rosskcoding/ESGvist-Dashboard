"use client";

import {
  useEffect,
  useEffectEvent,
  useId,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Circle,
  FileText,
  Loader2,
  ShieldAlert,
  TriangleAlert,
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

const EVIDENCE_FILE_ACCEPT =
  ".pdf,.json,.xlsx,.docx,.csv,.png,.jpg,.jpeg,application/pdf,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/csv,image/png,image/jpeg";

function isEditableStatus(status: string | undefined) {
  return status ? ["draft", "needs_revision", "rejected"].includes(status) : false;
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

type ReadinessTone = "done" | "pending" | "warning";

interface ReadinessItem {
  label: string;
  tone: ReadinessTone;
}

function getStatusBadgeVariant(status: string | undefined) {
  if (status === "approved") return "success" as const;
  if (status === "submitted" || status === "in_review") return "warning" as const;
  return "secondary" as const;
}

function methodologySelectionRequired(
  detail: Pick<DataPointDetail, "methodology_options"> | null | undefined
) {
  return (detail?.methodology_options?.length ?? 0) > 0;
}

function getMethodologyOptions(
  detail: Pick<DataPointDetail, "methodology" | "methodology_options"> | null | undefined
) {
  const options = [...(detail?.methodology_options ?? [])];
  const currentMethodology = detail?.methodology?.trim();
  if (currentMethodology && !options.includes(currentMethodology)) {
    options.unshift(currentMethodology);
  }
  return options;
}

function getReadinessItems(detail: DataPointDetail, form: GuidedEntryForm): ReadinessItem[] {
  const hasStoredValue =
    detail.element_type === "numeric"
      ? detail.numeric_value != null
      : Boolean(detail.text_value?.trim());
  const hasValue = Boolean(form.value.trim()) || hasStoredValue;
  const hasMethodology =
    !methodologySelectionRequired(detail) ||
    Boolean(form.methodology.trim()) ||
    Boolean(detail.methodology?.trim());
  const hasEvidence = !detail.evidence_required || detail.evidence_count + form.files.length > 0;
  const contextTone: ReadinessTone =
    detail.boundary_status === "included" ? "done" : "warning";

  return [
    { label: "Draft created", tone: "done" },
    { label: "Value entered", tone: hasValue ? "done" : "pending" },
    { label: "Methodology", tone: hasMethodology ? "done" : "pending" },
    { label: "Evidence", tone: hasEvidence ? "done" : "pending" },
    {
      label: detail.boundary_status === "included" ? "Context" : "Boundary review",
      tone: contextTone,
    },
  ];
}

function ReadinessIcon({ tone }: { tone: ReadinessTone }) {
  if (tone === "done") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-green-500 text-white">
        <CheckCircle2 className="h-4 w-4" />
      </span>
    );
  }

  if (tone === "warning") {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-md border border-amber-300 bg-amber-50 text-amber-700">
        <TriangleAlert className="h-4 w-4" />
      </span>
    );
  }

  return (
    <span className="flex h-6 w-6 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-400">
      <Circle className="h-4 w-4" />
    </span>
  );
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
  const [isDragOver, setIsDragOver] = useState(false);
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
        setIsDragOver(false);
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

  function addFiles(files: File[]) {
    if (files.length === 0) return;
    updateField("files", [...form.files, ...files]);
  }

  function handleFileSelect(event: ChangeEvent<HTMLInputElement>) {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragOver(false);
    if (!isEditable) return;
    addFiles(Array.from(event.dataTransfer.files ?? []));
  }

  function handleEvidenceZoneKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!isEditable) return;
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    fileInputRef.current?.click();
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
    if (methodologySelectionRequired(detail) && !form.methodology) {
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
    await queryClient.invalidateQueries({
      queryKey: ["collection-selected-detail", updated.id],
    });
    await queryClient.invalidateQueries({
      queryKey: ["collection-selected-evidence", updated.id],
    });
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
      await queryClient.invalidateQueries({
        queryKey: ["collection-selected-detail", updated.id],
      });
      await queryClient.invalidateQueries({
        queryKey: ["collection-selected-evidence", updated.id],
      });
    } catch (error) {
      setActionMessage(errorMessage(error, "Submission failed. Please try again."));
      setActionTone("error");
    } finally {
      setIsSubmitting(false);
    }
  }

  const readinessItems = detail ? getReadinessItems(detail, form) : [];
  const missingReadinessCount = readinessItems.filter((item) => item.tone !== "done").length;
  const linkedEvidenceCount = detail ? detail.evidence_count + form.files.length : 0;
  const availableMethodologyOptions = detail ? getMethodologyOptions(detail) : [];
  const requiresMethodologySelection = detail ? methodologySelectionRequired(detail) : false;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="inset-y-0 left-auto right-0 m-0 h-screen max-h-screen w-screen max-w-[min(1100px,100vw)] rounded-none border-y-0 border-r-0 border-l border-slate-200 bg-white shadow-2xl backdrop:bg-slate-950/35 backdrop:backdrop-blur-[2px]"
        contentClassName="flex h-full flex-col p-0"
        showCloseButton={false}
      >
        {isLoading ? (
          <div className="flex min-h-[240px] flex-1 items-center justify-center text-slate-500">
            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
            Preparing entry...
          </div>
        ) : loadError ? (
          <div className="flex min-h-[180px] flex-1 flex-col items-center justify-center px-6 py-8 text-center text-red-700">
            <AlertTriangle className="mb-3 h-6 w-6" />
            <p>{loadError}</p>
          </div>
        ) : !detail || !row ? (
          <div className="flex min-h-[180px] flex-1 items-center justify-center text-slate-500">
            No guided field selected.
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div className="flex min-w-0 items-center gap-3">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => onOpenChange(false)}
                  aria-label="Close panel"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-xl font-semibold text-slate-900">
                      {detail.element_name}
                    </h2>
                    <Badge variant={getStatusBadgeVariant(detail.status)}>
                      {detail.status}
                    </Badge>
                    {field?.required && (
                      <Badge variant="outline" className="text-[10px]">
                        Required
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 font-mono text-xs text-slate-500">{detail.element_code}</p>
                </div>
              </div>

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
            </div>

            {!isEditable && (
              <div className="border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm text-amber-800">
                <div className="flex items-start gap-2">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    This data point is read-only while it is in the{" "}
                    <span className="font-medium">{detail.status}</span> status.
                  </span>
                </div>
              </div>
            )}

            {actionMessage && (
              <div
                className={cn(
                  "border-b px-6 py-3 text-sm",
                  actionTone === "error" || (gateResult && !gateResult.allowed)
                    ? "border-red-200 bg-red-50 text-red-800"
                    : actionTone === "success"
                      ? "border-green-200 bg-green-50 text-green-800"
                      : "border-slate-200 bg-slate-50 text-slate-700"
                )}
              >
                {actionMessage}
              </div>
            )}

            <div className="min-h-0 flex-1 overflow-y-auto">
              <div className="grid min-h-full grid-cols-1 xl:grid-cols-[minmax(0,1fr)_280px]">
                <div className="space-y-6 px-6 py-5">
                  <section className="space-y-4">
                    <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Context
                    </h3>
                    <div className="space-y-3 rounded-xl border border-slate-200 bg-white">
                      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 text-sm">
                        <span className="text-slate-500">Entity</span>
                        <span className="font-medium text-slate-900">
                          {detail.entity_name ?? row.entity_name}
                        </span>
                      </div>
                      {(detail.facility_name ?? row.facility_name) && (
                        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 text-sm">
                          <span className="text-slate-500">Facility</span>
                          <span className="font-medium text-slate-900">
                            {detail.facility_name ?? row.facility_name}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 text-sm">
                        <span className="text-slate-500">Boundary</span>
                        <span className="font-medium text-slate-900">{detail.boundary_status}</span>
                      </div>
                      <div className="flex items-center justify-between px-4 py-3 text-sm">
                        <span className="text-slate-500">Consolidation</span>
                        <span className="font-medium text-slate-900">{detail.consolidation_method}</span>
                      </div>
                    </div>

                    {(detail.related_standards ?? []).length > 0 && (
                      <div className="space-y-2 rounded-xl border border-cyan-200 bg-cyan-50/70 p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
                            Used in {detail.related_standards.length} standards
                          </Badge>
                          {detail.related_standards.map((standard) => (
                            <Badge
                              key={standard.code}
                              variant="outline"
                              className="text-[10px] uppercase tracking-wide"
                            >
                              {standard.code}
                            </Badge>
                          ))}
                        </div>
                        {detail.related_standards.length > 1 && (
                          <p className="text-sm text-cyan-900">
                            This is one shared data point. Editing it here updates the linked disclosures across the connected standards.
                          </p>
                        )}
                      </div>
                    )}

                    {field?.help_text && (
                      <p className="whitespace-pre-line text-sm leading-6 text-slate-500">
                        {field.help_text}
                      </p>
                    )}
                  </section>

                  <section className="space-y-4">
                    <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      Data Entry
                    </h3>

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

                    {availableMethodologyOptions.length > 0 ? (
                      <div className="space-y-1.5">
                        <Select
                          label="Methodology"
                          value={form.methodology}
                          onChange={(value) => updateField("methodology", value)}
                          options={[
                            {
                              value: "",
                              label: requiresMethodologySelection
                                ? "Select methodology"
                                : "Methodology catalog unavailable",
                            },
                            ...availableMethodologyOptions.map((methodology) => ({
                              value: methodology,
                              label: methodology,
                            })),
                          ]}
                          error={validationErrors.methodology}
                          disabled={!isEditable || !requiresMethodologySelection}
                        />
                        {!requiresMethodologySelection && (
                          <p className="text-xs text-slate-500">
                            No methodology catalog is configured yet, so this field is read-only and not required.
                          </p>
                        )}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-500">
                        No methodologies are configured yet, so this field is not required for this entry.
                      </div>
                    )}

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
                            Linked evidence: {linkedEvidenceCount}
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
                        accept={EVIDENCE_FILE_ACCEPT}
                        className="hidden"
                        onChange={handleFileSelect}
                      />
                      <div
                        role="button"
                        tabIndex={isEditable ? 0 : -1}
                        onClick={() => {
                          if (!isEditable) return;
                          fileInputRef.current?.click();
                        }}
                        onKeyDown={handleEvidenceZoneKeyDown}
                        onDragOver={(event) => {
                          event.preventDefault();
                          if (!isEditable) return;
                          setIsDragOver(true);
                        }}
                        onDragLeave={() => setIsDragOver(false)}
                        onDrop={handleDrop}
                        className={cn(
                          "rounded-xl border-2 border-dashed px-4 py-6 text-center text-sm transition-colors",
                          isEditable
                            ? "cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-200"
                            : "cursor-not-allowed opacity-60",
                          isDragOver
                            ? "border-cyan-400 bg-cyan-50 text-cyan-700"
                            : "border-slate-200 text-slate-400",
                          isEditable && !isDragOver && "hover:border-slate-300 hover:bg-slate-50"
                        )}
                        aria-disabled={!isEditable}
                      >
                        Drop files here or click to browse. Allowed: PDF, JSON, XLSX, DOCX, CSV, PNG, JPG.
                      </div>
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
                  </section>
                </div>

                <aside className="border-t border-slate-200 bg-slate-50/80 px-5 py-5 xl:border-l xl:border-t-0">
                  <div className="space-y-5">
                    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Readiness
                        </h3>
                        <span className="text-sm font-semibold text-amber-700">
                          {missingReadinessCount} missing
                        </span>
                      </div>
                      <div className="space-y-3">
                        {readinessItems.map((item) => (
                          <div
                            key={item.label}
                            className="flex items-center gap-3 border-b border-slate-200 pb-3 last:border-b-0 last:pb-0"
                          >
                            <ReadinessIcon tone={item.tone} />
                            <span className="text-sm text-slate-700">{item.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {gateResult && (
                      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                        <h3 className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Gate Check
                        </h3>
                        {gateResult.allowed && gateResult.failedGates.length === 0 && (
                          <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-3 text-sm text-green-800">
                            <CheckCircle2 className="h-4 w-4 shrink-0" />
                            All checks passed. Ready to submit.
                          </div>
                        )}
                        {gateResult.failedGates.map((failure) => (
                          <div
                            key={failure.code}
                            className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-800"
                          >
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                            <div>{failure.message}</div>
                          </div>
                        ))}
                        {gateResult.warnings.map((warning) => (
                          <div
                            key={warning.code}
                            className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800"
                          >
                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                            <div>{warning.message}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600">
                      <p>
                        Entity: <span className="font-medium text-slate-900">{detail.entity_name ?? row.entity_name}</span>
                      </p>
                      {(detail.facility_name ?? row.facility_name) && (
                        <p>
                          Facility: <span className="font-medium text-slate-900">{detail.facility_name ?? row.facility_name}</span>
                        </p>
                      )}
                      {row.assignment_id && (
                        <p>
                          Assignment: <span className="font-medium text-slate-900">#{row.assignment_id}</span>
                        </p>
                      )}
                    </div>
                  </div>
                </aside>
              </div>
            </div>

            <div className="border-t border-slate-200 bg-white px-6 py-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-wrap gap-2">
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
                  <Button variant="outline" onClick={() => onOpenChange(false)}>
                    Close
                  </Button>
                </div>

                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <Button
                    variant="outline"
                    onClick={() => void handleSaveDraft()}
                    disabled={!isEditable || isLoading || isSaving || isChecking || isSubmitting}
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
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
                        <Loader2 className="h-4 w-4 animate-spin" />
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
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Submitting...
                      </>
                    ) : (
                      "Submit"
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
