"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  Loader2,
  Lock,
  LogOut,
  MonitorSmartphone,
  Save,
  ShieldCheck,
  Trash2,
  User,
} from "lucide-react";

import { api } from "@/lib/api";
import { clearClientAuthState, logoutAll } from "@/lib/auth";
import { useApiMutation, useApiQuery } from "@/lib/hooks/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type UserProfile = {
  id: number;
  full_name: string;
  email: string;
  organization_name: string | null;
  roles: Array<{
    id: number;
    role: string;
    scope_type: string;
    scope_id: number | null;
  }>;
};

type TwoFactorStatus = {
  enabled: boolean;
  pending_setup: boolean;
  confirmed_at: string | null;
  backup_codes_remaining: number;
};

type AuthSession = {
  id: number;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  ip_address: string | null;
  user_agent: string | null;
  is_current: boolean;
};

type AuthSessionList = {
  items: AuthSession[];
  total: number;
};

type AuthSessionRevokeResult = {
  session_id: number;
  revoked: boolean;
  is_current: boolean;
};

type ChangePasswordResult = {
  changed: boolean;
  revoked_sessions?: number;
  current_session_preserved?: boolean;
};

function formatDateTime(value: string | null) {
  if (!value) return "Unknown";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function sessionTitle(session: AuthSession) {
  if (session.is_current) return "Current session";
  if (session.user_agent) return session.user_agent;
  return "Browser session";
}

export default function ProfilePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [sessionError, setSessionError] = useState("");
  const [revokingSessionId, setRevokingSessionId] = useState<number | null>(null);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  const { data: profile, isLoading } = useApiQuery<UserProfile>(["profile"], "/auth/me");
  const { data: twoFactorStatus } = useApiQuery<TwoFactorStatus>(
    ["profile", "2fa-status"],
    "/auth/2fa/status"
  );
  const { data: sessionList, isLoading: sessionsLoading } = useApiQuery<AuthSessionList>(
    ["profile", "sessions"],
    "/auth/sessions"
  );

  const updateProfileMutation = useApiMutation<UserProfile, { full_name: string }>(
    "/auth/me",
    "PATCH"
  );
  const changePasswordMutation = useApiMutation<
    ChangePasswordResult,
    { current_password: string; new_password: string }
  >("/auth/change-password", "POST");

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.full_name);
    }
  }, [profile]);

  async function handleSaveProfile() {
    setProfileSaved(false);
    await updateProfileMutation.mutateAsync({ full_name: displayName.trim() });
    setProfileSaved(true);
  }

  async function handleChangePassword() {
    setPasswordError("");
    setPasswordSaved("");

    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters");
      return;
    }

    try {
      const result = await changePasswordMutation.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      });
      await queryClient.invalidateQueries({ queryKey: ["profile", "sessions"] });
      setPasswordSaved(
        result.revoked_sessions
          ? `Password changed. ${result.revoked_sessions} other session${result.revoked_sessions === 1 ? "" : "s"} revoked.`
          : "Password changed successfully."
      );
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : "Failed to change password.");
    }
  }

  async function handleRevokeSession(session: AuthSession) {
    setSessionError("");
    setRevokingSessionId(session.id);
    try {
      const result = await api.delete<AuthSessionRevokeResult>(`/auth/sessions/${session.id}`);
      if (result.is_current) {
        clearClientAuthState();
        router.replace("/login");
        return;
      }
      await queryClient.invalidateQueries({ queryKey: ["profile", "sessions"] });
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : "Failed to revoke session.");
    } finally {
      setRevokingSessionId(null);
    }
  }

  async function handleLogoutAll() {
    setSessionError("");
    setLoggingOutAll(true);
    try {
      await logoutAll();
      router.replace("/login");
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : "Failed to sign out all sessions.");
      setLoggingOutAll(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const sessions = sessionList?.items ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Profile</h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage your personal identity, organization context, and account security.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-4 w-4" />
              Personal Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Your name"
              />
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" value={profile?.email ?? ""} disabled className="bg-slate-50" />
            </div>

            <div className="grid gap-1.5">
              <Label>Roles</Label>
              <div className="flex flex-wrap gap-2">
                {(profile?.roles ?? []).map((role) => (
                  <Badge key={role.id} variant="secondary">
                    {role.role}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="grid gap-1.5">
              <Label>Organization</Label>
              <p className="text-sm font-medium text-slate-700">
                {profile?.organization_name ?? "No active organization"}
              </p>
            </div>

            {profileSaved && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                Profile updated successfully.
              </div>
            )}

            <div className="flex justify-end">
              <Button
                onClick={() => void handleSaveProfile()}
                disabled={updateProfileMutation.isPending || !displayName.trim()}
              >
                {updateProfileMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Save className="mr-2 h-4 w-4" />
                )}
                Save Changes
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" />
              Account Security
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              <p className="font-medium text-slate-900">Two-factor authentication</p>
              <p className="mt-2">
                Status:{" "}
                {twoFactorStatus?.enabled
                  ? "Enabled"
                  : twoFactorStatus?.pending_setup
                    ? "Setup pending"
                    : "Disabled"}
              </p>
              <p className="mt-1">
                Backup codes remaining: {twoFactorStatus?.backup_codes_remaining ?? 0}
              </p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              Password changes now revoke other refresh sessions server-side. Use the session list
              below to end the current device or sign out everywhere.
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MonitorSmartphone className="h-4 w-4" />
            Active Sessions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-600">
              Server-side refresh sessions stay visible here until revoked or expired.
            </p>
            <Button
              variant="outline"
              onClick={() => void handleLogoutAll()}
              disabled={loggingOutAll || sessions.length === 0}
            >
              {loggingOutAll ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="mr-2 h-4 w-4" />
              )}
              Sign Out All Sessions
            </Button>
          </div>

          {sessionError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="mr-2 inline h-4 w-4" />
              {sessionError}
            </div>
          )}

          {sessionsLoading ? (
            <div className="flex min-h-[120px] items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : sessions.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-500">
              No active refresh sessions found.
            </div>
          ) : (
            <div className="space-y-3">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-900">
                          {sessionTitle(session)}
                        </p>
                        {session.is_current && <Badge>Current</Badge>}
                      </div>
                      <div className="space-y-1 text-sm text-slate-600">
                        <p className="flex items-center gap-2">
                          <Clock3 className="h-4 w-4 text-slate-400" />
                          Started {formatDateTime(session.created_at)}
                        </p>
                        <p>Last used: {formatDateTime(session.last_used_at ?? session.created_at)}</p>
                        <p>Expires: {formatDateTime(session.expires_at)}</p>
                        <p>IP: {session.ip_address ?? "Unknown"}</p>
                      </div>
                    </div>

                    <div className="flex flex-col items-stretch gap-2 lg:min-w-[180px]">
                      <p className="text-xs uppercase tracking-wide text-slate-500">
                        User Agent
                      </p>
                      <p className="text-sm text-slate-700">
                        {session.user_agent ?? "Unavailable"}
                      </p>
                      <Button
                        variant={session.is_current ? "destructive" : "outline"}
                        onClick={() => void handleRevokeSession(session)}
                        disabled={revokingSessionId === session.id}
                      >
                        {revokingSessionId === session.id ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : session.is_current ? (
                          <LogOut className="mr-2 h-4 w-4" />
                        ) : (
                          <Trash2 className="mr-2 h-4 w-4" />
                        )}
                        {session.is_current ? "Sign Out This Device" : "Revoke Session"}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-4 w-4" />
            Change Password
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="currentPassword">Current Password</Label>
              <Input
                id="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="newPassword">New Password</Label>
              <Input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
              />
            </div>
          </div>

          {passwordError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="mr-2 inline h-4 w-4" />
              {passwordError}
            </div>
          )}

          {passwordSaved && (
            <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              <CheckCircle2 className="mr-2 inline h-4 w-4" />
              {passwordSaved}
            </div>
          )}

          <div className="flex justify-end">
            <Button
              onClick={() => void handleChangePassword()}
              disabled={
                !currentPassword ||
                !newPassword ||
                !confirmPassword ||
                changePasswordMutation.isPending
              }
            >
              {changePasswordMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Lock className="mr-2 h-4 w-4" />
              )}
              Change Password
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
