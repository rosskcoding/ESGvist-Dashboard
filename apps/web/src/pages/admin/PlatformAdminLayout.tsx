import { Link } from 'react-router-dom'
import { AppHeader } from '@/components/layout/AppHeader'
import dashboardStyles from '@/pages/DashboardPage.module.css'
import styles from './PlatformAdminLayout.module.css'

type TabKey = 'overview' | 'companies' | 'users'

type Props = {
  active: TabKey
  title: string
  hint?: string
  children: React.ReactNode
}

const TABS: Array<{ key: TabKey; label: string; to: string }> = [
  { key: 'overview', label: 'Overview', to: '/admin/platform' },
  { key: 'companies', label: 'Companies', to: '/admin/companies' },
  { key: 'users', label: 'Users', to: '/admin/users' },
]

export function PlatformAdminLayout({ active, title, hint, children }: Props) {
  return (
    <div className={dashboardStyles.container}>
      <AppHeader />

      <main className={dashboardStyles.main}>
        <div className={styles.header}>
          <div className={styles.titleBlock}>
            <h1 className={styles.title}>{title}</h1>
            {hint ? <p className={styles.hint}>{hint}</p> : null}
          </div>

          <nav className={styles.tabs} aria-label="Platform admin navigation">
            {TABS.map((t) => (
              <Link
                key={t.key}
                to={t.to}
                className={styles.tab}
                aria-current={active === t.key ? 'page' : undefined}
              >
                {t.label}
              </Link>
            ))}
          </nav>
        </div>

        {children}
      </main>
    </div>
  )
}

