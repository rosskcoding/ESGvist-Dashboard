"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { logout } from "@/lib/auth";
import { api, isAppApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
import { isProjectScopedPath, parseProjectId, withProjectId } from "@/lib/project-routing";
import { Providers } from "./providers";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { AICopilot } from "@/components/ai-copilot";
import { AIActionHandlers } from "@/components/ai-action-handlers";
import { AIContextProvider, useAIScreenContext } from "@/lib/ai-context";
import {
  readSupportMode,
  stopSupportMode,
  syncSupportModeState,
  subscribeSupportMode,
  type SupportModeState,
} from "@/lib/support-mode";
import {
  LayoutDashboard,
  ClipboardList,
  CheckSquare,
  GitMerge,
  FolderKanban,
  PieChart,
  FileOutput,
  Building2,
  UserCog,
  BookOpen,
  Share2,
  Users,
  Map,
  Webhook,
  Server,
  Search,
  Bell,
  BotMessageSquare,
  LogOut,
  ChevronDown,
  ScrollText,
  Settings,
  UserCircle,
  type LucideIcon,
} from "lucide-react";

interface UserInfo {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
  roles: Array<{
    id: number;
    role: string;
    scope_type: string;
    scope_id: number | null;
  }>;
}

interface SupportSessionCurrent {
  active: boolean;
  session_id: number | null;
  tenant_id: number | null;
  tenant_name: string | null;
  started_at: string | null;
}

interface TenantListResponse {
  items: Array<{
    id: number;
    name: string;
  }>;
  total: number;
}

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  requiredRoles?: string[];
}

interface NavGroup {
  title: string;
  items: NavItem[];
  requiredRoles?: string[];
}

const navGroups: NavGroup[] = [
  {
    title: "Main",
    items: [
      {
        label: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
        requiredRoles: ["collector", "reviewer", "esg_manager", "admin", "auditor", "platform_admin"],
      },
      {
        label: "Collection",
        href: "/collection",
        icon: ClipboardList,
        requiredRoles: ["collector", "esg_manager", "admin", "platform_admin"],
      },
      {
        label: "Evidence",
        href: "/evidence",
        icon: Search,
        requiredRoles: ["collector", "esg_manager", "auditor", "admin", "platform_admin"],
      },
      {
        label: "Validation",
        href: "/validation",
        icon: CheckSquare,
        requiredRoles: ["reviewer", "auditor"],
      },
      {
        label: "Merge View",
        href: "/merge",
        icon: GitMerge,
        requiredRoles: ["esg_manager", "admin", "auditor", "reviewer"],
      },
    ],
  },
  {
    title: "Reporting",
    items: [
      {
        label: "Projects",
        href: "/projects",
        icon: FolderKanban,
        requiredRoles: ["admin", "esg_manager", "platform_admin"],
      },
      {
        label: "Completeness",
        href: "/completeness",
        icon: PieChart,
        requiredRoles: ["admin", "esg_manager", "auditor", "platform_admin"],
      },
      {
        label: "Report / Export",
        href: "/report",
        icon: FileOutput,
        requiredRoles: ["admin", "esg_manager"],
      },
      {
        label: "Audit Log",
        href: "/audit",
        icon: ScrollText,
        requiredRoles: ["admin", "auditor"],
      },
    ],
  },
  {
    title: "Settings",
    items: [
      {
        label: "Organization",
        href: "/settings",
        icon: Settings,
        requiredRoles: ["admin", "platform_admin"],
      },
      { label: "Profile", href: "/settings/profile", icon: UserCircle },
      {
        label: "Company Structure",
        href: "/settings/company-structure",
        icon: Building2,
        requiredRoles: ["admin", "esg_manager", "platform_admin"],
      },
      {
        label: "Assignments",
        href: "/settings/assignments",
        icon: UserCog,
        requiredRoles: ["admin", "esg_manager", "platform_admin"],
      },
      {
        label: "Form Configs",
        href: "/settings/form-configs",
        icon: ClipboardList,
        requiredRoles: ["admin", "esg_manager", "platform_admin"],
      },
      {
        label: "Users",
        href: "/settings/users",
        icon: Users,
        requiredRoles: ["admin", "platform_admin"],
      },
      {
        label: "Boundaries",
        href: "/settings/boundaries",
        icon: Map,
        requiredRoles: ["admin", "platform_admin"],
      },
      {
        label: "Webhooks",
        href: "/settings/webhooks",
        icon: Webhook,
        requiredRoles: ["admin", "platform_admin"],
      },
    ],
  },
  {
    title: "Platform",
    items: [
      {
        label: "Framework Catalog",
        href: "/platform/framework",
        icon: BookOpen,
        requiredRoles: ["framework_admin", "platform_admin"],
      },
      {
        label: "Tenants",
        href: "/platform/tenants",
        icon: Server,
        requiredRoles: ["platform_admin"],
      },
    ],
  },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AIContextProvider>
        <AppShell>{children}</AppShell>
      </AIContextProvider>
    </Providers>
  );
}

