"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  GitMerge,
  History,
  Loader2,
  ShieldAlert,
} from "lucide-react";

import { useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type RoleBinding = { role: string };

type Standard = {
  id: number;
  code: string;
  name: string;
};

type StandardListResponse = {
  items: Standard[];
  total: number;
};

type Disclosure = {
  id: number;
  code: string;
  title: string;
};

type DisclosureListResponse = {
  items: Disclosure[];
  total: number;
};

type RequirementItem = {
  id: number;
  item_code: string | null;
  name: string;
  item_type: string;
  value_type: string;
};

type RequirementItemListResponse = {
  items: RequirementItem[];
  total: number;
};

type SharedElement = {
  id: number;
  code: string;
  name: string;
};

type SharedElementListResponse = {
  items: SharedElement[];
  total: number;
};

type MappingSummary = {
  id: number;
  requirement_item_id: number;
  shared_element_id: number;
  mapping_type: string;
  version: number;
  is_current: boolean;
  valid_from: string | null;
  valid_to: string | null;
};

type MappingListResponse = {
  items: MappingSummary[];
  total: number;
};

type MappingDiff = {
  v1: number;
  v2: number;
  changes: Array<{
    field: string;
    old_value: string | null;
    new_value: string | null;
  }>;
};

function formatDate(value: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}

function isOrgContextError(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "ORG_HEADER_REQUIRED" || /organization context|x-organization-id/i.test(error?.message ?? "");
}

function isNotFoundError(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "NOT_FOUND" || /not found/i.test(error?.message ?? "");
}

export default function MappingHistoryPage() {
  const searchParams = useSearchParams();
  const [selectedStandardId, setSelectedStandardId] = useState(
    searchParams.get("standardId") ?? ""
  );
  const [selectedDisclosureId, setSelectedDisclosureId] = useState(
    searchParams.get("disclosureId") ?? ""
  );
  const [selectedItemId, setSelectedItemId] = useState(
    searchParams.get("itemId") ?? ""
  );
  const [selectedElementId, setSelectedElementId] = useState(
    searchParams.get("elementId") ?? ""
  );
  const [compareV1, setCompareV1] = useState("");
  const [compareV2, setCompareV2] = useState("");

  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me"],
    "/auth/me"
  );
  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) => ["framework_admin", "platform_admin"].includes(role));
  const accessDenied = Boolean(me) && !canAccess;

  const {
    data: standardsData,
    isLoading: standardsLoading,
    error: standardsError,
  } = useApiQuery<StandardListResponse>(
    ["mapping-standards"],
    "/standards?page_size=100",
    { enabled: canAccess }
  );

  const {
    data: disclosuresData,
    isLoading: disclosuresLoading,
    error: disclosuresError,
  } = useApiQuery<DisclosureListResponse>(
    ["mapping-disclosures", selectedStandardId],
    selectedStandardId
      ? `/standards/${selectedStandardId}/disclosures?page_size=100`
      : "/standards/0/disclosures",
    { enabled: canAccess && Boolean(selectedStandardId) }
  );

  const {
    data: itemsData,
    isLoading: itemsLoading,
    error: itemsError,
  } = useApiQuery<RequirementItemListResponse>(
    ["mapping-items", selectedDisclosureId],
    selectedDisclosureId
      ? `/disclosures/${selectedDisclosureId}/items?page_size=100`
      : "/disclosures/0/items",
    { enabled: canAccess && Boolean(selectedDisclosureId) }
  );

  const {
    data: sharedElementsData,
    isLoading: sharedElementsLoading,
    error: sharedElementsError,
  } = useApiQuery<SharedElementListResponse>(
    ["mapping-shared-elements"],
    "/shared-elements?page_size=200",
    { enabled: canAccess }
  );

  const {
    data: mappingsData,
    isLoading: mappingsLoading,
    error: mappingsError,
  } = useApiQuery<MappingListResponse>(
    ["mapping-list"],
    "/mappings?page_size=500",
    { enabled: canAccess }
  );

  const {
    data: historyData,
    isLoading: historyLoading,
    error: historyError,
  } = useApiQuery<MappingListResponse>(
    ["mapping-history", selectedItemId, selectedElementId],
    selectedItemId && selectedElementId
      ? `/mappings/${selectedItemId}/${selectedElementId}/history`
      : "/mappings/0/0/history",
    { enabled: canAccess && Boolean(selectedItemId) && Boolean(selectedElementId) }
  );

  const {
    data: diffData,
    isLoading: diffLoading,
    error: diffError,
  } = useApiQuery<MappingDiff>(
    ["mapping-diff", selectedItemId, selectedElementId, compareV1, compareV2],
    selectedItemId && selectedElementId && compareV1 && compareV2
      ? `/mappings/${selectedItemId}/${selectedElementId}/diff?v1=${compareV1}&v2=${compareV2}`
      : "/mappings/0/0/diff?v1=1&v2=1",
    {
      enabled:
        canAccess &&
        Boolean(selectedItemId) &&
        Boolean(selectedElementId) &&
        Boolean(compareV1) &&
        Boolean(compareV2) &&
        compareV1 !== compareV2,
    }
  );

  const standards = standardsData?.items ?? [];
  const disclosures = disclosuresData?.items ?? [];
  const items = itemsData?.items ?? [];
  const sharedElements = sharedElementsData?.items ?? [];
  const mappings = mappingsData?.items ?? [];
  const history = historyData?.items ?? [];
  const currentMappings = useMemo(
    () => mappings.filter((mapping) => mapping.is_current),
    [mappings]
  );

  const selectedItemMappings = useMemo(
    () =>
      selectedItemId
        ? currentMappings.filter(
            (mapping) => mapping.requirement_item_id === Number(selectedItemId)
          )
        : [],
    [currentMappings, selectedItemId]
  );

  const orgContextMissing =
    isOrgContextError(standardsError) ||
    isOrgContextError(disclosuresError) ||
    isOrgContextError(itemsError) ||
    isOrgContextError(sharedElementsError) ||
    isOrgContextError(mappingsError);

  const pageError =
    standardsError ||
    disclosuresError ||
    itemsError ||
    sharedElementsError ||
    mappingsError ||
    null;

  useEffect(() => {
    if (!selectedStandardId && standards.length > 0) {
      setSelectedStandardId(String(standards[0].id));
    }
  }, [selectedStandardId, standards]);

  useEffect(() => {
    if (!selectedStandardId) return;
    if (disclosures.length === 0) {
      setSelectedDisclosureId("");
      return;
    }
    const stillExists = disclosures.some(
      (disclosure) => String(disclosure.id) === selectedDisclosureId
    );
    if (!selectedDisclosureId || !stillExists) {
      setSelectedDisclosureId(String(disclosures[0].id));
    }
  }, [disclosures, selectedDisclosureId, selectedStandardId]);

  useEffect(() => {
    if (!selectedDisclosureId) return;
    if (items.length === 0) {
      setSelectedItemId("");
      return;
    }
    const stillExists = items.some((item) => String(item.id) === selectedItemId);
    if (!selectedItemId || !stillExists) {
      setSelectedItemId(String(items[0].id));
    }
  }, [items, selectedDisclosureId, selectedItemId]);

  useEffect(() => {
    if (!selectedItemId) {
      setSelectedElementId("");
      return;
    }

    if (selectedItemMappings.length === 0) return;

    const stillMapped = selectedItemMappings.some(
      (mapping) => String(mapping.shared_element_id) === selectedElementId
    );
    if (!selectedElementId || !stillMapped) {
      setSelectedElementId(String(selectedItemMappings[0].shared_element_id));
    }
  }, [selectedElementId, selectedItemId, selectedItemMappings]);

  useEffect(() => {
    if (history.length === 0) {
      setCompareV1("");
      setCompareV2("");
      return;
    }

    setCompareV1(String(history[0].version));
    setCompareV2(String(history[1]?.version ?? history[0].version));
  }, [history]);

  const selectedStandard = standards.find((standard) => String(standard.id) === selectedStandardId) ?? null;
  const selectedDisclosure = disclosures.find((disclosure) => String(disclosure.id) === selectedDisclosureId) ?? null;
  const selectedItem = items.find((item) => String(item.id) === selectedItemId) ?? null;
  const sharedElementOptions = useMemo(() => {
    const mappedIds = new Set(
      selectedItemMappings.map((mapping) => mapping.shared_element_id)
    );
    return [...sharedElements]
      .sort((a, b) => {
        const mappedDelta = Number(mappedIds.has(b.id)) - Number(mappedIds.has(a.id));
        if (mappedDelta !== 0) return mappedDelta;
        return a.code.localeCompare(b.code);
      })
      .map((element) => ({
        value: String(element.id),
        label: `${element.code} · ${element.name}${mappedIds.has(element.id) ? " (mapped)" : ""}`,
      }));
  }, [selectedItemMappings, sharedElements]);

  if (meLoading || (canAccess && (standardsLoading || sharedElementsLoading || mappingsLoading))) {
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
          <h2 className="text-2xl font-bold text-slate-900">Mapping History</h2>
          <p className="mt-1 text-sm text-slate-500">
            Inspect mapping versions, compare changes, and trace evolution of standard-to-element links.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only framework admins and platform admins can inspect mapping history.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (orgContextMissing) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Mapping History</h2>
          <p className="mt-1 text-sm text-slate-500">
            Inspect mapping versions, compare changes, and trace evolution of standard-to-element links.
          </p>
        </div>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 text-sm text-amber-800">
            Select an organization context first. If you are a platform admin, enter support mode
            for a tenant and then reopen this page.
          </CardContent>
        </Card>
      </div>
    );
  }

  if (pageError) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Mapping History</h2>
          <p className="mt-1 text-sm text-slate-500">
            Inspect mapping versions, compare changes, and trace evolution of standard-to-element links.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6 text-sm text-red-700">{pageError.message}</CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Mapping History</h2>
        <p className="mt-1 text-sm text-slate-500">
          Inspect mapping versions, compare changes, and trace evolution of standard-to-element links.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_1.35fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitMerge className="h-4 w-4 text-slate-500" />
              Select Mapping Pair
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              label="Standard"
              value={selectedStandardId}
              onChange={setSelectedStandardId}
              options={standards.map((standard) => ({
                value: String(standard.id),
                label: `${standard.code} · ${standard.name}`,
              }))}
            />
            <Select
              label="Disclosure"
              value={selectedDisclosureId}
              onChange={setSelectedDisclosureId}
              options={disclosures.map((disclosure) => ({
                value: String(disclosure.id),
                label: `${disclosure.code} · ${disclosure.title}`,
              }))}
            />
            <Select
              label="Requirement Item"
              value={selectedItemId}
              onChange={setSelectedItemId}
              options={items.map((item) => ({
                value: String(item.id),
                label: `${item.item_code ?? `Item ${item.id}`} · ${item.name}`,
              }))}
            />
            <Select
              label="Shared Element"
              value={selectedElementId}
              onChange={setSelectedElementId}
              options={sharedElementOptions}
            />
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <p className="font-medium text-slate-900">
                {selectedItem?.name ?? "Choose a requirement item"}
              </p>
              <p className="mt-1">
                {selectedStandard
                  ? `${selectedStandard.code} / ${selectedDisclosure?.code ?? "Disclosure"}`
                  : "Use the selectors to narrow down the mapping pair."}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <History className="h-4 w-4 text-slate-500" />
              Current Mappings For Selected Item
            </CardTitle>
          </CardHeader>
          <CardContent>
            {disclosuresLoading || itemsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              </div>
            ) : !selectedItem ? (
              <p className="text-sm text-slate-500">Pick a standard, disclosure, and item to inspect mappings.</p>
            ) : selectedItemMappings.length === 0 ? (
              <p className="text-sm text-slate-500">No current mappings found for the selected requirement item.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Shared Element</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Valid From</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selectedItemMappings.map((mapping) => {
                    const element = sharedElements.find(
                      (entry) => entry.id === mapping.shared_element_id
                    );
                    return (
                      <TableRow key={mapping.id}>
                        <TableCell>
                          <div className="space-y-1">
                            <p className="font-mono text-xs text-slate-500">
                              {element?.code ?? `EL-${mapping.shared_element_id}`}
                            </p>
                            <p>{element?.name ?? `Shared element #${mapping.shared_element_id}`}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{mapping.mapping_type}</Badge>
                        </TableCell>
                        <TableCell>v{mapping.version}</TableCell>
                        <TableCell>{formatDate(mapping.valid_from)}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSelectedElementId(String(mapping.shared_element_id))}
                          >
                            Inspect History
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Version History</CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedItemId || !selectedElementId ? (
              <p className="text-sm text-slate-500">Choose both a requirement item and a shared element.</p>
            ) : historyLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              </div>
            ) : historyError && !isNotFoundError(historyError) ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {historyError.message}
              </div>
            ) : history.length === 0 ? (
              <p className="text-sm text-slate-500">
                No mapping history found for the selected pair.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Version</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Valid From</TableHead>
                    <TableHead>Valid To</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((version) => (
                    <TableRow key={version.id}>
                      <TableCell className="font-medium">v{version.version}</TableCell>
                      <TableCell>
                        <Badge variant={version.is_current ? "success" : "secondary"}>
                          {version.is_current ? "Current" : "Archived"}
                        </Badge>
                      </TableCell>
                      <TableCell>{version.mapping_type}</TableCell>
                      <TableCell>{formatDate(version.valid_from)}</TableCell>
                      <TableCell>{formatDate(version.valid_to)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Version Diff</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {history.length < 2 ? (
              <p className="text-sm text-slate-500">
                Diff becomes available once the mapping pair has at least two versions.
              </p>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <Select
                    label="Compare From"
                    value={compareV1}
                    onChange={setCompareV1}
                    options={history.map((version) => ({
                      value: String(version.version),
                      label: `Version ${version.version}`,
                    }))}
                  />
                  <Select
                    label="Compare To"
                    value={compareV2}
                    onChange={setCompareV2}
                    options={history.map((version) => ({
                      value: String(version.version),
                      label: `Version ${version.version}`,
                    }))}
                  />
                </div>

                {compareV1 === compareV2 ? (
                  <p className="text-sm text-slate-500">
                    Pick two different versions to see a diff.
                  </p>
                ) : diffLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
                  </div>
                ) : diffError ? (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {diffError.message}
                  </div>
                ) : (diffData?.changes.length ?? 0) === 0 ? (
                  <p className="text-sm text-slate-500">
                    No field-level changes detected between these versions.
                  </p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Field</TableHead>
                        <TableHead>Old Value</TableHead>
                        <TableHead>New Value</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {diffData?.changes.map((change) => (
                        <TableRow key={change.field}>
                          <TableCell className="font-medium">{change.field}</TableCell>
                          <TableCell>{change.old_value ?? "-"}</TableCell>
                          <TableCell>{change.new_value ?? "-"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
