"use client";

const SUPPORT_MODE_EVENT = "support-mode-changed";

let supportModeState: SupportModeState = {
  active: false,
  tenantId: null,
  tenantName: null,
};

export type SupportModeState = {
  active: boolean;
  tenantId: string | null;
  tenantName: string | null;
};

type SupportModeSyncInput = {
  active: boolean;
  tenantId?: string | number | null;
  tenantName?: string | null;
};

function emitSupportModeChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(SUPPORT_MODE_EVENT));
}

export function readSupportMode(): SupportModeState {
  return { ...supportModeState };
}

export function syncSupportModeState(state: SupportModeSyncInput) {
  if (typeof window === "undefined") return;
  const current = readSupportMode();
  const tenantId =
    state.active && state.tenantId !== null && state.tenantId !== undefined
      ? String(state.tenantId)
      : null;
  const tenantName = state.active ? state.tenantName ?? null : null;
  const changed =
    current.active !== Boolean(tenantId) ||
    current.tenantId !== tenantId ||
    current.tenantName !== tenantName;

  supportModeState = {
    active: Boolean(tenantId),
    tenantId,
    tenantName,
  };

  if (changed) {
    emitSupportModeChange();
  }
}

export function startSupportMode(tenantId: number, tenantName: string) {
  if (typeof window === "undefined") return;
  syncSupportModeState({ active: true, tenantId, tenantName });
}

export function stopSupportMode() {
  if (typeof window === "undefined") return;
  syncSupportModeState({ active: false });
}

export function clearSupportModeForLogout() {
  if (typeof window === "undefined") return;
  syncSupportModeState({ active: false });
}

/**
 * Validate that the local support mode state matches the server.
 * Clears local state if the server has no active session (e.g. after
 * restart, logout/login as different user, or session expiry).
 */
export async function validateSupportModeWithServer(
  fetchFn: (url: string) => Promise<Response> = fetch,
): Promise<SupportModeState> {
  const local = readSupportMode();
  if (!local.active) return local;

  try {
    const resp = await fetchFn("/api/platform/support-session/current");
    if (!resp.ok) {
      // Server says no active session — clear stale local state
      stopSupportMode();
      return { active: false, tenantId: null, tenantName: null };
    }
    const data = await resp.json();
    if (!data || !data.session_id) {
      stopSupportMode();
      return { active: false, tenantId: null, tenantName: null };
    }
    // Sync local state with server truth
    syncSupportModeState({
      active: true,
      tenantId: data.tenant_id,
      tenantName: data.tenant_name,
    });
    return readSupportMode();
  } catch {
    // Network error — keep local state as-is
    return local;
  }
}

export function subscribeSupportMode(listener: () => void) {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  window.addEventListener(SUPPORT_MODE_EVENT, listener);
  return () => {
    window.removeEventListener(SUPPORT_MODE_EVENT, listener);
  };
}
