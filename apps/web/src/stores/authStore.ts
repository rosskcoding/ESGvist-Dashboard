/**
 * Authentication Store
 * 
 * Security:
 * - Access token stored in memory (cleared on tab close)
 * - Refresh token stored in httpOnly cookie (handled by browser, XSS-safe)
 * - User info persisted for UI purposes
 */

import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

interface CompanyMembershipInfo {
  companyId: string
  companyName: string
  isCorporateLead: boolean
  isActive: boolean
  roles: string[]
}

interface User {
  userId: string
  email: string
  fullName: string
  isSuperuser: boolean
  memberships: CompanyMembershipInfo[]
}

// Roles that grant edit permissions (per RBAC spec)
const EDITOR_ROLES = ['editor', 'content_editor', 'section_editor']
// Read-only roles (viewer, auditor, etc.)
const READONLY_ROLES = ['viewer', 'internal_auditor', 'auditor', 'audit_lead', 'corporate_lead', 'translator']

/**
 * Permission helper: can user edit content?
 * 
 * Now uses roles[] from UserCompanyDTO for accurate RBAC checks.
 * - Superuser: YES (always)
 * - Has editor/content_editor/section_editor role: YES
 * - Only has viewer/auditor/corporate_lead roles: NO
 * - No roles data (legacy): YES (fail-open, backend enforces)
 */
export function canEditContent(user: User | null): boolean {
  if (!user) return false
  if (user.isSuperuser) return true
  
  // Get all roles across all active memberships
  const userRoles = user.memberships
    .filter(m => m.isActive)
    .flatMap(m => m.roles || [])
  
  // If no roles data available, fail-open (legacy behavior)
  if (userRoles.length === 0) return true
  
  // Check if user has any editor role
  const hasEditorRole = userRoles.some(role => EDITOR_ROLES.includes(role))
  if (hasEditorRole) return true
  
  // Explicit read-only roles
  const hasReadonlyRole = userRoles.some(role => READONLY_ROLES.includes(role))
  if (hasReadonlyRole) return false

  // Unknown roles only: fail-open, backend enforces
  return true
}

/**
 * Check if user is a Corporate Lead for any company
 */
export function isCorporateLead(user: User | null): boolean {
  if (!user) return false
  return user.memberships.some(m => m.isCorporateLead && m.isActive)
}

/**
 * Get roles for a specific company (from login payload).
 * If roles are missing (legacy / fail-open), returns [].
 */
export function getCompanyRoles(user: User | null, companyId: string): string[] {
  if (!user || !companyId) return []
  const membership = user.memberships.find((m) => m.isActive && m.companyId === companyId)
  return membership?.roles || []
}

/**
 * Can user open translation UI (read translation status/progress)?
 *
 * NOTE: We intentionally fail-open if roles are missing, because backend is source of truth.
 */
export function canViewTranslations(user: User | null, companyId: string): boolean {
  if (!user) return false
  if (user.isSuperuser) return true

  const roles = getCompanyRoles(user, companyId)
  if (roles.length === 0) return true // fail-open (legacy)

  const allowed = new Set(['translator', 'editor', 'content_editor', 'corporate_lead', 'viewer'])
  return roles.some((r) => allowed.has(r))
}

/**
 * Can user trigger expensive auto-translate job?
 *
 * Default (restricted): Translator + Corporate Lead.
 * If backend is configured as unrestricted, backend will still allow additional roles.
 * UI keeps conservative default.
 */
export function canTriggerTranslations(user: User | null, companyId: string): boolean {
  if (!user) return false
  if (user.isSuperuser) return true

  const roles = getCompanyRoles(user, companyId)
  if (roles.length === 0) return true // fail-open (legacy)

  const allowed = new Set(['translator', 'corporate_lead'])
  return roles.some((r) => allowed.has(r))
}

/**
 * Can user create draft build?
 *
 * Backend permission: release:create_draft
 * Allowed roles: editor (or superuser).
 */
export function canCreateDraftBuild(user: User | null, companyId: string): boolean {
  if (!user) return false
  if (user.isSuperuser) return true

  const roles = getCompanyRoles(user, companyId)
  if (roles.length === 0) return true // fail-open (legacy)

  return roles.includes('editor')
}

/**
 * Can user create release build?
 *
 * Backend permission: release:create_release
 * Allowed roles: corporate_lead (or superuser).
 */
