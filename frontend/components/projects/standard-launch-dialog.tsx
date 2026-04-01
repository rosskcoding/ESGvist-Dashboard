"use client";

import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Search,
} from "lucide-react";

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
import { api } from "@/lib/api";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";

type LaunchUser = {
  id: number;
  name: string;
  email: string;
};

type LaunchEntity = {
  id: number;
  name: string;
  code: string | null;
};

type BoundaryMembership = {
  entity_id: number;
  included: boolean;
};

type BoundaryMembershipResponse = {
  boundary_id: number;
  boundary_name: string;
  memberships: BoundaryMembership[];
};

type DisclosureContentBlock = {
  type: string;
  title: string;
  body_md?: string | null;
  paragraphs?: string[];
  items?: string[];
  metadata?: Record<string, unknown> & {
    rows?: DisclosureContentRow[];
  };
};

type DisclosureContentRow = {
  ref?: string;
  clause_ref?: string;
  source?: string | null;
  standardised_requirement?: string | null;
  interpretation?: string | null;
  data_points?: string[];
  evidence?: string | null;
  owner?: string | null;
  frequency?: string | null;
  row_kind?: string | null;
};

type DisclosureApplicabilityRule = {
  source_format?: string;
  group_key?: string;
  group_title?: string;
  sector_ref_code?: string;
  topic?: {
    code?: string;
    title?: string;
  } | null;
  content_blocks?: DisclosureContentBlock[];
};

type LaunchRequirement = {
  section_id: number | null;
  section_code: string | null;
  section_title: string | null;
  disclosure_id: number;
  disclosure_code: string;
  disclosure_title: string;
  disclosure_description: string | null;
  disclosure_applicability_rule: DisclosureApplicabilityRule | null;
  requirement_item_id: number;
  requirement_item_code: string | null;
  requirement_item_name: string;
  requirement_item_description: string | null;
  mapping_type: string;
};

type LaunchOption = {
  shared_element_id: number;
  shared_element_code: string;
  shared_element_name: string;
  concept_domain: string | null;
  default_value_type: string | null;
  default_unit_code: string | null;
  existing_assignment_count: number;
  assigned_entity_ids: number[];
  linked_requirements: LaunchRequirement[];
};

type LaunchOptionsResponse = {
  standard_id: number;
  standard_code: string;
  standard_name: string;
  option_count: number;
  options: LaunchOption[];
};

type LaunchPayload = {
  shared_element_ids: number[];
  entity_id: number;
  collector_id: number | null;
  reviewer_id: number | null;
  backup_collector_id: number | null;
  deadline: string | null;
  escalation_after_days: number;
};

type LaunchResult = {
  created_count: number;
  skipped_count: number;
  created_assignment_ids: number[];
  skipped_shared_element_ids: number[];
};

type DisclosureRequirementGroup = {
  requirement_item_id: number;
  requirement_item_code: string | null;
  requirement_item_name: string;
  requirement_item_description: string | null;
  mapping_types: string[];
  metrics: LaunchOption[];
};

type DisclosureGroup = {
  disclosure_id: number;
  disclosure_code: string;
  disclosure_title: string;
  disclosure_description: string | null;
  disclosure_applicability_rule: DisclosureApplicabilityRule | null;
  section_id: number | null;
  section_code: string | null;
  section_title: string | null;
  requirement_groups: DisclosureRequirementGroup[];
  shared_element_ids: number[];
  concept_domains: string[];
};

interface StandardLaunchDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  standard:
    | {
        standard_id: number;
        code: string;
        standard_name: string;
      }
    | null;
  users: LaunchUser[];
  entities: LaunchEntity[];
  boundaryId?: number | null;
  onLaunched?: (result: LaunchResult) => void;
  onError?: (message: string | null) => void;
}

type DisclosureGroupBuilder = {
  disclosure_id: number;
  disclosure_code: string;
  disclosure_title: string;
  disclosure_description: string | null;
  disclosure_applicability_rule: DisclosureApplicabilityRule | null;
  section_id: number | null;
  section_code: string | null;
  section_title: string | null;
  shared_element_ids: Set<number>;
  concept_domains: Set<string>;
  requirement_groups: Map<
    number,
    {
      requirement_item_id: number;
      requirement_item_code: string | null;
      requirement_item_name: string;
      requirement_item_description: string | null;
      mapping_types: Set<string>;
      metrics: Map<number, LaunchOption>;
    }
  >;
};

const ALL_ENTITIES_VALUE = "__all_entities__";
const EMPTY_OPTIONS: LaunchOption[] = [];
const EMPTY_NUMBER_LIST: number[] = [];

