"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated, getMe, logout } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<{ full_name: string; email: string } | null>(
    null
  );

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push("/login");
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 border-r border-gray-200 bg-white">
        <div className="flex h-16 items-center border-b border-gray-200 px-6">
          <h1 className="text-xl font-bold text-gray-900">ESGvist</h1>
        </div>
        <nav className="mt-4 space-y-1 px-3">
          <a
            href="/dashboard"
            className="flex items-center rounded-lg bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700"
          >
            Dashboard
          </a>
        </nav>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col">
        {/* Topbar */}
        <header className="flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
          <div />
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user.full_name}</span>
            <button
              onClick={handleLogout}
              className="rounded-lg px-3 py-1.5 text-sm text-gray-500 hover:bg-gray-100"
            >
              Logout
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