function routeRequiresTenantContext(pathname: string): boolean {
  return pathname !== "/onboarding" && !pathname.startsWith("/platform");
}

function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentProjectId = parseProjectId(searchParams.get("projectId"));
  const loginRedirect = useCallback(
    (reason: "session-expired" | "auth-required") => {
      const params = new URLSearchParams({ reason, next: pathname || "/dashboard" });
      router.push(`/login?${params.toString()}`);
    },
    [pathname, router]
  );
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [orgContextReady, setOrgContextReady] = useState(false);
  const [orgContextError, setOrgContextError] = useState<string | null>(null);
  const [supportMode, setSupportMode] = useState<SupportModeState>(() => readSupportMode());
  const [supportModeReady, setSupportModeReady] = useState(false);
  const [supportEnding, setSupportEnding] = useState(false);
  const [supportError, setSupportError] = useState("");
  const { resetScreenContext } = useAIScreenContext();

  // Reset AI context on every route change — wipes stale projectId/dataPointId/etc.
  // Pages then enrich via enrichScreenContext() in their own useEffect.
  useEffect(() => {
    const screen = pathname.replace(/^\//, "") || "dashboard";
    resetScreenContext(screen);
  }, [pathname, resetScreenContext]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const syncSupportMode = () => setSupportMode(readSupportMode());
    syncSupportMode();
    return subscribeSupportMode(syncSupportMode);
  }, []);

  const {
    data: user,
    error: userError,
  } = useApiQuery<UserInfo>(["auth-me"], "/auth/me", {
    enabled: mounted,
  });

  const userRoles = user?.roles?.map((role) => role.role) ?? [];
  const userRole = userRoles[0] ?? "";
  const isPlatformAdmin = user?.roles?.some((r) => r.role === "platform_admin") ?? false;
  const isFrameworkAdmin = user?.roles?.some((r) => r.role === "framework_admin") ?? false;
  const hasNotificationEligibleOrgRole =
    user?.roles?.some((binding) => binding.scope_type === "organization" && binding.role !== "auditor") ?? false;
  const requiresTenantContext = routeRequiresTenantContext(pathname);
  const organizationName = "Organization";
  const canAccessNotifications = isPlatformAdmin || hasNotificationEligibleOrgRole;
  const unreadQueryEnabled = mounted && Boolean(user) && canAccessNotifications && orgContextReady;

  const { data: currentSupportSession } = useApiQuery<SupportSessionCurrent>(
    ["platform-support-current"],
    "/platform/support-session/current",
    {
      enabled: mounted && Boolean(user) && isPlatformAdmin,
      retry: false,
      staleTime: 0,
      refetchOnMount: "always",
    }
  );

  const { data: unreadData } = useApiQuery<{ unread_count: number }>(
    ["notifications-unread-count"],
    "/notifications/unread-count",
    { enabled: unreadQueryEnabled }
  );
  const unreadCount = canAccessNotifications ? unreadData?.unread_count ?? 0 : 0;

  const hasRequiredRole = useCallback(
    (requiredRoles?: string[]) => {
      if (!requiredRoles || requiredRoles.length === 0) return true;
      return requiredRoles.some((requiredRole) => userRoles.includes(requiredRole));
    },
    [userRoles]
  );

  useEffect(() => {
    if (!mounted || !user) {
      setOrgContextReady(false);
      setOrgContextError(null);
      return;
    }

    if (!requiresTenantContext) {
      setOrgContextError(null);
      setOrgContextReady(true);
      return;
    }

    if (isPlatformAdmin && !supportModeReady) {
      setOrgContextReady(false);
      return;
    }

    if (supportMode.active) {
      setOrgContextError(null);
      setOrgContextReady(true);
      return;
    }

    const orgRole = user.roles.find(
      (role) => role.scope_type === "organization" && role.scope_id
    );

    let cancelled = false;
    setOrgContextReady(false);
    setOrgContextError(null);

    async function ensureTenantContext() {
      try {
        if (orgRole?.scope_id) {
          await api.post("/auth/context/organization", {
            organization_id: orgRole.scope_id,
          });
          if (!cancelled) {
            setOrgContextReady(true);
          }
          return;
        }

        if (!isPlatformAdmin) {
          if (!cancelled) {
            setOrgContextError(
              isFrameworkAdmin
                ? "This role works in Framework Catalog only. Open the platform framework workspace."
                : "Organization context is unavailable for this account."
            );
            setOrgContextReady(false);
          }
          return;
        }

        const tenants = await api.get<TenantListResponse>("/platform/tenants?page=1&page_size=2");
        if (cancelled) return;
        if (tenants.total === 1 && tenants.items[0]) {
          await api.post("/auth/context/organization", {
            organization_id: tenants.items[0].id,
          });
          if (!cancelled) {
            setOrgContextReady(true);
          }
          return;
        }

        setOrgContextError(
          tenants.total > 1
            ? "Select a tenant from Platform > Tenants before opening tenant-scoped screens."
            : "Create or select a tenant before opening tenant-scoped screens."
        );
        setOrgContextReady(false);
      } catch {
        if (!cancelled) {
          setOrgContextError("Unable to establish organization context.");
          setOrgContextReady(false);
        }
      }
    }

    void ensureTenantContext();

    return () => {
      cancelled = true;
    };
  }, [isFrameworkAdmin, isPlatformAdmin, mounted, requiresTenantContext, supportMode.active, supportModeReady, user]);

  useEffect(() => {
    if (!mounted || !user) {
      setSupportModeReady(false);
      return;
    }
    if (!isPlatformAdmin) {
      syncSupportModeState({ active: false });
      setSupportMode(readSupportMode());
      setSupportModeReady(true);
      return;
    }
    if (!currentSupportSession) {
      return;
    }
    syncSupportModeState({
      active: currentSupportSession.active,
      tenantId: currentSupportSession.tenant_id,
      tenantName: currentSupportSession.tenant_name,
    });
    setSupportMode(readSupportMode());
    setSupportModeReady(true);
  }, [currentSupportSession, isPlatformAdmin, mounted, user]);

  useEffect(() => {
    if (mounted && userError) {
      if (isAppApiError(userError) && userError.status === 401) {
        loginRedirect("auth-required");
        return;
      }
      router.push("/login");
    }
  }, [loginRedirect, mounted, router, userError]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const handleEndSupportMode = async () => {
    if (!supportMode.active || supportEnding) return;

    setSupportError("");
    setSupportEnding(true);
    try {
      await api.delete("/platform/support-session/current");
      stopSupportMode();
      router.push("/platform/tenants");
    } catch (error) {
      setSupportError(
        error instanceof Error
          ? error.message
          : "Unable to end support mode. Please try again."
      );
    } finally {
      setSupportEnding(false);
    }
  };

  const hasOrganizationRole =
    user?.roles?.some((role) => role.scope_type === "organization" && role.scope_id) ?? false;
  const supportModeActive = supportModeReady && supportMode.active;

  useEffect(() => {
    if (!user || isPlatformAdmin || hasOrganizationRole) return;
    if (isFrameworkAdmin) {
      if (!pathname.startsWith("/platform/framework")) {
        router.push("/platform/framework");
      }
      return;
    }
    if (pathname !== "/onboarding") {
      router.push("/onboarding");
    }
  }, [hasOrganizationRole, isFrameworkAdmin, isPlatformAdmin, pathname, router, user]);

  if (!mounted || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (requiresTenantContext && !orgContextReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <div className="text-lg font-semibold text-slate-900">Preparing tenant context</div>
          <p className="mt-2 text-sm text-slate-500">
            {orgContextError ?? "Loading the organization context for this workspace."}
          </p>
          {isPlatformAdmin && orgContextError && (
            <Button className="mt-4" onClick={() => router.push("/platform/tenants")}>
              Open Tenants
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-gray-200 bg-white">
        <div className="flex h-16 items-center border-b border-gray-200 px-4">
          <Link href={withProjectId("/dashboard", currentProjectId)} prefetch={false}>
            <Image
              src="/brand/logo-esgvist.png"
              alt="ESGvist"
              width={168}
              height={32}
              priority
            />
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
                  {navGroups.map((group) => {
            const visibleItems = group.items.filter((item) => hasRequiredRole(item.requiredRoles));
            if (group.requiredRoles && !hasRequiredRole(group.requiredRoles)) return null;
            if (visibleItems.length === 0) return null;

            return (
              <div key={group.title} className="mb-6 px-3">
                <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                  {group.title}
                </p>
                <div className="space-y-1">
                  {visibleItems.map((item) => {
                    const isActive =
                      pathname === item.href ||
                      (item.href !== "/settings" && pathname.startsWith(item.href + "/"));
                    const Icon = item.icon;
                    const href = isProjectScopedPath(item.href)
                      ? withProjectId(item.href, currentProjectId)
                      : item.href;

                    return (
                      <Link
                        key={item.href}
                        href={href}
                        prefetch={false}
                        className={cn(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-cyan-50 text-cyan-700"
                            : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                        )}
                      >
                        <Icon className="h-4 w-4 shrink-0" />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>
      </aside>

      {/* Main content area */}
      <div className="flex flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
          {/* Search */}
          <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm text-gray-400">
            <Search className="h-4 w-4" />
            <span>Search...</span>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            {/* AI Copilot toggle */}
            <Button
              variant={copilotOpen ? "default" : "outline"}
              size="sm"
              onClick={() => setCopilotOpen(!copilotOpen)}
              className="gap-2"
            >
              <BotMessageSquare className="h-4 w-4" />
              AI Copilot
            </Button>

            {/* Notification bell */}
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label="Notifications"
              onClick={() => router.push("/notifications")}
            >
              <Bell className="h-5 w-5 text-gray-500" />
              {unreadCount > 0 && (
                <Badge
                  variant="destructive"
                  className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-xs"
                >
                  {unreadCount > 99 ? "99+" : unreadCount}
                </Badge>
              )}
            </Button>

            {/* User dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-cyan-100 text-sm font-medium text-cyan-700">
                    {user.full_name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .toUpperCase()
                      .slice(0, 2)}
                  </div>
                  <div className="hidden text-left md:block">
                    <p className="text-sm font-medium text-gray-900">
                      {user.full_name}
                    </p>
                    <p className="text-xs text-gray-500">{userRole}</p>
                  </div>
                  <ChevronDown className="h-4 w-4 text-gray-400" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <div>
                    <p className="text-sm font-medium">{user.full_name}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled>
                  <span className="text-xs text-muted-foreground">
                    Role: {userRole}
                  </span>
                </DropdownMenuItem>
                <DropdownMenuItem disabled>
                  <span className="text-xs text-muted-foreground">
                    Org: {organizationName}
                  </span>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {supportModeActive && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-amber-900">
                  Support mode active
                </p>
                <p className="text-sm text-amber-700">
                  Tenant context: {supportMode.tenantName ?? `Tenant #${supportMode.tenantId ?? "unknown"}`}
                </p>
                {supportError && (
                  <p className="mt-1 text-xs text-red-700">{supportError}</p>
                )}
              </div>
              <Button
                variant="outline"
                onClick={() => void handleEndSupportMode()}
                disabled={supportEnding}
              >
                {supportEnding ? "Ending..." : "Exit Support Mode"}
              </Button>
            </div>
          </div>
        )}

        {/* Page content with optional copilot panel */}
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-y-auto p-6">{children}</main>

          {/* AI Copilot Panel */}
          <AICopilot
            open={copilotOpen}
            onClose={() => setCopilotOpen(false)}
          />
          {/* AI action handlers (open_dialog / highlight event listeners) */}
          <AIActionHandlers />
        </div>
      </div>
    </div>
  );
}
