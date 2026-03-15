import { useCallback, useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/authStore'
import {
  DropdownMenu,
  type DropdownMenuItem,
  IconBuilding,
  IconMenu,
  IconMoreHorizontal,
  IconSettings,
  IconUser,
  Tooltip,
} from '@/components/ui'
import styles from './AppHeader.module.css'

export function AppHeader() {
  const { t } = useTranslation(['dashboard', 'common', 'esg'])
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = useCallback(() => {
    logout()
    navigate('/login')
  }, [logout, navigate])

  const path = location.pathname
  const isEsg = path === '/esg' || path.startsWith('/esg/')
  const isCompany = path === '/company' || path.startsWith('/company/')
  const isPlatform = path === '/admin' || path.startsWith('/admin/')

  const activeMembership = user?.memberships?.find((m) => m.isActive) ?? null
  const companyName = activeMembership?.companyName ?? null
  const companyRoleLabel = (() => {
    if (user?.isSuperuser) return t('dashboard:roles.superuser')
    if (activeMembership?.isCorporateLead) return t('dashboard:roles.corporateLead')
    if (activeMembership?.roles?.includes('editor')) return t('dashboard:roles.editor')
    return t('dashboard:roles.member')
  })()

  const canSeeCompanyAdmin = Boolean(user?.memberships?.some((m) => m.isActive && m.isCorporateLead))
  const canSeePlatformAdmin = Boolean(user?.isSuperuser)

  const moreMenuItems: DropdownMenuItem[] = useMemo(() => {
    const items: DropdownMenuItem[] = []
    if (canSeeCompanyAdmin) items.push({ label: t('dashboard:nav.company'), onSelect: () => navigate('/company') })
    if (canSeePlatformAdmin) items.push({ label: t('dashboard:nav.platform'), onSelect: () => navigate('/admin/companies') })
    return items
  }, [canSeeCompanyAdmin, canSeePlatformAdmin, navigate, t])

  const mobileMenuItems: DropdownMenuItem[] = useMemo(() => {
    const items: DropdownMenuItem[] = [
      { label: t('dashboard:nav.esgDashboard'), onSelect: () => navigate('/esg') },
      { type: 'divider' },
    ]
    if (canSeeCompanyAdmin) items.push({ label: t('dashboard:nav.company'), onSelect: () => navigate('/company') })
    if (canSeePlatformAdmin) items.push({ label: t('dashboard:nav.platform'), onSelect: () => navigate('/admin/companies') })
    items.push({ type: 'divider' })
    items.push({ label: t('common:actions.logout'), onSelect: handleLogout, variant: 'danger' })
    return items
  }, [canSeeCompanyAdmin, canSeePlatformAdmin, handleLogout, navigate, t])

  const userMenuItems: DropdownMenuItem[] = useMemo(
    () => [{ label: t('common:actions.logout'), onSelect: handleLogout, variant: 'danger' as const }],
    [handleLogout, t]
  )

  return (
    <header className={styles.header}>
      <div className={styles.topRow}>
        <div className={styles.logo}>
          <span className={styles.logoIcon} aria-hidden="true">
            <img className={styles.logoImage} src="/brand/logo-esgvist.png" alt="" />
          </span>
          <span className={styles.logoBadge}>Platform</span>
        </div>

        <div className={styles.user}>
          <span className={styles.userName}>{user?.fullName}</span>
          {companyName ? (
            <div className={styles.userBadges}>
              <span className={styles.userRole}>{companyRoleLabel}</span>
              <span className={styles.userCompany} title={companyName}>
                {companyName}
              </span>
            </div>
          ) : (
            <span className={styles.userRole}>{companyRoleLabel}</span>
          )}
          <DropdownMenu
            triggerLabel={
              <span className={styles.userMenuTrigger}>
                <IconUser size={16} />
              </span>
            }
            triggerAriaLabel="User menu"
            items={userMenuItems}
            align="end"
          />
        </div>
      </div>

      <div className={styles.bottomRow}>
        <nav className={styles.nav} aria-label="Main navigation">
          <div className={styles.navPrimary}>
            <Link to="/esg" className={styles.navLink} aria-current={isEsg ? 'page' : undefined}>
              {t('dashboard:nav.esgDashboard')}
            </Link>
          </div>

          <div className={styles.navSecondary}>
            {canSeeCompanyAdmin && (
              <Tooltip content={t('dashboard:nav.company')}>
                <Link
                  to="/company"
                  className={`${styles.navLink} ${styles.navIconLink}`}
                  aria-current={isCompany ? 'page' : undefined}
                  aria-label={t('dashboard:nav.company')}
                  title={t('dashboard:nav.company')}
                >
                  <IconBuilding size={16} />
                </Link>
              </Tooltip>
            )}
            {canSeePlatformAdmin && (
              <Tooltip content={t('dashboard:nav.platform')}>
                <Link
                  to="/admin/companies"
                  className={`${styles.navLink} ${styles.navIconLink}`}
                  aria-current={isPlatform ? 'page' : undefined}
                  aria-label={t('dashboard:nav.platform')}
                  title={t('dashboard:nav.platform')}
                >
                  <IconSettings size={16} />
                </Link>
              </Tooltip>
            )}
          </div>
        </nav>

        <div className={styles.bottomRight}>
          <div className={styles.navMore}>
            <DropdownMenu
              triggerLabel={<IconMoreHorizontal size={18} />}
              triggerAriaLabel="More"
              items={moreMenuItems}
              align="end"
            />
          </div>

          <div className={styles.mobileNav}>
            <DropdownMenu triggerLabel={<IconMenu size={18} />} triggerAriaLabel="Menu" items={mobileMenuItems} align="end" />
          </div>
        </div>
      </div>
    </header>
  )
}
