import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { LoginPage } from './pages/LoginPage'
import { StartPage } from './pages/StartPage'
import { CorporateLeadLoginPage } from './pages/CorporateLeadLoginPage'
import { EsgDashboardPage } from './pages/EsgDashboardPage'
import { EsgMetricsPage } from './pages/esg/EsgMetricsPage'
import { EsgFactsPage } from './pages/esg/EsgFactsPage'
import { EsgFactCreatePage } from './pages/esg/EsgFactCreatePage'
import { EsgGapsPage } from './pages/esg/EsgGapsPage'
import { EsgSnapshotPage } from './pages/esg/EsgSnapshotPage'
import { EsgDataPage } from './pages/esg/EsgDataPage'
import { EsgReviewPage } from './pages/esg/EsgReviewPage'
import { EsgEvidencePage } from './pages/esg/EsgEvidencePage'
import {
  CompaniesPage,
  CompanyMembersPage,
  CompanyRolesPage,
  UsersPage,
  MyCompanyPage,
  MyCompanyMembersPage,
  MyCompanyRolesPage,
  SuperuserDashboardPage,
} from './pages/admin'
import { ToastContainer, LanguageSwitcher } from './components/ui'
import { useAuthStore } from './stores/authStore'

function FullPageLoader() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#ffffff',
        color: '#64748b',
        fontSize: '0.95rem',
      }}
    >
      Loading...
    </div>
  )
}

/**
 * Helper to create login redirect URL preserving the current path
 */
function useLoginRedirect() {
  const location = useLocation()
  const currentPath = location.pathname + location.search
  if (currentPath === '/login' || currentPath === '/start' || currentPath === '/') {
    return '/login'
  }
  return `/login?redirect=${encodeURIComponent(currentPath)}`
}

/**
 * Read CSRF token from cookie
 */
function getCsrfToken(): string | null {
  if (typeof document === 'undefined') return null

  const cookies = document.cookie.split(';')
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=')
    if (name === 'csrf_token') {
      return decodeURIComponent(value)
    }
  }
  return null
}

/**
 * Hook to ensure we have a valid access token after page reload.
 */
function useEnsureAccessToken() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const accessToken = useAuthStore((s) => s.accessToken)
  const hasHydrated = useAuthStore((s) => s._hasHydrated)
  const logout = useAuthStore((s) => s.logout)
  const setAccessToken = useAuthStore((s) => s.setAccessToken)

  const [isRefreshing, setIsRefreshing] = useState(false)
  const [refreshAttempted, setRefreshAttempted] = useState(false)

  useEffect(() => {
    if (hasHydrated && isAuthenticated && !accessToken && !refreshAttempted && !isRefreshing) {
      setIsRefreshing(true)

      const csrfToken = getCsrfToken()

      fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({}),
      })
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json()
            setAccessToken(data.access_token)
          } else {
            logout()
          }
        })
        .catch(() => {
          logout()
        })
        .finally(() => {
          setIsRefreshing(false)
          setRefreshAttempted(true)
        })
    }
  }, [hasHydrated, isAuthenticated, accessToken, refreshAttempted, isRefreshing, logout, setAccessToken])

  const isReady = !hasHydrated || !isAuthenticated || !!accessToken || refreshAttempted

  return { isReady, isRefreshing }
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const hasHydrated = useAuthStore((s) => s._hasHydrated)
  const loginRedirect = useLoginRedirect()
  const { isReady, isRefreshing } = useEnsureAccessToken()

  if (!hasHydrated) return <FullPageLoader />
  if (!isReady || isRefreshing) return <FullPageLoader />
  if (!isAuthenticated) return <Navigate to={loginRedirect} replace />

  return <>{children}</>
}

function SuperuserRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isSuperuser = useAuthStore((s) => s.user?.isSuperuser)
  const hasHydrated = useAuthStore((s) => s._hasHydrated)
  const loginRedirect = useLoginRedirect()
  const { isReady, isRefreshing } = useEnsureAccessToken()

  if (!hasHydrated) return <FullPageLoader />
  if (!isReady || isRefreshing) return <FullPageLoader />
  if (!isAuthenticated) return <Navigate to={loginRedirect} replace />
  if (!isSuperuser) return <Navigate to="/esg" replace />

  return <>{children}</>
}

function CompanyAdminRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const hasHydrated = useAuthStore((s) => s._hasHydrated)
  const memberships = useAuthStore((s) => s.user?.memberships || [])
  const loginRedirect = useLoginRedirect()
  const { isReady, isRefreshing } = useEnsureAccessToken()

  if (!hasHydrated) return <FullPageLoader />
  if (!isReady || isRefreshing) return <FullPageLoader />
  if (!isAuthenticated) return <Navigate to={loginRedirect} replace />

  const isCompanyAdmin = memberships.some((m) => m.isActive && m.isCorporateLead)
  if (!isCompanyAdmin) return <Navigate to="/esg" replace />

  return <>{children}</>
}

export default function App() {
  return (
    <>
      <ToastContainer />
      <LanguageSwitcher />
      <Routes>
        <Route path="/start" element={<StartPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/login/corporate-lead" element={<CorporateLeadLoginPage />} />

        {/* ESG Dashboard */}
        <Route path="/esg" element={<ProtectedRoute><EsgDashboardPage /></ProtectedRoute>} />
        <Route path="/esg/metrics" element={<ProtectedRoute><EsgMetricsPage /></ProtectedRoute>} />
        <Route path="/esg/data" element={<ProtectedRoute><EsgDataPage /></ProtectedRoute>} />
        <Route path="/esg/review" element={<ProtectedRoute><EsgReviewPage /></ProtectedRoute>} />
        <Route path="/esg/evidence" element={<ProtectedRoute><EsgEvidencePage /></ProtectedRoute>} />
        <Route path="/esg/facts" element={<ProtectedRoute><EsgFactsPage /></ProtectedRoute>} />
        <Route path="/esg/facts/new" element={<ProtectedRoute><EsgFactCreatePage /></ProtectedRoute>} />
        <Route path="/esg/gaps" element={<ProtectedRoute><EsgGapsPage /></ProtectedRoute>} />
        <Route path="/esg/snapshot" element={<ProtectedRoute><EsgSnapshotPage /></ProtectedRoute>} />

        {/* Platform Admin (superuser) */}
        <Route path="/admin/platform" element={<SuperuserRoute><SuperuserDashboardPage /></SuperuserRoute>} />
        <Route path="/admin/platform/companies/:companySlug/members" element={<SuperuserRoute><CompanyMembersPage /></SuperuserRoute>} />
        <Route path="/admin/platform/companies/:companySlug/roles" element={<SuperuserRoute><CompanyRolesPage /></SuperuserRoute>} />
        <Route path="/admin/companies" element={<SuperuserRoute><CompaniesPage /></SuperuserRoute>} />
        <Route path="/admin/companies/:companyId/members" element={<SuperuserRoute><CompanyMembersPage /></SuperuserRoute>} />
        <Route path="/admin/companies/:companyId/roles" element={<SuperuserRoute><CompanyRolesPage /></SuperuserRoute>} />
        <Route path="/admin/users" element={<SuperuserRoute><UsersPage /></SuperuserRoute>} />

        {/* Company Admin (corporate lead) */}
        <Route path="/company" element={<CompanyAdminRoute><MyCompanyPage /></CompanyAdminRoute>} />
        <Route path="/company/members" element={<CompanyAdminRoute><MyCompanyMembersPage /></CompanyAdminRoute>} />
        <Route path="/company/roles" element={<CompanyAdminRoute><MyCompanyRolesPage /></CompanyAdminRoute>} />

        {/* Default redirect to ESG dashboard */}
        <Route path="/" element={<Navigate to="/esg" replace />} />
        <Route path="*" element={<Navigate to="/esg" replace />} />
      </Routes>
    </>
  )
}
