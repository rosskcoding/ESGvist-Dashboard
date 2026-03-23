"use client";

import { use } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import {
  Loader2,
  ArrowLeft,
  Building2,
  Users,
  Activity,
  Calendar,
  Globe,
  CreditCard,
} from "lucide-react";
import { useRouter } from "next/navigation";

interface TenantUser {
  id: number;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  last_login: string | null;
}

interface TenantAuditEntry {
  id: number;
  action: string;
  user_name: string;
  created_at: string;
  description: string;
}

interface TenantDetails {
  id: number;
  name: string;
  country: string;
  industry: string;
  status: "active" | "suspended" | "archived";
  created_at: string;
  subscription_plan: string;
  subscription_expires: string | null;
  users: TenantUser[];
  recent_activity: TenantAuditEntry[];
}

export default function TenantDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const { data, isLoading } = useApiQuery<TenantDetails>(
    ["tenant", id],
    `/platform/tenants/${id}`
  );

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const tenant = data;
  if (!tenant) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center">
        <Building2 className="mb-3 h-10 w-10 text-slate-300" />
        <p className="text-sm text-slate-500">Tenant not found</p>
      </div>
    );
  }

  const getStatusBadge = (status: TenantDetails["status"]) => {
    switch (status) {
      case "active":
        return <Badge className="bg-green-100 text-green-700">Active</Badge>;
      case "suspended":
        return <Badge className="bg-amber-100 text-amber-700">Suspended</Badge>;
      case "archived":
        return <Badge className="bg-slate-100 text-slate-600">Archived</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push("/platform/tenants")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-slate-900">{tenant.name}</h2>
            {getStatusBadge(tenant.status)}
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Tenant ID: {tenant.id}
          </p>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  Organization Details
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Name</span>
                  <span className="text-sm font-medium">{tenant.name}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">
                    <Globe className="mr-1 inline h-3 w-3" />
                    Country
                  </span>
                  <span className="text-sm font-medium">{tenant.country}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Industry</span>
                  <span className="text-sm font-medium">{tenant.industry}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Status</span>
                  {getStatusBadge(tenant.status)}
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">
                    <Calendar className="mr-1 inline h-3 w-3" />
                    Created
                  </span>
                  <span className="text-sm font-medium">
                    {new Date(tenant.created_at).toLocaleDateString()}
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CreditCard className="h-4 w-4" />
                  Subscription
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Plan</span>
                  <Badge variant="secondary">{tenant.subscription_plan}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Expires</span>
                  <span className="text-sm font-medium">
                    {tenant.subscription_expires
                      ? new Date(tenant.subscription_expires).toLocaleDateString()
                      : "N/A"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">Total Users</span>
                  <span className="text-sm font-medium">
                    {tenant.users.length}
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                Users ({tenant.users.length})
              </CardTitle>
              <CardDescription>
                Users belonging to this organization
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {tenant.users.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Users className="mb-3 h-10 w-10 text-slate-300" />
                  <p className="text-sm text-slate-500">No users found</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last Login</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tenant.users.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell className="font-medium">
                          {user.full_name}
                        </TableCell>
                        <TableCell className="text-sm text-slate-600">
                          {user.email}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{user.role}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            className={
                              user.is_active
                                ? "bg-green-100 text-green-700"
                                : "bg-slate-100 text-slate-600"
                            }
                          >
                            {user.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-slate-600">
                          {user.last_login
                            ? new Date(user.last_login).toLocaleString()
                            : "Never"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Activity Tab */}
        <TabsContent value="activity">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Recent Activity
              </CardTitle>
              <CardDescription>
                Recent audit log entries for this tenant
              </CardDescription>
            </CardHeader>
            <CardContent>
              {tenant.recent_activity.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Activity className="mb-3 h-10 w-10 text-slate-300" />
                  <p className="text-sm text-slate-500">
                    No recent activity
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {tenant.recent_activity.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex items-start gap-3 rounded-lg border border-slate-100 p-3"
                    >
                      <div className="mt-0.5 rounded-full bg-slate-100 p-1.5">
                        <Activity className="h-3 w-3 text-slate-600" />
                      </div>
                      <div className="flex-1 space-y-1">
                        <p className="text-sm">
                          <span className="font-medium">{entry.user_name}</span>{" "}
                          {entry.action}
                        </p>
                        {entry.description && (
                          <p className="text-xs text-slate-500">
                            {entry.description}
                          </p>
                        )}
                        <p className="text-xs text-slate-400">
                          {new Date(entry.created_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
