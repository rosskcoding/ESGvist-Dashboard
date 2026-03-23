"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  Plus,
  MoreHorizontal,
  Search,
  Building2,
  Eye,
  Pause,
  Play,
  Archive,
} from "lucide-react";

interface Tenant {
  id: number;
  name: string;
  country: string;
  users_count: number;
  status: "active" | "suspended" | "archived";
  created_at: string;
}

interface TenantsResponse {
  items: Tenant[];
  total: number;
}

const statusOptions = [
  { value: "", label: "All Statuses" },
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
  { value: "archived", label: "Archived" },
];

export default function TenantsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const queryParams = new URLSearchParams();
  if (search) queryParams.set("search", search);
  if (statusFilter) queryParams.set("status", statusFilter);

  const { data, isLoading, refetch } = useApiQuery<TenantsResponse>(
    ["tenants", search, statusFilter],
    `/platform/tenants?${queryParams.toString()}`
  );

  const suspendMutation = useApiMutation(
    "",
    "POST"
  );

  const reactivateMutation = useApiMutation(
    "",
    "POST"
  );

  const archiveMutation = useApiMutation(
    "",
    "POST"
  );

  const handleSuspend = async (id: number) => {
    await suspendMutation.mutateAsync({ path: `/platform/tenants/${id}/suspend` } as never);
    refetch();
  };

  const handleReactivate = async (id: number) => {
    await reactivateMutation.mutateAsync({ path: `/platform/tenants/${id}/reactivate` } as never);
    refetch();
  };

  const handleArchive = async (id: number) => {
    await archiveMutation.mutateAsync({ path: `/platform/tenants/${id}/archive` } as never);
    refetch();
  };

  const tenants = data?.items ?? [];

  const getStatusBadge = (status: Tenant["status"]) => {
    switch (status) {
      case "active":
        return (
          <Badge className="bg-green-100 text-green-700">Active</Badge>
        );
      case "suspended":
        return (
          <Badge className="bg-amber-100 text-amber-700">Suspended</Badge>
        );
      case "archived":
        return (
          <Badge className="bg-slate-100 text-slate-600">Archived</Badge>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Tenants</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage organizations on the platform
          </p>
        </div>
        <Button onClick={() => router.push("/platform/tenants/new")}>
          <Plus className="mr-2 h-4 w-4" />
          Create Organization
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            className="pl-9"
            placeholder="Search organizations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="w-48">
          <Select
            options={statusOptions}
            value={statusFilter}
            onChange={setStatusFilter}
            placeholder="Status"
          />
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            </div>
          ) : tenants.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Building2 className="mb-3 h-10 w-10 text-slate-300" />
              <p className="text-sm text-slate-500">No tenants found</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Organization Name</TableHead>
                  <TableHead>Country</TableHead>
                  <TableHead>Users</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-12" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {tenants.map((tenant) => (
                  <TableRow key={tenant.id} className="hover:bg-slate-50">
                    <TableCell className="font-medium">
                      {tenant.name}
                    </TableCell>
                    <TableCell className="text-sm text-slate-600">
                      {tenant.country}
                    </TableCell>
                    <TableCell className="text-sm">
                      {tenant.users_count}
                    </TableCell>
                    <TableCell>{getStatusBadge(tenant.status)}</TableCell>
                    <TableCell className="text-sm text-slate-600">
                      {new Date(tenant.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() =>
                              router.push(`/platform/tenants/${tenant.id}`)
                            }
                          >
                            <Eye className="mr-2 h-4 w-4" />
                            View Details
                          </DropdownMenuItem>
                          {tenant.status === "active" && (
                            <DropdownMenuItem
                              onClick={() => handleSuspend(tenant.id)}
                            >
                              <Pause className="mr-2 h-4 w-4" />
                              Suspend
                            </DropdownMenuItem>
                          )}
                          {tenant.status === "suspended" && (
                            <DropdownMenuItem
                              onClick={() => handleReactivate(tenant.id)}
                            >
                              <Play className="mr-2 h-4 w-4" />
                              Reactivate
                            </DropdownMenuItem>
                          )}
                          {tenant.status !== "archived" && (
                            <DropdownMenuItem
                              onClick={() => handleArchive(tenant.id)}
                              className="text-red-600"
                            >
                              <Archive className="mr-2 h-4 w-4" />
                              Archive
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
