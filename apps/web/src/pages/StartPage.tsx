import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  IconAlertTriangle,
  IconBuilding,
  IconChartBar,
  IconLightbulb,
  IconLock,
  IconSettings,
  IconZap,
} from '@/components/ui'
import styles from './StartPage.module.css'

export function StartPage() {
  const { t } = useTranslation('start')

  const pages: Array<{
    category: { icon: ReactNode; label: string }
    items: Array<{ name: string; path: string; description: string; protected?: boolean }>
  }> = [
    {
      category: { icon: <IconLock size={16} />, label: t('categories.login') },
      items: [
        {
          name: t('pages.login.name'),
          path: t('pages.login.path'),
          description: t('pages.login.description'),
        },
        {
          name: t('pages.corporateLeadLogin.name'),
          path: t('pages.corporateLeadLogin.path'),
          description: t('pages.corporateLeadLogin.description'),
        },
      ],
    },
    {
      category: { icon: <IconChartBar size={16} />, label: t('categories.core') },
      items: [
        {
          name: t('pages.dashboard.name'),
          path: t('pages.dashboard.path'),
          description: t('pages.dashboard.description'),
          protected: true,
        },
      ],
    },
    {
      category: { icon: <IconSettings size={16} />, label: t('categories.admin') },
      items: [
        {
          name: t('pages.companies.name'),
          path: t('pages.companies.path'),
          description: t('pages.companies.description'),
          protected: true,
        },
        {
          name: t('pages.users.name'),
          path: t('pages.users.path'),
          description: t('pages.users.description'),
          protected: true,
        },
      ],
    },
    {
      category: { icon: <IconBuilding size={16} />, label: t('categories.company') },
      items: [
        {
          name: t('pages.myCompany.name'),
          path: t('pages.myCompany.path'),
          description: t('pages.myCompany.description'),
          protected: true,
        },
        {
          name: t('pages.companyMembers.name'),
          path: t('pages.companyMembers.path'),
          description: t('pages.companyMembers.description'),
          protected: true,
        },
        {
          name: t('pages.companyRoles.name'),
          path: t('pages.companyRoles.path'),
          description: t('pages.companyRoles.description'),
          protected: true,
        },
      ],
    },
  ]

  const demoCredentials = {
    email: 'e2e-test@example.com',
    password: 'TestPassword123!',
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <div className={styles.header}>
          <h1 className={styles.title}>
            <span className={styles.titleIcon} aria-hidden="true">
              <IconZap size={18} />
            </span>
            {t('title')}
          </h1>
          <p className={styles.subtitle}>{t('subtitle')}</p>
          <div className={styles.badge}>{t('badge')}</div>
        </div>

        {/* Demo Credentials */}
        <div className={styles.demoBlock}>
          <h3 className={styles.demoTitle}>
            <span className={styles.inlineIcon} aria-hidden="true">
              <IconLock size={16} />
            </span>
            {t('credentials.title')}
          </h3>
          <div className={styles.credentials}>
            <div className={styles.credItem}>
              <span className={styles.credLabel}>{t('credentials.email')}</span>
              <code className={styles.credValue} onClick={() => copyToClipboard(demoCredentials.email)}>
                {demoCredentials.email}
              </code>
            </div>
            <div className={styles.credItem}>
              <span className={styles.credLabel}>{t('credentials.password')}</span>
              <code className={styles.credValue} onClick={() => copyToClipboard(demoCredentials.password)}>
                {demoCredentials.password}
              </code>
            </div>
          </div>
          <p className={styles.credHint}>
            <span className={styles.inlineIcon} aria-hidden="true">
              <IconLightbulb size={16} />
            </span>
            {t('credentials.copyHint')}
          </p>
        </div>

        {/* Pages Navigation */}
        <div className={styles.navigation}>
          {pages.map((section) => (
            <div key={section.category.label} className={styles.section}>
              <h2 className={styles.categoryTitle}>
                <span className={styles.inlineIcon} aria-hidden="true">
                  {section.category.icon}
                </span>
                {section.category.label}
              </h2>
              <div className={styles.links}>
                {section.items.map((page) => (
                  <Link
                    key={page.path}
                    to={page.path}
                    className={styles.link}
                  >
                    <div className={styles.linkHeader}>
                      <span className={styles.linkName}>{page.name}</span>
                      {'protected' in page && page.protected && (
                        <span className={styles.protectedBadge} aria-hidden="true">
                          <IconLock size={14} />
                        </span>
                      )}
                    </div>
                    <div className={styles.linkDescription}>{page.description}</div>
                    <div className={styles.linkPath}>{page.path}</div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Warning */}
        <div className={styles.warning}>
          <span className={styles.inlineIcon} aria-hidden="true">
            <IconAlertTriangle size={16} />
          </span>
          {t('warning')}
        </div>
      </div>
    </div>
  )
}
