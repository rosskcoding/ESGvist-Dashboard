"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { isAuthenticated, getMe, logout } from "@/lib/auth";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
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
      { label: "Collection", href: "/collection", icon: ClipboardList },
      { label: "Validation", href: "/validation", icon: CheckSquare },
      { label: "Merge View", href: "/merge", icon: GitMerge },
    ],
  },
  {
    title: "Reporting",
    items: [
      { label: "Projects", href: "/projects", icon: FolderKanban },
      { label: "Completeness", href: "/completeness", icon: PieChart },
      { label: "Report / Export", href: "/reports", icon: FileOutput },
    ],
  },
  {
    title: "Settings",
    items: [
      { label: "Company Structure", href: "/settings/structure", icon: Building2 },
      { label: "Assignments", href: "/settings/assignments", icon: UserCog },
      { label: "Standards", href: "/settings/standards", icon: BookOpen },
      { label: "Shared Elements", href: "/settings/shared-elements", icon: Share2 },
      { label: "Users", href: "/settings/users", icon: Users },
      { label: "Boundaries", href: "/settings/boundaries", icon: Map },
      { label: "Webhooks", href: "/settings/webhooks", icon: Webhook },
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
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [copilotOpen, setCopilotOpen] = useState(false);

  const userRole = user?.roles?.[0]?.role ?? "";
  const organizationName = "Organization";

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  const fetchUnread = useCallback(async () => {
    try {
      const data = await api.get<{ count: number }>("/notifications/unread-count");
      setUnreadCount(data.count);
    } catch {
      // silently ignore
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    fetchUnread();
    const interval = setInterval(fetchUnread, 30_000);
    return () => clearInterval(interval);
  }, [user, fetchUnread]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const isPlatformAdmin = user?.roles?.some((r) => r.role === "platform_admin") ?? false;

  if (!user) {
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
          <Link href="/dashboard" className="text-xl font-bold text-gray-900">
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
                    const isActive =
                      pathname === item.href ||
                      pathname.startsWith(item.href + "/");
                    const Icon = item.icon;

                    return (
                      <Link
                        key={item.href}
                        href={item.href}
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
            <Button variant="ghost" size="icon" className="relative">
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

        {/* Page content with optional copilot panel */}
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-y-auto p-6">{children}</main>

          {/* AI Copilot Panel */}
          {copilotOpen && (
            <aside className="w-80 border-l border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-900">
                  AI Copilot
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCopilotOpen(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  &times;
                </Button>
              </div>
              <div className="mt-4 flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 py-12 text-center">
                <BotMessageSquare className="h-8 w-8 text-gray-300" />
                <p className="mt-2 text-sm text-muted-foreground">
                  AI assistant coming soon
                </p>
              </div>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
