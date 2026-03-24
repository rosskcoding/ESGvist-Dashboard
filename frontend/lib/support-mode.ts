"use client";

const SUPPORT_TENANT_ID_KEY = "support_tenant_id";
const SUPPORT_TENANT_NAME_KEY = "support_tenant_name";
const SUPPORT_MODE_EVENT = "support-mode-changed";

export type SupportModeState = {
  active: boolean;
  tenantId: string | null;
  tenantName: string | null;
};

function emitSupportModeChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(SUPPORT_MODE_EVENT));
}

export function readSupportMode(): SupportModeState {
  if (typeof window === "undefined") {
    return { active: false, tenantId: null, tenantName: null };
  }

  const tenantId = localStorage.getItem(SUPPORT_TENANT_ID_KEY);
  return {
    active: Boolean(tenantId),
    tenantId,
    tenantName: localStorage.getItem(SUPPORT_TENANT_NAME_KEY),
  };
}

export function startSupportMode(tenantId: number, tenantName: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(SUPPORT_TENANT_ID_KEY, String(tenantId));
  localStorage.setItem(SUPPORT_TENANT_NAME_KEY, tenantName);
  emitSupportModeChange();
}

export function stopSupportMode() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SUPPORT_TENANT_ID_KEY);
  localStorage.removeItem(SUPPORT_TENANT_NAME_KEY);
  emitSupportModeChange();
}

export function clearSupportModeForLogout() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SUPPORT_TENANT_ID_KEY);
  localStorage.removeItem(SUPPORT_TENANT_NAME_KEY);
  emitSupportModeChange();
}

export function subscribeSupportMode(listener: () => void) {
  if (typeof window === "undefined") {
    return () => undefined;
  }

  window.addEventListener(SUPPORT_MODE_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(SUPPORT_MODE_EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}
