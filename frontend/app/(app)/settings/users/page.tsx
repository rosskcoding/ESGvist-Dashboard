"use client";

import { useState, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  AlertTriangle,
  Users,
  UserPlus,
  Mail,
  Shield,
  ShieldAlert,
  MoreHorizontal,
  Pencil,
  UserX,
  UserCheck,
  Trash2,
  Send,
  RefreshCw,
  X,
  Clock,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

// ---------- Types ----------

type UserRole = "collector" | "reviewer" | "esg_manager" | "admin" | "auditor";
type UserStatus = "active" | "inactive";

interface OrgUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  status: UserStatus;
  joined_date: string;
}

interface PendingInvitation {
  id: number;
  email: string;
  role: UserRole;
  invited_at: string;
  invited_by: string;
}

interface UsersResponse {
  users: OrgUser[];
  pending_invitations: PendingInvitation[];
}

interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  roles: Array<{ role: UserRole | "platform_admin" }>;
}

interface InvitationMutationResponse {
  id: number;
  email: string;
  role: UserRole;
  status: string;
  expires_at?: string | null;
}

interface UserRoleUpdateResponse {
  id: number;
  role: UserRole;
}

interface UserStatusUpdateResponse {
  id: number;
  status: UserStatus;
}

interface RemoveUserResponse {
  user_id: number;
  removed: boolean;
}

// ---------- Constants ----------

const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: "collector", label: "Collector" },
  { value: "reviewer", label: "Reviewer" },
  { value: "esg_manager", label: "ESG Manager" },
  { value: "admin", label: "Admin" },
  { value: "auditor", label: "Auditor" },
];

const ROLE_BADGE_VARIANT: Record<
  UserRole,
  "default" | "secondary" | "success" | "warning" | "destructive"
> = {
  admin: "destructive",
  esg_manager: "default",
  reviewer: "warning",
  collector: "secondary",
  auditor: "success",
};

const ROLE_LABELS: Record<UserRole, string> = {
  collector: "Collector",
  reviewer: "Reviewer",
  esg_manager: "ESG Manager",
  admin: "Admin",
  auditor: "Auditor",
};

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function isForbidden(error: Error | null) {
  const code = (error as Error & { code?: string } | null)?.code;
  return code === "FORBIDDEN" || /not allowed|access denied|forbidden/i.test(error?.message || "");
}

