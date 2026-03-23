"use client";

import { useState, useEffect } from "react";
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
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { useApiQuery, useApiMutation } from "@/lib/hooks/use-api";
import {
  Loader2,
  User,
  Lock,
  Save,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

interface UserProfile {
  id: number;
  full_name: string;
  email: string;
  roles: Array<{
    id: number;
    role: string;
    scope_type: string;
    scope_id: number | null;
  }>;
  organization_name: string;
}

export default function ProfilePage() {
  const [displayName, setDisplayName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [profileSaved, setProfileSaved] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordError, setPasswordError] = useState("");

  const { data, isLoading } = useApiQuery<UserProfile>(
    ["profile"],
    "/auth/me"
  );

  const updateProfileMutation = useApiMutation(
    "/auth/me",
    "PATCH"
  );

  const changePasswordMutation = useApiMutation(
    "/auth/change-password",
    "POST"
  );

  useEffect(() => {
    if (data) {
      setDisplayName(data.full_name);
    }
  }, [data]);

  const handleSaveProfile = async () => {
    setProfileSaved(false);
    await updateProfileMutation.mutateAsync({
      full_name: displayName,
    } as never);
    setProfileSaved(true);
    setTimeout(() => setProfileSaved(false), 3000);
  };

  const handleChangePassword = async () => {
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
      } as never);
      setPasswordSaved(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setPasswordSaved(false), 3000);
    } catch {
      setPasswordError("Failed to change password. Check your current password.");
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  const profile = data;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Profile</h2>
        <p className="mt-1 text-sm text-slate-500">
          Manage your personal information and security
        </p>
      </div>

      {/* Profile Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Personal Information
          </CardTitle>
          <CardDescription>
            Update your display name and view your account details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="displayName">Display Name</Label>
            <Input
              id="displayName"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={profile?.email ?? ""}
              disabled
              className="bg-slate-50"
            />
            <p className="text-xs text-slate-400">
              Email cannot be changed
            </p>
          </div>

          <div className="space-y-2">
            <Label>Role</Label>
            <div className="flex items-center gap-2">
              {profile?.roles.map((r) => (
                <Badge key={r.id} variant="secondary">
                  {r.role}
                </Badge>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Organization</Label>
            <p className="text-sm font-medium text-slate-700">
              {profile?.organization_name ?? "N/A"}
            </p>
          </div>

          {profileSaved && (
            <Alert variant="success">
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>Profile updated successfully</AlertDescription>
            </Alert>
          )}

          <Button
            onClick={handleSaveProfile}
            disabled={updateProfileMutation.isPending}
          >
            {updateProfileMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Changes
          </Button>
        </CardContent>
      </Card>

      {/* Change Password */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-4 w-4" />
            Change Password
          </CardTitle>
          <CardDescription>
            Update your account password
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="currentPassword">Current Password</Label>
            <Input
              id="currentPassword"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Enter current password"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="newPassword">New Password</Label>
            <Input
              id="newPassword"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter new password"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm New Password</Label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
            />
          </div>

          {passwordError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{passwordError}</AlertDescription>
            </Alert>
          )}

          {passwordSaved && (
            <Alert variant="success">
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>Password changed successfully</AlertDescription>
            </Alert>
          )}

          <Button
            onClick={handleChangePassword}
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
        </CardContent>
      </Card>
    </div>
  );
}
