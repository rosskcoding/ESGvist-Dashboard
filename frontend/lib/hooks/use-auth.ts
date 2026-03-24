"use client";

import { useState, useEffect, useCallback } from "react";
import { getMe } from "@/lib/auth";
import { api } from "@/lib/api";

interface UserRole {
  id: number;
  role: string;
  scope_type: string;
  scope_id: number | null;
}

interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: UserRole[];
}

interface UseAuthReturn {
  user: AuthUser | null;
  role: string;
  organizationId: string | null;
  isLoading: boolean;
  setOrganizationId: (id: string) => void;
  refetch: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [organizationId, setOrganizationIdState] = useState<string | null>(null);

  const fetchUser = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    const orgRole = user?.roles?.find(
      (binding) => binding.scope_type === "organization" && binding.scope_id
    );
    if (orgRole?.scope_id) {
      setOrganizationIdState(String(orgRole.scope_id));
      return;
    }
    setOrganizationIdState(null);
  }, [user]);

  const setOrganizationId = useCallback((id: string) => {
    setOrganizationIdState(id);
    void api.post("/auth/context/organization", {
      organization_id: Number(id),
    });
  }, []);

  const role =
    user?.roles?.find((binding) => binding.scope_type === "organization")?.role
    ?? user?.roles?.[0]?.role
    ?? "";

  return {
    user,
    role,
    organizationId,
    isLoading,
    setOrganizationId,
    refetch: fetchUser,
  };
}
