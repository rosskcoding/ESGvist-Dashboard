"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { logout } from "@/lib/auth";
import { api, isAppApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useApiQuery } from "@/lib/hooks/use-api";
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

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  requiredRoles?: string[];
}

interface NavGroup {
  title: string;
  items: NavItem[];
  requiredRole?: string;
}

const navGroups: NavGroup[] = [
  {
    title: "Main",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
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
        requiredRoles: ["admin", "esg_manager", "platform_admin"],
      },
      {
        label: "Audit Log",
        href: "/audit",
        icon: ScrollText,
        requiredRoles: ["admin", "auditor", "platform_admin"],
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
        label: "Standards",
        href: "/settings/standards",
        icon: BookOpen,
        requiredRoles: ["admin", "platform_admin"],
      },
      {
        label: "Shared Elements",
        href: "/settings/shared-elements",
        icon: Share2,
        requiredRoles: ["admin", "platform_admin"],
      },
      {
        label: "Mapping History",
        href: "/settings/mappings",
        icon: GitMerge,
        requiredRoles: ["admin", "platform_admin"],
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
    requiredRole: "platform_admin",
    items: [
      { label: "Tenants", href: "/platform/tenants", icon: Server },
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

function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
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
  const [supportMode, setSupportMode] = useState<SupportModeState>(() => readSupportMode());
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
  const organizationName = "Organization";
  const canAccessNotifications = userRoles.some((role) => role !== "auditor");
  const unreadQueryEnabled = mounted && Boolean(user) && canAccessNotifications && orgContextReady;

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
      return;
    }
    if (supportMode.active) {
      setOrgContextReady(true);
      return;
    }

    const orgRole = user.roles.find(
      (role) => role.scope_type === "organization" && role.scope_id
    );
    if (!orgRole?.scope_id) {
      setOrgContextReady(false);
      return;
    }

    let cancelled = false;
    setOrgContextReady(false);
    void api
      .post("/auth/context/organization", {
        organization_id: orgRole.scope_id,
      })
      .then(() => {
        if (!cancelled) {
          setOrgContextReady(true);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setOrgContextReady(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [mounted, supportMode.active, user]);

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

  const isPlatformAdmin = user?.roles?.some((r) => r.role === "platform_admin") ?? false;
  const hasOrganizationRole =
    user?.roles?.some((role) => role.scope_type === "organization" && role.scope_id) ?? false;
  const supportModeActive = supportMode.active;

  useEffect(() => {
    if (!user || isPlatformAdmin || hasOrganizationRole) return;
    if (pathname !== "/onboarding") {
      router.push("/onboarding");
    }
  }, [hasOrganizationRole, isPlatformAdmin, pathname, router, user]);

  if (!mounted || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-gray-200 bg-white">
        <div className="flex h-16 items-center border-b border-gray-200 px-6">
          <Link href="/dashboard" prefetch={false} className="text-xl font-bold text-gray-900">
            ESGvist
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          {navGroups.map((group) => {
            if (group.requiredRole && !isPlatformAdmin) return null;

            return (
              <div key={group.title} className="mb-6 px-3">
                <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                  {group.title}
                </p>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    if (!hasRequiredRole(item.requiredRoles)) {
                      return null;
                    }
                    const isActive =
                      pathname === item.href ||
                      (item.href !== "/settings" && pathname.startsWith(item.href + "/"));
                    const Icon = item.icon;

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        prefetch={false}
                        className={cn(
                          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-blue-50 text-blue-700"
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
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-sm font-medium text-blue-700">
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
