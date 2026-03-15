import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/authStore'
import { apiClient } from '@/api/client'
import {
  IconBuilding,
  IconChartBar,
  IconCheck,
  IconEye,
  IconFolder,
  IconLightbulb,
  IconLock,
  IconMapPin,
  IconPackage,
  IconSettings,
  IconUser,
  IconUsers,
  IconX,
  IconZap,
} from '@/components/ui'
import styles from './CorporateLeadLoginPage.module.css'

const DEMO_CREDENTIALS = {
  email: 'lead@kazenergo.kz',
  password: 'KazEnergy2024!',
  company: 'JSC "KazEnergo"',
  fullName: 'Corporate Lead Demo',
}

export function CorporateLeadLoginPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const [email, setEmail] = useState(DEMO_CREDENTIALS.email)
  const [password, setPassword] = useState(DEMO_CREDENTIALS.password)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Smart redirect based on user role
  useEffect(() => {
    if (isAuthenticated) {
      const user = useAuthStore.getState().user
      
      // 1. Superuser → Admin panel
      if (user?.isSuperuser) {
        navigate('/admin/companies', { replace: true })
        return
      }
      
      // 2. Corporate Lead → Company management
      const isCorporateLead = user?.memberships.some(m => m.isActive && m.isCorporateLead)
      if (isCorporateLead) {
        navigate('/company/members', { replace: true })
        return
      }
      
      // 3. All other roles → Reports
      navigate('/reports', { replace: true })
    }
  }, [isAuthenticated, navigate])

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
      setError(t('corporateLead.errors.invalidCredentials'))
    } finally {
      setLoading(false)
    }
  }

  const handleQuickLogin = async () => {
    setEmail(DEMO_CREDENTIALS.email)
    setPassword(DEMO_CREDENTIALS.password)
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
        email: DEMO_CREDENTIALS.email,
        password: DEMO_CREDENTIALS.password,
      }, { credentials: 'include' })

      const { user, access_token } = response.data
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
    } catch (err) {
      setError(t('corporateLead.errors.quickLoginFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.container}>
      <div className={styles.content}>
        {/* Left side - Info */}
        <div className={styles.infoPanel}>
          <div className={styles.roleHeader}>
            <span className={styles.roleIcon} aria-hidden="true">
              <IconUser size={20} />
            </span>
            <div>
              <h1 className={styles.roleTitle}>{t('corporateLead.roleTitle')}</h1>
              <p className={styles.roleSubtitle}>{t('corporateLead.roleSubtitle')}</p>
            </div>
          </div>

          <div className={styles.infoSection}>
            <h2 className={styles.sectionTitle}>
              <span className={styles.sectionIcon} aria-hidden="true">
                <IconMapPin size={18} />
              </span>
              {t('corporateLead.where.title')}
            </h2>
            <p className={styles.sectionText}>
              {t('corporateLead.where.text')}
            </p>
          </div>

          <div className={styles.infoSection}>
            <h2 className={styles.sectionTitle}>
              <span className={styles.sectionIcon} aria-hidden="true">
                <IconCheck size={18} />
              </span>
              {t('corporateLead.implemented.title')}
            </h2>
            <ul className={styles.permissionsList}>
              <li>
                <span className={styles.permissionIcon} aria-hidden="true">
                  <IconUsers size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.implemented.teamTitle')}</strong>
                  <p>{t('corporateLead.implemented.teamDescription')}</p>
                </div>
              </li>
              <li>
                <span className={styles.permissionIcon} aria-hidden="true">
                  <IconEye size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.implemented.contentTitle')}</strong>
                  <p>{t('corporateLead.implemented.contentDescription')}</p>
                </div>
              </li>
            </ul>
          </div>

          <div className={styles.infoSection}>
            <h2 className={styles.sectionTitle}>
              <span className={styles.sectionIcon} aria-hidden="true">
                <IconSettings size={18} />
              </span>
              {t('corporateLead.apiReady.title')}
            </h2>
            <ul className={styles.permissionsList}>
              <li>
                <span className={styles.permissionIcon} aria-hidden="true">
                  <IconPackage size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.apiReady.releasesTitle')}</strong>
                  <p><code>{t('corporateLead.apiReady.releasesDescription')}</code></p>
                </div>
              </li>
              <li>
                <span className={styles.permissionIcon} aria-hidden="true">
                  <IconLock size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.apiReady.locksTitle')}</strong>
                  <p><code>{t('corporateLead.apiReady.locksDescription')}</code></p>
                </div>
              </li>
              <li>
                <span className={styles.permissionIcon} aria-hidden="true">
                  <IconCheck size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.apiReady.auditTitle')}</strong>
                  <p><code>{t('corporateLead.apiReady.auditDescription')}</code></p>
                </div>
              </li>
            </ul>
          </div>

          <div className={styles.infoSection}>
            <h2 className={styles.sectionTitle}>
              <span className={styles.sectionIcon} aria-hidden="true">
                <IconX size={18} />
              </span>
              {t('corporateLead.restrictions.title')}
            </h2>
            <ul className={styles.restrictionsList}>
              <li>{t('corporateLead.restrictions.contentEditing')}</li>
              <li>{t('corporateLead.restrictions.freezeStructure')}</li>
              <li>{t('corporateLead.restrictions.draftExports')}</li>
            </ul>
          </div>

          <div className={styles.pagesSection}>
            <h2 className={styles.sectionTitle}>
              <span className={styles.sectionIcon} aria-hidden="true">
                <IconFolder size={18} />
              </span>
              {t('corporateLead.availablePages.title')}
            </h2>
            <div className={styles.pagesGrid}>
              <div className={styles.pageCard}>
                <span className={styles.pageIcon} aria-hidden="true">
                  <IconBuilding size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.availablePages.companyPath')}</strong>
                  <p>{t('corporateLead.availablePages.companyDescription')}</p>
                </div>
              </div>
              <div className={styles.pageCard}>
                <span className={styles.pageIcon} aria-hidden="true">
                  <IconUsers size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.availablePages.companyMembersPath')}</strong>
                  <p>{t('corporateLead.availablePages.companyMembersDescription')}</p>
                </div>
              </div>
              <div className={styles.pageCard}>
                <span className={styles.pageIcon} aria-hidden="true">
                  <IconSettings size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.availablePages.companyRolesPath')}</strong>
                  <p>{t('corporateLead.availablePages.companyRolesDescription')}</p>
                </div>
              </div>
              <div className={styles.pageCard}>
                <span className={styles.pageIcon} aria-hidden="true">
                  <IconChartBar size={18} />
                </span>
                <div>
                  <strong>{t('corporateLead.availablePages.reportsPath')}</strong>
                  <p>{t('corporateLead.availablePages.reportsDescription')}</p>
                </div>
              </div>
            </div>
            <p style={{ marginTop: '1rem', fontSize: '0.85rem', opacity: 0.7, textAlign: 'center' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                <IconLightbulb size={16} />
                {t('corporateLead.availablePages.upcomingHint')}
              </span>
            </p>
          </div>
        </div>

        {/* Right side - Login */}
        <div className={styles.loginPanel}>
          <div className={styles.loginCard}>
            <div className={styles.loginHeader}>
              <h2 className={styles.loginTitle}>{t('corporateLead.login.title')}</h2>
              <p className={styles.loginSubtitle}>
                {t('corporateLead.login.subtitle', { company: DEMO_CREDENTIALS.company })}
              </p>
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
                  placeholder="leadkz@example.com"
                  required
                />
              </div>

              <div className={styles.field}>
                <label htmlFor="password" className={styles.label}>
                  {t('corporateLead.login.password')}
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
                className={styles.submitButton}
                disabled={loading}
              >
                {loading ? t('corporateLead.login.signingIn') : t('corporateLead.login.signin')}
              </button>

              <button
                type="button"
                onClick={handleQuickLogin}
                className={styles.quickLoginButton}
                disabled={loading}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                  <IconZap size={16} />
                  {t('corporateLead.login.quick')}
                </span>
              </button>
            </form>

            <div className={styles.credentials}>
              <h3 className={styles.credentialsTitle}>{t('corporateLead.credentials.title')}</h3>
              <div className={styles.credentialRow}>
                <span className={styles.credentialLabel}>{t('corporateLead.credentials.email')}</span>
                <code className={styles.credentialValue}>{DEMO_CREDENTIALS.email}</code>
              </div>
              <div className={styles.credentialRow}>
                <span className={styles.credentialLabel}>{t('corporateLead.credentials.password')}</span>
                <code className={styles.credentialValue}>{DEMO_CREDENTIALS.password}</code>
              </div>
            </div>

            <div className={styles.links}>
              <Link to="/login" className={styles.link}>
                ← {t('corporateLead.regularLogin')}
              </Link>
              <span className={styles.linkDivider}>•</span>
              <a 
                href="http://localhost:8000/docs" 
                target="_blank" 
                rel="noopener noreferrer"
                className={styles.link}
              >
                {t('corporateLead.apiDocs')} →
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