// ---------- Component ----------

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  // Dialog states
  const [inviteOpen, setInviteOpen] = useState(false);
  const [editRoleTarget, setEditRoleTarget] = useState<OrgUser | null>(null);
  const [removeTarget, setRemoveTarget] = useState<OrgUser | null>(null);

  // Invite form
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("collector");
  const [inviteMessage, setInviteMessage] = useState("");

  // Edit role form
  const [editNewRole, setEditNewRole] = useState<UserRole>("collector");

  // Queries
  const { data: currentUser, isLoading: meLoading } = useApiQuery<CurrentUser>(
    ["auth-me"],
    "/auth/me"
  );
  const canManageUsers = (currentUser?.roles ?? []).some((binding) =>
    ["admin", "platform_admin"].includes(binding.role)
  );

  const { data, isLoading, error } = useApiQuery<UsersResponse>(
    ["users"],
    "/auth/organization/users",
    { enabled: canManageUsers }
  );

  function updateUsersCache(updater: (current: UsersResponse) => UsersResponse) {
    queryClient.setQueryData<UsersResponse>(["users"], (current) =>
      current ? updater(current) : current
    );
  }

  // Mutations
  const inviteMutation = useApiMutation<
    InvitationMutationResponse,
    { email: string; role: UserRole; message?: string }
  >("/auth/invitations", "POST", {
    onSuccess: (invitation) => {
      setActionError(null);
      setInviteOpen(false);
      setInviteEmail("");
      setInviteRole("collector");
      setInviteMessage("");
      updateUsersCache((current) => ({
        ...current,
        pending_invitations: [
          {
            id: invitation.id,
            email: invitation.email,
            role: invitation.role,
            invited_at: new Date().toISOString(),
            invited_by: currentUser?.full_name || currentUser?.email || "Current user",
          },
          ...current.pending_invitations.filter((item) => item.id !== invitation.id),
        ],
      }));
    },
    onError: (error) => {
      setActionError(error.message);
    },
  });

  const updateRoleMutation = useApiMutation<UserRoleUpdateResponse, { role: UserRole }>(
    editRoleTarget ? `/auth/users/${editRoleTarget.id}/role` : "/auth/users",
    "PATCH",
    {
      onSuccess: (updated) => {
        setActionError(null);
        updateUsersCache((current) => ({
          ...current,
          users: current.users.map((user) =>
            user.id === updated.id ? { ...user, role: updated.role } : user
          ),
        }));
        setEditRoleTarget(null);
      },
      onError: (error) => {
        setActionError(error.message);
      },
    }
  );

  const toggleStatusMutation = useMutation<
    UserStatusUpdateResponse,
    Error,
    { userId: number; status: UserStatus }
  >({
    mutationFn: async ({ userId, status }) => {
      return api.patch<UserStatusUpdateResponse>(`/auth/users/${userId}/status`, { status });
    },
    onSuccess: (updated) => {
      setActionError(null);
      updateUsersCache((current) => ({
        ...current,
        users: current.users.map((user) =>
          user.id === updated.id ? { ...user, status: updated.status } : user
        ),
      }));
    },
    onError: (error) => {
      setActionError(error.message);
    },
  });

  const removeUserMutation = useApiMutation<RemoveUserResponse, void>(
    removeTarget ? `/auth/users/${removeTarget.id}` : "/auth/users",
    "DELETE",
    {
      onSuccess: (result) => {
        setActionError(null);
        updateUsersCache((current) => ({
          ...current,
          users: current.users.filter((user) => user.id !== result.user_id),
        }));
        setRemoveTarget(null);
      },
      onError: (error) => {
        setActionError(error.message);
      },
    }
  );

  const resendInviteMutation = useMutation<InvitationMutationResponse, Error, number>({
    mutationFn: async (invitationId) => {
      return api.post<InvitationMutationResponse>(`/auth/invitations/${invitationId}/resend`, {});
    },
    onSuccess: (updated) => {
      setActionError(null);
      updateUsersCache((current) => ({
        ...current,
        pending_invitations: current.pending_invitations.map((invitation) =>
          invitation.id === updated.id
            ? {
                ...invitation,
                invited_at: new Date().toISOString(),
                invited_by: currentUser?.full_name || currentUser?.email || invitation.invited_by,
              }
            : invitation
        ),
      }));
    },
    onError: (error) => {
      setActionError(error.message);
    },
  });

  const cancelInviteMutation = useMutation<{ id: number; cancelled: boolean }, Error, number>({
    mutationFn: async (invitationId) => {
      return api.delete<{ id: number; cancelled: boolean }>(`/auth/invitations/${invitationId}`);
    },
    onSuccess: (result) => {
      setActionError(null);
      updateUsersCache((current) => ({
        ...current,
        pending_invitations: current.pending_invitations.filter(
          (invitation) => invitation.id !== result.id
        ),
      }));
    },
    onError: (error) => {
      setActionError(error.message);
    },
  });

  const users = data?.users ?? [];
  const pendingInvitations = data?.pending_invitations ?? [];
  const accessDenied = (Boolean(currentUser) && !canManageUsers) || (Boolean(error) && isForbidden(error));

  const filteredUsers = useMemo(() => {
    let result = users;

    if (roleFilter) {
      result = result.filter((u) => u.role === roleFilter);
    }

    if (statusFilter) {
      result = result.filter((u) => u.status === statusFilter);
    }

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (u) =>
          u.email.toLowerCase().includes(q) ||
          u.full_name.toLowerCase().includes(q)
      );
    }

    return result;
  }, [users, roleFilter, statusFilter, searchQuery]);

  const handleToggleStatus = (user: OrgUser) => {
    const newStatus: UserStatus =
      user.status === "active" ? "inactive" : "active";
    toggleStatusMutation.mutate({ userId: user.id, status: newStatus });
  };

  // ---------- Render ----------

  if (meLoading || (canManageUsers && isLoading)) {
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
          <h2 className="text-2xl font-bold text-slate-900">User Management</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage users and invitations for your organization
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ShieldAlert className="mb-3 h-10 w-10 text-red-500" />
            <p className="text-sm font-medium text-slate-900">Access denied</p>
            <p className="mt-1 text-sm text-slate-500">
              Only admin roles can manage organization users.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">User Management</h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage users and invitations for your organization
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertTriangle className="mb-3 h-10 w-10 text-amber-500" />
            <p className="text-sm text-slate-500">
              Unable to load user data. Please try again later.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-bold text-slate-900">
            <Users className="h-6 w-6" />
            User Management
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Manage users and invitations for your organization
          </p>
        </div>
        <Button onClick={() => setInviteOpen(true)}>
          <UserPlus className="mr-1.5 h-4 w-4" />
          Add User
        </Button>
      </div>

      {actionError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4 text-sm text-red-700">{actionError}</CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 py-4">
          <div className="w-40">
            <Select
              label="Role"
              placeholder="All Roles"
              value={roleFilter}
              onChange={setRoleFilter}
              options={[
                { value: "", label: "All Roles" },
                ...ROLE_OPTIONS,
              ]}
            />
          </div>
          <div className="w-40">
            <Select
              label="Status"
              placeholder="All"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "", label: "All" },
                { value: "active", label: "Active" },
                { value: "inactive", label: "Inactive" },
              ]}
            />
          </div>
          <div className="w-64">
            <Input
              label="Search"
              placeholder="Search by name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Users table */}
      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
          <CardDescription>
            {filteredUsers.length} user{filteredUsers.length !== 1 && "s"}
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>Full Name</TableHead>
                <TableHead>Role</TableHead>
                <TableHead className="text-center">Status</TableHead>
                <TableHead className="hidden md:table-cell">
                  Joined Date
                </TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.length === 0 ? (
                <TableRow>
                  <TableCell
                    colSpan={6}
                    className="py-12 text-center text-sm text-slate-400"
                  >
                    No users match the current filters.
                  </TableCell>
                </TableRow>
              ) : (
                filteredUsers.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">{user.email}</TableCell>
                    <TableCell>{user.full_name}</TableCell>
                    <TableCell>
                      <Badge variant={ROLE_BADGE_VARIANT[user.role]}>
                        {ROLE_LABELS[user.role]}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge
                        variant={
                          user.status === "active" ? "success" : "secondary"
                        }
                      >
                        {user.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden text-sm text-slate-500 md:table-cell">
                      {formatDate(user.joined_date)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-slate-100">
                          <MoreHorizontal className="h-4 w-4" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            disabled={updateRoleMutation.isPending}
                            onClick={() => {
                              setEditRoleTarget(user);
                              setEditNewRole(user.role);
                            }}
                          >
                            <Pencil className="mr-2 h-4 w-4" />
                            Edit Role
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            disabled={toggleStatusMutation.isPending}
                            onClick={() => handleToggleStatus(user)}
                          >
                            {user.status === "active" ? (
                              <>
                                <UserX className="mr-2 h-4 w-4" />
                                Deactivate
                              </>
                            ) : (
                              <>
                                <UserCheck className="mr-2 h-4 w-4" />
                                Reactivate
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            disabled={removeUserMutation.isPending}
                            onClick={() => setRemoveTarget(user)}
                            className="text-red-600"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Remove
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pending Invitations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Pending Invitations
          </CardTitle>
          <CardDescription>
            {pendingInvitations.length} pending invitation
            {pendingInvitations.length !== 1 && "s"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {pendingInvitations.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-400">
              No pending invitations.
            </p>
          ) : (
            <div className="space-y-3">
              {pendingInvitations.map((inv) => (
                <div
                  key={inv.id}
                  className="flex items-center justify-between rounded-lg border border-slate-200 p-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100">
                      <Mail className="h-4 w-4 text-slate-500" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{inv.email}</p>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={ROLE_BADGE_VARIANT[inv.role]}
                          className="text-[10px]"
                        >
                          {ROLE_LABELS[inv.role]}
                        </Badge>
                        <span className="text-xs text-slate-400">
                          Invited {formatDate(inv.invited_at)} by{" "}
                          {inv.invited_by}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={resendInviteMutation.isPending || cancelInviteMutation.isPending}
                      onClick={() => resendInviteMutation.mutate(inv.id)}
                    >
                      <RefreshCw className="mr-1 h-3 w-3" />
                      Resend
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={resendInviteMutation.isPending || cancelInviteMutation.isPending}
                      onClick={() => cancelInviteMutation.mutate(inv.id)}
                    >
                      <X className="mr-1 h-3 w-3 text-red-500" />
                      Cancel
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Invite user dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite User</DialogTitle>
            <DialogDescription>
              Send an invitation to join your organization.
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <Input
              label="Email"
              type="email"
              placeholder="user@example.com"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <Select
              label="Role"
              value={inviteRole}
              onChange={(v) => setInviteRole(v as UserRole)}
              options={ROLE_OPTIONS}
            />
            <Textarea
              label="Custom Message (optional)"
              placeholder="Add a personal note to the invitation..."
              value={inviteMessage}
              onChange={(e) => setInviteMessage(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter className="mt-4">
            <DialogClose className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium shadow-sm hover:bg-slate-50">
              Cancel
            </DialogClose>
            <Button
              disabled={!inviteEmail.trim() || inviteMutation.isPending}
              onClick={() =>
                inviteMutation.mutate({
                  email: inviteEmail,
                  role: inviteRole,
                  message: inviteMessage || undefined,
                })
              }
            >
              {inviteMutation.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Send className="mr-1.5 h-4 w-4" />
              )}
              Send Invite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit role dialog */}
      <Dialog
        open={editRoleTarget !== null}
        onOpenChange={(open) => {
          if (!open) setEditRoleTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Role</DialogTitle>
            <DialogDescription>
              Change the role for {editRoleTarget?.full_name} (
              {editRoleTarget?.email}).
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4">
            <Select
              label="New Role"
              value={editNewRole}
              onChange={(v) => setEditNewRole(v as UserRole)}
              options={ROLE_OPTIONS}
            />
          </div>
          <DialogFooter className="mt-4">
            <DialogClose className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium shadow-sm hover:bg-slate-50">
              Cancel
            </DialogClose>
            <Button
              disabled={updateRoleMutation.isPending}
              onClick={() =>
                updateRoleMutation.mutate({ role: editNewRole })
              }
            >
              {updateRoleMutation.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Shield className="mr-1.5 h-4 w-4" />
              )}
              Update Role
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove user confirmation dialog */}
      <Dialog
        open={removeTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRemoveTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove User</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove {removeTarget?.full_name} (
              {removeTarget?.email}) from the organization? This action cannot
              be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose className="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-4 text-sm font-medium shadow-sm hover:bg-slate-50">
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              disabled={removeUserMutation.isPending}
              onClick={() =>
                removeUserMutation.mutate(undefined as never)
              }
            >
              {removeUserMutation.isPending ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-1.5 h-4 w-4" />
              )}
              Remove User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
