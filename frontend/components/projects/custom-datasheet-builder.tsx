"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { api, type AppApiError } from "@/lib/api";
import {
  AlertTriangle,
  Archive,
  CheckCircle2,
  ExternalLink,
  FileText,
  Eye,
  Link2,
  Loader2,
  Plus,
  Search,
} from "lucide-react";

type CustomDatasheetStatus = "draft" | "active" | "archived";
type CustomDatasheetCategory =
  | "environmental"
  | "social"
  | "governance"
  | "business_operations"
  | "other";
type CustomDatasheetCollectionScope = "project" | "entity" | "facility";
type CustomDatasheetItemSourceType = "framework" | "existing_custom" | "new_custom";

interface CustomDatasheet {
  id: number;
  reporting_project_id: number;
  name: string;
  description: string | null;
  status: CustomDatasheetStatus;
  created_at: string;
  updated_at: string;
  item_count: number;
  framework_item_count: number;
  custom_item_count: number;
}

interface CustomDatasheetItem {
  id: number;
  shared_element_id: number;
  shared_element_code: string | null;
  shared_element_name: string | null;
  shared_element_key: string | null;
  owner_layer: string | null;
  assignment_id: number | null;
  source_type: CustomDatasheetItemSourceType;
  category: CustomDatasheetCategory;
  display_group: string | null;
  label_override: string | null;
  help_text: string | null;
  collection_scope: CustomDatasheetCollectionScope;
  entity_id: number | null;
  entity_name: string | null;
  facility_id: number | null;
  facility_name: string | null;
  is_required: boolean;
  sort_order: number;
  status: string;
  created_at: string;
  updated_at: string;
}

interface CustomDatasheetDetail extends CustomDatasheet {
  items: CustomDatasheetItem[];
}

interface CustomDatasheetListResponse {
  items: CustomDatasheet[];
  total: number;
}

interface CustomDatasheetOption {
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  shared_element_key: string | null;
  owner_layer: string;
  source_type: "framework" | "existing_custom";
  concept_domain: string | null;
  default_value_type: string | null;
  default_unit_code: string | null;
  suggested_category: CustomDatasheetCategory;
  standard_id: number | null;
  standard_code: string | null;
  standard_name: string | null;
  disclosure_id: number | null;
  disclosure_code: string | null;
  disclosure_title: string | null;
  requirement_item_id: number | null;
  requirement_item_code: string | null;
  requirement_item_name: string | null;
}

interface CustomDatasheetOptionListResponse {
  items: CustomDatasheetOption[];
  total: number;
}

interface EntityRecord {
  id: number;
  name: string;
  code?: string | null;
  entity_type?: string;
  status?: string;
}

interface EntitiesResponse {
  items?: EntityRecord[];
  entities?: EntityRecord[];
}

interface CustomDatasheetCreatePayload {
  name: string;
  description?: string;
}

interface CustomDatasheetItemCreatePayload {
  shared_element_id: number;
  source_type: "framework" | "existing_custom";
  category: CustomDatasheetCategory;
  display_group?: string;
  label_override?: string;
  help_text?: string;
  collection_scope: CustomDatasheetCollectionScope;
  entity_id?: number;
  facility_id?: number;
  is_required: boolean;
  sort_order: number;
}

interface CustomDatasheetCreateCustomMetricPayload {
  code: string;
  name: string;
  description?: string;
  concept_domain?: string;
  default_value_type?: "number" | "text" | "boolean" | "date" | "enum" | "document";
  default_unit_code?: string;
  category: CustomDatasheetCategory;
  display_group?: string;
  label_override?: string;
  help_text?: string;
  collection_scope: CustomDatasheetCollectionScope;
  entity_id?: number;
  facility_id?: number;
  is_required: boolean;
  sort_order: number;
}

interface ProjectDataPoint {
  id: number;
  shared_element_id: number;
  entity_id: number | null;
  facility_id: number | null;
  status: string;
  collection_status: string | null;
  evidence_count: number;
}

interface ProjectDataPointsResponse {
  items: ProjectDataPoint[];
  total: number;
}

interface DatasheetEvidenceItem {
  id: number;
  type: "file" | "link";
  title: string;
  description?: string | null;
  file_name?: string | null;
  url?: string | null;
  upload_date?: string | null;
  binding_status?: "bound" | "unbound";
}

const CATEGORY_OPTIONS = [
  { value: "environmental", label: "Environmental" },
  { value: "social", label: "Social" },
  { value: "governance", label: "Governance" },
  { value: "business_operations", label: "Business / Operations" },
  { value: "other", label: "Other" },
];

const CATEGORY_ORDER: CustomDatasheetCategory[] = [
  "environmental",
  "social",
  "governance",
  "business_operations",
  "other",
];

const COLLECTION_SCOPE_OPTIONS = [
  { value: "project", label: "Project-wide" },
  { value: "entity", label: "Entity" },
  { value: "facility", label: "Facility" },
];

const CUSTOM_VALUE_TYPE_OPTIONS = [
  { value: "", label: "Select value type" },
  { value: "number", label: "Number" },
  { value: "text", label: "Text" },
  { value: "boolean", label: "Boolean" },
  { value: "date", label: "Date" },
  { value: "enum", label: "Enum" },
  { value: "document", label: "Document" },
];

type AddItemFormState = {
  category: CustomDatasheetCategory;
  display_group: string;
  label_override: string;
  help_text: string;
  collection_scope: CustomDatasheetCollectionScope;
  entity_id: string;
  facility_id: string;
  is_required: boolean;
  sort_order: string;
};

type CreateCustomMetricFormState = {
  code: string;
  name: string;
  description: string;
  concept_domain: string;
  default_value_type: "" | "number" | "text" | "boolean" | "date" | "enum" | "document";
  default_unit_code: string;
} & AddItemFormState;

function emptyAddItemForm(): AddItemFormState {
  return {
    category: "other",
    display_group: "",
    label_override: "",
    help_text: "",
    collection_scope: "project",
    entity_id: "",
    facility_id: "",
    is_required: true,
    sort_order: "0",
  };
}

function emptyCustomMetricForm(): CreateCustomMetricFormState {
  return {
    code: "",
    name: "",
    description: "",
    concept_domain: "",
    default_value_type: "number",
    default_unit_code: "",
    ...emptyAddItemForm(),
  };
}

function formatCategoryLabel(category: string) {
  return CATEGORY_OPTIONS.find((option) => option.value === category)?.label ?? category;
}

