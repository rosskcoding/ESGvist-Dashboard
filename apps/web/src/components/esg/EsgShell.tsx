import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { AppHeader } from '@/components/layout/AppHeader'
import dashboardStyles from '@/pages/DashboardPage.module.css'
import styles from './EsgShell.module.css'

interface EsgShellProps {
  title: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
}

export function EsgShell({ title, subtitle, actions, children }: EsgShellProps) {
  const { t } = useTranslation(['dashboard', 'common', 'esg'])
  const location = useLocation()

  const path = location.pathname
  const isWorkspace = path === '/esg'
  const isData = path.startsWith('/esg/data')
  const isReview = path.startsWith('/esg/review')
  const isEvidence = path.startsWith('/esg/evidence')
  const isSnapshot = path.startsWith('/esg/snapshot')
  const isReports = path.startsWith('/esg/reports')

  // Advanced/secondary sections kept for power users and implementation parity.
  const isIssues = path.startsWith('/esg/gaps')
  const isFactsAdvanced = path.startsWith('/esg/facts')
  const isLibrary = path.startsWith('/esg/metrics')

  const breadcrumbs = (() => {
    if (isWorkspace) return null
    const section = isData
      ? t('esg:nav.data')
      : isReview
        ? t('esg:nav.review')
        : isEvidence
          ? t('esg:nav.evidence')
          : isSnapshot
            ? t('esg:nav.snapshot')
            : isReports
              ? t('esg:nav.reports')
              : isIssues
                ? t('esg:nav.issues')
                : isFactsAdvanced
                  ? t('esg:nav.factsAdvanced')
                  : isLibrary
                    ? t('esg:nav.library')
                    : ''
    if (!section) return null
    return (
      <div className={styles.breadcrumbs} aria-label="Breadcrumbs">
        <Link to="/esg" className={styles.breadcrumbLink}>
          {t('esg:nav.workspace')}
        </Link>
        <span className={styles.breadcrumbSep}>/</span>
        <span className={styles.breadcrumbCurrent}>{section}</span>
      </div>
    )
  })()

  return (
    <div className={dashboardStyles.container}>
      <AppHeader />

      <main className={dashboardStyles.main}>
        <nav className={styles.subnav} aria-label="ESG navigation">
          <div className={styles.subnavPrimary}>
            <Link to="/esg" className={`${styles.subnavLink} ${isWorkspace ? styles.subnavActive : ''}`}>
              {t('esg:nav.workspace')}
            </Link>
            <Link to="/esg/data" className={`${styles.subnavLink} ${isData ? styles.subnavActive : ''}`}>
              {t('esg:nav.data')}
            </Link>
            <Link to="/esg/review" className={`${styles.subnavLink} ${isReview ? styles.subnavActive : ''}`}>
              {t('esg:nav.review')}
            </Link>
            <Link to="/esg/evidence" className={`${styles.subnavLink} ${isEvidence ? styles.subnavActive : ''}`}>
              {t('esg:nav.evidence')}
            </Link>
            <Link to="/esg/snapshot" className={`${styles.subnavLink} ${isSnapshot ? styles.subnavActive : ''}`}>
              {t('esg:nav.snapshot')}
            </Link>
            <Link to="/esg/reports" className={`${styles.subnavLink} ${isReports ? styles.subnavActive : ''}`}>
              {t('esg:nav.reports')}
            </Link>
          </div>

          <div className={styles.subnavSecondary} aria-label={t('esg:nav.advancedAria')}>
            <Link
              to="/esg/gaps"
              className={`${styles.subnavLink} ${styles.subnavLinkSecondary} ${isIssues ? styles.subnavActive : ''}`}
            >
              {t('esg:nav.issues')}
            </Link>
            <Link
              to="/esg/facts"
              className={`${styles.subnavLink} ${styles.subnavLinkSecondary} ${isFactsAdvanced ? styles.subnavActive : ''}`}
            >
              {t('esg:nav.factsAdvanced')}
            </Link>
            <Link
              to="/esg/metrics"
              className={`${styles.subnavLink} ${styles.subnavLinkSecondary} ${isLibrary ? styles.subnavActive : ''}`}
            >
              {t('esg:nav.library')}
            </Link>
          </div>
        </nav>

        {breadcrumbs}

        <div className={styles.pageTitleRow}>
          <div>
            <h1 className={styles.pageTitle}>{title}</h1>
            {subtitle && <p className={styles.pageSubtitle}>{subtitle}</p>}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </div>

        {children}
      </main>
    </div>
  )
}