export function canCreateReleaseBuild(user: User | null, companyId: string): boolean {
  if (!user) return false
  if (user.isSuperuser) return true

  const roles = getCompanyRoles(user, companyId)
  if (roles.length === 0) return true // fail-open (legacy)

  return roles.includes('corporate_lead')
}

/**
 * ESG RBAC helpers.
 *
 * Backend permissions:
 * - esg:write  => corporate_lead, editor, content_editor, section_editor
 * - esg:publish => corporate_lead, editor
 *
 * UI remains fail-open if roles/membership are missing; backend is source of truth.
 */
export function canWriteEsg(user: User | null, companyId: string): boolean {
  if (!user) return false
  if (user.isSuperuser) return true
  if (!companyId) return true // fail-open (legacy)

  const membership = user.memberships.find((m) => m.isActive && m.companyId === companyId)
  if (!membership) return true // fail-open (legacy)
  if (membership.isCorporateLead) return true

  const roles = membership.roles || []
  if (roles.length === 0) return true // fail-open (legacy)

  const allowed = new Set(['editor', 'content_editor', 'section_editor'])
  return roles.some((r) => allowed.has(r))
}

export function canPublishEsg(user: User | null, companyId: string): boolean {
  if (!user) return false
  if (user.isSuperuser) return true
  if (!companyId) return true // fail-open (legacy)

  const membership = user.memberships.find((m) => m.isActive && m.companyId === companyId)
  if (!membership) return true // fail-open (legacy)
  if (membership.isCorporateLead) return true

  const roles = membership.roles || []
  if (roles.length === 0) return true // fail-open (legacy)

  return roles.includes('editor')
}

interface AuthState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  _hasHydrated: boolean
  
  // Actions
  login: (user: User, accessToken: string) => void
  setAccessToken: (accessToken: string) => void
  logout: () => void
  setHasHydrated: (value: boolean) => void
  
  // Backward compatibility (deprecated)
  /** @deprecated Use login(user, accessToken) instead */
  refreshToken: string | null
  /** @deprecated Use setAccessToken instead */
  setTokens: (accessToken: string, refreshToken?: string) => void
}

function canUseWebStorage(): boolean {
  // In tests/SSR, `window` might not exist or storage can be partially implemented.
  // Persist middleware requires a Storage-like interface with getItem/setItem/removeItem.
  try {
    if (typeof window === 'undefined') return false
    const storage = window.localStorage
    return (
      !!storage &&
      typeof storage.getItem === 'function' &&
      typeof storage.setItem === 'function' &&
      typeof storage.removeItem === 'function'
    )
  } catch {
    return false
  }
}

const createAuthStore = (set: (fn: (state: AuthState) => Partial<AuthState>) => void): AuthState => ({
  user: null,
  accessToken: null,
  refreshToken: null, // Deprecated - kept for backward compatibility
  isAuthenticated: false,
  _hasHydrated: false,
  
  login: (user, accessToken) =>
    set(() => ({
      user,
      accessToken,
      isAuthenticated: true,
    })),
  
  setAccessToken: (accessToken) =>
    set(() => ({
      accessToken,
    })),
  
  // Backward compatibility
  setTokens: (accessToken) =>
    set(() => ({
      accessToken,
      // Don't store refresh token anymore - it's in httpOnly cookie
    })),
  
  logout: () =>
    set(() => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    })),
  
  setHasHydrated: (value) => set(() => ({ _hasHydrated: value })),
})

export const useAuthStore = create<AuthState>()(
  canUseWebStorage()
    ? persist(
        createAuthStore,
        {
          name: 'auth-storage',
          // Use window.localStorage explicitly to avoid Node.js (v25+) experimental
          // `globalThis.localStorage` collisions in test environments.
          storage: createJSONStorage(() => window.localStorage),
          partialize: (state) => ({
            // Only persist user info and isAuthenticated flag
            // Access token is NOT persisted (security)
            user: state.user,
            isAuthenticated: state.isAuthenticated,
            // Note: accessToken is intentionally excluded from persistence
            // It will be refreshed on page load using httpOnly cookie
          }),
          onRehydrateStorage: () => (state) => {
            state?.setHasHydrated(true)
            // If we have user but no accessToken after rehydration,
            // we'll need to refresh the token
            if (state?.isAuthenticated && !state?.accessToken) {
              // Token refresh will happen on first API call
              // See client.ts refreshTokens()
            }
          },
        }
      )
    : createAuthStore
)
