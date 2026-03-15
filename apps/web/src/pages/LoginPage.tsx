import { useEffect, useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/authStore'
import { apiClient } from '@/api/client'
import { IconUser } from '@/components/ui'
import styles from './LoginPage.module.css'

export function LoginPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const login = useAuthStore((s) => s.login)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Get redirect URL from query params (set when user was logged out)
  const redirectUrl = searchParams.get('redirect')

  // Smart redirect based on user role OR saved redirect URL
  useEffect(() => {
    if (isAuthenticated) {
      const user = useAuthStore.getState().user
      
      // If there's a saved redirect URL, use it (return user where they were)
      if (redirectUrl) {
        navigate(redirectUrl, { replace: true })
        return
      }
      
      // Otherwise, use role-based default redirect:
      // 1. Superuser → Platform Dashboard
      if (user?.isSuperuser) {
        navigate('/admin/platform', { replace: true })
        return
      }
      
      // 2. Corporate Lead → Company management
      const isCorporateLead = user?.memberships.some(m => m.isActive && m.isCorporateLead)
      if (isCorporateLead) {
        navigate('/company/members', { replace: true })
        return
      }
      
      // 3. All other roles (Editor, Viewer, Auditor, etc.) → Reports
      navigate('/reports', { replace: true })
    }
  }, [isAuthenticated, navigate, redirectUrl])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      // Note: refresh_token is set as httpOnly cookie by backend
      const response = await apiClient.post<{
        access_token: string
        token_type: string
        expires_in: number
        user: {
          user_id: string
          email: string
          full_name: string
          is_active: boolean
          is_superuser: boolean
          companies: {
            company_id: string
            company_name: string
            is_corporate_lead: boolean
            is_active: boolean
            roles: string[]
          }[]
        }
      }>('/api/v1/auth/login', {
        email,
        password,
      }, { credentials: 'include' })

      const { user, access_token } = response.data
      // Note: refresh_token is set as httpOnly cookie by backend
      login(
        {
          userId: user.user_id,
          email: user.email,
          fullName: user.full_name,
          isSuperuser: user.is_superuser ?? false,
          memberships: (user.companies || []).map((c) => ({
            companyId: c.company_id,
            companyName: c.company_name,
            isCorporateLead: c.is_corporate_lead ?? false,
            isActive: c.is_active,
            roles: c.roles || [],
          })),
        },
        access_token
      )
      // Navigation handled by useEffect
    } catch (err) {
      setError(t('login.invalidCredentials'))
    } finally {
      setLoading(false)
    }
  }

  // Demo login for development - uses real API with test user
  const handleDemoLogin = async () => {
    setError(null)
    setLoading(true)

    try {
      const response = await apiClient.post<{
        access_token: string
        token_type: string
        expires_in: number
        user: {
          user_id: string
          email: string
          full_name: string
          is_active: boolean
          is_superuser: boolean
          companies: {
            company_id: string
            company_name: string
            is_corporate_lead: boolean
            is_active: boolean
            roles: string[]
          }[]
        }
      }>('/api/v1/auth/login', {
        email: 'e2e-test@example.com',
        password: 'TestPassword123!',
      }, { credentials: 'include' })

      const { user, access_token } = response.data
      // Note: refresh_token is set as httpOnly cookie by backend
      login(
        {
          userId: user.user_id,
          email: user.email,
          fullName: user.full_name,
          isSuperuser: user.is_superuser ?? false,
          memberships: (user.companies || []).map((c) => ({
            companyId: c.company_id,
            companyName: c.company_name,
            isCorporateLead: c.is_corporate_lead ?? false,
            isActive: c.is_active,
            roles: c.roles || [],
          })),
        },
        access_token
      )
      // Navigation handled by useEffect
    } catch (err) {
      setError(t('login.demoLoginFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <h1 className={styles.title}>ESGvist</h1>
          <p className={styles.subtitle}>ESG Data Dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && <div className={styles.error}>{error}</div>}

          <div className={styles.field}>
            <label htmlFor="email" className={styles.label}>
              {t('login.email')}
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={styles.input}
              placeholder="user@company.com"
              required
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password" className={styles.label}>
              {t('login.password')}
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={styles.input}
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            className={styles.button}
            disabled={loading}
          >
            {loading ? t('login.signingIn') : t('login.signin')}
          </button>

          <button
            type="button"
            onClick={handleDemoLogin}
            className={styles.demoButton}
          >
            {t('login.demoLogin')}
          </button>

          <Link to="/login/corporate-lead" className={styles.demoButton} style={{ textAlign: 'center', textDecoration: 'none' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', justifyContent: 'center' }}>
              <IconUser size={16} />
              {t('login.useCorporateLead')}
            </span>
          </Link>
        </form>

        {import.meta.env.DEV && (
          <div style={{
            marginTop: '1rem',
            padding: '0.75rem',
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            borderRadius: '8px',
            fontSize: '0.75rem',
            color: '#334155',
          }}>
            <div style={{ fontWeight: 600, marginBottom: '0.5rem', color: '#16a34a' }}>
              Test Accounts
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.7rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #bbf7d0' }}>
                  <th style={{ textAlign: 'left', padding: '2px 4px' }}>Role</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px' }}>Email</th>
                  <th style={{ textAlign: 'left', padding: '2px 4px' }}>Password</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: '2px 4px' }}>Platform Admin</td>
                  <td style={{ padding: '2px 4px' }}>e2e-test@example.com</td>
                  <td style={{ padding: '2px 4px' }}>TestPassword123!</td>
                </tr>
                <tr style={{ borderTop: '1px solid #dcfce7' }}>
                  <td colSpan={3} style={{ padding: '4px 4px 2px', fontWeight: 600, color: '#16a34a', fontSize: '0.65rem' }}>
                    KazEnergo JSC
                  </td>
                </tr>
                <tr>
                  <td style={{ padding: '2px 4px' }}>Corporate Lead</td>
                  <td style={{ padding: '2px 4px' }}>lead@kazenergo.kz</td>
                  <td style={{ padding: '2px 4px' }}>KazEnergy2024!</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
