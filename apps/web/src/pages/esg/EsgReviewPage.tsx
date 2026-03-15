import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useEsgFacts, useEsgMetrics, usePublishEsgFact, useRequestEsgFactChanges } from '@/api/hooks'
import { EsgFactEvidenceModal } from '@/components/esg/EsgFactEvidenceModal'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, ConfirmDialog, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { canPublishEsg, canWriteEsg, useAuthStore } from '@/stores/authStore'
import type { EsgFact, EsgMetric } from '@/types/api'
import { collectEsgFactQualityGateIssues, getEsgEvidenceMinItems } from '@/utils/esgFactSchema'

import styles from './EsgReviewPage.module.css'

const REVIEW_SLA_DAYS = 7
const PAGE_SIZE = 50

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

type ReviewView = 'in_review' | 'overdue' | 'ready'

function resolveView(raw: string | null): ReviewView {
  if (raw === 'overdue' || raw === 'ready' || raw === 'in_review') return raw
  return 'in_review'
}

function statusBadge(status: string, metric?: EsgMetric) {
  if (status === 'published') return <span className={`${styles.badge} ${styles.badgePublished}`}>{metric ? 'Published' : status}</span>
  if (status === 'in_review') return <span className={`${styles.badge} ${styles.badgeInReview}`}>{metric ? 'In review' : status}</span>
  if (status === 'superseded') return <span className={`${styles.badge} ${styles.badgeSuperseded}`}>{status}</span>
  return <span className={`${styles.badge} ${styles.badgeDraft}`}>{metric ? 'Draft' : status}</span>
}

function issueChipLabel(code: string) {
  if (code === 'missing_evidence') return 'Evidence'
  if (code.startsWith('missing_source:')) return 'Source'
  if (code === 'range_below_min' || code === 'range_above_max') return 'Range'
  if (code === 'review_overdue') return 'Overdue'
  return code
}

