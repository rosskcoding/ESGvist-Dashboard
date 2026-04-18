"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { getMe, type UserResponse } from "@/lib/auth";

type Role = "platform_admin" | "admin" | "esg_manager" | "reviewer" | "collector" | "auditor";

interface ProjectListResponse {
  items: Array<{ id: number; name: string; status: string; reporting_year: number | null }>;
}

interface AssignmentMatrixResponse {
  assignments: Array<{
    id: number;
    shared_element_id: number;
    shared_element_code: string;
    shared_element_name: string;
    entity_name?: string | null;
    facility_name?: string | null;
    collector_name?: string | null;
    reviewer_name?: string | null;
    status: string;
    deadline?: string | null;
    sla_status: string;
  }>;
  users: Array<{ id: number; name: string; email: string }>;
  entities: Array<{ id: number; name: string; code?: string | null }>;
}

interface DataPointListResponse {
  items: Array<{
    id: number;
    shared_element_id: number;
    entity_id?: number | null;
    facility_id?: number | null;
    status: string;
    numeric_value?: number | null;
    text_value?: string | null;
    unit_code?: string | null;
    created_by?: number | null;
  }>;
}

interface CompletenessResponse {
  overall_percent: number;
  overall_status: string;
  disclosures: Array<{
    disclosure_requirement_id: number;
    code?: string | null;
    title?: string | null;
    status: string;
    completion_percent: number;
  }>;
  boundary_context?: {
    boundary_name?: string | null;
    entities_in_scope: number;
    excluded_entities: number;
    snapshot_locked: boolean;
    entities_without_data: string[];
  } | null;
}

interface UsersResponse {
  users: Array<{
    id: number;
    email: string;
    full_name: string;
    role: Role;
    status: string;
  }>;
  pending_invitations: Array<{
    id: number;
    email: string;
    role: string;
    invited_at?: string | null;
  }>;
}

interface StandardListResponse {
  items: Array<{ id: number; code: string; name: string; version?: string | null; is_active: boolean }>;
}

interface DisclosureListResponse {
  items: Array<{ id: number; code: string; title: string; mandatory_level: string }>;
}

interface AuditListResponse {
  items: Array<{
    id: number;
    action: string;
    entity_type: string;
    created_at?: string | null;
  }>;
}

interface EntityTreeNode {
  id: number;
  name: string;
  code?: string | null;
  entity_type: string;
  country?: string | null;
  children: EntityTreeNode[];
}

function flattenTree(nodes: EntityTreeNode[], depth = 0): Array<EntityTreeNode & { depth: number }> {
  const rows: Array<EntityTreeNode & { depth: number }> = [];
  for (const node of nodes) {
    rows.push({ ...node, depth });
    rows.push(...flattenTree(node.children ?? [], depth + 1));
  }
  return rows;
}

interface LoadError {
  path: string;
  message: string;
}

async function safeGet<T>(path: string, errors?: LoadError[]): Promise<T | null> {
  try {
    return await api.get<T>(path);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    console.error(`[demo] GET ${path} failed:`, err);
    errors?.push({ path, message });
    return null;
  }
}

