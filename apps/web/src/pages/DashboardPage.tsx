import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '@/stores/authStore'
import { useReports, useDeleteReport, useCompanies } from '@/api/hooks'
import { ReportCard, CreateReportModal } from '@/components/reports'
import { AppHeader } from '@/components/layout/AppHeader'
import { Button, IconAlertTriangle, IconBuilding, IconFileText, Tooltip } from '@/components/ui'
import styles from './DashboardPage.module.css'

export function DashboardPage() {
  const { t } = useTranslation(['dashboard', 'common', 'esg'])
  const user = useAuthStore((s) => s.user)
  const [searchParams, setSearchParams] = useSearchParams()
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const companySlug = searchParams.get('company')
  
  const { data: reportsData, isLoading, error, refetch } = useReports()
  const { data: companiesData } = useCompanies()
  const deleteReport = useDeleteReport()

  const handleDeleteReport = async (reportId: string) => {
    if (deleteConfirm === reportId) {
      try {
        await deleteReport.mutateAsync(reportId)
        setDeleteConfirm(null)
      } catch (err) {
        console.error('Failed to delete report:', err)
      }
    } else {
      setDeleteConfirm(reportId)
      // Auto-reset after 3 seconds
      setTimeout(() => setDeleteConfirm(null), 3000)
    }
  }

  const allReports = useMemo(() => reportsData?.items || [], [reportsData?.items])
  const companies = useMemo(() => companiesData?.items || [], [companiesData?.items])
  
  // Filter reports by company if specified
  const reports = useMemo(() => {
    if (!companySlug) return allReports
    
    const company = companies.find(c => c.slug === companySlug)
    if (!company) return allReports
    
    return allReports.filter(r => r.company_id === company.company_id)
  }, [allReports, companies, companySlug])
  
  const selectedCompany = useMemo(() => {
    if (!companySlug) return null
    return companies.find(c => c.slug === companySlug)
  }, [companies, companySlug])
  
  const clearCompanyFilter = () => {
    setSearchParams({})
  }

  return (
    <div className={styles.container}>
      <AppHeader />

      <main className={styles.main}>
        {/* Company Admin Banner */}
        {user?.memberships?.some((m) => m.isActive && m.isCorporateLead) && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            borderRadius: '12px',
            padding: '1rem 1.5rem',
            marginBottom: '1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div>
              <div style={{ fontSize: '0.9rem', color: '#a5b4fc', marginBottom: '0.25rem' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                  <IconBuilding size={16} />
                  {t('dashboard:companyBanner.title')}
                </span>
              </div>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
                {t('dashboard:companyBanner.description')}
              </div>
            </div>
            <Link to="/company">
              <Button variant="secondary" style={{ marginLeft: '1rem' }}>
                {t('dashboard:companyBanner.cta')} →
              </Button>
            </Link>
          </div>
        )}

        {/* Company filter indicator */}
        {selectedCompany && (
          <div style={{
            background: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center' }} aria-hidden="true">
                <IconBuilding size={18} />
              </span>
              <div>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.125rem' }}>
                  {t('dashboard:companyFilter.label')}
                </div>
                <div style={{ fontSize: '0.9rem', color: '#e2e8f0', fontWeight: 500 }}>
                  {selectedCompany.name}
                </div>
              </div>
            </div>
            <button
              onClick={clearCompanyFilter}
              style={{
                background: 'rgba(59, 130, 246, 0.2)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                borderRadius: '6px',
                padding: '0.5rem 1rem',
                color: '#93c5fd',
                fontSize: '0.875rem',
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
            >
              {t('dashboard:companyFilter.showAll')}
            </button>
          </div>
        )}

        <div className={styles.toolbar}>
          <Tooltip content={t('dashboard:hints.title')} position="right">
            <h1 className={styles.pageTitle}>
              {t('dashboard:title')}
              {!companySlug && reportsData && (
                <span className={styles.count}>
                  {reportsData.total}
                </span>
              )}
              {companySlug && (
                <span className={styles.count}>
                  {reports.length}
                </span>
              )}
            </h1>
          </Tooltip>
          <Tooltip content={t('dashboard:hints.createReport')}>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              + {t('dashboard:report.create')}
            </Button>
          </Tooltip>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <span>{t('dashboard:loading.reports')}</span>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className={styles.errorState}>
            <div className={styles.errorIcon} aria-hidden="true">
              <IconAlertTriangle size={22} />
            </div>
            <h2 className={styles.errorTitle}>{t('dashboard:errors.title')}</h2>
            <p className={styles.errorText}>
              {error instanceof Error ? error.message : t('dashboard:errors.fallback')}
            </p>
            <Button onClick={() => refetch()} variant="secondary">
              {t('common:actions.retry')}
            </Button>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && reports.length === 0 && (
          <div className={styles.empty}>
            <div className={styles.emptyIcon} aria-hidden="true">
              <IconFileText size={24} />
            </div>
            <h2 className={styles.emptyTitle}>{t('dashboard:empty.reports')}</h2>
            <p className={styles.emptyText}>
              {t('dashboard:empty.description')}
            </p>
            <Button onClick={() => setIsCreateModalOpen(true)}>
              + {t('dashboard:report.create')}
            </Button>
          </div>
        )}

        {/* Reports grid */}
        {!isLoading && !error && reports.length > 0 && (
          <div className={styles.grid}>
            {reports.map((report) => (
              <ReportCard
                key={report.report_id}
                report={report}
                onDelete={
                  user?.isSuperuser
                    ? (id) => handleDeleteReport(id)
                    : undefined
                }
              />
            ))}
          </div>
        )}

        {/* Delete confirmation toast */}
        {deleteConfirm && (
          <div className={styles.deleteConfirm}>
            <span>{t('dashboard:deleteConfirm.text')}</span>
            <button
              onClick={() => setDeleteConfirm(null)}
              className={styles.cancelDelete}
            >
              {t('dashboard:deleteConfirm.cancel')}
            </button>
          </div>
        )}
      </main>

      <CreateReportModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
      />
    </div>
  )
}
