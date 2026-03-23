"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, Lock, Save, ShieldCheck, User } from "lucide-react";

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

export default function ProfilePage() {
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  const { data: profile, isLoading } = useApiQuery<UserProfile>(["profile"], "/auth/me");
  const { data: twoFactorStatus } = useApiQuery<TwoFactorStatus>(["profile", "2fa-status"], "/auth/2fa/status");

  const updateProfileMutation = useApiMutation<UserProfile, { full_name: string }>("/auth/me", "PATCH");
  const changePasswordMutation = useApiMutation<{ changed: boolean }, { current_password: string; new_password: string }>(
    "/auth/change-password",
    "POST"
  );

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
    setPasswordSaved(false);

    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters");
      return;
    }

    try {
      await changePasswordMutation.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPasswordSaved(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : "Failed to change password.");
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
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
              <p className="text-sm font-medium text-slate-700">{profile?.organization_name ?? "No active organization"}</p>
            </div>

            {profileSaved && (
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                Profile updated successfully.
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={() => void handleSaveProfile()} disabled={updateProfileMutation.isPending || !displayName.trim()}>
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
                Status: {twoFactorStatus?.enabled ? "Enabled" : twoFactorStatus?.pending_setup ? "Setup pending" : "Disabled"}
              </p>
              <p className="mt-1">Backup codes remaining: {twoFactorStatus?.backup_codes_remaining ?? 0}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
              Password changes invalidate existing refresh sessions and require new sign-in from other devices.
            </div>
          </CardContent>
        </Card>
      </div>

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
              Password changed successfully.
            </div>
          )}

          <div className="flex justify-end">
            <Button
              onClick={() => void handleChangePassword()}
              disabled={
                !currentPassword || !newPassword || !confirmPassword || changePasswordMutation.isPending
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
