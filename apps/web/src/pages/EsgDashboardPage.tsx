import { useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { EsgShell } from '@/components/esg/EsgShell'
import { useEsgFacts, useEsgGaps } from '@/api/hooks'
import { Button, Select } from '@/components/ui'
import styles from './EsgDashboardPage.module.css'

function defaultGapYear() {
  return new Date().getFullYear() - 1
}

const STANDARD_VALUES = new Set(['GRI', 'SASB', 'ISSB', 'CSRD', 'ESRS'])

export function EsgDashboardPage() {
  const { t } = useTranslation(['esg'])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const resolvedYear = (() => {
    const raw = searchParams.get('year')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return defaultGapYear()
    if (!Number.isInteger(parsed)) return defaultGapYear()
    if (parsed < 2000 || parsed > 2100) return defaultGapYear()
    return parsed
  })()

  const resolvedStandard = (() => {
    const raw = searchParams.get('standard')
    if (!raw) return ''
    const cleaned = raw.trim().toUpperCase()
    if (!cleaned) return ''
    if (!STANDARD_VALUES.has(cleaned)) return ''
    return cleaned
  })()

  const periodStart = `${resolvedYear}-01-01`
  const periodEnd = `${resolvedYear}-12-31`

  const issuesLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('year', String(resolvedYear))
    if (resolvedStandard) p.set('standard', resolvedStandard)
    return `/esg/gaps?${p.toString()}`
  }, [resolvedStandard, resolvedYear])

  const reviewLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('year', String(resolvedYear))
    return `/esg/review?${p.toString()}`
  }, [resolvedYear])

  const evidenceLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('year', String(resolvedYear))
    return `/esg/evidence?${p.toString()}`
  }, [resolvedYear])

  const snapshotLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('year', String(resolvedYear))
    if (resolvedStandard) p.set('standard', resolvedStandard)
    return `/esg/snapshot?${p.toString()}`
  }, [resolvedStandard, resolvedYear])

  const factsEvidenceMissingLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('has_evidence', 'false')
    p.set('period_from', periodStart)
    p.set('period_to', periodEnd)
    p.set('latest_only', 'true')
    return `/esg/facts?${p.toString()}`
  }, [periodEnd, periodStart])

  const factsInReviewLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('status', 'in_review')
    p.set('period_from', periodStart)
    p.set('period_to', periodEnd)
    p.set('latest_only', 'true')
    return `/esg/facts?${p.toString()}`
  }, [periodEnd, periodStart])

  const yearOptions = useMemo(() => {
    const current = new Date().getFullYear()
    const years: Array<{ value: string; label: string }> = []
    for (let y = current + 1; y >= current - 10; y -= 1) {
      years.push({ value: String(y), label: String(y) })
    }
    return years
  }, [])

  const standardOptions = useMemo(() => {
    return [
      { value: '', label: t('esg:dashboard.filters.allStandards') },
      { value: 'GRI', label: 'GRI' },
      { value: 'SASB', label: 'SASB' },
      { value: 'ISSB', label: 'ISSB' },
      { value: 'CSRD', label: 'CSRD' },
      { value: 'ESRS', label: 'ESRS' },
    ]
  }, [t])

  const handleYearChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('year', next)
    setSearchParams(nextParams, { replace: true })
  }

  const handleStandardChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('standard', next)
    else nextParams.delete('standard')
    setSearchParams(nextParams, { replace: true })
  }

  const factsAllQuery = useEsgFacts({
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: 1,
  })
  const factsPublishedQuery = useEsgFacts({
    status: 'published',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: 1,
  })
  const factsInReviewQuery = useEsgFacts({
    status: 'in_review',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: 1,
  })
  const factsDraftQuery = useEsgFacts({
    status: 'draft',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: 1,
  })
  const gapsQuery = useEsgGaps({
    periodType: 'year',
    periodStart: periodStart,
    periodEnd: periodEnd,
    isYtd: false,
    standard: resolvedStandard || undefined,
    reviewOverdueDays: 7,
    maxAttentionFacts: 60,
  })

  const factsAll = factsAllQuery.data?.total ?? 0
  const factsPublished = factsPublishedQuery.data?.total ?? 0
  const factsInReview = factsInReviewQuery.data?.total ?? 0
  const factsDraft = factsDraftQuery.data?.total ?? 0
  const factsLoading =
    factsAllQuery.isLoading || factsPublishedQuery.isLoading || factsInReviewQuery.isLoading || factsDraftQuery.isLoading
  const gapsLoading = gapsQuery.isLoading

  const gaps = gapsQuery.data
  const gapsTotal = gaps?.metrics_total ?? 0
  const gapsWithPublished = gaps?.metrics_with_published ?? 0
  const gapsMissing = gaps?.metrics_missing_published ?? 0
  const completenessPercent = gapsTotal > 0 ? Math.round((gapsWithPublished / gapsTotal) * 100) : 0

  const issueCounts = gaps?.issue_counts ?? {}
  const missingSourcesCount = Object.entries(issueCounts).reduce((sum, [code, count]) => {
    if (!code.startsWith('missing_source:')) return sum
    return sum + (typeof count === 'number' && Number.isFinite(count) ? count : 0)
  }, 0)
  const missingEvidenceCount = issueCounts['missing_evidence'] ?? 0
  const outOfRangeCount = (issueCounts['range_below_min'] ?? 0) + (issueCounts['range_above_max'] ?? 0)
  const reviewOverdueCount = gaps?.in_review_overdue ?? 0
  const attentionFactsCount = gaps?.attention_facts.length ?? 0
  const issuesTotal = Object.values(issueCounts).reduce((sum, count) => {
    if (typeof count !== 'number' || !Number.isFinite(count)) return sum
    return sum + count
  }, 0)

  const blockersCount = Math.max(0, issuesTotal - (issueCounts['review_overdue'] ?? 0))

  return (
    <EsgShell
      title={t('esg:title')}
      subtitle={t('esg:subtitle')}
      actions={
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={() => navigate('/esg/metrics')}>
            {t('esg:dashboard.actions.metricLibrary')}
          </Button>
          <Button onClick={() => navigate('/esg/facts/new')}>
            {t('esg:dashboard.actions.addData')}
          </Button>
        </div>
      }
    >
      <section className={styles.reportControls} aria-label={t('esg:dashboard.filters.aria')}>
        <Select
          label={t('esg:dashboard.filters.year')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <Select
          label={t('esg:dashboard.filters.standard')}
          value={resolvedStandard}
          onChange={(e) => handleStandardChange(e.target.value)}
          options={standardOptions}
        />
        <div className={styles.reportControlsMeta}>
          {t('esg:dashboard.filters.period', { start: periodStart, end: periodEnd })}
        </div>
      </section>

      <section className={styles.quickGrid} aria-label={t('esg:dashboard.kpis.aria')}>
        <Link to={issuesLink} className={styles.quickCard} aria-label={t('esg:dashboard.kpis.coverage.title')}>
          <div className={styles.quickHeader}>
            <div className={styles.quickTitle}>{t('esg:dashboard.kpis.coverage.title')}</div>
            <div className={styles.quickArrow} aria-hidden="true">
              →
            </div>
          </div>
          <div className={styles.quickValue}>{gapsLoading ? '…' : `${completenessPercent}%`}</div>
          <div className={styles.quickMeta}>
            {gapsLoading
              ? t('esg:dashboard.kpis.coverage.metaLoading')
              : t('esg:dashboard.kpis.coverage.meta', {
                  published: gapsWithPublished.toLocaleString(),
                  total: gapsTotal.toLocaleString(),
                  missing: gapsMissing.toLocaleString(),
                })}
          </div>
          <div className={styles.progressTrack} aria-hidden="true">
            <div className={styles.progressFill} style={{ width: `${completenessPercent}%` }} />
          </div>
        </Link>

        <Link to={reviewLink} className={styles.quickCard} aria-label={t('esg:dashboard.kpis.readiness.title')}>
          <div className={styles.quickHeader}>
            <div className={styles.quickTitle}>{t('esg:dashboard.kpis.readiness.title')}</div>
            <div className={styles.quickArrow} aria-hidden="true">
              →
            </div>
          </div>
          <div className={styles.quickValue}>{factsLoading ? '…' : factsAll.toLocaleString()}</div>
          <div className={styles.quickMeta}>
            {factsLoading
              ? t('esg:dashboard.kpis.readiness.metaLoading')
              : t('esg:dashboard.kpis.readiness.meta', {
                  published: factsPublished.toLocaleString(),
                  inReview: factsInReview.toLocaleString(),
                  draft: factsDraft.toLocaleString(),
                  missing: gapsMissing.toLocaleString(),
                })}
          </div>
        </Link>

        <Link to={evidenceLink} className={styles.quickCard} aria-label={t('esg:dashboard.kpis.evidence.title')}>
          <div className={styles.quickHeader}>
            <div className={styles.quickTitle}>{t('esg:dashboard.kpis.evidence.title')}</div>
            <div className={styles.quickArrow} aria-hidden="true">
              →
            </div>
          </div>
          <div className={styles.quickValue}>{gapsLoading ? '…' : missingEvidenceCount.toLocaleString()}</div>
          <div className={styles.quickMeta}>
            {gapsLoading
              ? t('esg:dashboard.kpis.evidence.metaLoading')
              : t('esg:dashboard.kpis.evidence.meta', {
                  missingEvidence: missingEvidenceCount.toLocaleString(),
                  missingSources: missingSourcesCount.toLocaleString(),
                })}
          </div>
        </Link>

        <Link to={issuesLink} className={styles.quickCard} aria-label={t('esg:dashboard.kpis.blockers.title')}>
          <div className={styles.quickHeader}>
            <div className={styles.quickTitle}>{t('esg:dashboard.kpis.blockers.title')}</div>
            <div className={styles.quickArrow} aria-hidden="true">
              →
            </div>
          </div>
          <div className={styles.quickValue}>{gapsLoading ? '…' : blockersCount.toLocaleString()}</div>
          <div className={styles.quickMeta}>
            {gapsLoading
              ? t('esg:dashboard.kpis.blockers.metaLoading')
              : t('esg:dashboard.kpis.blockers.meta', {
                  attention: attentionFactsCount.toLocaleString(),
                  overdue: reviewOverdueCount.toLocaleString(),
                })}
          </div>
        </Link>

        <Link to={reviewLink} className={styles.quickCard} aria-label={t('esg:dashboard.kpis.overdue.title')}>
          <div className={styles.quickHeader}>
            <div className={styles.quickTitle}>{t('esg:dashboard.kpis.overdue.title')}</div>
            <div className={styles.quickArrow} aria-hidden="true">
              →
            </div>
          </div>
          <div className={styles.quickValue}>{gapsLoading ? '…' : reviewOverdueCount.toLocaleString()}</div>
          <div className={styles.quickMeta}>{t('esg:dashboard.kpis.overdue.meta')}</div>
        </Link>

        <Link to={snapshotLink} className={styles.quickCard} aria-label={t('esg:dashboard.kpis.snapshot.title')}>
          <div className={styles.quickHeader}>
            <div className={styles.quickTitle}>{t('esg:dashboard.kpis.snapshot.title')}</div>
            <div className={styles.quickArrow} aria-hidden="true">
              →
            </div>
          </div>
          <div className={styles.quickValue}>{gapsLoading ? '…' : gapsWithPublished.toLocaleString()}</div>
          <div className={styles.quickMeta}>
            {gapsLoading
              ? t('esg:dashboard.kpis.snapshot.metaLoading')
              : t('esg:dashboard.kpis.snapshot.meta', {
                  published: gapsWithPublished.toLocaleString(),
                  total: gapsTotal.toLocaleString(),
                  missing: gapsMissing.toLocaleString(),
                })}
          </div>
        </Link>
      </section>

      <section className={styles.secondaryGrid} aria-label={t('esg:dashboard.queue.aria')}>
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2 className={styles.panelTitle}>{t('esg:dashboard.queue.title')}</h2>
            <span className={styles.panelHint}>{t('esg:dashboard.queue.hint')}</span>
          </div>

          <ul className={styles.taskList}>
            {gapsLoading && (
              <li className={styles.taskItem}>
                <span className={styles.taskLinkMuted}>{t('esg:dashboard.queue.loading.title')}</span>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.loading.meta')}</span>
              </li>
            )}

            {!gapsLoading && gapsQuery.error && (
              <li className={styles.taskItem}>
                <span className={styles.taskLinkMuted}>{t('esg:dashboard.queue.error.title')}</span>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.error.meta')}</span>
              </li>
            )}

            {!gapsLoading && !gapsQuery.error && gapsTotal > 0 && gapsMissing > 0 && (
              <li className={styles.taskItem}>
                <Link to={issuesLink} className={styles.taskLink}>
                  {t('esg:dashboard.queue.items.missingPublished.title', { count: gapsMissing })}
                </Link>
                <span className={styles.taskMeta}>
                  {t('esg:dashboard.queue.items.missingPublished.meta', {
                    published: gapsWithPublished.toLocaleString(),
                    total: gapsTotal.toLocaleString(),
                  })}
                </span>
              </li>
            )}

            {!gapsLoading && !gapsQuery.error && reviewOverdueCount > 0 && (
              <li className={styles.taskItem}>
                <Link to={factsInReviewLink} className={styles.taskLink}>
                  {t('esg:dashboard.queue.items.reviewOverdue.title', { count: reviewOverdueCount })}
                </Link>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.items.reviewOverdue.meta')}</span>
              </li>
            )}

            {!gapsLoading && !gapsQuery.error && missingEvidenceCount > 0 && (
              <li className={styles.taskItem}>
                <Link to={factsEvidenceMissingLink} className={styles.taskLink}>
                  {t('esg:dashboard.queue.items.missingEvidence.title', {
                    count: missingEvidenceCount,
                  })}
                </Link>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.items.missingEvidence.meta')}</span>
              </li>
            )}

            {!gapsLoading && !gapsQuery.error && outOfRangeCount > 0 && (
              <li className={styles.taskItem}>
                <Link to={issuesLink} className={styles.taskLink}>
                  {t('esg:dashboard.queue.items.outOfRange.title', { count: outOfRangeCount })}
                </Link>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.items.outOfRange.meta')}</span>
              </li>
            )}

            {!gapsLoading && !gapsQuery.error && missingSourcesCount > 0 && (
              <li className={styles.taskItem}>
                <Link to={issuesLink} className={styles.taskLink}>
                  {t('esg:dashboard.queue.items.missingSources.title', { count: missingSourcesCount })}
                </Link>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.items.missingSources.meta')}</span>
              </li>
            )}

            {!gapsLoading && !gapsQuery.error && gapsTotal > 0 && gapsMissing === 0 && issuesTotal === 0 && (
              <li className={styles.taskItem}>
                <span className={styles.taskLinkMuted}>{t('esg:dashboard.queue.empty.title')}</span>
                <span className={styles.taskMeta}>{t('esg:dashboard.queue.empty.meta')}</span>
              </li>
            )}
          </ul>
        </div>

      </section>
    </EsgShell>
  )
}
