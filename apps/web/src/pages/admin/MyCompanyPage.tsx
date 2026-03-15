import { useMemo } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { AppHeader } from '@/components/layout/AppHeader'
import dashboardStyles from '@/pages/DashboardPage.module.css'
import { IconSettings, IconUser } from '@/components/ui'
import styles from './MyCompanyPage.module.css'

/**
 * My Company page - redirect to the first company where user is owner/admin
 */
export function MyCompanyPage() {
  const user = useAuthStore((s) => s.user)
  const memberships = useMemo(() => user?.memberships ?? [], [user?.memberships])

  // Find first company where user is corporate lead
  const adminMembership = useMemo(() => {
    return memberships.find((m) => m.isActive && m.isCorporateLead)
  }, [memberships])

  if (!adminMembership) {
    return <Navigate to="/reports" replace />
  }

  return (
    <div className={dashboardStyles.container}>
      <AppHeader />

      <main className={dashboardStyles.main}>
        <div className={styles.hero}>
          <div className={styles.heroTop}>
            <h1 className={styles.companyName}>{adminMembership.companyName}</h1>
            <span className={styles.roleBadge}>Corporate Lead</span>
          </div>
          <p className={styles.heroText}>
            Manage members and assign working roles (editor, auditor, etc.) for this company.
          </p>
        </div>

        <div className={styles.cards}>
          <Link to="/company/members" className={styles.card}>
            <div className={styles.cardIcon} aria-hidden="true">
              <IconUser size={18} />
            </div>
            <div className={styles.cardBody}>
              <div className={styles.cardTitle}>Members</div>
              <div className={styles.cardDesc}>Manage company membership</div>
            </div>
          </Link>

          <Link to="/company/roles" className={styles.card}>
            <div className={styles.cardIcon} aria-hidden="true">
              <IconSettings size={18} />
            </div>
            <div className={styles.cardBody}>
              <div className={styles.cardTitle}>Roles</div>
              <div className={styles.cardDesc}>Assign working roles and scopes</div>
            </div>
          </Link>
        </div>

        {memberships.filter((m) => m.isActive && m.isCorporateLead).length > 1 && (
          <div className={styles.otherCompanies}>
            <h2 className={styles.otherTitle}>Your other companies</h2>
            <div className={styles.otherBadges}>
              {memberships
                .filter((m) => m.isActive && m.isCorporateLead && m.companyId !== adminMembership.companyId)
                .map((m) => (
                  <span key={m.companyId} className={styles.otherBadge} title={m.companyName}>
                    {m.companyName}
                  </span>
                ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
