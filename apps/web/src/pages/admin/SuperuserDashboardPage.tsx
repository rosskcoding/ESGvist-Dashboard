/**
 * Superuser Dashboard Page — Platform operations for superusers.
 * 
 * Safe by default:
 * - Read-only by default
 * - No access to customer content
 * - Cross-tenant observability
 * - Safe recovery actions only
 */

import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiClient } from '@/api/client'
import { IconAlertTriangle, IconCheck, IconX } from '@/components/ui'
import {
  AttentionInboxTab,
  BuildsTab,
  ArtifactsTab,
  TranslationsTab,
  AuditLogTab,
  AIUsageTab,
  CompaniesTab,
  UsersTab,
  StorageTab,
} from './SuperuserDashboardTabs'
import { PlatformAdminLayout } from './PlatformAdminLayout'
import styles from './MyCompanyAdmin.module.css'

type Tab = 'overview' | 'companies' | 'users' | 'attention' | 'builds' | 'artifacts' | 'translations' | 'audit' | 'ai-usage' | 'storage'

const VALID_TABS: Tab[] = ['overview', 'companies', 'users', 'attention', 'builds', 'artifacts', 'translations', 'audit', 'ai-usage', 'storage']

function isValidTab(tab: string | null): tab is Tab {
  return tab !== null && VALID_TABS.includes(tab as Tab)
}

export function SuperuserDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  
  // Read tab from URL, default to 'overview'
  const tabFromUrl = searchParams.get('tab')
  const activeTab: Tab = isValidTab(tabFromUrl) ? tabFromUrl : 'overview'
  
  // Update URL when tab changes
  const setActiveTab = (tab: Tab) => {
    setSearchParams({ tab }, { replace: true })
  }

  return (
    <PlatformAdminLayout
      active="overview"
      title="Platform admin"
      hint="Superuser operations, observability, and safe recovery."
    >
      <nav className={styles.subnav} aria-label="Platform admin sections">
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'overview' ? 'page' : undefined}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'companies' ? 'page' : undefined}
          onClick={() => setActiveTab('companies')}
        >
          Companies
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'users' ? 'page' : undefined}
          onClick={() => setActiveTab('users')}
        >
          Users
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'attention' ? 'page' : undefined}
          onClick={() => setActiveTab('attention')}
        >
          Attention inbox
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'builds' ? 'page' : undefined}
          onClick={() => setActiveTab('builds')}
        >
          Builds
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'artifacts' ? 'page' : undefined}
          onClick={() => setActiveTab('artifacts')}
        >
          Artifacts
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'translations' ? 'page' : undefined}
          onClick={() => setActiveTab('translations')}
        >
          Translations
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'audit' ? 'page' : undefined}
          onClick={() => setActiveTab('audit')}
        >
          Audit log
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'ai-usage' ? 'page' : undefined}
          onClick={() => setActiveTab('ai-usage')}
        >
          AI usage
        </button>
        <button
          type="button"
          className={styles.subnavButton}
          aria-current={activeTab === 'storage' ? 'page' : undefined}
          onClick={() => setActiveTab('storage')}
        >
          Storage
        </button>
      </nav>

      <div>
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'companies' && <CompaniesTab />}
        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'attention' && <AttentionInboxTab />}
        {activeTab === 'builds' && <BuildsTab />}
        {activeTab === 'artifacts' && <ArtifactsTab />}
        {activeTab === 'translations' && <TranslationsTab />}
        {activeTab === 'audit' && <AuditLogTab />}
        {activeTab === 'ai-usage' && <AIUsageTab />}
        {activeTab === 'storage' && <StorageTab />}
      </div>
    </PlatformAdminLayout>
  )
}

// =============================================================================
// Overview Tab (inline implementation)
// =============================================================================

interface PlatformOverview {
  companies: {
    total: number
    active: number
    disabled: number
  }
  users: {
    total: number
    superusers: number
  }
  reports: {
    total: number
  }
  builds_last_24h: {
    success: number
    failed: number
  }
  health: {
    database: string
    redis: string
  }
}

function OverviewTab() {
  const [data, setData] = useState<PlatformOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchOverview() {
      try {
        const res = await apiClient.get<PlatformOverview>('/api/v1/admin/overview')
        setData(res.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchOverview()
  }, [])

  if (loading) {
    return (
      <div>
        <h2>Platform Overview</h2>
        <p className={styles.muted}>Loading stats...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <h2>Platform Overview</h2>
        <p style={{ color: 'red' }}>Error: {error}</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div>
        <h2>Platform Overview</h2>
        <p className={styles.muted}>No data available</p>
      </div>
    )
  }

  return (
    <div>
      <h2>Platform Overview</h2>
      <div className={styles.kpiGrid}>
        {/* Companies Card */}
        <div className={styles.kpiCard}>
          <div className={styles.kpiLabel}>Companies</div>
          <div className={styles.kpiValue}>{data.companies.total}</div>
          <div className={styles.muted}>
            <span style={{ color: '#16a34a', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <IconCheck size={16} />
              {data.companies.active} active
            </span>
            {data.companies.disabled > 0 && (
              <>
                {' '}•{' '}
                <span style={{ color: '#dc2626', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <IconAlertTriangle size={16} />
                  {data.companies.disabled} disabled
                </span>
              </>
            )}
          </div>
        </div>

        {/* Users Card */}
        <div className={styles.kpiCard}>
          <div className={styles.kpiLabel}>Users</div>
          <div className={styles.kpiValue}>{data.users.total}</div>
          <div className={styles.muted}>
            {data.users.superusers} superuser{data.users.superusers !== 1 ? 's' : ''}
          </div>
        </div>

        {/* Reports Card */}
        <div className={styles.kpiCard}>
          <div className={styles.kpiLabel}>Reports</div>
          <div className={styles.kpiValue}>{data.reports.total}</div>
          <div className={styles.muted}>Total reports</div>
        </div>

        {/* Builds (24h) Card */}
        <div className={styles.kpiCard}>
          <div className={styles.kpiLabel}>Builds (24h)</div>
          <div className={styles.kpiValue}>{data.builds_last_24h.success + data.builds_last_24h.failed}</div>
          <div className={styles.muted}>
            <span style={{ color: '#16a34a', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <IconCheck size={16} />
              {data.builds_last_24h.success}
            </span>
            {data.builds_last_24h.failed > 0 && (
              <>
                {' '}•{' '}
                <span style={{ color: '#dc2626', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <IconX size={16} />
                  {data.builds_last_24h.failed} failed
                </span>
              </>
            )}
          </div>
        </div>

        {/* Health Card */}
        <div className={styles.kpiCard}>
          <div className={styles.kpiLabel}>System Health</div>
          <div className={styles.muted} style={{ marginTop: '8px' }}>
            <div style={{ marginBottom: '0.5rem' }}>
              Database: <span style={{ color: data.health.database === 'ok' ? '#22c55e' : '#ef4444' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  {data.health.database === 'ok' ? <IconCheck size={16} /> : <IconX size={16} />}
                  {data.health.database === 'ok' ? 'OK' : 'ERROR'}
                </span>
              </span>
            </div>
            <div>
              Redis: <span style={{ color: data.health.redis === 'ok' ? '#22c55e' : '#ef4444' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  {data.health.redis === 'ok' ? <IconCheck size={16} /> : <IconX size={16} />}
                  {data.health.redis === 'ok' ? 'OK' : 'ERROR'}
                </span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
