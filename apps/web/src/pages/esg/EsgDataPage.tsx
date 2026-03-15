import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useCompanyMemberships, useEsgFacts, useEsgMetricOwners, useEsgMetrics, useUpsertEsgMetricOwner } from '@/api/hooks'
import { EsgFactEvidenceModal } from '@/components/esg/EsgFactEvidenceModal'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { canWriteEsg, useAuthStore } from '@/stores/authStore'
import type { EsgFact, EsgMetric } from '@/types/api'
import { collectEsgFactQualityGateIssues, getEsgEvidenceMinItems } from '@/utils/esgFactSchema'

import styles from './EsgDataPage.module.css'

const METRICS_PAGE_SIZE = 50
const FACTS_PAGE_SIZE = 100
const REVIEW_SLA_DAYS = 7

function getDefaultYear() {
  const now = new Date()
  return now.getFullYear() - 1
}

function shortId(id: string) {
  return id.length > 10 ? `${id.slice(0, 8)}…` : id
}

function renderFactValue(fact: EsgFact): string {
  if (fact.dataset_id) {
    return `dataset:${shortId(fact.dataset_revision_id ?? fact.dataset_id)}`
  }
  const v = fact.value_json
  if (v === null || typeof v === 'undefined') return '—'
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v)
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function formatIsoDate(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

type ChecklistStatus = 'all' | 'missing' | 'draft' | 'in_review' | 'published'

function resolveStatus(raw: string | null): ChecklistStatus {
  if (raw === 'missing' || raw === 'draft' || raw === 'in_review' || raw === 'published' || raw === 'all') return raw
  return 'all'
}

function statusBadge(status: ChecklistStatus | EsgFact['status']) {
  if (status === 'missing') return <span className={`${styles.badge} ${styles.badgeMissing}`}>Missing</span>
  if (status === 'published') return <span className={`${styles.badge} ${styles.badgePublished}`}>Published</span>
  if (status === 'in_review') return <span className={`${styles.badge} ${styles.badgeInReview}`}>In review</span>
  if (status === 'draft') return <span className={`${styles.badge} ${styles.badgeDraft}`}>Draft</span>
  if (status === 'superseded') return <span className={`${styles.badge} ${styles.badgeMissing}`}>Superseded</span>
  return <span className={styles.badge}>—</span>
}

function issueChipLabel(code: string) {
  if (code === 'missing_evidence') return 'Evidence'
  if (code.startsWith('missing_source:')) return 'Source'
  if (code === 'range_below_min' || code === 'range_above_max') return 'Range'
  if (code === 'review_overdue') return 'Overdue'
  return code
}

function isChecklistFact(f: EsgFact, periodStart: string, periodEnd: string) {
  return (
    f.period_type === 'year' &&
    f.period_start === periodStart &&
    f.period_end === periodEnd &&
    !f.is_ytd &&
    f.entity_id === null &&
    f.location_id === null &&
    f.segment_id === null
  )
}

export function EsgDataPage() {
  const { t } = useTranslation(['esg', 'common'])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const user = useAuthStore((s) => s.user)
  const activeMembership = user?.memberships?.find((m) => m.isActive) ?? null
  const companyId = activeMembership?.companyId ?? ''
  const canWrite = canWriteEsg(user, companyId)

  const resolvedYear = (() => {
    const raw = searchParams.get('year')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return getDefaultYear()
    if (!Number.isInteger(parsed)) return getDefaultYear()
    if (parsed < 2000 || parsed > 2100) return getDefaultYear()
    return parsed
  })()

  const statusFilter = resolveStatus(searchParams.get('status'))

  const metricsPage = (() => {
    const raw = searchParams.get('page')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return 1
    if (!Number.isInteger(parsed)) return 1
    if (parsed < 1) return 1
    return parsed
  })()

  const [query, setQuery] = useState('')

  const periodStart = `${resolvedYear}-01-01`
  const periodEnd = `${resolvedYear}-12-31`

  const yearOptions = useMemo(() => {
    const current = new Date().getFullYear()
    const years: Array<{ value: string; label: string }> = []
    for (let y = current + 1; y >= current - 10; y -= 1) {
      years.push({ value: String(y), label: String(y) })
    }
    return years
  }, [])

  const statusOptions = useMemo(
    () => [
      { value: 'all', label: t('esg:dataPage.filters.status.all') },
      { value: 'missing', label: t('esg:dataPage.filters.status.missing') },
      { value: 'draft', label: t('esg:dataPage.filters.status.draft') },
      { value: 'in_review', label: t('esg:dataPage.filters.status.inReview') },
      { value: 'published', label: t('esg:dataPage.filters.status.published') },
    ],
    [t]
  )

  const metricsQuery = useEsgMetrics({
    search: query.trim() ? query.trim() : undefined,
    includeInactive: false,
    page: metricsPage,
    pageSize: METRICS_PAGE_SIZE,
  })

  const metrics = useMemo(() => metricsQuery.data?.items ?? [], [metricsQuery.data?.items])

  const metricOwnersQuery = useEsgMetricOwners()
  const ownersByMetricId = useMemo(() => {
    const items = metricOwnersQuery.data ?? []
    return new Map(items.map((o) => [o.metric_id, o]))
  }, [metricOwnersQuery.data])

  const membershipsQuery = useCompanyMemberships(companyId)
  const upsertOwner = useUpsertEsgMetricOwner()

  const factsInReview1 = useEsgFacts({
    status: 'in_review',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: FACTS_PAGE_SIZE,
  })
  const factsInReview2 = useEsgFacts({
    status: 'in_review',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 2,
    pageSize: FACTS_PAGE_SIZE,
    enabled: (factsInReview1.data?.total ?? 0) > FACTS_PAGE_SIZE,
  })

  const factsDraft1 = useEsgFacts({
    status: 'draft',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: FACTS_PAGE_SIZE,
  })
  const factsDraft2 = useEsgFacts({
    status: 'draft',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 2,
    pageSize: FACTS_PAGE_SIZE,
    enabled: (factsDraft1.data?.total ?? 0) > FACTS_PAGE_SIZE,
  })

  const factsPublished1 = useEsgFacts({
    status: 'published',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 1,
    pageSize: FACTS_PAGE_SIZE,
  })
  const factsPublished2 = useEsgFacts({
    status: 'published',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page: 2,
    pageSize: FACTS_PAGE_SIZE,
    enabled: (factsPublished1.data?.total ?? 0) > FACTS_PAGE_SIZE,
  })

  const allInReviewFacts = useMemo(() => {
    const items = [...(factsInReview1.data?.items ?? []), ...(factsInReview2.data?.items ?? [])]
    return items.filter((f) => isChecklistFact(f, periodStart, periodEnd))
  }, [factsInReview1.data?.items, factsInReview2.data?.items, periodEnd, periodStart])

  const allDraftFacts = useMemo(() => {
    const items = [...(factsDraft1.data?.items ?? []), ...(factsDraft2.data?.items ?? [])]
    return items.filter((f) => isChecklistFact(f, periodStart, periodEnd))
  }, [factsDraft1.data?.items, factsDraft2.data?.items, periodEnd, periodStart])

  const allPublishedFacts = useMemo(() => {
    const items = [...(factsPublished1.data?.items ?? []), ...(factsPublished2.data?.items ?? [])]
    return items.filter((f) => isChecklistFact(f, periodStart, periodEnd))
  }, [factsPublished1.data?.items, factsPublished2.data?.items, periodEnd, periodStart])

  const factsByMetric = useMemo(() => {
    const bucket = new Map<string, { in_review: EsgFact[]; draft: EsgFact[]; published: EsgFact[] }>()
    const ensure = (metricId: string) => {
      const current = bucket.get(metricId)
      if (current) return current
      const next = { in_review: [], draft: [], published: [] }
      bucket.set(metricId, next)
      return next
    }

    for (const f of allInReviewFacts) ensure(f.metric_id).in_review.push(f)
    for (const f of allDraftFacts) ensure(f.metric_id).draft.push(f)
    for (const f of allPublishedFacts) ensure(f.metric_id).published.push(f)

    for (const v of bucket.values()) {
      v.in_review.sort((a, b) => new Date(b.updated_at_utc).getTime() - new Date(a.updated_at_utc).getTime())
      v.draft.sort((a, b) => new Date(b.updated_at_utc).getTime() - new Date(a.updated_at_utc).getTime())
      v.published.sort((a, b) => new Date(b.updated_at_utc).getTime() - new Date(a.updated_at_utc).getTime())
    }

    return bucket
  }, [allDraftFacts, allInReviewFacts, allPublishedFacts])

  const cutoffUtc = useMemo(() => new Date(Date.now() - REVIEW_SLA_DAYS * 24 * 60 * 60 * 1000), [])

  const rows = useMemo(() => {
    return metrics
      .map((metric) => {
        const facts = factsByMetric.get(metric.metric_id) ?? { in_review: [], draft: [], published: [] }
        const bestFact = facts.in_review[0] ?? facts.draft[0] ?? facts.published[0] ?? null
        const status: ChecklistStatus = bestFact ? (bestFact.status === 'superseded' ? 'draft' : bestFact.status) : 'missing'

        const evidenceMin = getEsgEvidenceMinItems(metric.value_schema_json)
        const evidenceCount = bestFact && typeof bestFact.evidence_count === 'number' ? bestFact.evidence_count : null

        const gateIssues =
          bestFact && bestFact.status !== 'published'
            ? collectEsgFactQualityGateIssues({
                schema: metric.value_schema_json,
                fact: {
                  value_json: bestFact.value_json,
                  dataset_id: bestFact.dataset_id,
                  sources_json: bestFact.sources_json,
                  evidence_count: evidenceCount,
                },
              })
            : []

        const overdue =
          bestFact && bestFact.status === 'in_review' && new Date(bestFact.updated_at_utc).getTime() < cutoffUtc.getTime()

        return {
          metric,
          facts,
          bestFact,
          status,
          evidenceMin,
          evidenceCount,
          gateIssues,
          overdue,
        }
      })
      .filter((row) => {
        if (statusFilter === 'all') return true
        return row.status === statusFilter
      })
  }, [cutoffUtc, factsByMetric, metrics, statusFilter])

  const [activeRow, setActiveRow] = useState<{
    metric: EsgMetric
    facts: { in_review: EsgFact[]; draft: EsgFact[]; published: EsgFact[] }
    bestFact: EsgFact | null
  } | null>(null)

  const [evidenceFact, setEvidenceFact] = useState<EsgFact | null>(null)

  const ownerOptions = useMemo(() => {
    const items = membershipsQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:dataPage.owner.unassigned') }]
    for (const m of items) {
      const label = m.user_name || m.user_email || m.user_id
      opts.push({ value: m.user_id, label })
    }
    return opts
  }, [membershipsQuery.data?.items, t])

  const handleYearChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('year', next)
    nextParams.delete('page')
    setSearchParams(nextParams, { replace: true })
  }

  const handleStatusChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next && next !== 'all') nextParams.set('status', next)
    else nextParams.delete('status')
    nextParams.delete('page')
    setSearchParams(nextParams, { replace: true })
  }

  const setMetricsPage = (next: number) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next <= 1) nextParams.delete('page')
    else nextParams.set('page', String(next))
    setSearchParams(nextParams, { replace: true })
  }

  const openCreateFact = (metricId: string) => {
    navigate(`/esg/facts/new?metric_id=${encodeURIComponent(metricId)}&year=${resolvedYear}`)
  }

  const openFactsForMetric = (metricId: string) => {
    const p = new URLSearchParams()
    p.set('metric_id', metricId)
    p.set('latest_only', 'true')
    p.set('period_from', periodStart)
    p.set('period_to', periodEnd)
    navigate(`/esg/facts?${p.toString()}`)
  }

  const evidenceLabel = (row: { evidenceCount: number | null; evidenceMin: number | null }) => {
    if (row.evidenceCount === null) return '—'
    if (row.evidenceMin) return `${row.evidenceCount}/${row.evidenceMin}`
    return String(row.evidenceCount)
  }

  const evidenceClass = (row: { evidenceCount: number | null; evidenceMin: number | null }) => {
    if (row.evidenceCount === null) return `${styles.evidenceBadge} ${styles.evidenceBadgeLoading}`
    if (row.evidenceMin) {
      return row.evidenceCount >= row.evidenceMin
        ? `${styles.evidenceBadge} ${styles.evidenceBadgeOk}`
        : `${styles.evidenceBadge} ${styles.evidenceBadgeMissing}`
    }
    return row.evidenceCount > 0 ? `${styles.evidenceBadge} ${styles.evidenceBadgeOk}` : styles.evidenceBadge
  }

  const allFactsLoading = factsInReview1.isLoading || factsDraft1.isLoading || factsPublished1.isLoading
  const anyFactsError = Boolean(factsInReview1.error || factsDraft1.error || factsPublished1.error)

  return (
    <EsgShell
      title={t('esg:dataPage.title')}
      subtitle={t('esg:dataPage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={() => navigate('/esg/facts')}>
            {t('esg:dataPage.actions.openFacts')}
          </Button>
          <Button onClick={() => navigate(`/esg/facts/new?year=${resolvedYear}`)}>{t('esg:dataPage.actions.addData')}</Button>
        </div>
      }
    >
      <section className={styles.toolbar} aria-label={t('esg:dataPage.filters.aria')}>
        <Select
          label={t('esg:dataPage.filters.year')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <Select
          label={t('esg:dataPage.filters.status.label')}
          value={statusFilter}
          onChange={(e) => handleStatusChange(e.target.value)}
          options={statusOptions}
        />
        <Input
          label={t('esg:dataPage.filters.search')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('esg:dataPage.filters.searchPlaceholder')}
        />
        <div className={styles.toolbarMeta}>{t('esg:dataPage.filters.period', { start: periodStart, end: periodEnd })}</div>
      </section>

      {(metricsQuery.isLoading || allFactsLoading) && <div className={styles.loading}>{t('esg:dataPage.loading')}</div>}
      {(metricsQuery.error || anyFactsError) && <div className={styles.error}>{t('esg:dataPage.error')}</div>}

      {!metricsQuery.isLoading && !metricsQuery.error && metrics.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyTitle}>{t('esg:dataPage.empty.title')}</div>
          <div className={styles.emptyBody}>{t('esg:dataPage.empty.body')}</div>
        </div>
      )}

      {metrics.length > 0 && (
        <>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t('esg:dataPage.table.headers.metric')}</th>
                  <th style={{ width: '16%' }}>{t('esg:dataPage.table.headers.owner')}</th>
                  <th style={{ width: '20%' }}>{t('esg:dataPage.table.headers.value')}</th>
                  <th style={{ width: '12%' }}>{t('esg:dataPage.table.headers.status')}</th>
                  <th style={{ width: '12%' }}>{t('esg:dataPage.table.headers.evidence')}</th>
                  <th>{t('esg:dataPage.table.headers.quality')}</th>
                  <th style={{ width: '18%' }}>{t('esg:dataPage.table.headers.updated')}</th>
                  <th style={{ width: '14%' }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const metric = row.metric
                  const code = metric.code
                  const owner = ownersByMetricId.get(metric.metric_id)
                  const ownerLabel = owner?.owner_user_name || owner?.owner_user_email || owner?.owner_user_id || t('esg:dataPage.owner.unassigned')
                  const chips = [
                    ...(row.gateIssues.map((i) => i.code) as string[]),
                    ...(row.overdue ? (['review_overdue'] as const) : []),
                  ]
                  const uniqueChips = Array.from(new Set(chips))
                  const updatedAt = row.bestFact ? row.bestFact.updated_at_utc : metric.updated_at_utc
                  return (
                    <tr key={metric.metric_id}>
                      <td>
                        <div className={styles.metricName}>{metric.name}</div>
                        <div className={styles.metricMeta}>
                          {code ? <span className={styles.metricCode}>{code}</span> : null}
                        </div>
                      </td>
                      <td className={styles.ownerCell}>{ownerLabel}</td>
                      <td className={styles.mono}>{row.bestFact ? renderFactValue(row.bestFact) : '—'}</td>
                      <td>{statusBadge(row.status)}</td>
                      <td>
                        {row.bestFact ? (
                          <button
                            type="button"
                            className={evidenceClass({ evidenceCount: row.evidenceCount, evidenceMin: row.evidenceMin })}
                            onClick={() => row.bestFact && setEvidenceFact(row.bestFact)}
                            disabled={!canWrite}
                          >
                            {evidenceLabel({ evidenceCount: row.evidenceCount, evidenceMin: row.evidenceMin })}
                          </button>
                        ) : (
                          <span className={styles.muted}>—</span>
                        )}
                      </td>
                      <td>
                        <div className={styles.chips}>
                          {uniqueChips.length === 0 ? (
                            <span className={styles.chipOk}>{t('esg:dataPage.quality.ok')}</span>
                          ) : (
                            uniqueChips.map((c) => (
                              <span key={c} className={c === 'review_overdue' ? styles.chipWarn : styles.chip}>
                                {issueChipLabel(c)}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className={styles.updatedAt}>{formatIsoDate(updatedAt)}</td>
                      <td>
                        <div className={styles.rowActions}>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              setActiveRow({
                                metric,
                                facts: row.facts,
                                bestFact: row.bestFact,
                              })
                            }
                          >
                            {t('esg:dataPage.actions.open')}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className={styles.pager}>
            <div className={styles.pagerMeta}>{t('esg:dataPage.pager.page', { page: metricsPage })}</div>
            <div className={styles.pagerActions}>
              <Button variant="secondary" size="sm" onClick={() => setMetricsPage(metricsPage - 1)} disabled={metricsPage <= 1}>
                {t('common:actions.prev')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setMetricsPage(metricsPage + 1)}
                disabled={metricsQuery.data ? metricsQuery.data.items.length < METRICS_PAGE_SIZE : true}
              >
                {t('common:actions.next')}
              </Button>
            </div>
          </div>
        </>
      )}

      <Modal
        isOpen={Boolean(activeRow)}
        onClose={() => setActiveRow(null)}
        title={t('esg:dataPage.details.title')}
        size="lg"
      >
        {activeRow && (
          <>
          <div className={styles.detailTop}>
            <div>
              <div className={styles.detailMetricName}>{activeRow.metric.name}</div>
              <div className={styles.detailMetricMeta}>
                {activeRow.metric.code ? <span className={styles.metricCode}>{activeRow.metric.code}</span> : null}
                {statusBadge(activeRow.bestFact ? activeRow.bestFact.status : 'missing')}
              </div>
            </div>
            <div className={styles.detailActions}>
              <Button variant="secondary" onClick={() => openFactsForMetric(activeRow.metric.metric_id)}>
                {t('esg:dataPage.details.openAdvanced')}
              </Button>
              <Button onClick={() => openCreateFact(activeRow.metric.metric_id)} disabled={!canWrite}>
                {t('esg:dataPage.details.addData')}
              </Button>
            </div>
          </div>

          <section className={styles.detailOwner} aria-label={t('esg:dataPage.owner.aria')}>
            <Select
              label={t('esg:dataPage.owner.label')}
              value={ownersByMetricId.get(activeRow.metric.metric_id)?.owner_user_id ?? ''}
              onChange={(e) => {
                const next = e.target.value
                void (async () => {
                  try {
                    await upsertOwner.mutateAsync({
                      metricId: activeRow.metric.metric_id,
                      data: { owner_user_id: next ? next : null },
                    })
                    toast.success(t('esg:dataPage.owner.toast.saved'))
                  } catch (err) {
                    toast.error((err as Error).message || t('esg:dataPage.owner.toast.saveFailed'))
                  }
                })()
              }}
              options={ownerOptions}
              disabled={!canWrite || upsertOwner.isPending}
            />
          </section>

          {!activeRow.bestFact && (
            <div className={styles.detailEmpty}>
              <div className={styles.detailEmptyTitle}>{t('esg:dataPage.details.noDataTitle')}</div>
              <div className={styles.detailEmptyBody}>{t('esg:dataPage.details.noDataBody')}</div>
            </div>
            )}

            {activeRow.bestFact && (
              <>
                <div className={styles.detailGrid}>
                  <div className={styles.detailCard}>
                    <div className={styles.detailLabel}>{t('esg:dataPage.details.currentValue')}</div>
                    <div className={styles.detailValueMono}>{renderFactValue(activeRow.bestFact)}</div>
                  </div>
                  <div className={styles.detailCard}>
                    <div className={styles.detailLabel}>{t('esg:dataPage.details.updated')}</div>
                    <div className={styles.detailValue}>{formatIsoDate(activeRow.bestFact.updated_at_utc)}</div>
                  </div>
                </div>

                <div className={styles.detailActionsRow}>
                  <Button variant="secondary" onClick={() => setEvidenceFact(activeRow.bestFact)} disabled={!canWrite}>
                    {t('esg:dataPage.details.openEvidence')}
                  </Button>
                  {activeRow.bestFact.status === 'in_review' && (
                    <Button variant="secondary" onClick={() => navigate(`/esg/review?year=${resolvedYear}&view=in_review`)}>
                      {t('esg:dataPage.details.openReview')}
                    </Button>
                  )}
                </div>

                <div className={styles.detailIssues}>
                  <div className={styles.detailLabel}>{t('esg:dataPage.details.issues')}</div>
                  {(() => {
                    const evidenceCount = typeof activeRow.bestFact?.evidence_count === 'number' ? activeRow.bestFact.evidence_count : null
                    const issues = collectEsgFactQualityGateIssues({
                      schema: activeRow.metric.value_schema_json,
                      fact: {
                        value_json: activeRow.bestFact.value_json,
                        dataset_id: activeRow.bestFact.dataset_id,
                        sources_json: activeRow.bestFact.sources_json,
                        evidence_count: evidenceCount,
                      },
                    })
                    const overdue =
                      activeRow.bestFact.status === 'in_review' &&
                      new Date(activeRow.bestFact.updated_at_utc).getTime() < cutoffUtc.getTime()
                    const chips = [...issues, ...(overdue ? [{ code: 'review_overdue', message: 'Review overdue' }] : [])]
                    if (chips.length === 0) {
                      return <div className={styles.detailOk}>{t('esg:dataPage.quality.ok')}</div>
                    }
                    return (
                      <ul className={styles.issueList}>
                        {chips.map((i, idx) => (
                          <li key={`${i.code}-${idx}`}>
                            <span className={styles.issueCode}>{i.code}</span>
                            <span className={styles.issueMsg}>{i.message}</span>
                          </li>
                        ))}
                      </ul>
                    )
                  })()}
                </div>
              </>
            )}

            <div className={styles.detailFooter}>
              <Link className={styles.advancedLink} to="/esg/facts">
                {t('esg:dataPage.details.openFactsRoot')}
              </Link>
            </div>
          </>
        )}
      </Modal>

      {evidenceFact && (
        <EsgFactEvidenceModal
          isOpen={Boolean(evidenceFact)}
          companyId={companyId}
          factId={evidenceFact.fact_id}
          canWrite={canWrite}
          meta={`${activeRow?.metric.name ?? shortId(evidenceFact.metric_id)} · ${evidenceFact.period_start} → ${evidenceFact.period_end}`}
          onClose={() => setEvidenceFact(null)}
        />
      )}
    </EsgShell>
  )
}