export default function DemoPage() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [project, setProject] = useState<ProjectListResponse["items"][number] | null>(null);
  const [assignments, setAssignments] = useState<AssignmentMatrixResponse | null>(null);
  const [dataPoints, setDataPoints] = useState<DataPointListResponse | null>(null);
  const [completeness, setCompleteness] = useState<CompletenessResponse | null>(null);
  const [usersResponse, setUsersResponse] = useState<UsersResponse | null>(null);
  const [standards, setStandards] = useState<Array<{
    id: number;
    code: string;
    name: string;
    version?: string | null;
    is_active: boolean;
    disclosures: DisclosureListResponse["items"];
  }>>([]);
  const [entityTree, setEntityTree] = useState<EntityTreeNode[]>([]);
  const [auditLog, setAuditLog] = useState<AuditListResponse | null>(null);
  const [loadErrors, setLoadErrors] = useState<LoadError[]>([]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const errors: LoadError[] = [];
      const me = await getMe();
      setUser(me);

      const projects = await safeGet<ProjectListResponse>("/projects", errors);
      const currentProject = projects?.items?.[0] ?? null;
      setProject(currentProject);

      const [
        tree,
        standardsResponse,
        usersData,
        auditData,
        assignmentData,
        pointData,
        completenessData,
      ] = await Promise.all([
        safeGet<EntityTreeNode[]>("/entities/tree", errors),
        safeGet<StandardListResponse>("/standards", errors),
        safeGet<UsersResponse>("/auth/organization/users", errors),
        safeGet<AuditListResponse>("/audit-log?page=1&page_size=10", errors),
        currentProject ? safeGet<AssignmentMatrixResponse>(`/projects/${currentProject.id}/assignments`, errors) : Promise.resolve(null),
        currentProject ? safeGet<DataPointListResponse>(`/projects/${currentProject.id}/data-points`, errors) : Promise.resolve(null),
        currentProject
          ? safeGet<CompletenessResponse>(`/projects/${currentProject.id}/completeness?boundaryContext=true`, errors)
          : Promise.resolve(null),
      ]);

      setEntityTree(tree ?? []);
      setUsersResponse(usersData);
      setAuditLog(auditData);
      setAssignments(assignmentData);
      setDataPoints(pointData);
      setCompleteness(completenessData);

      const standardsWithDisclosures = standardsResponse
        ? await Promise.all(
            standardsResponse.items.map(async (standard) => ({
              ...standard,
              disclosures:
                (await safeGet<DisclosureListResponse>(`/standards/${standard.id}/disclosures`, errors))?.items ?? [],
            }))
          )
        : [];
      setStandards(standardsWithDisclosures);
      setLoadErrors(errors);
      setLoading(false);
    }

    load().catch((err) => {
      console.error("[demo] load failed:", err);
      const message = err instanceof Error ? err.message : String(err);
      setLoadErrors((prev) => [...prev, { path: "getMe", message }]);
      setLoading(false);
    });
  }, []);

  const currentRole = user?.roles?.find((role) => role.scope_type === "organization")?.role
    ?? user?.roles?.[0]?.role
    ?? "collector";
  const treeRows = useMemo(() => flattenTree(entityTree), [entityTree]);
  const assignmentsByElement = useMemo(() => {
    const map = new Map<number, AssignmentMatrixResponse["assignments"][number]>();
    for (const row of assignments?.assignments ?? []) {
      map.set(row.shared_element_id, row);
    }
    return map;
  }, [assignments]);

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading demo verification hub...</div>;
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Demo Verification Hub</h1>
        <p className="mt-1 text-sm text-slate-500">
          Read-only view over the seeded demo tenant and scenario outputs.
        </p>
      </div>

      {loadErrors.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <div className="font-medium">Some data failed to load ({loadErrors.length})</div>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs">
            {loadErrors.map((e, i) => (
              <li key={`${e.path}-${i}`}>
                <span className="font-mono">{e.path}</span> — {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Signed in as</CardDescription>
            <CardTitle className="text-base">{user?.full_name}</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline">{currentRole}</Badge>
            <p className="mt-2 text-xs text-slate-500">{user?.email}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Project</CardDescription>
            <CardTitle className="text-base">{project?.name ?? "No project"}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            <div>Status: {project?.status ?? "n/a"}</div>
            <div>Reporting year: {project?.reporting_year ?? "n/a"}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completeness</CardDescription>
            <CardTitle className="text-base">
              {completeness ? `${Math.round(completeness.overall_percent)}%` : "n/a"}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            <div>Status: {completeness?.overall_status ?? "n/a"}</div>
            <div>Assignments: {assignments?.assignments?.length ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Boundary</CardDescription>
            <CardTitle className="text-base">{completeness?.boundary_context?.boundary_name ?? "n/a"}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            <div>In scope entities: {completeness?.boundary_context?.entities_in_scope ?? 0}</div>
            <div>Locked snapshot: {completeness?.boundary_context?.snapshot_locked ? "yes" : "no"}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Organization Structure</CardTitle>
            <CardDescription>Seeded parent, subsidiaries, branch, facility and excluded JV</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2">Entity</th>
                  <th className="pb-2">Type</th>
                  <th className="pb-2">Country</th>
                </tr>
              </thead>
              <tbody>
                {treeRows.map((row) => (
                  <tr key={row.id} className="border-b border-slate-100">
                    <td className="py-2">
                      <span style={{ paddingLeft: `${row.depth * 16}px` }} className="inline-block">
                        {row.name}
                      </span>
                    </td>
                    <td className="py-2">{row.entity_type}</td>
                    <td className="py-2">{row.country ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Standards & Disclosures</CardTitle>
            <CardDescription>GRI, IFRS S1, IFRS S2, ESRS and custom additions</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {standards.map((standard) => (
              <div key={standard.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{standard.code}</div>
                    <div className="text-sm text-slate-500">{standard.name}</div>
                  </div>
                  <Badge variant={standard.is_active ? "default" : "outline"}>
                    {standard.is_active ? "active" : "inactive"}
                  </Badge>
                </div>
                <ul className="mt-3 space-y-1 text-sm text-slate-600">
                  {standard.disclosures.slice(0, 6).map((disclosure) => (
                    <li key={disclosure.id}>
                      <span className="font-mono text-xs">{disclosure.code}</span>{" "}
                      <span>{disclosure.title}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Assignments</CardTitle>
            <CardDescription>Role-scoped assignment view for the current user</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2">Element</th>
                  <th className="pb-2">Scope</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">SLA</th>
                </tr>
              </thead>
              <tbody>
                {(assignments?.assignments ?? []).map((assignment) => (
                  <tr key={assignment.id} className="border-b border-slate-100">
                    <td className="py-2">
                      <div className="font-medium">{assignment.shared_element_name}</div>
                      <div className="font-mono text-xs text-slate-500">{assignment.shared_element_code}</div>
                    </td>
                    <td className="py-2">{assignment.facility_name ?? assignment.entity_name ?? "Group"}</td>
                    <td className="py-2">{assignment.status}</td>
                    <td className="py-2">{assignment.sla_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Data Points</CardTitle>
            <CardDescription>Created submissions and their workflow statuses</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2">Data Point</th>
                  <th className="pb-2">Value</th>
                  <th className="pb-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(dataPoints?.items ?? []).map((point) => {
                  const assignment = assignmentsByElement.get(point.shared_element_id);
                  const value = point.numeric_value ?? point.text_value ?? "n/a";
                  return (
                    <tr key={point.id} className="border-b border-slate-100">
                      <td className="py-2">
                        <div className="font-medium">{assignment?.shared_element_name ?? `Element #${point.shared_element_id}`}</div>
                        <div className="text-xs text-slate-500">Data point #{point.id}</div>
                      </td>
                      <td className="py-2">{String(value)} {point.unit_code ?? ""}</td>
                      <td className="py-2">{point.status}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>

      {usersResponse && (
        <Card>
          <CardHeader>
            <CardTitle>Users & Invitations</CardTitle>
            <CardDescription>Visible for admin / ESG manager roles</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 xl:grid-cols-2">
            <div>
              <h2 className="mb-3 text-sm font-semibold text-slate-700">Users</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-slate-500">
                    <th className="pb-2">Name</th>
                    <th className="pb-2">Role</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {usersResponse.users.map((member) => (
                    <tr key={member.id} className="border-b border-slate-100">
                      <td className="py-2">
                        <div>{member.full_name}</div>
                        <div className="text-xs text-slate-500">{member.email}</div>
                      </td>
                      <td className="py-2">{member.role}</td>
                      <td className="py-2">{member.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h2 className="mb-3 text-sm font-semibold text-slate-700">Pending Invitations</h2>
              <ul className="space-y-2 text-sm text-slate-600">
                {usersResponse.pending_invitations.length === 0 && <li>No pending invitations.</li>}
                {usersResponse.pending_invitations.map((invitation) => (
                  <li key={invitation.id} className="rounded border border-slate-200 p-3">
                    <div className="font-medium">{invitation.email}</div>
                    <div className="text-xs text-slate-500">Role: {invitation.role}</div>
                  </li>
                ))}
              </ul>
            </div>
          </CardContent>
        </Card>
      )}

      {auditLog && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Audit Entries</CardTitle>
            <CardDescription>Visible for auditor / manager / admin roles</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="pb-2">Action</th>
                  <th className="pb-2">Entity Type</th>
                  <th className="pb-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {auditLog.items.map((entry) => (
                  <tr key={entry.id} className="border-b border-slate-100">
                    <td className="py-2">{entry.action}</td>
                    <td className="py-2">{entry.entity_type}</td>
                    <td className="py-2">{entry.created_at ? new Date(entry.created_at).toLocaleString() : "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