function formatCollectionScopeLabel(scope: string) {
  return COLLECTION_SCOPE_OPTIONS.find((option) => option.value === scope)?.label ?? scope;
}

function formatFileEvidenceCount(count: number) {
  return `${count} ${count === 1 ? "evidence item" : "evidence items"}`;
}

function formatEvidenceDate(date?: string | null) {
  if (!date) return "Unknown";
  return new Date(date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatEvidenceType(type: "file" | "link") {
  return type === "link" ? "External link" : "File";
}

function buildMetricContextKey(
  sharedElementId?: number | null,
  entityId?: number | null,
  facilityId?: number | null
) {
  return [sharedElementId ?? 0, entityId ?? 0, facilityId ?? 0].join(":");
}

async function fetchAllProjectDataPoints(projectId: number): Promise<ProjectDataPoint[]> {
  const pageSize = 100;
  const items: ProjectDataPoint[] = [];
  let page = 1;

  while (true) {
    const response = await api.get<ProjectDataPointsResponse>(
      `/projects/${projectId}/data-points?page=${page}&page_size=${pageSize}`
    );
    items.push(...response.items);
    if (response.items.length < pageSize || items.length >= response.total) {
      break;
    }
    page += 1;
  }

  return items;
}

function formatSourceLabel(sourceType: CustomDatasheetItemSourceType | "framework" | "existing_custom") {
  if (sourceType === "framework") return "Framework metric";
  return "Custom metric";
}

function formatStatusVariant(status: CustomDatasheetStatus) {
  switch (status) {
    case "active":
      return "success" as const;
    case "archived":
      return "secondary" as const;
    default:
      return "warning" as const;
  }
}

function normalizeEntities(data: EntitiesResponse | undefined): EntityRecord[] {
  if (!data) return [];
  return data.entities ?? data.items ?? [];
}

function trimOptional(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function toOptionalNumber(value: string) {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function buildOptionMeta(option: CustomDatasheetOption) {
  const standard = option.standard_code
    ? `${option.standard_code}${option.standard_name && option.standard_name !== option.standard_code ? ` - ${option.standard_name}` : ""}`
    : null;
  const disclosure = option.disclosure_code
    ? `${option.disclosure_code}${option.disclosure_title ? ` - ${option.disclosure_title}` : ""}`
    : null;
  const requirement = option.requirement_item_code
    ? `${option.requirement_item_code}${option.requirement_item_name ? ` - ${option.requirement_item_name}` : ""}`
    : null;
  return [standard, disclosure, requirement].filter(Boolean);
}

function buildItemContextLabel(item: CustomDatasheetItem) {
  if (item.facility_name) {
    return [item.entity_name, item.facility_name].filter(Boolean).join(" / ");
  }
  if (item.entity_name) return item.entity_name;
  return "Project-wide";
}

type GroupedItemBlock = {
  category: CustomDatasheetCategory;
  categoryLabel: string;
  groups: Array<{
    key: string;
    label: string | null;
    items: CustomDatasheetItem[];
  }>;
};

function groupItems(items: CustomDatasheetItem[]): GroupedItemBlock[] {
  const blocks: GroupedItemBlock[] = [];
  for (const category of CATEGORY_ORDER) {
    const categoryItems = items
      .filter((item) => item.status === "active" && item.category === category)
      .sort((left, right) => {
        if (left.sort_order !== right.sort_order) return left.sort_order - right.sort_order;
        return (left.label_override || left.shared_element_name || left.shared_element_code || "").localeCompare(
          right.label_override || right.shared_element_name || right.shared_element_code || ""
        );
      });

    if (categoryItems.length === 0) continue;

    const groups = new Map<string, CustomDatasheetItem[]>();
    for (const item of categoryItems) {
      const key = item.display_group?.trim() || "__ungrouped__";
      const group = groups.get(key) ?? [];
      group.push(item);
      groups.set(key, group);
    }

    blocks.push({
      category,
      categoryLabel: formatCategoryLabel(category),
      groups: Array.from(groups.entries()).map(([key, groupedItems]) => ({
        key,
        label: key === "__ungrouped__" ? null : key,
        items: groupedItems,
      })),
    });
  }

  return blocks;
}

export function CustomDatasheetBuilder({ projectId }: { projectId: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [selectedDatasheetId, setSelectedDatasheetId] = useState<number | null>(null);
  const [pendingDatasheetId, setPendingDatasheetId] = useState<number | null>(null);
  const selectedDatasheetIdRef = useRef<number | null>(null);
  const setActiveDatasheetId = (id: number | null) => {
    selectedDatasheetIdRef.current = id;
    setSelectedDatasheetId(id);
  };
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [addItemDialogOpen, setAddItemDialogOpen] = useState(false);
  const [addItemSource, setAddItemSource] = useState<"framework" | "existing_custom" | "new_custom">("framework");
  const [optionSearch, setOptionSearch] = useState("");
  const [selectedOptionId, setSelectedOptionId] = useState<number | null>(null);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [addItemForm, setAddItemForm] = useState<AddItemFormState>(emptyAddItemForm);
  const [customMetricForm, setCustomMetricForm] = useState<CreateCustomMetricFormState>(emptyCustomMetricForm);
  const [localError, setLocalError] = useState<string | null>(null);
  const [archivingItemId, setArchivingItemId] = useState<number | null>(null);
  const [evidenceItemTarget, setEvidenceItemTarget] = useState<CustomDatasheetItem | null>(null);

  const {
    data: datasheetsData,
    isLoading: datasheetsLoading,
    error: datasheetsError,
  } = useApiQuery<CustomDatasheetListResponse>(
    ["project-custom-datasheets", projectId],
    `/projects/${projectId}/custom-datasheets`
  );

  const datasheets = useMemo(() => datasheetsData?.items ?? [], [datasheetsData]);
  const preferredDatasheetId = useMemo(() => {
    const raw = searchParams.get("datasheetId");
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [searchParams]);

  useEffect(() => {
    selectedDatasheetIdRef.current = selectedDatasheetId;
  }, [selectedDatasheetId]);

  useEffect(() => {
    if (datasheets.length === 0) {
      setActiveDatasheetId(null);
      setPendingDatasheetId(null);
      return;
    }
    if (pendingDatasheetId) {
      if (selectedDatasheetId !== pendingDatasheetId) {
        setActiveDatasheetId(pendingDatasheetId);
      }
      if (datasheets.some((item) => item.id === pendingDatasheetId)) {
        setPendingDatasheetId(null);
      }
      return;
    }
    if (
      preferredDatasheetId &&
      datasheets.some((item) => item.id === preferredDatasheetId) &&
      selectedDatasheetId !== preferredDatasheetId
    ) {
      setActiveDatasheetId(preferredDatasheetId);
      return;
    }
    if (!selectedDatasheetId || !datasheets.some((item) => item.id === selectedDatasheetId)) {
      setActiveDatasheetId(datasheets[0].id);
    }
  }, [datasheets, pendingDatasheetId, preferredDatasheetId, selectedDatasheetId]);

  useEffect(() => {
    if (!pathname) return;
    const hasPreferredDatasheet =
      preferredDatasheetId != null &&
      datasheets.some((item) => item.id === preferredDatasheetId);
    if (pendingDatasheetId && selectedDatasheetId !== pendingDatasheetId) {
      return;
    }
    if (hasPreferredDatasheet && selectedDatasheetId !== preferredDatasheetId) {
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    const current = params.get("datasheetId");
    if (selectedDatasheetId == null) {
      if (!current) return;
      params.delete("datasheetId");
    } else if (current !== String(selectedDatasheetId)) {
      params.set("datasheetId", String(selectedDatasheetId));
    } else {
      return;
    }
    const next = params.toString();
    router.replace(`${pathname}${next ? `?${next}` : ""}`);
  }, [
    datasheets,
    pathname,
    pendingDatasheetId,
    preferredDatasheetId,
    router,
    searchParams,
    selectedDatasheetId,
  ]);

  const {
    data: selectedDatasheet,
    isLoading: selectedDatasheetLoading,
  } = useApiQuery<CustomDatasheetDetail>(
    ["project-custom-datasheet", projectId, selectedDatasheetId],
    selectedDatasheetId
      ? `/projects/${projectId}/custom-datasheets/${selectedDatasheetId}`
      : `/projects/${projectId}/custom-datasheets/0`,
    {
      enabled: Boolean(selectedDatasheetId),
    }
  );

  const { data: entitiesData } = useApiQuery<EntitiesResponse>(["entities"], "/entities");
  const { data: projectDataPoints = [] } = useQuery<ProjectDataPoint[], Error>({
    queryKey: ["project-custom-datasheet-data-points", projectId],
    queryFn: () => fetchAllProjectDataPoints(Number(projectId)),
    enabled: Boolean(selectedDatasheetId),
  });

  const optionQueryPath =
    selectedDatasheetId && addItemSource !== "new_custom"
      ? `/projects/${projectId}/custom-datasheets/${selectedDatasheetId}/item-options?source=${addItemSource}${optionSearch.trim() ? `&q=${encodeURIComponent(optionSearch.trim())}` : ""}`
      : `/projects/${projectId}/custom-datasheets/0/item-options?source=framework`;

  const { data: optionResults, isLoading: optionResultsLoading } =
    useApiQuery<CustomDatasheetOptionListResponse>(
      ["project-custom-datasheet-options", projectId, selectedDatasheetId, addItemSource, optionSearch],
      optionQueryPath,
      {
        enabled: addItemDialogOpen && Boolean(selectedDatasheetId) && addItemSource !== "new_custom",
      }
    );

  const allEntities = useMemo(() => normalizeEntities(entitiesData), [entitiesData]);
  const entityOptions = useMemo(
    () =>
      allEntities
        .filter((entity) => entity.entity_type !== "facility")
        .map((entity) => ({
          value: String(entity.id),
          label: entity.code ? `${entity.name} (${entity.code})` : entity.name,
        })),
    [allEntities]
  );
  const facilityOptions = useMemo(
    () =>
      allEntities
        .filter((entity) => entity.entity_type === "facility")
        .map((entity) => ({
          value: String(entity.id),
          label: entity.code ? `${entity.name} (${entity.code})` : entity.name,
        })),
    [allEntities]
  );

  const selectedOption = useMemo(
    () => optionResults?.items.find((option) => option.shared_element_id === selectedOptionId) ?? null,
    [optionResults?.items, selectedOptionId]
  );

  const groupedItems = useMemo(
    () => groupItems(selectedDatasheet?.items ?? []),
    [selectedDatasheet?.items]
  );
  const dataPointsByContext = useMemo(() => {
    const mapping = new Map<string, ProjectDataPoint>();
    for (const dataPoint of projectDataPoints) {
      mapping.set(
        buildMetricContextKey(dataPoint.shared_element_id, dataPoint.entity_id, dataPoint.facility_id),
        dataPoint
      );
    }
    return mapping;
  }, [projectDataPoints]);
  const evidenceTargetDataPoint = useMemo(() => {
    if (!evidenceItemTarget) return null;
    return (
      dataPointsByContext.get(
        buildMetricContextKey(
          evidenceItemTarget.shared_element_id,
          evidenceItemTarget.entity_id,
          evidenceItemTarget.facility_id
        )
      ) ?? null
    );
  }, [dataPointsByContext, evidenceItemTarget]);
  const {
    data: evidenceItems = [],
    isLoading: evidenceItemsLoading,
  } = useApiQuery<DatasheetEvidenceItem[]>(
    ["project-custom-datasheet-item-evidence", evidenceTargetDataPoint?.id],
    `/data-points/${evidenceTargetDataPoint?.id ?? 0}/evidences`,
    {
      enabled: Boolean(evidenceItemTarget && evidenceTargetDataPoint?.id),
    }
  );

  const totalItemsAcrossDatasheets = useMemo(
    () => datasheets.reduce((sum, datasheet) => sum + datasheet.item_count, 0),
    [datasheets]
  );

  const totalCustomItemsAcrossDatasheets = useMemo(
    () => datasheets.reduce((sum, datasheet) => sum + datasheet.custom_item_count, 0),
    [datasheets]
  );

  const refreshDatasheetQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["project-custom-datasheets", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["project-custom-datasheet", projectId] }),
      queryClient.invalidateQueries({ queryKey: ["project-custom-datasheet-options", projectId] }),
    ]);
  };

  const closeCreateDialog = () => {
    setLocalError(null);
    setCreateDialogOpen(false);
    setCreateName("");
    setCreateDescription("");
  };

  const closeAddItemDialog = () => {
    setLocalError(null);
    setAddItemDialogOpen(false);
    setAddItemSource("framework");
    setOptionSearch("");
    setSelectedOptionId(null);
    setAddItemForm(emptyAddItemForm());
    setCustomMetricForm(emptyCustomMetricForm());
  };

  useEffect(() => {
    setSelectedOptionId(null);
    setOptionSearch("");
    setAddItemForm(emptyAddItemForm());
    setCustomMetricForm(emptyCustomMetricForm());
  }, [addItemSource]);

  const createDatasheetMutation = useApiMutation<CustomDatasheet, CustomDatasheetCreatePayload>(
    `/projects/${projectId}/custom-datasheets`,
    "POST",
    {
      onMutate: () => {
        setLocalError(null);
      },
      onSuccess: async (result) => {
        queryClient.setQueryData<CustomDatasheetListResponse | undefined>(
          ["project-custom-datasheets", projectId],
          (current) => {
            const existingItems = current?.items ?? [];
            const withoutDuplicate = existingItems.filter((item) => item.id !== result.id);
            return {
              items: [result, ...withoutDuplicate],
              total: (current?.total ?? withoutDuplicate.length) + Number(!existingItems.some((item) => item.id === result.id)),
            };
          }
        );
        queryClient.setQueryData<CustomDatasheetDetail>(
          ["project-custom-datasheet", projectId, result.id],
          {
            ...result,
            items: [],
          }
        );
        setPendingDatasheetId(result.id);
        setActiveDatasheetId(result.id);
        closeCreateDialog();
        await refreshDatasheetQueries();
      },
      onError: (error) => {
        setLocalError(error.message || "Unable to create custom datasheet.");
      },
    }
  );

  const addItemMutation = useMutation<
    CustomDatasheetItem,
    AppApiError | Error,
    CustomDatasheetItemCreatePayload
  >({
    mutationFn: async (payload) => {
      const currentDatasheetId = selectedDatasheetIdRef.current;
      if (!currentDatasheetId) {
        throw new Error("Select a custom datasheet before adding an item.");
      }
      return api.post<CustomDatasheetItem>(
        `/projects/${projectId}/custom-datasheets/${currentDatasheetId}/items`,
        payload
      );
    },
    onMutate: () => {
      setLocalError(null);
    },
    onSuccess: async () => {
      closeAddItemDialog();
      await refreshDatasheetQueries();
    },
    onError: (error) => {
      setLocalError(error.message || "Unable to add datasheet item.");
    },
  });

  const createCustomMetricMutation = useMutation<
    CustomDatasheetItem,
    AppApiError | Error,
    CustomDatasheetCreateCustomMetricPayload
  >({
    mutationFn: async (payload) => {
      const currentDatasheetId = selectedDatasheetIdRef.current;
      if (!currentDatasheetId) {
        throw new Error("Select a custom datasheet before creating a metric.");
      }
      return api.post<CustomDatasheetItem>(
        `/projects/${projectId}/custom-datasheets/${currentDatasheetId}/items/create-custom`,
        payload
      );
    },
    onMutate: () => {
      setLocalError(null);
    },
    onSuccess: async () => {
      closeAddItemDialog();
      await refreshDatasheetQueries();
    },
    onError: (error) => {
      setLocalError(error.message || "Unable to create custom metric.");
    },
  });

  const archiveDatasheetMutation = useMutation<CustomDatasheet, AppApiError | Error, void>({
    mutationFn: async () => {
      const currentDatasheetId = selectedDatasheetIdRef.current;
      if (!currentDatasheetId) {
        throw new Error("Select a custom datasheet before archiving it.");
      }
      return api.post<CustomDatasheet>(
        `/projects/${projectId}/custom-datasheets/${currentDatasheetId}/archive`,
        {}
      );
    },
    onMutate: () => {
      setLocalError(null);
    },
    onSuccess: async () => {
      await refreshDatasheetQueries();
    },
    onError: (error) => {
      setLocalError(error.message || "Unable to archive datasheet.");
    },
  });

  const handleCreateDatasheet = () => {
    if (!createName.trim()) {
      setLocalError("Datasheet name is required.");
      return;
    }
    createDatasheetMutation.mutate({
      name: createName.trim(),
      description: trimOptional(createDescription),
    });
  };

  const handleSelectOption = (option: CustomDatasheetOption) => {
    setSelectedOptionId(option.shared_element_id);
    setAddItemForm((current) => ({
      ...current,
      category: option.suggested_category,
    }));
  };

  const handleAddExistingItem = () => {
    if (!selectedOption) {
      setLocalError("Select a metric to add.");
      return;
    }

    addItemMutation.mutate({
      shared_element_id: selectedOption.shared_element_id,
      source_type: addItemSource === "existing_custom" ? "existing_custom" : "framework",
      category: addItemForm.category,
      display_group: trimOptional(addItemForm.display_group),
      label_override: trimOptional(addItemForm.label_override),
      help_text: trimOptional(addItemForm.help_text),
      collection_scope: addItemForm.collection_scope,
      entity_id: toOptionalNumber(addItemForm.entity_id),
      facility_id: toOptionalNumber(addItemForm.facility_id),
      is_required: addItemForm.is_required,
      sort_order: Number(addItemForm.sort_order || 0),
    });
  };

  const handleCreateCustomMetric = () => {
    if (!customMetricForm.code.trim() || !customMetricForm.name.trim()) {
      setLocalError("Custom metric code and name are required.");
      return;
    }

    createCustomMetricMutation.mutate({
      code: customMetricForm.code.trim(),
      name: customMetricForm.name.trim(),
      description: trimOptional(customMetricForm.description),
      concept_domain: trimOptional(customMetricForm.concept_domain),
      default_value_type: customMetricForm.default_value_type || undefined,
      default_unit_code: trimOptional(customMetricForm.default_unit_code),
      category: customMetricForm.category,
      display_group: trimOptional(customMetricForm.display_group),
      label_override: trimOptional(customMetricForm.label_override),
      help_text: trimOptional(customMetricForm.help_text),
      collection_scope: customMetricForm.collection_scope,
      entity_id: toOptionalNumber(customMetricForm.entity_id),
      facility_id: toOptionalNumber(customMetricForm.facility_id),
      is_required: customMetricForm.is_required,
      sort_order: Number(customMetricForm.sort_order || 0),
    });
  };

  const handleArchiveItem = async (itemId: number) => {
    if (!selectedDatasheetId) return;
    if (!window.confirm("Archive this datasheet item? It will be hidden from the builder, but the metric will stay in the project.")) {
      return;
    }
    setLocalError(null);
    setArchivingItemId(itemId);
    try {
      await api.post(
        `/projects/${projectId}/custom-datasheets/${selectedDatasheetId}/items/${itemId}/archive`,
        {}
      );
      await refreshDatasheetQueries();
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Unable to archive datasheet item.");
    } finally {
      setArchivingItemId(null);
    }
  };

  const canArchiveSelectedDatasheet =
    selectedDatasheet && selectedDatasheet.status !== "archived" && !archiveDatasheetMutation.isPending;

  const buildCollectionContextUrl = (item: CustomDatasheetItem) => {
    const params = new URLSearchParams();
    params.set("projectId", projectId);
    params.set("sharedElementId", String(item.shared_element_id));
    params.set("openContext", "1");
    if (item.entity_id != null) {
      params.set("entityId", String(item.entity_id));
    }
    if (item.facility_id != null) {
      params.set("facilityId", String(item.facility_id));
    }

    const returnParams = new URLSearchParams(searchParams.toString());
    returnParams.set("tab", "custom-datasheet");
    if (selectedDatasheetId != null) {
      returnParams.set("datasheetId", String(selectedDatasheetId));
    }
    const returnTo = `${pathname}${returnParams.toString() ? `?${returnParams.toString()}` : ""}`;
    params.set("returnTo", returnTo);
    params.set("returnLabel", "Back to Custom Datasheet");

    return `/collection?${params.toString()}`;
  };

  const buildEvidenceRepositoryUrl = (evidenceId: number) => {
    const params = new URLSearchParams();
    params.set("projectId", projectId);
    params.set("evidenceId", String(evidenceId));
    return `/evidence?${params.toString()}`;
  };

  return (
    <div className="space-y-6">
      {localError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {localError}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>Custom Datasheets</CardTitle>
                <CardDescription>
                  Curate a project-specific view of framework and custom metrics.
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setCreateDialogOpen(true)}>
                <Plus className="h-4 w-4" />
                Create
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                    Datasheets
                  </p>
                  <p className="mt-1 text-2xl font-bold text-slate-900">{datasheets.length}</p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                    Items
                  </p>
                  <p className="mt-1 text-2xl font-bold text-slate-900">{totalItemsAcrossDatasheets}</p>
                </div>
              </div>
              <div className="rounded-xl border border-cyan-100 bg-cyan-50 px-4 py-3 text-sm text-cyan-950">
                <p className="font-medium">Framework + custom in one builder</p>
                <p className="mt-1 text-cyan-900">
                  Reuse project standards where they exist, then fill the gaps with client-specific metrics.
                </p>
                <p className="mt-2 text-xs text-cyan-800">
                  {totalCustomItemsAcrossDatasheets} custom metric items currently included across this project.
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Available Datasheets</CardTitle>
              <CardDescription>Select one to open its builder.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {datasheetsLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : datasheetsError ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Unable to load custom datasheets.
                </div>
              ) : datasheets.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center">
                  <FileText className="mx-auto h-8 w-8 text-slate-300" />
                  <p className="mt-3 text-sm font-medium text-slate-900">No datasheets yet</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Create a datasheet to organize standards-based and custom metrics for this project.
                  </p>
                  <Button className="mt-4" size="sm" onClick={() => setCreateDialogOpen(true)}>
                    <Plus className="h-4 w-4" />
                    Create first datasheet
                  </Button>
                </div>
              ) : (
                datasheets.map((datasheet) => {
                  const isSelected = datasheet.id === selectedDatasheetId;
                  return (
                    <button
                      key={datasheet.id}
                      type="button"
                      onClick={() => setActiveDatasheetId(datasheet.id)}
                      className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                        isSelected
                          ? "border-cyan-300 bg-cyan-50 shadow-sm"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900">{datasheet.name}</p>
                          {datasheet.description && (
                            <p className="mt-1 line-clamp-2 text-sm text-slate-500">{datasheet.description}</p>
                          )}
                        </div>
                        <Badge variant={formatStatusVariant(datasheet.status)}>{datasheet.status}</Badge>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                        <span>{datasheet.item_count} items</span>
                        <span>•</span>
                        <span>{datasheet.framework_item_count} framework</span>
                        <span>•</span>
                        <span>{datasheet.custom_item_count} custom</span>
                      </div>
                    </button>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          {!selectedDatasheetId ? (
            <Card>
              <CardContent className="flex min-h-[420px] flex-col items-center justify-center py-12 text-center">
                <FileText className="h-10 w-10 text-slate-300" />
                <p className="mt-4 text-base font-medium text-slate-900">Choose a custom datasheet</p>
                <p className="mt-2 max-w-lg text-sm text-slate-500">
                  The builder lets you mix framework metrics from attached standards with tenant custom metrics in one project-specific container.
                </p>
              </CardContent>
            </Card>
          ) : selectedDatasheetLoading || !selectedDatasheet ? (
            <Card>
              <CardContent className="flex min-h-[420px] items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
              </CardContent>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader className="flex flex-row items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <CardTitle>{selectedDatasheet.name}</CardTitle>
                      <Badge variant={formatStatusVariant(selectedDatasheet.status)}>
                        {selectedDatasheet.status}
                      </Badge>
                    </div>
                    <CardDescription className="mt-1">
                      {selectedDatasheet.description || "Project-specific curated metric view."}
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" onClick={() => setAddItemDialogOpen(true)}>
                      <Plus className="h-4 w-4" />
                      Add item
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!canArchiveSelectedDatasheet}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Archive this datasheet? The builder will stay in history, but it will no longer be active."
                          )
                        ) {
                          archiveDatasheetMutation.mutate(undefined);
                        }
                      }}
                    >
                      {archiveDatasheetMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Archive className="h-4 w-4" />
                      )}
                      Archive
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Total items</p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">{selectedDatasheet.item_count}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Framework</p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">
                        {selectedDatasheet.framework_item_count}
                      </p>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Custom</p>
                      <p className="mt-1 text-2xl font-bold text-slate-900">{selectedDatasheet.custom_item_count}</p>
                    </div>
                  </div>

                  {groupedItems.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-6 py-10 text-center">
                      <CheckCircle2 className="mx-auto h-8 w-8 text-slate-300" />
                      <p className="mt-3 text-base font-medium text-slate-900">Datasheet is empty</p>
                      <p className="mt-2 text-sm text-slate-500">
                        Start by pulling in metrics from attached standards or create a new custom metric on the spot.
                      </p>
                      <Button className="mt-4" onClick={() => setAddItemDialogOpen(true)}>
                        <Plus className="h-4 w-4" />
                        Add first item
                      </Button>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {groupedItems.map((block) => (
                        <div key={block.category} className="space-y-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <h3 className="text-base font-semibold text-slate-900">{block.categoryLabel}</h3>
                              <p className="text-sm text-slate-500">
                                {block.groups.reduce((sum, group) => sum + group.items.length, 0)} items
                              </p>
                            </div>
                            <Badge variant="outline" className="border-slate-300 text-slate-600">
                              {block.category}
                            </Badge>
                          </div>

                          {block.groups.map((group) => (
                            <div key={`${block.category}:${group.key}`} className="space-y-3">
                              {group.label && (
                                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5">
                                  <p className="text-sm font-medium text-slate-900">{group.label}</p>
                                </div>
                              )}
                              <div className="grid gap-3">
                                {group.items.map((item) => (
                                  (() => {
                                    const itemDataPoint =
                                      dataPointsByContext.get(
                                        buildMetricContextKey(
                                          item.shared_element_id,
                                          item.entity_id,
                                          item.facility_id
                                        )
                                      ) ?? null;
                                    const evidenceCount = itemDataPoint?.evidence_count ?? 0;
                                    const hasEvidence = evidenceCount > 0;

                                    return (
                                      <div
                                        key={item.id}
                                        className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
                                      >
                                        <div className="flex items-start justify-between gap-4">
                                      <div className="min-w-0 space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                          <p className="text-sm font-semibold text-slate-900">
                                            {item.label_override ||
                                              item.shared_element_name ||
                                              item.shared_element_code ||
                                              "Untitled metric"}
                                          </p>
                                          <Badge
                                            variant={item.owner_layer === "tenant_catalog" ? "warning" : "secondary"}
                                          >
                                            {formatSourceLabel(item.source_type)}
                                          </Badge>
                                          {item.is_required && <Badge variant="outline">Required</Badge>}
                                        </div>
                                        <div className="flex flex-wrap gap-2 text-xs text-slate-500">
                                          {item.shared_element_code && (
                                            <span className="rounded-full border border-slate-200 px-2 py-1">
                                              {item.shared_element_code}
                                            </span>
                                          )}
                                          <span className="rounded-full border border-slate-200 px-2 py-1">
                                            {formatCollectionScopeLabel(item.collection_scope)}
                                          </span>
                                          <span className="rounded-full border border-slate-200 px-2 py-1">
                                            {buildItemContextLabel(item)}
                                          </span>
                                          <span
                                            className={`rounded-full border px-2 py-1 ${
                                              hasEvidence
                                                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                                : "border-slate-200 text-slate-500"
                                            }`}
                                          >
                                            {hasEvidence ? formatFileEvidenceCount(evidenceCount) : "No evidence yet"}
                                          </span>
                                          {itemDataPoint?.status && (
                                            <span className="rounded-full border border-slate-200 px-2 py-1">
                                              {itemDataPoint.status}
                                            </span>
                                          )}
                                        </div>
                                        {item.help_text && (
                                          <p className="text-sm text-slate-600">{item.help_text}</p>
                                        )}
                                        <p className="text-xs text-slate-500">
                                          {itemDataPoint
                                            ? hasEvidence
                                              ? "This datasheet context already has linked evidence."
                                              : "A draft data point exists, but evidence has not been linked yet."
                                            : "No draft data point exists yet for this datasheet context."}
                                        </p>
                                      </div>
                                        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={!itemDataPoint}
                                            onClick={() => setEvidenceItemTarget(item)}
                                          >
                                            <Eye className="h-4 w-4" />
                                            {hasEvidence ? "View evidence" : "Evidence"}
                                          </Button>
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={archivingItemId === item.id}
                                            onClick={() => router.push(buildCollectionContextUrl(item))}
                                          >
                                            <Link2 className="h-4 w-4" />
                                            {itemDataPoint ? "Open in Collection" : "Create in Collection"}
                                          </Button>
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            disabled={archivingItemId === item.id}
                                            onClick={() => handleArchiveItem(item.id)}
                                          >
                                            {archivingItemId === item.id ? (
                                              <Loader2 className="h-4 w-4 animate-spin" />
                                            ) : (
                                              <Archive className="h-4 w-4" />
                                            )}
                                            Archive
                                          </Button>
                                        </div>
                                      </div>
                                    </div>
                                    );
                                  })()
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>

      <Dialog
        open={createDialogOpen}
        onOpenChange={(open) => {
          if (open) {
            setCreateDialogOpen(true);
            return;
          }
          closeCreateDialog();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Custom Datasheet</DialogTitle>
            <DialogDescription>
              Create a project-scoped container that can mix framework metrics with custom client metrics.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            {localError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                {localError}
              </div>
            )}
            <Input
              label="Name"
              placeholder="BP ESG Datasheet"
              value={createName}
              onChange={(event) => setCreateName(event.target.value)}
            />
            <Textarea
              label="Description"
              placeholder="Optional notes about what this datasheet is for."
              value={createDescription}
              onChange={(event) => setCreateDescription(event.target.value)}
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeCreateDialog}>
              Cancel
            </Button>
            <Button onClick={handleCreateDatasheet} disabled={createDatasheetMutation.isPending}>
              {createDatasheetMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Create datasheet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={addItemDialogOpen}
        onOpenChange={(open) => {
          if (open) {
            setAddItemDialogOpen(true);
            return;
          }
          closeAddItemDialog();
        }}
      >
        <DialogContent className="max-w-4xl" contentClassName="max-h-[85vh] overflow-y-auto p-6">
          <DialogHeader>
            <DialogTitle>Add Datasheet Item</DialogTitle>
            <DialogDescription>
              Pull from project-attached standards, reuse an existing custom metric, or create a new one in-place.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 space-y-5">
            {localError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                {localError}
              </div>
            )}
            <div className="grid gap-2 md:grid-cols-3">
              {[
                { value: "framework", label: "From standards" },
                { value: "existing_custom", label: "Existing custom" },
                { value: "new_custom", label: "Create new custom" },
              ].map((option) => {
                const isActive = addItemSource === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() =>
                      setAddItemSource(option.value as "framework" | "existing_custom" | "new_custom")
                    }
                    className={`rounded-xl border px-4 py-3 text-left transition ${
                      isActive
                        ? "border-cyan-300 bg-cyan-50 text-cyan-950"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    <p className="text-sm font-semibold">{option.label}</p>
                  </button>
                );
              })}
            </div>

            {addItemSource === "new_custom" ? (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Metric code"
                    placeholder="CUST-BP-BOARD-DIVERSITY"
                    value={customMetricForm.code}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({ ...current, code: event.target.value }))
                    }
                  />
                  <Input
                    label="Metric name"
                    placeholder="Female representation on board"
                    value={customMetricForm.name}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({ ...current, name: event.target.value }))
                    }
                  />
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <Input
                    label="Concept domain"
                    placeholder="governance"
                    value={customMetricForm.concept_domain}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        concept_domain: event.target.value,
                      }))
                    }
                  />
                  <Select
                    label="Value type"
                    options={CUSTOM_VALUE_TYPE_OPTIONS}
                    value={customMetricForm.default_value_type}
                    onChange={(value) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        default_value_type: value as CreateCustomMetricFormState["default_value_type"],
                      }))
                    }
                  />
                  <Input
                    label="Default unit"
                    placeholder="%"
                    value={customMetricForm.default_unit_code}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        default_unit_code: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <Select
                    label="Category"
                    options={CATEGORY_OPTIONS}
                    value={customMetricForm.category}
                    onChange={(value) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        category: value as CustomDatasheetCategory,
                      }))
                    }
                  />
                  <Select
                    label="Collection scope"
                    options={COLLECTION_SCOPE_OPTIONS}
                    value={customMetricForm.collection_scope}
                    onChange={(value) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        collection_scope: value as CustomDatasheetCollectionScope,
                        entity_id: value === "entity" ? current.entity_id : "",
                        facility_id: value === "facility" ? current.facility_id : "",
                      }))
                    }
                  />
                </div>
                {customMetricForm.collection_scope === "entity" && (
                  <Select
                    label="Entity"
                    options={entityOptions}
                    placeholder="Select entity"
                    value={customMetricForm.entity_id}
                    onChange={(value) =>
                      setCustomMetricForm((current) => ({ ...current, entity_id: value }))
                    }
                  />
                )}
                {customMetricForm.collection_scope === "facility" && (
                  <Select
                    label="Facility"
                    options={facilityOptions}
                    placeholder="Select facility"
                    value={customMetricForm.facility_id}
                    onChange={(value) =>
                      setCustomMetricForm((current) => ({ ...current, facility_id: value }))
                    }
                  />
                )}
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Display group"
                    placeholder="Board composition"
                    value={customMetricForm.display_group}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        display_group: event.target.value,
                      }))
                    }
                  />
                  <Input
                    label="Label override"
                    placeholder="Optional datasheet label"
                    value={customMetricForm.label_override}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        label_override: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Sort order"
                    type="number"
                    value={customMetricForm.sort_order}
                    onChange={(event) =>
                      setCustomMetricForm((current) => ({
                        ...current,
                        sort_order: event.target.value,
                      }))
                    }
                  />
                  <div className="flex items-end rounded-xl border border-slate-200 px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Checkbox
                        checked={customMetricForm.is_required}
                        onCheckedChange={(checked) =>
                          setCustomMetricForm((current) => ({
                            ...current,
                            is_required: checked,
                          }))
                        }
                      />
                      <div>
                        <p className="text-sm font-medium text-slate-900">Required in datasheet</p>
                        <p className="text-xs text-slate-500">
                          Use this when the item should always appear in the curated view.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
                <Textarea
                  label="Metric description"
                  placeholder="Explain what this custom metric captures."
                  value={customMetricForm.description}
                  onChange={(event) =>
                    setCustomMetricForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  rows={4}
                />
                <Textarea
                  label="Collector help text"
                  placeholder="Optional instructions that will appear in the datasheet context."
                  value={customMetricForm.help_text}
                  onChange={(event) =>
                    setCustomMetricForm((current) => ({
                      ...current,
                      help_text: event.target.value,
                    }))
                  }
                  rows={3}
                />
              </div>
            ) : (
              <div className="grid gap-5 xl:grid-cols-[1.15fr_minmax(0,0.85fr)]">
                <div className="space-y-4">
                  <Input
                    label="Search metrics"
                    placeholder={
                      addItemSource === "framework"
                        ? "Search attached standards by code or metric name"
                        : "Search existing custom metrics"
                    }
                    value={optionSearch}
                    onChange={(event) => setOptionSearch(event.target.value)}
                  />
                  <div className="rounded-2xl border border-slate-200">
                    <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Available metrics</p>
                        <p className="text-xs text-slate-500">
                          {addItemSource === "framework"
                            ? "Only metrics from standards already attached to this project are shown."
                            : "Tenant custom metrics already available to this organization."}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-slate-500">
                        <Search className="h-3.5 w-3.5" />
                        {optionResults?.total ?? 0}
                      </div>
                    </div>
                    <div className="max-h-[420px] space-y-3 overflow-y-auto p-4">
                      {optionResultsLoading ? (
                        <div className="flex justify-center py-10">
                          <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                        </div>
                      ) : (optionResults?.items ?? []).length === 0 ? (
                        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center">
                          <p className="text-sm font-medium text-slate-900">No matching metrics</p>
                          <p className="mt-1 text-sm text-slate-500">
                            Try a broader search or switch source type.
                          </p>
                        </div>
                      ) : (
                        optionResults?.items.map((option) => {
                          const isSelected = selectedOptionId === option.shared_element_id;
                          const optionMeta = buildOptionMeta(option);
                          return (
                            <button
                              key={`${option.source_type}:${option.shared_element_id}`}
                              type="button"
                              onClick={() => handleSelectOption(option)}
                              className={`w-full rounded-2xl border px-4 py-4 text-left transition ${
                                isSelected
                                  ? "border-cyan-300 bg-cyan-50 shadow-sm"
                                  : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <p className="truncate text-sm font-semibold text-slate-900">
                                      {option.shared_element_name}
                                    </p>
                                    <Badge
                                      variant={option.owner_layer === "tenant_catalog" ? "warning" : "secondary"}
                                    >
                                      {formatSourceLabel(option.source_type)}
                                    </Badge>
                                  </div>
                                  <p className="mt-1 text-xs text-slate-500">{option.shared_element_code}</p>
                                  {optionMeta.length > 0 && (
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {optionMeta.map((meta) => (
                                        <span
                                          key={meta}
                                          className="rounded-full border border-slate-200 px-2 py-1 text-[11px] text-slate-600"
                                        >
                                          {meta}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                                {isSelected && <CheckCircle2 className="h-4 w-4 shrink-0 text-cyan-700" />}
                              </div>
                            </button>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Datasheet item settings</CardTitle>
                      <CardDescription>
                        Choose how this metric should appear inside the custom datasheet.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {selectedOption ? (
                        <div className="rounded-xl border border-cyan-100 bg-cyan-50 px-4 py-3 text-sm text-cyan-950">
                          <div className="flex items-center gap-2 font-medium">
                            <Link2 className="h-4 w-4" />
                            {selectedOption.shared_element_name}
                          </div>
                          <p className="mt-1 text-cyan-900">{selectedOption.shared_element_code}</p>
                        </div>
                      ) : (
                        <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500">
                          Select a metric from the left before adding it.
                        </div>
                      )}

                      <Select
                        label="Category"
                        options={CATEGORY_OPTIONS}
                        value={addItemForm.category}
                        onChange={(value) =>
                          setAddItemForm((current) => ({
                            ...current,
                            category: value as CustomDatasheetCategory,
                          }))
                        }
                      />
                      <Input
                        label="Display group"
                        placeholder="Optional grouping label"
                        value={addItemForm.display_group}
                        onChange={(event) =>
                          setAddItemForm((current) => ({
                            ...current,
                            display_group: event.target.value,
                          }))
                        }
                      />
                      <Input
                        label="Label override"
                        placeholder="Optional datasheet label"
                        value={addItemForm.label_override}
                        onChange={(event) =>
                          setAddItemForm((current) => ({
                            ...current,
                            label_override: event.target.value,
                          }))
                        }
                      />
                      <Select
                        label="Collection scope"
                        options={COLLECTION_SCOPE_OPTIONS}
                        value={addItemForm.collection_scope}
                        onChange={(value) =>
                          setAddItemForm((current) => ({
                            ...current,
                            collection_scope: value as CustomDatasheetCollectionScope,
                            entity_id: value === "entity" ? current.entity_id : "",
                            facility_id: value === "facility" ? current.facility_id : "",
                          }))
                        }
                      />
                      {addItemForm.collection_scope === "entity" && (
                        <Select
                          label="Entity"
                          options={entityOptions}
                          placeholder="Select entity"
                          value={addItemForm.entity_id}
                          onChange={(value) =>
                            setAddItemForm((current) => ({ ...current, entity_id: value }))
                          }
                        />
                      )}
                      {addItemForm.collection_scope === "facility" && (
                        <Select
                          label="Facility"
                          options={facilityOptions}
                          placeholder="Select facility"
                          value={addItemForm.facility_id}
                          onChange={(value) =>
                            setAddItemForm((current) => ({ ...current, facility_id: value }))
                          }
                        />
                      )}
                      <Input
                        label="Sort order"
                        type="number"
                        value={addItemForm.sort_order}
                        onChange={(event) =>
                          setAddItemForm((current) => ({
                            ...current,
                            sort_order: event.target.value,
                          }))
                        }
                      />
                      <Textarea
                        label="Collector help text"
                        placeholder="Optional instructions for this metric in the datasheet context."
                        value={addItemForm.help_text}
                        onChange={(event) =>
                          setAddItemForm((current) => ({
                            ...current,
                            help_text: event.target.value,
                          }))
                        }
                        rows={3}
                      />
                      <div className="flex items-start gap-3 rounded-xl border border-slate-200 px-4 py-3">
                        <Checkbox
                          checked={addItemForm.is_required}
                          onCheckedChange={(checked) =>
                            setAddItemForm((current) => ({
                              ...current,
                              is_required: checked,
                            }))
                          }
                        />
                        <div>
                          <p className="text-sm font-medium text-slate-900">Required in datasheet</p>
                          <p className="text-xs text-slate-500">
                            Keeps the item visible as part of the curated datasheet.
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeAddItemDialog}>
              Cancel
            </Button>
            {addItemSource === "new_custom" ? (
              <Button onClick={handleCreateCustomMetric} disabled={createCustomMetricMutation.isPending}>
                {createCustomMetricMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Create and add
              </Button>
            ) : (
              <Button onClick={handleAddExistingItem} disabled={addItemMutation.isPending || !selectedOption}>
                {addItemMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                Add to datasheet
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={evidenceItemTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setEvidenceItemTarget(null);
          }
        }}
      >
        <DialogContent className="max-w-3xl" contentClassName="max-h-[85vh] overflow-y-auto p-6">
          <DialogHeader>
            <DialogTitle>Linked Evidence</DialogTitle>
            <DialogDescription>
              {evidenceItemTarget
                ? `${evidenceItemTarget.label_override || evidenceItemTarget.shared_element_name || evidenceItemTarget.shared_element_code} · ${buildItemContextLabel(evidenceItemTarget)}`
                : "Evidence linked to this datasheet metric context."}
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 space-y-4">
            {evidenceTargetDataPoint ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <p className="font-medium text-slate-900">
                  {formatFileEvidenceCount(evidenceTargetDataPoint.evidence_count ?? 0)}
                </p>
                <p className="mt-1">
                  Data point status: <span className="font-medium text-slate-900">{evidenceTargetDataPoint.status}</span>
                </p>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-500">
                This datasheet item does not have a draft data point yet. Open it in Collection first to start attaching evidence.
              </div>
            )}

            {!evidenceTargetDataPoint ? null : evidenceItemsLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
              </div>
            ) : evidenceItems.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center">
                <p className="text-sm font-medium text-slate-900">No evidence linked yet</p>
                <p className="mt-1 text-sm text-slate-500">
                  Add evidence from Collection or Evidence Repository once this metric has supporting files or links.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {evidenceItems.map((evidence) => (
                  <div
                    key={evidence.id}
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold text-slate-900">{evidence.title}</p>
                          <Badge variant={evidence.type === "link" ? "warning" : "secondary"}>
                            {formatEvidenceType(evidence.type)}
                          </Badge>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                          <span className="rounded-full border border-slate-200 px-2 py-1">
                            {formatEvidenceDate(evidence.upload_date)}
                          </span>
                          {evidence.file_name && (
                            <span className="rounded-full border border-slate-200 px-2 py-1">
                              {evidence.file_name}
                            </span>
                          )}
                        </div>
                        {evidence.description && (
                          <p className="mt-2 text-sm text-slate-600">{evidence.description}</p>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => router.push(buildEvidenceRepositoryUrl(evidence.id))}
                      >
                        <ExternalLink className="h-4 w-4" />
                        Open in Repository
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            {evidenceItemTarget && (
              <Button variant="outline" onClick={() => router.push(buildCollectionContextUrl(evidenceItemTarget))}>
                <Link2 className="h-4 w-4" />
                Open in Collection
              </Button>
            )}
            <Button variant="outline" onClick={() => setEvidenceItemTarget(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
