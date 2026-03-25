"use client";

import Link from "next/link";
import { BookOpen, GitMerge, Layers, Loader2, Share2, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApiQuery } from "@/lib/hooks/use-api";

type RoleBinding = { role: string };

type StandardListResponse = {
  items: Array<{ id: number; code: string; name: string; is_active: boolean }>;
  total: number;
};

type SharedElementListResponse = {
  items: Array<{ id: number; code: string; name: string }>;
  total: number;
};

type MappingListResponse = {
  items: Array<{ id: number; mapping_type: string; version: number; is_current: boolean }>;
  total: number;
};

export default function FrameworkCatalogPage() {
  const { data: me, isLoading: meLoading } = useApiQuery<{ roles: RoleBinding[] }>(
    ["auth-me"],
    "/auth/me"
  );

  const roles = me?.roles?.map((binding) => binding.role) ?? [];
  const canAccess = roles.some((role) => role === "framework_admin" || role === "platform_admin");
  const accessDenied = Boolean(me) && !canAccess;

  const { data: standardsData, isLoading: standardsLoading } = useApiQuery<StandardListResponse>(
    ["framework-standards-summary"],
    "/standards?page_size=100",
    { enabled: canAccess }
  );
  const { data: sharedElementsData, isLoading: sharedElementsLoading } =
    useApiQuery<SharedElementListResponse>(
      ["framework-shared-elements-summary"],
      "/shared-elements?page_size=100",
      { enabled: canAccess }
    );
  const { data: mappingsData, isLoading: mappingsLoading } = useApiQuery<MappingListResponse>(
    ["framework-mappings-summary"],
    "/mappings?page_size=500",
    { enabled: canAccess }
  );

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
          <h2 className="text-2xl font-bold text-slate-900">Framework Catalog</h2>
          <p className="mt-1 text-sm text-slate-500">
            Maintain the master ESG framework catalog used across tenants and projects.
          </p>
        </div>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-start gap-3 p-6 text-red-700">
            <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Access denied</p>
              <p className="mt-1 text-sm">
                Only framework admin and platform admin roles can open the framework catalog.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const standards = standardsData?.items ?? [];
  const sharedElements = sharedElementsData?.items ?? [];
  const mappings = mappingsData?.items ?? [];
  const currentMappings = mappings.filter((item) => item.is_current).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Framework Catalog</h2>
          <p className="mt-1 text-sm text-slate-500">
            Central workspace for maintaining standards, reusable data elements, and mapping logic.
          </p>
        </div>
        <Badge variant="outline" className="w-fit">
          {roles.includes("platform_admin") ? "Platform admin access" : "Framework admin access"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Standards</CardDescription>
            <CardTitle className="text-3xl">{standards.length}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-500">
            Canonical frameworks, sections, disclosures, and requirement item entry points.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Shared Elements</CardDescription>
            <CardTitle className="text-3xl">{sharedElements.length}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-500">
            Reusable ESG data elements that normalize collection across frameworks.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Current Mappings</CardDescription>
            <CardTitle className="text-3xl">{currentMappings}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-500">
            Active links between requirement items and shared elements.
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-slate-500" />
              Standards Catalog
            </CardTitle>
            <CardDescription>
              Create or revise standards, sections, disclosures, and requirement items.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 text-sm text-slate-500">
              {standards.slice(0, 4).map((standard) => (
                <div key={standard.id} className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xs text-slate-600">{standard.code}</span>
                  <span className="truncate text-right">{standard.name}</span>
                </div>
              ))}
              {standards.length === 0 && <p>No standards configured yet.</p>}
            </div>
            <Button asChild className="w-full">
              <Link href="/platform/framework/standards">Open standards</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Share2 className="h-5 w-5 text-slate-500" />
              Shared Elements
            </CardTitle>
            <CardDescription>
              Maintain normalized data points, dimensions, and cross-framework reuse targets.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 text-sm text-slate-500">
              {sharedElements.slice(0, 4).map((element) => (
                <div key={element.id} className="flex items-center justify-between gap-3">
                  <span className="font-mono text-xs text-slate-600">{element.code}</span>
                  <span className="truncate text-right">{element.name}</span>
                </div>
              ))}
              {sharedElements.length === 0 && <p>No shared elements configured yet.</p>}
            </div>
            <Button asChild className="w-full" variant="outline">
              <Link href="/platform/framework/shared-elements">Open shared elements</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitMerge className="h-5 w-5 text-slate-500" />
              Mapping Logic
            </CardTitle>
            <CardDescription>
              Inspect active versions and compare mapping history across disclosure items.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 text-sm text-slate-500">
              <div className="flex items-center justify-between gap-3">
                <span>Current mappings</span>
                <span className="font-medium text-slate-900">{currentMappings}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Total mapping versions</span>
                <span className="font-medium text-slate-900">{mappings.length}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span>Workflow</span>
                <span className="flex items-center gap-1 text-slate-600">
                  <Layers className="h-4 w-4" />
                  standards {"->"} shared elements {"->"} mappings
                </span>
              </div>
            </div>
            <Button asChild className="w-full" variant="outline">
              <Link href="/platform/framework/mappings">Open mapping history</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
