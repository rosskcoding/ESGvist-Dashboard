"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { register, login, isAuthenticated } from "@/lib/auth";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";

interface InvitationInfo {
  organization_id?: number;
  organization_name: string;
  email: string;
  role: string;
  inviter_name: string;
  already_registered: boolean;
}

export default function InvitePage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;

  const [invitation, setInvitation] = useState<InvitationInfo | null>(null);
  const [validating, setValidating] = useState(true);
  const [validationError, setValidationError] = useState("");

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    async function validateToken() {
      try {
        const data = await api.get<InvitationInfo>(
          `/invitations/accept?token=${encodeURIComponent(token)}`
        );
        setInvitation(data);
      } catch (err: unknown) {
        setValidationError(
          err instanceof Error ? err.message : "Invalid or expired invitation"
        );
      } finally {
        setValidating(false);
      }
    }

    validateToken();
  }, [token]);

  const handleAccept = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!hydrated || loading) return;
    setError("");
    setLoading(true);

    try {
      if (!invitation?.already_registered) {
        if (password !== confirmPassword) {
          setError("Passwords do not match");
          setLoading(false);
          return;
        }
        if (password.length < 8) {
          setError("Password must be at least 8 characters");
          setLoading(false);
          return;
        }

        await register(invitation!.email, password, fullName);
        await login(invitation!.email, password);
      }

      await api.post(`/invitations/accept`, { token });
      if (invitation?.organization_id) {
        localStorage.setItem("organization_id", String(invitation.organization_id));
      }
      setAccepted(true);

      setTimeout(() => {
        router.push("/dashboard");
      }, 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to accept invitation");
    } finally {
      setLoading(false);
    }
  };

  const handleDecline = async () => {
    setLoading(true);
    try {
      await api.post(`/invitations/decline`, { token });
      router.push(isAuthenticated() ? "/dashboard" : "/login");
    } catch {
      setError("Failed to decline invitation");
    } finally {
      setLoading(false);
    }
  };

  if (validating) {
    return (
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="mt-4 text-sm text-muted-foreground">
            Validating invitation...
          </p>
        </CardContent>
      </Card>
    );
  }

  if (validationError) {
    return (
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <XCircle className="h-12 w-12 text-red-500" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            Invalid Invitation
          </h2>
          <p className="mt-2 text-sm text-muted-foreground text-center">
            {validationError}
          </p>
          <Button
            variant="outline"
            className="mt-6"
            onClick={() => router.push("/login")}
          >
            Go to Login
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (accepted) {
    return (
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <CheckCircle2 className="h-12 w-12 text-green-500" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">
            Welcome aboard!
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Redirecting to dashboard...
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl font-bold">
          You&apos;ve been invited
        </CardTitle>
        <CardDescription>
          <span className="font-medium text-gray-700">
            {invitation?.inviter_name}
          </span>{" "}
          has invited you to join{" "}
          <span className="font-semibold text-gray-900">
            {invitation?.organization_name}
          </span>{" "}
          as{" "}
          <span className="font-medium text-blue-600">
            {invitation?.role}
          </span>
        </CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleAccept} className="space-y-4">
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {!invitation?.already_registered && (
            <>
              <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-700">
                Create your account to accept this invitation.
              </div>

              <div className="space-y-2">
                <Label htmlFor="inviteEmail">Email</Label>
                <Input
                  id="inviteEmail"
                  type="email"
                  autoComplete="email"
                  value={invitation?.email ?? ""}
                  disabled
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="inviteFullName">Full Name</Label>
                <Input
                  id="inviteFullName"
                  type="text"
                  required
                  autoComplete="name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="invitePassword">Password</Label>
                <Input
                  id="invitePassword"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="inviteConfirmPassword">Confirm Password</Label>
                <Input
                  id="inviteConfirmPassword"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter your password"
                />
              </div>
            </>
          )}

          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={handleDecline}
              disabled={!hydrated || loading}
            >
              Decline
            </Button>
            <Button type="submit" className="flex-1" disabled={!hydrated || loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                "Accept Invitation"
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
