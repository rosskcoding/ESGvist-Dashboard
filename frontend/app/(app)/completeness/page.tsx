"use client";

import { Fragment, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Globe,
  BarChart3,
  Info,
} from "lucide-react";

interface StandardCompletion {
  standard_id: number;
  standard_name: string;
  code: string;
  total_disclosures: number;
  completed_disclosures: number;
  completion_percentage: number;
}

interface DisclosureDetail {
  id: number;
  code: string;
  title: string;
  status: "complete" | "partial" | "missing" | "not_applicable";
  covered_entities: string[];
  missing_entities: string[];
  explanation: string;
}

interface CompletenessData {
  overall_completion: number;
  boundary_name: string;
  entity_count: number;
  standards: StandardCompletion[];
  disclosures: DisclosureDetail[];
}

const disclosureStatusConfig: Record<
  DisclosureDetail["status"],
  {
    label: string;
    variant: "success" | "warning" | "destructive" | "secondary";
    icon: typeof CheckCircle2;
  }
> = {
  complete: { label: "Complete", variant: "success", icon: CheckCircle2 },
  partial: { label: "Partial", variant: "warning", icon: Clock },
  missing: { label: "Missing", variant: "destructive", icon: XCircle },
  not_applicable: { label: "N/A", variant: "secondary", icon: Info },
};

export default function CompletenessPage() {
  const [projectId] = useState(1);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const { data, isLoading, error } = useApiQuery<CompletenessData>(
    ["completeness", projectId],
    `/dashboard/projects/${projectId}/completeness`
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Completeness</h2>
          <p className="mt-1 text-sm text-slate-500">
            Data completeness analysis
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load completeness data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const completeness = data ?? {
    overall_completion: 0,
    boundary_name: "No boundary",
    entity_count: 0,
    standards: [],
    disclosures: [],
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Completeness</h2>
        <p className="mt-1 text-sm text-slate-500">
          Data completeness analysis for your ESG reporting
        </p>
      </div>

      {/* Summary header */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Overall Completeness
            </CardDescription>
            <BarChart3 className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {Math.round(completeness.overall_completion)}%
            </div>
            <Progress
              value={completeness.overall_completion}
              className="mt-3"
              indicatorClassName={cn(
                completeness.overall_completion >= 80
                  ? "bg-green-500"
                  : completeness.overall_completion >= 50
                    ? "bg-amber-500"
                    : "bg-blue-600"
              )}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Boundary
            </CardDescription>
            <Globe className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">
              {completeness.boundary_name}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Selected organizational boundary
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">
              Entities in Scope
            </CardDescription>
            <CheckCircle2 className="h-4 w-4 text-slate-500" />
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {completeness.entity_count}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              reporting entities
            </p>
          </CardContent>
        </Card>
      </div>

      {/* By Standard breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Completion by Standard</CardTitle>
          <CardDescription>
            Breakdown of completeness across reporting frameworks
          </CardDescription>
        </CardHeader>
        <CardContent>
          {completeness.standards.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">
              No standards data available.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {completeness.standards.map((std) => (
                <div
                  key={std.standard_id}
                  className="rounded-lg border border-slate-200 p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-semibold">{std.code}</span>
                      <p className="text-xs text-slate-500">
                        {std.standard_name}
                      </p>
                    </div>
                    <span className="text-lg font-bold">
                      {Math.round(std.completion_percentage)}%
                    </span>
                  </div>
                  <Progress
                    value={std.completion_percentage}
                    indicatorClassName={cn(
                      std.completion_percentage >= 80
                        ? "bg-green-500"
                        : std.completion_percentage >= 50
                          ? "bg-amber-500"
                          : "bg-blue-600"
                    )}
                  />
                  <p className="text-xs text-slate-400">
                    {std.completed_disclosures} / {std.total_disclosures}{" "}
                    disclosures
                  </p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Disclosure-level detail table */}
      <Card>
        <CardHeader>
          <CardTitle>Disclosure Details</CardTitle>
          <CardDescription>
            Status of individual disclosures across all standards. Click a row to
            see entity coverage details.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {completeness.disclosures.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-400">
              No disclosure data available.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Covered</TableHead>
                  <TableHead>Missing</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {completeness.disclosures.map((disclosure) => {
                  const statusCfg = disclosureStatusConfig[disclosure.status];
                  const StatusIcon = statusCfg.icon;
                  const isExpanded = expandedRow === disclosure.id;

                  return (
                    <Fragment key={disclosure.id}>
                      <TableRow
                        className="cursor-pointer"
                        onClick={() =>
                          setExpandedRow(isExpanded ? null : disclosure.id)
                        }
                      >
                        <TableCell className="font-mono text-sm font-medium">
                          {disclosure.code}
                        </TableCell>
                        <TableCell>{disclosure.title}</TableCell>
                        <TableCell>
                          <Badge variant={statusCfg.variant}>
                            <StatusIcon className="mr-1 h-3 w-3" />
                            {statusCfg.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-green-600">
                            {disclosure.covered_entities.length}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              "text-sm",
                              disclosure.missing_entities.length > 0
                                ? "font-medium text-red-600"
                                : "text-slate-400"
                            )}
                          >
                            {disclosure.missing_entities.length}
                          </span>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow>
                          <TableCell colSpan={5} className="bg-slate-50 p-4">
                            <div className="space-y-3">
                              {/* Explanation */}
                              {disclosure.explanation && (
                                <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3">
                                  <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-500" />
                                  <p className="text-sm text-blue-800">
                                    {disclosure.explanation}
                                  </p>
                                </div>
                              )}

                              <div className="grid gap-4 sm:grid-cols-2">
                                {/* Covered entities */}
                                <div>
                                  <p className="mb-1 text-xs font-medium text-green-700">
                                    Covered Entities (
                                    {disclosure.covered_entities.length})
                                  </p>
                                  {disclosure.covered_entities.length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                      {disclosure.covered_entities.map(
                                        (entity) => (
                                          <Badge
                                            key={entity}
                                            variant="outline"
                                            className="border-green-200 bg-green-50 text-green-700"
                                          >
                                            {entity}
                                          </Badge>
                                        )
                                      )}
                                    </div>
                                  ) : (
                                    <p className="text-xs text-slate-400">
                                      None
                                    </p>
                                  )}
                                </div>

                                {/* Missing entities */}
                                <div>
                                  <p className="mb-1 text-xs font-medium text-red-700">
                                    Missing Entities (
                                    {disclosure.missing_entities.length})
                                  </p>
                                  {disclosure.missing_entities.length > 0 ? (
                                    <div className="flex flex-wrap gap-1">
                                      {disclosure.missing_entities.map(
                                        (entity) => (
                                          <Badge
                                            key={entity}
                                            variant="outline"
                                            className="border-red-200 bg-red-50 text-red-700"
                                          >
                                            {entity}
                                          </Badge>
                                        )
                                      )}
                                    </div>
                                  ) : (
                                    <p className="text-xs text-slate-400">
                                      None
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