export function EsgReviewPage() {
  const { t } = useTranslation(['esg', 'common'])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const user = useAuthStore((s) => s.user)
  const activeMembership = user?.memberships?.find((m) => m.isActive) ?? null
  const companyId = activeMembership?.companyId ?? ''
  const canWrite = canWriteEsg(user, companyId)
  const canPublish = canPublishEsg(user, companyId)

  const resolvedYear = (() => {
    const raw = searchParams.get('year')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return getDefaultYear()
    if (!Number.isInteger(parsed)) return getDefaultYear()
    if (parsed < 2000 || parsed > 2100) return getDefaultYear()
    return parsed
  })()

  const view = resolveView(searchParams.get('view'))

  const [query, setQuery] = useState('')

  const page = (() => {
    const raw = searchParams.get('page')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return 1
    if (!Number.isInteger(parsed)) return 1
    if (parsed < 1) return 1
    return parsed
  })()

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

  const viewOptions = useMemo(
    () => [
      { value: 'in_review', label: t('esg:reviewPage.filters.views.inReview') },
      { value: 'ready', label: t('esg:reviewPage.filters.views.ready') },
      { value: 'overdue', label: t('esg:reviewPage.filters.views.overdue') },
    ],
    [t]
  )

  const metricsQuery = useEsgMetrics({ includeInactive: true, page: 1, pageSize: 100 })
  const metricsById = useMemo(() => new Map((metricsQuery.data?.items ?? []).map((m) => [m.metric_id, m])), [metricsQuery.data?.items])

  const factsQuery = useEsgFacts({
    status: 'in_review',
    period_from: periodStart,
    period_to: periodEnd,
    latest_only: true,
    page,
    pageSize: PAGE_SIZE,
  })

  const publishFact = usePublishEsgFact()
  const requestChanges = useRequestEsgFactChanges()

  const [activeFact, setActiveFact] = useState<EsgFact | null>(null)
  const [evidenceFact, setEvidenceFact] = useState<EsgFact | null>(null)
  const [requestChangesFact, setRequestChangesFact] = useState<EsgFact | null>(null)
  const [requestChangesReason, setRequestChangesReason] = useState('')
  const [confirmPublish, setConfirmPublish] = useState<EsgFact | null>(null)

  const cutoffUtc = useMemo(() => {
    const ms = REVIEW_SLA_DAYS * 24 * 60 * 60 * 1000
    return new Date(Date.now() - ms)
  }, [])

  const rows = useMemo(() => {
    const items = factsQuery.data?.items ?? []
    const q = query.trim().toLowerCase()
    return items
      .map((fact) => {
        const metric = metricsById.get(fact.metric_id)
        const evidenceMin = getEsgEvidenceMinItems(metric?.value_schema_json)
        const evidenceCount = typeof fact.evidence_count === 'number' ? fact.evidence_count : null
        const gateIssues = collectEsgFactQualityGateIssues({
          schema: metric?.value_schema_json,
          fact: {
            value_json: fact.value_json,
            dataset_id: fact.dataset_id,
            sources_json: fact.sources_json,
            evidence_count: evidenceCount,
          },
        })
        const overdue = new Date(fact.updated_at_utc).getTime() < cutoffUtc.getTime()
        const passesGates = gateIssues.length === 0
        return { fact, metric, evidenceMin, evidenceCount, gateIssues, overdue, passesGates }
      })
      .filter((row) => {
        if (view === 'overdue') return row.overdue
        if (view === 'ready') return row.passesGates
        return true
      })
      .filter((row) => {
        if (!q) return true
        const metric = row.metric
        if (!metric) return row.fact.metric_id.toLowerCase().includes(q)
        return (
          metric.name.toLowerCase().includes(q) ||
          (metric.code ? metric.code.toLowerCase().includes(q) : false) ||
          metric.metric_id.toLowerCase().includes(q)
        )
      })
  }, [cutoffUtc, factsQuery.data?.items, metricsById, query, view])

  const counts = useMemo(() => {
    const items = factsQuery.data?.items ?? []
    let overdue = 0
    let ready = 0
    for (const fact of items) {
      const metric = metricsById.get(fact.metric_id)
      const evidenceCount = typeof fact.evidence_count === 'number' ? fact.evidence_count : null
      const gateIssues = collectEsgFactQualityGateIssues({
        schema: metric?.value_schema_json,
        fact: {
          value_json: fact.value_json,
          dataset_id: fact.dataset_id,
          sources_json: fact.sources_json,
          evidence_count: evidenceCount,
        },
      })
      const isOverdue = new Date(fact.updated_at_utc).getTime() < cutoffUtc.getTime()
      if (isOverdue) overdue += 1
      if (gateIssues.length === 0) ready += 1
    }
    return { total: items.length, overdue, ready }
  }, [cutoffUtc, factsQuery.data?.items, metricsById])

  const handleYearChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('year', next)
    nextParams.delete('page')
    setSearchParams(nextParams, { replace: true })
  }

  const handleViewChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('view', next)
    else nextParams.delete('view')
    nextParams.delete('page')
    setSearchParams(nextParams, { replace: true })
  }

  const setPage = (next: number) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next <= 1) nextParams.delete('page')
    else nextParams.set('page', String(next))
    setSearchParams(nextParams, { replace: true })
  }

  const approveAndPublish = async (fact: EsgFact) => {
    if (!canPublish) return
    try {
      await publishFact.mutateAsync(fact.fact_id)
      toast.success(t('esg:reviewPage.toast.published'))
      setConfirmPublish(null)
    } catch (e) {
      toast.error((e as Error).message || t('esg:reviewPage.toast.publishFailed'))
    }
  }

  const doRequestChanges = async (fact: EsgFact, reason: string) => {
    if (!canWrite) return
    try {
      await requestChanges.mutateAsync({ factId: fact.fact_id, data: { reason } })
      toast.success(t('esg:reviewPage.toast.changesRequested'))
      setRequestChangesFact(null)
      setRequestChangesReason('')
    } catch (e) {
      toast.error((e as Error).message || t('esg:reviewPage.toast.requestChangesFailed'))
    }
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

  return (
    <EsgShell
      title={t('esg:reviewPage.title')}
      subtitle={t('esg:reviewPage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={() => navigate(`/esg/facts?status=in_review&latest_only=true&period_from=${periodStart}&period_to=${periodEnd}`)}>
            {t('esg:reviewPage.actions.openFacts')}
          </Button>
        </div>
      }
    >
      <section className={styles.toolbar} aria-label={t('esg:reviewPage.filters.aria')}>
        <Select
          label={t('esg:reviewPage.filters.year')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <Select
          label={t('esg:reviewPage.filters.view')}
          value={view}
          onChange={(e) => handleViewChange(e.target.value)}
          options={viewOptions}
        />
        <Input
          label={t('esg:reviewPage.filters.search')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('esg:reviewPage.filters.searchPlaceholder')}
        />
        <div className={styles.toolbarMeta}>
          {t('esg:reviewPage.filters.period', { start: periodStart, end: periodEnd })}
        </div>
      </section>

      <div className={styles.summaryRow} aria-label={t('esg:reviewPage.summary.aria')}>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:reviewPage.summary.total')}</div>
          <div className={styles.summaryValue}>{counts.total}</div>
        </div>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:reviewPage.summary.ready')}</div>
          <div className={styles.summaryValue}>{counts.ready}</div>
        </div>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:reviewPage.summary.overdue')}</div>
          <div className={styles.summaryValue}>{counts.overdue}</div>
        </div>
      </div>

      {factsQuery.isLoading && <div className={styles.loading}>{t('esg:reviewPage.loading')}</div>}
      {factsQuery.error && <div className={styles.error}>{t('esg:reviewPage.error')}</div>}

      {!factsQuery.isLoading && !factsQuery.error && rows.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyTitle}>{t('esg:reviewPage.empty.title')}</div>
          <div className={styles.emptyBody}>{t('esg:reviewPage.empty.body')}</div>
        </div>
      )}

      {rows.length > 0 && (
        <>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t('esg:reviewPage.table.headers.metric')}</th>
                  <th style={{ width: '22%' }}>{t('esg:reviewPage.table.headers.value')}</th>
                  <th style={{ width: '12%' }}>{t('esg:reviewPage.table.headers.evidence')}</th>
                  <th style={{ width: '22%' }}>{t('esg:reviewPage.table.headers.quality')}</th>
                  <th style={{ width: '16%' }}>{t('esg:reviewPage.table.headers.updated')}</th>
                  <th style={{ width: '20%' }} />
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const metric = row.metric
                  const title = metric?.name ?? shortId(row.fact.metric_id)
                  const code = metric?.code
                  const chips = [
                    ...(row.gateIssues.map((i) => i.code) as string[]),
                    ...(row.overdue ? (['review_overdue'] as const) : []),
                  ]
                  const uniqueChips = Array.from(new Set(chips))
                  return (
                    <tr key={row.fact.fact_id}>
                      <td>
                        <div className={styles.metricName}>{title}</div>
                        <div className={styles.metricMeta}>
                          {code ? <span className={styles.metricCode}>{code}</span> : null}
                          <span className={styles.metricStatus}>{statusBadge(row.fact.status)}</span>
                        </div>
                      </td>
                      <td className={styles.mono}>{renderFactValue(row.fact)}</td>
                      <td>
                        <button
                          type="button"
                          className={evidenceClass({ evidenceCount: row.evidenceCount, evidenceMin: row.evidenceMin })}
                          onClick={() => setEvidenceFact(row.fact)}
                          disabled={!canWrite}
                        >
                          {evidenceLabel({ evidenceCount: row.evidenceCount, evidenceMin: row.evidenceMin })}
                        </button>
                      </td>
                      <td>
                        <div className={styles.chips}>
                          {uniqueChips.length === 0 ? (
                            <span className={styles.chipOk}>{t('esg:reviewPage.quality.ok')}</span>
                          ) : (
                            uniqueChips.map((code) => (
                              <span key={code} className={code === 'review_overdue' ? styles.chipWarn : styles.chip}>
                                {issueChipLabel(code)}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td>
                        <div className={styles.updatedAt}>{formatIsoDate(row.fact.updated_at_utc)}</div>
                      </td>
                      <td>
                        <div className={styles.rowActions}>
                          <Button variant="secondary" size="sm" onClick={() => setActiveFact(row.fact)}>
                            {t('esg:reviewPage.actions.open')}
                          </Button>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => {
                              setRequestChangesFact(row.fact)
                              setRequestChangesReason('')
                            }}
                            disabled={!canWrite}
                          >
                            {t('esg:reviewPage.actions.requestChanges')}
                          </Button>
                          <Button
                            size="sm"
                            disabled={!canPublish || !row.passesGates}
                            loading={publishFact.isPending && confirmPublish?.fact_id === row.fact.fact_id}
                            onClick={() => setConfirmPublish(row.fact)}
                          >
                            {t('esg:reviewPage.actions.publish')}
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
            <div className={styles.pagerMeta}>
              {t('esg:reviewPage.pager.page', { page })}
            </div>
            <div className={styles.pagerActions}>
              <Button variant="secondary" size="sm" onClick={() => setPage(page - 1)} disabled={page <= 1}>
                {t('common:actions.prev')}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={factsQuery.data ? factsQuery.data.items.length < PAGE_SIZE : true}
              >
                {t('common:actions.next')}
              </Button>
            </div>
          </div>
        </>
      )}

      {activeFact && (
        <Modal
          isOpen={Boolean(activeFact)}
          onClose={() => setActiveFact(null)}
          title={t('esg:reviewPage.details.title')}
          size="lg"
        >
          <div className={styles.detailTop}>
            <div>
              <div className={styles.detailMetricName}>{metricsById.get(activeFact.metric_id)?.name ?? shortId(activeFact.metric_id)}</div>
              <div className={styles.detailMetricMeta}>
                {metricsById.get(activeFact.metric_id)?.code ? (
                  <span className={styles.metricCode}>{metricsById.get(activeFact.metric_id)?.code}</span>
                ) : null}
                <span className={styles.metricStatus}>{statusBadge(activeFact.status)}</span>
              </div>
            </div>
            <div className={styles.detailActions}>
              <Button variant="secondary" onClick={() => setEvidenceFact(activeFact)} disabled={!canWrite}>
                {t('esg:reviewPage.details.openEvidence')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setRequestChangesFact(activeFact)
                  setRequestChangesReason('')
                }}
                disabled={!canWrite}
              >
                {t('esg:reviewPage.actions.requestChanges')}
              </Button>
              <Button
                disabled={!canPublish}
                loading={publishFact.isPending && confirmPublish?.fact_id === activeFact.fact_id}
                onClick={() => setConfirmPublish(activeFact)}
              >
                {t('esg:reviewPage.actions.publish')}
              </Button>
            </div>
          </div>

          <div className={styles.detailGrid}>
            <div className={styles.detailCard}>
              <div className={styles.detailLabel}>{t('esg:reviewPage.details.currentValue')}</div>
              <div className={styles.detailValueMono}>{renderFactValue(activeFact)}</div>
            </div>
            <div className={styles.detailCard}>
              <div className={styles.detailLabel}>{t('esg:reviewPage.details.updated')}</div>
              <div className={styles.detailValue}>{formatIsoDate(activeFact.updated_at_utc)}</div>
            </div>
          </div>

          <div className={styles.detailFooter}>
            <Link className={styles.advancedLink} to={`/esg/facts?status=in_review&latest_only=true&period_from=${periodStart}&period_to=${periodEnd}`}>
              {t('esg:reviewPage.details.openAdvanced')}
            </Link>
          </div>
        </Modal>
      )}

      <Modal
        isOpen={Boolean(requestChangesFact)}
        onClose={() => setRequestChangesFact(null)}
        title={t('esg:reviewPage.requestChanges.title')}
        size="lg"
      >
        {requestChangesFact && (
          <>
            <label className={styles.textareaLabel} htmlFor="esg-review-request-changes">
              {t('esg:reviewPage.requestChanges.reasonLabel')}
            </label>
            <textarea
              id="esg-review-request-changes"
              className={styles.textarea}
              value={requestChangesReason}
              onChange={(e) => setRequestChangesReason(e.target.value)}
              placeholder={t('esg:reviewPage.requestChanges.reasonPlaceholder')}
              disabled={requestChanges.isPending}
            />
            <div className={styles.modalActions}>
              <Button variant="secondary" onClick={() => setRequestChangesFact(null)} disabled={requestChanges.isPending}>
                {t('common:actions.cancel')}
              </Button>
              <Button
                onClick={() => {
                  const reason = requestChangesReason.trim()
                  if (!reason) {
                    toast.error(t('esg:reviewPage.toast.reasonRequired'))
                    return
                  }
                  void doRequestChanges(requestChangesFact, reason)
                }}
                loading={requestChanges.isPending}
                disabled={!canWrite}
              >
                {t('esg:reviewPage.requestChanges.send')}
              </Button>
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
          meta={`${metricsById.get(evidenceFact.metric_id)?.name ?? shortId(evidenceFact.metric_id)} · ${evidenceFact.period_start} → ${evidenceFact.period_end}`}
          onClose={() => setEvidenceFact(null)}
        />
      )}

      <ConfirmDialog
        isOpen={Boolean(confirmPublish)}
        title={t('esg:reviewPage.publish.confirmTitle')}
        message={t('esg:reviewPage.publish.confirmBody')}
        confirmLabel={t('esg:reviewPage.actions.publish')}
        cancelLabel={t('common:actions.cancel')}
        confirmLoading={publishFact.isPending}
        variant="info"
        onCancel={() => setConfirmPublish(null)}
        onConfirm={() => {
          if (!confirmPublish) return
          void approveAndPublish(confirmPublish)
        }}
      />
    </EsgShell>
  )
}