function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function areNumberListsEqual(left: number[], right: number[]) {
  if (left.length !== right.length) return false;
  return left.every((value, index) => value === right[index]);
}

function normalizeInlineText(value: string | null | undefined) {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

function isDuplicateText(left: string | null | undefined, right: string | null | undefined) {
  return normalizeInlineText(left).toLowerCase() === normalizeInlineText(right).toLowerCase();
}

function normalizeLegacyDisclosureDescription(description: string) {
  return description
    .replace(/REQUIREMENTS?/g, "\nREQUIREMENTS\n")
    .replace(/RECOMMENDATIONS/g, "\nRECOMMENDATIONS\n")
    .replace(/GUIDANCE/g, "\nGUIDANCE\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function splitLegacyDisclosureDescription(description: string): DisclosureContentBlock[] {
  const normalized = normalizeLegacyDisclosureDescription(description);
  if (!normalized) {
    return [];
  }

  const lines = normalized
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const blocks: DisclosureContentBlock[] = [];
  let currentType = "requirements";
  let currentTitle = "Requirements";
  let currentLines: string[] = [];

  const pushCurrentBlock = () => {
    if (currentLines.length === 0) return;
    blocks.push({
      type: currentType,
      title: currentTitle,
      paragraphs: [...currentLines],
      items: [],
      body_md: currentLines.join("\n"),
    });
    currentLines = [];
  };

  for (const line of lines) {
    const normalizedLine = line.toUpperCase();
    if (normalizedLine === "REQUIREMENTS" || normalizedLine === "REQUIREMENT") {
      pushCurrentBlock();
      currentType = "requirements";
      currentTitle = "Requirements";
      continue;
    }
    if (normalizedLine === "RECOMMENDATIONS") {
      pushCurrentBlock();
      currentType = "recommendations";
      currentTitle = "Recommendations";
      continue;
    }
    if (normalizedLine === "GUIDANCE") {
      pushCurrentBlock();
      currentType = "guidance";
      currentTitle = "Guidance";
      continue;
    }
    currentLines.push(line);
  }

  pushCurrentBlock();

  if (blocks.length === 0 && normalized) {
    return [
      {
        type: "requirements",
        title: "Requirements",
        paragraphs: [normalized],
        items: [],
        body_md: normalized,
      },
    ];
  }

  return blocks;
}

function getDisclosureContentBlocks(disclosure: DisclosureGroup): DisclosureContentBlock[] {
  const structuredBlocks = (disclosure.disclosure_applicability_rule?.content_blocks ?? []).filter(
    (block) => block.type !== "data_points" && Boolean(block.body_md || block.paragraphs?.length || block.items?.length)
  );
  if (structuredBlocks.length > 0) {
    return structuredBlocks;
  }
  if (disclosure.disclosure_description) {
    return splitLegacyDisclosureDescription(disclosure.disclosure_description);
  }
  return [];
}

export function StandardLaunchDialog({
  open,
  onOpenChange,
  projectId,
  standard,
  users,
  entities,
  boundaryId = null,
  onLaunched,
  onError,
}: StandardLaunchDialogProps) {
  const queryClient = useQueryClient();
  const [entityId, setEntityId] = useState("");
  const [collectorId, setCollectorId] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [deadline, setDeadline] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDisclosureIds, setSelectedDisclosureIds] = useState<number[]>([]);
  const [detailDisclosureId, setDetailDisclosureId] = useState<number | null>(null);
  const [isBatchLaunching, setIsBatchLaunching] = useState(false);

  useEffect(() => {
    if (!open) {
      setEntityId("");
      setCollectorId("");
      setReviewerId("");
      setSearchTerm("");
      setSelectedDisclosureIds([]);
      setDetailDisclosureId(null);
      setDeadline("");
      setIsBatchLaunching(false);
      return;
    }
  }, [open]);

  useEffect(() => {
    setEntityId("");
    setCollectorId("");
    setReviewerId("");
    setDeadline("");
    setSearchTerm("");
    setSelectedDisclosureIds([]);
    setDetailDisclosureId(null);
  }, [standard?.standard_id]);

  const optionsPath = standard
    ? `/projects/${projectId}/standards/${standard.standard_id}/launch-options`
    : `/projects/${projectId}/standards/0/launch-options`;
  const launchPath = standard
    ? `/projects/${projectId}/standards/${standard.standard_id}/launch`
    : `/projects/${projectId}/standards/0/launch`;

  const {
    data,
    isLoading,
    error,
  } = useApiQuery<LaunchOptionsResponse>(
    ["project-standard-launch-options", projectId, standard?.standard_id ?? 0],
    optionsPath,
    {
      enabled: open && !!standard,
    }
  );

  const boundaryMembershipsPath = boundaryId
    ? `/boundaries/${boundaryId}/memberships`
    : "/boundaries/0/memberships";

  const { data: boundaryMembershipsData } = useApiQuery<BoundaryMembershipResponse>(
    ["boundary-memberships", boundaryId],
    boundaryMembershipsPath,
    {
      enabled: open && boundaryId !== null,
    }
  );

  const launchMutation = useApiMutation<LaunchResult, LaunchPayload>(launchPath, "POST", {
    onSuccess: async (result) => {
      onError?.(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["project-standards", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["project-team", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["project-assignment-options", projectId] }),
        queryClient.invalidateQueries({ queryKey: ["assignments", Number(projectId)] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard", "progress", Number(projectId)] }),
        queryClient.invalidateQueries({ queryKey: ["projects"] }),
      ]);
      onLaunched?.(result);
      onOpenChange(false);
      setSelectedDisclosureIds([]);
    },
    onError: (mutationError) => {
      onError?.(mutationError.message || "Unable to launch selected indicators.");
    },
  });

  const userOptions = useMemo(
    () =>
      users.map((user) => ({
        value: String(user.id),
        label: `${user.name}${user.email ? ` (${user.email})` : ""}`,
      })),
    [users]
  );

  const availableEntities = useMemo(() => {
    if (!boundaryId || !boundaryMembershipsData) {
      return entities;
    }

    const includedEntityIds = new Set(
      boundaryMembershipsData.memberships
        .filter((membership) => membership.included)
        .map((membership) => membership.entity_id)
    );
    return entities.filter((entity) => includedEntityIds.has(entity.id));
  }, [boundaryId, boundaryMembershipsData, entities]);

  const entityOptions = useMemo(
    () => [
      {
        value: ALL_ENTITIES_VALUE,
        label: "All in-scope entities",
      },
      ...availableEntities.map((entity) => ({
        value: String(entity.id),
        label: entity.code ? `${entity.code} - ${entity.name}` : entity.name,
      })),
    ],
    [availableEntities]
  );

  const options = data?.options ?? EMPTY_OPTIONS;
  const hasLoadError = Boolean(error);
  const normalizedSearch = searchTerm.trim().toLowerCase();
  const allEntityIds = useMemo(
    () => availableEntities.map((entity) => entity.id),
    [availableEntities]
  );
  const isAllEntitiesSelected = entityId === ALL_ENTITIES_VALUE;
  const selectedEntityIds = useMemo(() => {
    if (isAllEntitiesSelected) {
      return allEntityIds;
    }
    if (!entityId) {
      return EMPTY_NUMBER_LIST;
    }
    return [Number(entityId)];
  }, [allEntityIds, entityId, isAllEntitiesSelected]);

  useEffect(() => {
    if (!entityId) return;
    if (entityId === ALL_ENTITIES_VALUE) {
      if (availableEntities.length === 0) {
        setEntityId("");
      }
      return;
    }

    const isStillAvailable = availableEntities.some((entity) => String(entity.id) === entityId);
    if (!isStillAvailable) {
      setEntityId("");
    }
  }, [availableEntities, entityId]);

  const optionById = useMemo(
    () => new Map(options.map((option) => [option.shared_element_id, option])),
    [options]
  );

  const disclosureGroups = useMemo<DisclosureGroup[]>(() => {
    const groups = new Map<number, DisclosureGroupBuilder>();

    for (const option of options) {
      for (const requirement of option.linked_requirements) {
        let disclosure = groups.get(requirement.disclosure_id);
        if (!disclosure) {
          disclosure = {
            disclosure_id: requirement.disclosure_id,
            disclosure_code: requirement.disclosure_code,
            disclosure_title: requirement.disclosure_title,
            disclosure_description: requirement.disclosure_description,
            disclosure_applicability_rule: requirement.disclosure_applicability_rule,
            section_id: requirement.section_id,
            section_code: requirement.section_code,
            section_title: requirement.section_title,
            shared_element_ids: new Set<number>(),
            concept_domains: new Set<string>(),
            requirement_groups: new Map(),
          };
          groups.set(requirement.disclosure_id, disclosure);
        }

        if (!disclosure.disclosure_applicability_rule && requirement.disclosure_applicability_rule) {
          disclosure.disclosure_applicability_rule = requirement.disclosure_applicability_rule;
        }

        disclosure.shared_element_ids.add(option.shared_element_id);
        if (option.concept_domain) {
          disclosure.concept_domains.add(option.concept_domain);
        }

        let requirementGroup = disclosure.requirement_groups.get(requirement.requirement_item_id);
        if (!requirementGroup) {
          requirementGroup = {
            requirement_item_id: requirement.requirement_item_id,
            requirement_item_code: requirement.requirement_item_code,
            requirement_item_name: requirement.requirement_item_name,
            requirement_item_description: requirement.requirement_item_description,
            mapping_types: new Set<string>(),
            metrics: new Map<number, LaunchOption>(),
          };
          disclosure.requirement_groups.set(requirement.requirement_item_id, requirementGroup);
        }

        requirementGroup.mapping_types.add(requirement.mapping_type);
        requirementGroup.metrics.set(option.shared_element_id, option);
      }
    }

    return Array.from(groups.values()).map((group) => ({
      disclosure_id: group.disclosure_id,
      disclosure_code: group.disclosure_code,
      disclosure_title: group.disclosure_title,
      disclosure_description: group.disclosure_description,
      disclosure_applicability_rule: group.disclosure_applicability_rule,
      section_id: group.section_id,
      section_code: group.section_code,
      section_title: group.section_title,
      shared_element_ids: Array.from(group.shared_element_ids),
      concept_domains: Array.from(group.concept_domains).sort(),
      requirement_groups: Array.from(group.requirement_groups.values()).map((requirementGroup) => ({
        requirement_item_id: requirementGroup.requirement_item_id,
        requirement_item_code: requirementGroup.requirement_item_code,
        requirement_item_name: requirementGroup.requirement_item_name,
        requirement_item_description: requirementGroup.requirement_item_description,
        mapping_types: Array.from(requirementGroup.mapping_types).sort(),
        metrics: Array.from(requirementGroup.metrics.values()).sort((left, right) =>
          left.shared_element_name.localeCompare(right.shared_element_name)
        ),
      })),
    }));
  }, [options]);

  const filteredDisclosureGroups = useMemo(() => {
    if (!normalizedSearch) return disclosureGroups;

    return disclosureGroups.filter((disclosure) => {
      const searchableText = [
        disclosure.section_code,
        disclosure.section_title,
        disclosure.disclosure_code,
        disclosure.disclosure_title,
        disclosure.disclosure_description,
        ...disclosure.requirement_groups.flatMap((requirementGroup) => [
          requirementGroup.requirement_item_code,
          requirementGroup.requirement_item_name,
          requirementGroup.requirement_item_description,
          ...requirementGroup.mapping_types,
          ...requirementGroup.metrics.flatMap((metric) => [
            metric.shared_element_code,
            metric.shared_element_name,
            metric.default_value_type,
            metric.default_unit_code,
            metric.concept_domain,
          ]),
        ]),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return searchableText.includes(normalizedSearch);
    });
  }, [disclosureGroups, normalizedSearch]);

  const launchableIdsByDisclosure = useMemo(() => {
    const launchableMap = new Map<number, number[]>();

    for (const disclosure of disclosureGroups) {
      const launchableIds = disclosure.shared_element_ids.filter((sharedElementId) => {
        if (selectedEntityIds.length === 0) {
          return true;
        }
        const option = optionById.get(sharedElementId);
        if (!option) {
          return true;
        }
        return selectedEntityIds.some(
          (targetEntityId) => !option.assigned_entity_ids.includes(targetEntityId)
        );
      });
      launchableMap.set(disclosure.disclosure_id, launchableIds);
    }

    return launchableMap;
  }, [disclosureGroups, optionById, selectedEntityIds]);

  useEffect(() => {
    if (selectedEntityIds.length === 0) return;
    setSelectedDisclosureIds((current) => {
      const next = current.filter(
        (disclosureId) => (launchableIdsByDisclosure.get(disclosureId) ?? []).length > 0
      );
      return areNumberListsEqual(current, next) ? current : next;
    });
  }, [launchableIdsByDisclosure, selectedEntityIds]);

  const visibleSelectableDisclosureIds = filteredDisclosureGroups
    .filter((disclosure) => (launchableIdsByDisclosure.get(disclosure.disclosure_id) ?? []).length > 0)
    .map((disclosure) => disclosure.disclosure_id);

  const selectedVisibleCount = visibleSelectableDisclosureIds.filter((id) =>
    selectedDisclosureIds.includes(id)
  ).length;
  const canSelectAll = visibleSelectableDisclosureIds.length > 0;

  const selectedSharedElementIds = useMemo(
    () =>
      Array.from(
        new Set(
          selectedDisclosureIds.flatMap(
            (disclosureId) => launchableIdsByDisclosure.get(disclosureId) ?? []
          )
        )
      ),
    [launchableIdsByDisclosure, selectedDisclosureIds]
  );

  const collectorReviewerConflict =
    collectorId !== "" && reviewerId !== "" && collectorId === reviewerId;

  const toggleDisclosureSelection = (disclosureId: number) => {
    const launchableIds = launchableIdsByDisclosure.get(disclosureId) ?? [];
    if (selectedEntityIds.length > 0 && launchableIds.length === 0) {
      return;
    }

    setSelectedDisclosureIds((current) =>
      current.includes(disclosureId)
        ? current.filter((id) => id !== disclosureId)
        : [...current, disclosureId]
    );
  };

  const toggleSelectAllVisible = () => {
    setSelectedDisclosureIds((current) => {
      const allVisibleSelected = visibleSelectableDisclosureIds.every((id) => current.includes(id));
      if (allVisibleSelected) {
        return current.filter((id) => !visibleSelectableDisclosureIds.includes(id));
      }
      return Array.from(new Set([...current, ...visibleSelectableDisclosureIds]));
    });
  };

  const handleLaunch = () => {
    if (
      selectedEntityIds.length === 0 ||
      selectedSharedElementIds.length === 0 ||
      collectorReviewerConflict ||
      launchMutation.isPending ||
      isBatchLaunching
    ) {
      return;
    }

    onError?.(null);

    const payloadBase = {
      shared_element_ids: selectedSharedElementIds,
      collector_id: collectorId ? Number(collectorId) : null,
      reviewer_id: reviewerId ? Number(reviewerId) : null,
      backup_collector_id: null,
      deadline: deadline || null,
      escalation_after_days: 3,
    };

    if (selectedEntityIds.length === 1) {
      launchMutation.mutate({
        ...payloadBase,
        entity_id: selectedEntityIds[0],
      });
      return;
    }

    void (async () => {
      setIsBatchLaunching(true);

      try {
        const settled = await Promise.allSettled(
          selectedEntityIds.map((targetEntityId) =>
            api.post<LaunchResult>(launchPath, {
              ...payloadBase,
              entity_id: targetEntityId,
            })
          )
        );

        const successes = settled.flatMap((result) =>
          result.status === "fulfilled" ? [result.value] : []
        );
        const failures = settled.flatMap((result) =>
          result.status === "rejected" ? [result.reason] : []
        );

        if (successes.length > 0) {
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ["project-standards", projectId] }),
            queryClient.invalidateQueries({ queryKey: ["project-team", projectId] }),
            queryClient.invalidateQueries({ queryKey: ["project-assignment-options", projectId] }),
            queryClient.invalidateQueries({ queryKey: ["assignments", Number(projectId)] }),
            queryClient.invalidateQueries({ queryKey: ["dashboard", "progress", Number(projectId)] }),
            queryClient.invalidateQueries({ queryKey: ["projects"] }),
          ]);
        }

        const aggregatedResult: LaunchResult = {
          created_count: successes.reduce((total, result) => total + result.created_count, 0),
          skipped_count: successes.reduce((total, result) => total + result.skipped_count, 0),
          created_assignment_ids: successes.flatMap((result) => result.created_assignment_ids),
          skipped_shared_element_ids: Array.from(
            new Set(successes.flatMap((result) => result.skipped_shared_element_ids))
          ),
        };

        if (failures.length > 0) {
          const firstFailure = failures[0];
          const failureMessage =
            firstFailure instanceof Error
              ? firstFailure.message
              : "Unable to launch selected disclosures for all entities.";
          onLaunched?.(aggregatedResult);
          onError?.(
            `Launched for ${successes.length} of ${selectedEntityIds.length} entities. ${failureMessage}`
          );
          return;
        }

        onLaunched?.(aggregatedResult);
        onOpenChange(false);
        setSelectedDisclosureIds([]);
      } finally {
        setIsBatchLaunching(false);
      }
    })();
  };

  const launchSummary = !entityId
    ? selectedDisclosureIds.length > 0
      ? `Choose an entity or All entities to launch ${pluralize(selectedDisclosureIds.length, "disclosure")}.`
      : "Choose an entity scope and one or more disclosures to launch."
    : selectedSharedElementIds.length > 0
      ? isAllEntitiesSelected
        ? `${pluralize(selectedDisclosureIds.length, "disclosure")} selected across ${pluralize(
            selectedEntityIds.length,
            "entity",
            "entities"
          )}. ${pluralize(selectedSharedElementIds.length, "data point")} will be launched for each entity where still needed.`
        : `${pluralize(selectedDisclosureIds.length, "disclosure")} selected, ${pluralize(
            selectedSharedElementIds.length,
            "data point"
          )} will be launched.`
      : isAllEntitiesSelected
        ? "Select one or more disclosures that are not yet fully launched across all entities."
        : "Select one or more disclosures that are not yet launched for this entity.";

  const launchButtonLabel = !entityId
    ? "Choose Scope First"
    : launchMutation.isPending || isBatchLaunching
      ? "Launching..."
      : isAllEntitiesSelected
        ? `Launch ${pluralize(selectedDisclosureIds.length, "Disclosure")} to All Entities`
        : `Launch ${pluralize(selectedDisclosureIds.length, "Disclosure")} to Collection`;

  const detailDisclosure =
    detailDisclosureId === null
      ? null
      : disclosureGroups.find((disclosure) => disclosure.disclosure_id === detailDisclosureId) ?? null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-6xl">
        <DialogHeader>
          <DialogTitle>
            {standard ? `Launch Disclosures from ${standard.code}` : "Launch Disclosures"}
          </DialogTitle>
          <DialogDescription>
            Select disclosures first. Each selected disclosure launches all of its mapped data points for the chosen entity.
          </DialogDescription>
        </DialogHeader>

        {!standard ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
            Select a standard first.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3">
              <p className="text-sm font-medium text-slate-900">
                GRI Standard -&gt; Disclosure -&gt; Requirement -&gt; Data Points
              </p>
              <p className="mt-1 text-sm text-slate-500">
                You assign work at the disclosure level. The data points stay nested inside each disclosure and launch together.
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <Select
                label="Entity"
                options={entityOptions}
                value={entityId}
                onChange={setEntityId}
                placeholder="Select entity"
              />
              <Select
                label="Collector"
                options={[{ value: "", label: "Unassigned" }, ...userOptions]}
                value={collectorId}
                onChange={setCollectorId}
              />
              <Select
                label="Reviewer"
                options={[{ value: "", label: "Unassigned" }, ...userOptions]}
                value={reviewerId}
                onChange={setReviewerId}
              />
              <div className="grid gap-1.5">
                <label className="text-sm font-medium leading-none text-slate-700">
                  Deadline
                </label>
                <Input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
              </div>
            </div>

            {collectorReviewerConflict && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                Collector and reviewer must be different people.
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                {error.message || "Unable to load disclosures for this standard."}
              </div>
            )}

            <div className="flex flex-col gap-3 rounded-xl border border-slate-200 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex-1">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <Input
                    className="pl-9"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    placeholder="Search disclosure, requirement, or data point..."
                  />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{pluralize(filteredDisclosureGroups.length, "disclosure")}</Badge>
                <Badge variant="outline">
                  {pluralize(selectedDisclosureIds.length, "selected disclosure")}
                </Badge>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={toggleSelectAllVisible}
                  disabled={!canSelectAll}
                >
                  {selectedVisibleCount === visibleSelectableDisclosureIds.length &&
                  visibleSelectableDisclosureIds.length > 0
                    ? "Clear Visible"
                    : "Select Visible"}
                </Button>
              </div>
            </div>

            {!entityId && (
              <div className="rounded-lg border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm text-cyan-900">
                Choose one entity or All entities to enable launch and to see which disclosures are already launched for that scope.
              </div>
            )}

            {selectedDisclosureIds.length > 0 && !entityId && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                Select an entity scope to launch the chosen disclosures.
              </div>
            )}

            {selectedDisclosureIds.length > 0 && entityId && selectedSharedElementIds.length === 0 && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                The selected disclosures are already fully launched for this entity.
              </div>
            )}

            <div className="max-h-[520px] space-y-3 overflow-y-auto pr-1">
              {isLoading ? (
                <div className="flex min-h-[180px] items-center justify-center">
                  <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                </div>
              ) : hasLoadError ? (
                <div className="rounded-xl border border-dashed border-red-200 bg-red-50 px-4 py-10 text-center text-sm text-red-700">
                  Disclosures could not be loaded for this standard. Refresh the page or reopen this dialog.
                </div>
              ) : filteredDisclosureGroups.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-500">
                  No disclosures match the current search.
                </div>
              ) : (
                filteredDisclosureGroups.map((disclosure) => {
                  const launchableIds =
                    launchableIdsByDisclosure.get(disclosure.disclosure_id) ?? [];
                  const totalDataPoints = disclosure.shared_element_ids.length;
                  const allAlreadyLaunched =
                    selectedEntityIds.length > 0 &&
                    totalDataPoints > 0 &&
                    launchableIds.length === 0;
                  const partiallyLaunched =
                    selectedEntityIds.length > 0 &&
                    totalDataPoints > launchableIds.length &&
                    launchableIds.length > 0;
                  const checked = selectedDisclosureIds.includes(disclosure.disclosure_id);
                  const sectionLabel = disclosure.section_title
                    ? disclosure.section_code
                      ? `${disclosure.section_code} - ${disclosure.section_title}`
                      : disclosure.section_title
                    : standard.code;

                  return (
                    <div
                      key={disclosure.disclosure_id}
                      className={cn(
                        "rounded-xl border p-4 transition-colors",
                        checked && !allAlreadyLaunched
                          ? "border-slate-900 bg-slate-50"
                          : "border-slate-200 bg-white",
                        allAlreadyLaunched && "border-green-200 bg-green-50/70"
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <div className="pt-1">
                          <Checkbox
                            checked={checked}
                            disabled={allAlreadyLaunched}
                            onCheckedChange={() => toggleDisclosureSelection(disclosure.disclosure_id)}
                          />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="min-w-0 space-y-2">
                              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                                {sectionLabel}
                              </p>
                              <p className="text-sm font-semibold text-slate-700">
                                {disclosure.disclosure_code}
                              </p>
                              <h3 className="text-lg font-semibold text-slate-900">
                                {disclosure.disclosure_title}
                              </h3>
                            </div>

                            <div className="flex flex-col items-start gap-3 lg:items-end">
                              <div className="flex flex-wrap gap-2 lg:justify-end">
                                <Badge variant="outline">
                                  {pluralize(disclosure.requirement_groups.length, "requirement")}
                                </Badge>
                                <Badge variant="outline">
                                  {pluralize(totalDataPoints, "data point")}
                                </Badge>
                                {disclosure.concept_domains.map((domain) => (
                                  <Badge key={domain} variant="outline">
                                    {domain}
                                  </Badge>
                                ))}
                                {partiallyLaunched && (
                                  <Badge variant="warning">
                                    {launchableIds.length}/{totalDataPoints} remaining
                                  </Badge>
                                )}
                                {allAlreadyLaunched && (
                                  <Badge variant="success">
                                    <CheckCircle2 className="mr-1 h-3 w-3" />
                                    Already launched
                                  </Badge>
                                )}
                              </div>

                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => setDetailDisclosureId(disclosure.disclosure_id)}
                              >
                                View Details
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        <DialogFooter className="mt-6 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-slate-500">{launchSummary}</p>
          <div className="flex w-full flex-col-reverse gap-3 sm:w-auto sm:flex-row">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleLaunch}
              disabled={
                !standard ||
                !entityId ||
                selectedSharedElementIds.length === 0 ||
                collectorReviewerConflict ||
                launchMutation.isPending ||
                isBatchLaunching
              }
            >
              {(launchMutation.isPending || isBatchLaunching) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {launchButtonLabel}
            </Button>
          </div>
        </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={detailDisclosure !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setDetailDisclosureId(null);
          }
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-4xl overflow-y-auto">
          {detailDisclosure && (
            <>
              <DialogHeader>
                <DialogTitle>{detailDisclosure.disclosure_code}</DialogTitle>
                <DialogDescription>{detailDisclosure.disclosure_title}</DialogDescription>
              </DialogHeader>

              <div className="space-y-4">
                {(() => {
                  const topic = detailDisclosure.disclosure_applicability_rule?.topic;
                  const topicLabel =
                    topic?.code && topic?.title
                      ? `Topic ${topic.code} - ${topic.title}`
                      : topic?.title ?? topic?.code ?? null;
                  const contentBlocks = getDisclosureContentBlocks(detailDisclosure);

                  return (
                    <>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">
                          {detailDisclosure.section_code
                            ? `${detailDisclosure.section_code} - ${detailDisclosure.section_title ?? standard?.code ?? ""}`
                            : detailDisclosure.section_title ?? standard?.code ?? ""}
                        </Badge>
                        {topicLabel && <Badge variant="outline">{topicLabel}</Badge>}
                        <Badge variant="outline">
                          {pluralize(detailDisclosure.requirement_groups.length, "requirement")}
                        </Badge>
                        <Badge variant="outline">
                          {pluralize(detailDisclosure.shared_element_ids.length, "data point")}
                        </Badge>
                      </div>

                      {contentBlocks.length > 0 && (
                        <div className="space-y-3">
                          {contentBlocks.map((block, index) => (
                            <div
                              key={`${detailDisclosure.disclosure_id}-${block.type}-${index}`}
                              className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3"
                            >
                              <p className="text-sm font-semibold text-slate-900">{block.title}</p>
                              {block.metadata?.rows && block.metadata.rows.length > 0 && (
                                <div className="mt-3 space-y-3">
                                  {block.metadata.rows.map((row, rowIndex) => (
                                    <div
                                      key={`${detailDisclosure.disclosure_id}-${block.type}-${index}-row-${row.ref ?? rowIndex}`}
                                      className="rounded-lg border border-slate-200 bg-white px-3 py-3"
                                    >
                                      <div className="flex flex-wrap items-center gap-2">
                                        {row.ref && <Badge variant="outline">{row.ref}</Badge>}
                                        {row.source && (
                                          <span className="text-xs font-medium text-slate-500">
                                            {row.source}
                                          </span>
                                        )}
                                      </div>
                                      {row.standardised_requirement && (
                                        <p className="mt-2 text-sm font-medium text-slate-900">
                                          {row.standardised_requirement}
                                        </p>
                                      )}
                                      {row.interpretation && (
                                        <p className="mt-2 text-sm text-slate-600">
                                          {row.interpretation}
                                        </p>
                                      )}
                                      {row.data_points && row.data_points.length > 0 && (
                                        <div className="mt-3">
                                          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                            Data points
                                          </p>
                                          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                                            {row.data_points.map((item, itemIndex) => (
                                              <li
                                                key={`${detailDisclosure.disclosure_id}-${block.type}-${index}-row-${row.ref ?? rowIndex}-item-${itemIndex}`}
                                              >
                                                {item}
                                              </li>
                                            ))}
                                          </ul>
                                        </div>
                                      )}
                                      {row.evidence && (
                                        <p className="mt-3 text-xs text-slate-500">
                                          Evidence: {row.evidence}
                                        </p>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {!block.metadata?.rows?.length &&
                                block.paragraphs &&
                                block.paragraphs.length > 0 && (
                                <div className="mt-2 space-y-2">
                                  {block.paragraphs.map((paragraph, paragraphIndex) => (
                                    <p
                                      key={`${detailDisclosure.disclosure_id}-${block.type}-${index}-paragraph-${paragraphIndex}`}
                                      className="whitespace-pre-line text-sm text-slate-700"
                                    >
                                      {paragraph}
                                    </p>
                                  ))}
                                </div>
                              )}
                              {!block.metadata?.rows?.length && block.items && block.items.length > 0 && (
                                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                                  {block.items.map((item, itemIndex) => (
                                    <li
                                      key={`${detailDisclosure.disclosure_id}-${block.type}-${index}-item-${itemIndex}`}
                                    >
                                      {item}
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {!block.metadata?.rows?.length &&
                                !block.paragraphs?.length &&
                                !block.items?.length &&
                                block.body_md && (
                                <p className="mt-2 whitespace-pre-line text-sm text-slate-700">
                                  {block.body_md}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {contentBlocks.length === 0 && detailDisclosure.disclosure_description && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                          <p className="whitespace-pre-line text-sm text-slate-700">
                            {detailDisclosure.disclosure_description}
                          </p>
                        </div>
                      )}
                    </>
                  );
                })()}

                <div className="space-y-3">
                  <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">Data points</p>
                        <p className="mt-1 text-sm text-slate-500">
                          Structured data items that will launch together with this disclosure.
                        </p>
                      </div>
                      <Badge variant="outline">
                        {pluralize(detailDisclosure.requirement_groups.length, "data point")}
                      </Badge>
                    </div>
                    <ul className="mt-3 list-disc space-y-3 pl-5">
                      {detailDisclosure.requirement_groups.map((requirementGroup) => {
                        const metricMetadata = Array.from(
                          new Set(
                            requirementGroup.metrics.map((metric) =>
                              [
                                metric.shared_element_code,
                                metric.default_value_type,
                                metric.default_unit_code,
                              ]
                                .filter(Boolean)
                                .join(" · ")
                            )
                          )
                        ).filter(Boolean);
                        const itemMetadata = [
                          requirementGroup.requirement_item_code,
                          ...metricMetadata,
                        ].filter(Boolean);

                        return (
                          <li key={requirementGroup.requirement_item_id} className="space-y-1 text-sm">
                            <p className="font-medium text-slate-900">
                              {requirementGroup.requirement_item_name}
                            </p>
                            {requirementGroup.requirement_item_description &&
                              !isDuplicateText(
                                requirementGroup.requirement_item_description,
                                requirementGroup.requirement_item_name
                              ) && (
                              <p className="whitespace-pre-line text-slate-600">
                                {requirementGroup.requirement_item_description}
                              </p>
                            )}
                            {itemMetadata.length > 0 && (
                              <p className="text-xs text-slate-500">{itemMetadata.join(" · ")}</p>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
