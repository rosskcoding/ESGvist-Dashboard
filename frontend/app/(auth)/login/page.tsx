"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { login } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [nextPath, setNextPath] = useState<string | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  useEffect(() => {
    setHydrated(true);
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    setNextPath(params.get("next"));
    setSessionExpired(params.get("reason") === "session-expired");
  }, []);

  function resolveNextRoute(defaultRoute: string): string {
    if (!nextPath || !nextPath.startsWith("/") || nextPath.startsWith("//")) {
      return defaultRoute;
    }
    return nextPath;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!hydrated || loading) return;
    setError("");
    setLoading(true);

    try {
      const session = await login(email, password);
      router.push(resolveNextRoute(session.next_route));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="flex flex-col items-center text-center">
        <Image
          src="/brand/logo-esgvist.png"
          alt="ESGvist"
          width={200}
          height={38}
          priority
          className="mb-2"
        />
        <CardDescription>ESG data management platform</CardDescription>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          {sessionExpired && !error && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              Your session expired. Sign in again to continue.
            </div>
          )}
          {error && (
            <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
            />
          </div>

          <Button type="submit" className="w-full" disabled={!hydrated || loading}>
            {!hydrated ? "Loading..." : loading ? "Signing in..." : "Sign in"}
          </Button>

          <div className="rounded-md bg-slate-50 border border-slate-200 p-3 text-xs text-slate-500">
            <p className="font-medium text-slate-600 mb-2">Dev accounts (password: <span className="font-mono text-slate-700">Test1234</span>)</p>
            <table className="w-full text-left">
              <tbody className="divide-y divide-slate-200">
                <tr><td className="py-0.5 font-mono text-slate-700">admin@esgvist.com</td><td className="py-0.5 text-slate-400">platform_admin</td></tr>
                <tr><td className="py-0.5 font-mono text-slate-700">framework@esgvist.com</td><td className="py-0.5 text-slate-400">framework_admin</td></tr>
                <tr><td className="py-0.5 font-mono text-slate-700">manager@greentech.com</td><td className="py-0.5 text-slate-400">esg_manager</td></tr>
                <tr><td className="py-0.5 font-mono text-slate-700">collector1@greentech.com</td><td className="py-0.5 text-slate-400">collector</td></tr>
                <tr><td className="py-0.5 font-mono text-slate-700">collector2@greentech.com</td><td className="py-0.5 text-slate-400">collector</td></tr>
                <tr><td className="py-0.5 font-mono text-slate-700">reviewer@greentech.com</td><td className="py-0.5 text-slate-400">reviewer</td></tr>
                <tr><td className="py-0.5 font-mono text-slate-700">auditor@greentech.com</td><td className="py-0.5 text-slate-400">auditor</td></tr>
              </tbody>
            </table>
          </div>
        </form>
      </CardContent>

      <CardFooter className="justify-center">
        <p className="text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-cyan-600 hover:text-cyan-500"
          >
            Create one
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}
