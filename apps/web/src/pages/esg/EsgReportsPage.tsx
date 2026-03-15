import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'

import { apiClient } from '@/api/client'
import { useReports } from '@/api/hooks'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import type { Block, EsgSnapshot, PaginatedResponse, Report, Section } from '@/types/api'
import { QA_FLAG_DATA_PENDING, getEsgSourceRef } from '@/utils/esgReportIntegration'

import styles from './EsgReportsPage.module.css'

const PAGE_SIZE = 100

function getDefaultYear() {
  const now = new Date()
  return now.getFullYear() - 1
}

function formatPeriod(year: number) {
  return {
    start: `${year}-01-01`,
    end: `${year}-12-31`,
  }
}

async function fetchAllPages<T>(
  fetchPage: (page: number) => Promise<PaginatedResponse<T>>,
  maxPages = 100
): Promise<T[]> {
  const items: T[] = []
  for (let page = 1; page <= maxPages; page += 1) {
    const data = await fetchPage(page)
    items.push(...(data.items || []))
    if (!data.has_next) break
  }
  return items
}

async function fetchReportPendingEsgUpdates(reportId: string) {
  const sections = await fetchAllPages<Section>(async (page) => {
    const { data } = await apiClient.get<PaginatedResponse<Section>>('/api/v1/sections', {
      params: { report_id: reportId, page, page_size: PAGE_SIZE },
    })
    return data
  })

  let linked = 0
  let pending = 0

  for (const section of sections) {
    const blocks = await fetchAllPages<Block>(async (page) => {
      const { data } = await apiClient.get<PaginatedResponse<Block>>('/api/v1/blocks', {
        params: { section_id: section.section_id, page, page_size: PAGE_SIZE },
      })
      return data
    })

    for (const block of blocks) {
      const ref = getEsgSourceRef(block)
      if (!ref) continue
      linked += 1
      if ((block.qa_flags_global || []).includes(QA_FLAG_DATA_PENDING)) {
        pending += 1
      }
    }
  }

  return { linked, pending }
}

function ReportHandoffCard(props: { report: Report }) {
  const { t } = useTranslation(['esg', 'common'])
  const navigate = useNavigate()

  const pendingQuery = useQuery({
    queryKey: ['reports', 'esg-handoff', 'pending', props.report.report_id],
    queryFn: async () => fetchReportPendingEsgUpdates(props.report.report_id),
    enabled: Boolean(props.report.report_id),
  })

  const pendingLabel = (() => {
    if (pendingQuery.isLoading) return t('esg:reportsPage.pending.loading')
    if (pendingQuery.error) return t('esg:reportsPage.pending.unavailable')
    const linked = pendingQuery.data?.linked ?? 0
    const pending = pendingQuery.data?.pending ?? 0
    return t('esg:reportsPage.pending.value', { pending, linked })
  })()

  return (
    <article className={styles.reportCard}>
      <div className={styles.reportTop}>
        <div>
          <div className={styles.reportTitle}>{props.report.title}</div>
          <div className={styles.reportMeta}>
            <span className={styles.mono}>{props.report.slug}</span>
            <span className={styles.metaSep}>|</span>
            <span className={styles.muted}>{t('esg:reportsPage.reportMeta.year', { year: props.report.year })}</span>
          </div>
        </div>
        <div className={styles.reportActions}>
          <Button onClick={() => navigate(`/reports/${props.report.slug}`)}>
            {t('esg:reportsPage.actions.openEditor')}
          </Button>
        </div>
      </div>

      <div className={styles.reportKpis}>
        <div className={styles.reportKpi}>
          <div className={styles.reportKpiLabel}>{t('esg:reportsPage.pending.label')}</div>
          <div className={styles.reportKpiValue}>{pendingLabel}</div>
          <div className={styles.reportKpiMeta}>{t('esg:reportsPage.pending.meta')}</div>
        </div>
      </div>
    </article>
  )
}

export function EsgReportsPage() {
  const { t } = useTranslation(['esg', 'common'])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const resolvedYear = (() => {
    const raw = searchParams.get('year')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return getDefaultYear()
    if (!Number.isInteger(parsed)) return getDefaultYear()
    if (parsed < 2000 || parsed > 2100) return getDefaultYear()
    return parsed
  })()

  const { start: periodStart, end: periodEnd } = formatPeriod(resolvedYear)

  const yearOptions = useMemo(() => {
    const current = new Date().getFullYear()
    const years: Array<{ value: string; label: string }> = []
    for (let y = current + 1; y >= current - 10; y -= 1) {
      years.push({ value: String(y), label: String(y) })
    }
    return years
  }, [])

  const reportsQuery = useReports({ year: resolvedYear, page: 1 })
  const reports = reportsQuery.data?.items ?? []

  const [isDownloading, setIsDownloading] = useState(false)

  const handleYearChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('year', next)
    setSearchParams(nextParams, { replace: true })
  }

  const handleDownloadSnapshot = async () => {
    setIsDownloading(true)
    try {
      const { data } = await apiClient.get<EsgSnapshot>('/api/v1/esg/snapshot', {
        params: {
          period_type: 'year',
          period_start: periodStart,
          period_end: periodEnd,
          is_ytd: 'false',
        },
      })

      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `esg-snapshot-${resolvedYear}.json`
      a.click()
      URL.revokeObjectURL(url)
      toast.success(t('esg:reportsPage.toast.snapshotDownloaded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:reportsPage.toast.snapshotDownloadFailed'))
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <EsgShell
      title={t('esg:reportsPage.title')}
      subtitle={t('esg:reportsPage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={() => navigate(`/esg/snapshot?year=${encodeURIComponent(String(resolvedYear))}`)}>
            {t('esg:reportsPage.actions.openSnapshot')}
          </Button>
          <Button variant="secondary" onClick={() => void handleDownloadSnapshot()} disabled={isDownloading}>
            {t('esg:reportsPage.actions.downloadSnapshot')}
          </Button>
          <Button onClick={() => navigate('/reports')}>{t('esg:reportsPage.actions.openReports')}</Button>
        </div>
      }
    >
      <section className={styles.toolbar} aria-label={t('esg:reportsPage.filters.aria')}>
        <Select
          label={t('esg:reportsPage.filters.reportingYear')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <div className={styles.toolbarMeta}>
          {t('esg:reportsPage.filters.period')} <strong>{periodStart}</strong> {t('esg:reportsPage.filters.periodTo')}{' '}
          <strong>{periodEnd}</strong>
        </div>
      </section>

      {reportsQuery.isLoading && <div className={styles.loading}>{t('esg:reportsPage.loading')}</div>}
      {reportsQuery.error && <div className={styles.error}>{t('esg:reportsPage.error')}</div>}

      {!reportsQuery.isLoading && !reportsQuery.error && reports.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyTitle}>{t('esg:reportsPage.empty.title', { year: resolvedYear })}</div>
          <div className={styles.emptyBody}>{t('esg:reportsPage.empty.body')}</div>
        </div>
      )}

      {reports.length > 0 && (
        <section className={styles.reportGrid} aria-label={t('esg:reportsPage.listAria')}>
          {reports.map((report) => (
            <ReportHandoffCard key={report.report_id} report={report} />
          ))}
        </section>
      )}
    </EsgShell>
  )
}

