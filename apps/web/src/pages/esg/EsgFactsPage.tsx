import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, DropdownMenu, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { canPublishEsg, canWriteEsg, useAuthStore } from '@/stores/authStore'
import {
  useCompanyMemberships,
  useCreateEsgFactComment,
  useEsgEntities,
  useEsgFactComments,
  useEsgFactTimeline,
  useEsgFacts,
  useEsgMetrics,
  usePublishEsgFact,
  useRequestEsgFactChanges,
  useRestateEsgFact,
  useSubmitEsgFactReview,
  useUpdateEsgFact,
} from '@/api/hooks'
import type { EsgFact, EsgMetric } from '@/types/api'
import { DatasetPicker } from '@/components/datasets/DatasetPicker'
import { EsgFactImportModal } from '@/components/esg/EsgFactImportModal'
import { EsgFactEvidenceModal } from '@/components/esg/EsgFactEvidenceModal'
import {
  collectEsgFactQualityGateIssues,
  getEsgEvidenceMinItems,
  getEsgRangeSpec,
  getEsgRequiredSourceFields,
} from '@/utils/esgFactSchema'
import styles from './EsgFactsPage.module.css'

const DEFAULT_PAGE_SIZE = 50

function shortId(id: string) {
  return id.length > 10 ? `${id.slice(0, 8)}…` : id
}

function factStatusBadge(status: string, t: (key: string) => string) {
  const cls =
    status === 'published'
      ? styles.badgePublished
      : status === 'in_review'
        ? styles.badgeInReview
        : status === 'superseded'
          ? styles.badgeSuperseded
          : styles.badgeDraft
  const label =
    status === 'draft'
      ? t('esg:factsPage.status.draft')
      : status === 'in_review'
        ? t('esg:factsPage.status.inReview')
        : status === 'published'
          ? t('esg:factsPage.status.published')
          : status === 'superseded'
            ? t('esg:factsPage.status.superseded')
            : status
  return <span className={`${styles.badge} ${cls}`}>{label}</span>
}

function renderValue(fact: EsgFact): string {
  if (fact.dataset_id) {
    return `dataset:${shortId(fact.dataset_id)}`
  }
  const v = fact.value_json
  if (v === null || v === undefined) return '—'
  if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') return String(v)
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function formatTimelineAction(action: string, t: (key: string) => string): string {
  switch (action) {
    case 'esg.fact.create':
      return t('esg:factsPage.timeline.created')
    case 'esg.fact.update':
      return t('esg:factsPage.timeline.updated')
    case 'esg.fact.submit_review':
      return t('esg:factsPage.timeline.submittedForReview')
    case 'esg.fact.request_changes':
      return t('esg:factsPage.timeline.requestedChanges')
    case 'esg.fact.publish':
      return t('esg:factsPage.timeline.approvedPublished')
    case 'esg.fact.restatement':
      return t('esg:factsPage.timeline.restated')
    case 'esg.fact_evidence.create':
      return t('esg:factsPage.timeline.evidenceAdded')
    case 'esg.fact_evidence.delete':
      return t('esg:factsPage.timeline.evidenceRemoved')
    default:
      return action
  }
}

function renderCommentBody(body: string) {
  const parts = body.split(/(\s+)/)
  return parts.map((p, idx) => {
    if (p.startsWith('@') && p.length > 1) {
      return (
        <span key={idx} className={styles.mention}>
          {p}
        </span>
      )
    }
    return <span key={idx}>{p}</span>
  })
}

export function EsgFactsPage() {
  const { t } = useTranslation(['esg', 'common'])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const didInitFromUrl = useRef(false)
  const user = useAuthStore((s) => s.user)
  const activeMembership = user?.memberships?.find((m) => m.isActive) ?? null
  const companyId = activeMembership?.companyId ?? ''
  const canWrite = canWriteEsg(user, companyId)
  const canPublish = canPublishEsg(user, companyId)

  const [metricId, setMetricId] = useState<string>('')
  const [entityId, setEntityId] = useState<string>('')
  const [status, setStatus] = useState<string>('')
  const [hasEvidence, setHasEvidence] = useState<string>('') // '' | 'true' | 'false'
  const [periodFrom, setPeriodFrom] = useState<string>('')
  const [periodTo, setPeriodTo] = useState<string>('')
  const [latestOnly, setLatestOnly] = useState<boolean>(true)
  const [page, setPage] = useState(1)

  const [historyKey, setHistoryKey] = useState<string | null>(null)
  const [editingFact, setEditingFact] = useState<EsgFact | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [evidenceFact, setEvidenceFact] = useState<EsgFact | null>(null)
  const [reviewFact, setReviewFact] = useState<EsgFact | null>(null)
  const [requestChangesFact, setRequestChangesFact] = useState<EsgFact | null>(null)
  const [requestChangesReason, setRequestChangesReason] = useState<string>('')
  const [reviewCommentBody, setReviewCommentBody] = useState<string>('')
  const [activeMention, setActiveMention] = useState<{ at: number; query: string } | null>(null)
  const reviewCommentRef = useRef<HTMLTextAreaElement | null>(null)

  const metricsQuery = useEsgMetrics({ includeInactive: true, page: 1, pageSize: 200 })
  const entitiesQuery = useEsgEntities({ includeInactive: true, page: 1, pageSize: 200 })

  const factsQuery = useEsgFacts({
    metric_id: metricId || undefined,
    entity_id: entityId || undefined,
    status: status || undefined,
    has_evidence: hasEvidence === '' ? undefined : hasEvidence === 'true',
    period_from: periodFrom || undefined,
    period_to: periodTo || undefined,
    latest_only: latestOnly,
    page,
    pageSize: DEFAULT_PAGE_SIZE,
  })

  useEffect(() => {
    if (didInitFromUrl.current) return
    didInitFromUrl.current = true

    const urlMetricId = searchParams.get('metric_id')
    if (urlMetricId) setMetricId(urlMetricId)

    const urlEntityId = searchParams.get('entity_id')
    if (urlEntityId) setEntityId(urlEntityId)

    const urlStatus = searchParams.get('status')
    if (urlStatus) setStatus(urlStatus)

    const urlHasEvidence = searchParams.get('has_evidence')
    if (urlHasEvidence === 'true' || urlHasEvidence === 'false') {
      setHasEvidence(urlHasEvidence)
    }

    const urlFrom = searchParams.get('period_from')
    if (urlFrom) setPeriodFrom(urlFrom)

    const urlTo = searchParams.get('period_to')
    if (urlTo) setPeriodTo(urlTo)

    const urlLatestOnly = searchParams.get('latest_only')
    if (urlLatestOnly === 'true' || urlLatestOnly === 'false') {
      setLatestOnly(urlLatestOnly === 'true')
    }
  }, [searchParams])

  useEffect(() => {
    if (!didInitFromUrl.current) return

    const next = new URLSearchParams()
    if (metricId) next.set('metric_id', metricId)
    if (entityId) next.set('entity_id', entityId)
    if (status) next.set('status', status)
    if (hasEvidence) next.set('has_evidence', hasEvidence)
    if (periodFrom) next.set('period_from', periodFrom)
    if (periodTo) next.set('period_to', periodTo)
    next.set('latest_only', String(latestOnly))

    setSearchParams(next, { replace: true })
  }, [entityId, hasEvidence, latestOnly, metricId, periodFrom, periodTo, setSearchParams, status])

  useEffect(() => {
    setPage(1)
  }, [entityId, hasEvidence, latestOnly, metricId, periodFrom, periodTo, status])

  useEffect(() => {
    setReviewCommentBody('')
  }, [reviewFact?.fact_id])

  const metrics = useMemo(() => metricsQuery.data?.items ?? [], [metricsQuery.data?.items])
  const entities = useMemo(() => entitiesQuery.data?.items ?? [], [entitiesQuery.data?.items])
  const facts = useMemo(() => factsQuery.data?.items ?? [], [factsQuery.data?.items])
  const total = factsQuery.data?.total ?? facts.length
  const resolvedPage = factsQuery.data?.page ?? page
  const resolvedPageSize = factsQuery.data?.page_size ?? DEFAULT_PAGE_SIZE
  const totalPages = factsQuery.data?.total_pages ?? 1
  const showingFrom = total === 0 ? 0 : (resolvedPage - 1) * resolvedPageSize + 1
  const showingTo = total === 0 ? 0 : Math.min(resolvedPage * resolvedPageSize, total)

  const metricsById = useMemo(() => {
    const m = new Map<string, EsgMetric>()
    metrics.forEach((x) => m.set(x.metric_id, x))
    return m
  }, [metrics])

  const publishFact = usePublishEsgFact()
  const restateFact = useRestateEsgFact()
  const updateFact = useUpdateEsgFact()
  const submitReview = useSubmitEsgFactReview()
  const requestChanges = useRequestEsgFactChanges()
  const membershipsQuery = useCompanyMemberships(companyId)
  const reviewCommentsQuery = useEsgFactComments(reviewFact?.fact_id || '')
  const createReviewComment = useCreateEsgFactComment()
  const reviewTimelineQuery = useEsgFactTimeline(reviewFact?.fact_id || '')

  const getActiveMentionAtCursor = (text: string, cursor: number) => {
    const before = text.slice(0, cursor)
    const at = before.lastIndexOf('@')
    if (at === -1) return null
    const prev = at === 0 ? ' ' : before[at - 1]
    if (at > 0 && !/\s|[([{]/.test(prev)) return null

    const query = before.slice(at + 1)
    if (query.includes(' ') || query.includes('\n')) return null

    return { at, query }
  }

  const mentionCandidates = useMemo(() => {
    const q = (activeMention?.query ?? '').trim().toLowerCase()
    if (!activeMention) return []

    const members = membershipsQuery.data?.items ?? []
    const enriched = members
      .filter((m) => m.is_active)
      .map((m) => ({
        user_id: m.user_id,
        name: m.user_name ?? '',
        email: m.user_email ?? '',
      }))
      .filter((m) => m.email || m.name)

    const filtered = q
      ? enriched.filter((m) => m.email.toLowerCase().includes(q) || m.name.toLowerCase().includes(q))
      : enriched

    return filtered.slice(0, 6)
  }, [activeMention, membershipsQuery.data?.items])

  const historyFactsQuery = useEsgFacts({
    logical_key_hash: historyKey || undefined,
    latest_only: false,
    page: 1,
    pageSize: 100,
    enabled: Boolean(historyKey),
  })

  const historyFacts = historyFactsQuery.data?.items ?? []

  const reviewFactsQuery = useEsgFacts({
    logical_key_hash: reviewFact?.logical_key_hash || undefined,
    latest_only: false,
    page: 1,
    pageSize: 100,
    enabled: Boolean(reviewFact),
  })

  const reviewHistory = reviewFactsQuery.data?.items ?? []
  const reviewBaseline = reviewHistory.find((i) => i.status === 'published') ?? null

  const metricOptions = useMemo(() => {
    const opts = [{ value: '', label: t('esg:factsPage.filters.allMetrics') }]
    opts.push(
      ...metrics.map((m) => ({ value: m.metric_id, label: `${m.name}${m.code ? ` (${m.code})` : ''}` }))
    )
    return opts
  }, [metrics, t])

  const entityOptions = useMemo(() => {
    const opts = [{ value: '', label: t('esg:factsPage.filters.allEntities') }]
    opts.push(...entities.map((e) => ({ value: e.entity_id, label: e.name })))
    return opts
  }, [entities, t])

  const statusOptions = [
    { value: '', label: t('esg:factsPage.filters.anyStatus') },
    { value: 'draft', label: t('esg:factsPage.status.draft') },
    { value: 'in_review', label: t('esg:factsPage.status.inReview') },
    { value: 'published', label: t('esg:factsPage.status.published') },
    { value: 'superseded', label: t('esg:factsPage.status.superseded') },
  ]

  const evidenceOptions = [
    { value: '', label: t('esg:factsPage.filters.anyEvidence') },
    { value: 'false', label: t('esg:factsPage.filters.missingEvidence') },
    { value: 'true', label: t('esg:factsPage.filters.hasEvidence') },
  ]

  const openEdit = (fact: EsgFact) => {
    setEditingFact(fact)
  }

  const doPublish = async (factId: string) => {
    try {
      await publishFact.mutateAsync(factId)
      toast.success(t('esg:factsPage.toast.published'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factsPage.toast.publishFailed'))
    }
  }

  const doSubmitReview = async (factId: string) => {
    try {
      await submitReview.mutateAsync(factId)
      toast.success(t('esg:factsPage.toast.submittedForReview'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factsPage.toast.submitForReviewFailed'))
    }
  }

  const doRequestChanges = async (factId: string, reason: string) => {
    try {
      await requestChanges.mutateAsync({ factId, data: { reason } })
      toast.success(t('esg:factsPage.toast.changesRequested'))
      setRequestChangesFact(null)
      setRequestChangesReason('')
    } catch (e) {
      toast.error((e as Error).message || t('esg:factsPage.toast.requestChangesFailed'))
    }
  }

  const doRestate = async (factId: string) => {
    try {
      const newFact = await restateFact.mutateAsync(factId)
      toast.success(t('esg:factsPage.toast.restateCreated'))
      setEditingFact(newFact)
    } catch (e) {
      toast.error((e as Error).message || t('esg:factsPage.toast.restateFailed'))
    }
  }

  const doUpdate = async (
    factId: string,
    payload: {
      value_json?: unknown
      dataset_id?: string | null
      quality_json?: Record<string, unknown>
      sources_json?: Record<string, unknown>
    }
  ) => {
    try {
      await updateFact.mutateAsync({ factId, data: payload })
      toast.success(t('esg:factsPage.toast.updated'))
      setEditingFact(null)
    } catch (e) {
      toast.error((e as Error).message || t('esg:factsPage.toast.updateFailed'))
    }
  }

  const insertMention = (email: string) => {
    const el = reviewCommentRef.current
    if (!el) return

    const cursor = el.selectionStart ?? reviewCommentBody.length
    const active = getActiveMentionAtCursor(reviewCommentBody, cursor)
    if (!active) return

    const before = reviewCommentBody.slice(0, active.at)
    const after = reviewCommentBody.slice(cursor)
    const next = `${before}@${email} ${after}`

    setReviewCommentBody(next)
    setActiveMention(null)

    requestAnimationFrame(() => {
      el.focus()
      const pos = active.at + 1 + email.length + 1
      el.setSelectionRange(pos, pos)
    })
  }

  const doAddReviewComment = async () => {
    if (!reviewFact) return
    const body = reviewCommentBody.trim()
    if (!body) {
      toast.error(t('esg:factsPage.toast.commentRequired'))
      return
    }

    try {
      await createReviewComment.mutateAsync({ factId: reviewFact.fact_id, data: { body_md: body } })
      toast.success(t('esg:factsPage.toast.commentAdded'))
      setReviewCommentBody('')
      setActiveMention(null)
    } catch (e) {
      toast.error((e as Error).message || t('esg:factsPage.toast.commentAddFailed'))
    }
  }

  return (
    <EsgShell
      title={t('esg:factsPage.title')}
      subtitle={t('esg:factsPage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={() => setImportOpen(true)} disabled={!canWrite}>
            {t('esg:factsPage.actions.import')}
          </Button>
          <Button onClick={() => navigate('/esg/facts/new')} disabled={!canWrite}>
            {t('esg:factsPage.actions.newFact')}
          </Button>
        </div>
      }
    >
      <div className={styles.filters}>
        <Select label={t('esg:factsPage.filters.metric')} value={metricId} onChange={(e) => setMetricId(e.target.value)} options={metricOptions} />
        <Select label={t('esg:factsPage.filters.entity')} value={entityId} onChange={(e) => setEntityId(e.target.value)} options={entityOptions} />
        <Select label={t('esg:factsPage.filters.status')} value={status} onChange={(e) => setStatus(e.target.value)} options={statusOptions} />
        <Select
          label={t('esg:factsPage.filters.evidence')}
          value={hasEvidence}
          onChange={(e) => setHasEvidence(e.target.value)}
          options={evidenceOptions}
        />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <Input label={t('esg:factsPage.filters.periodFrom')} type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
          <Input label={t('esg:factsPage.filters.periodTo')} type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
        </div>
      </div>

      <div className={styles.filtersRow}>
        <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input type="checkbox" checked={latestOnly} onChange={(e) => setLatestOnly(e.target.checked)} />
          {t('esg:factsPage.filters.latestOnly')}
        </label>
      </div>

      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>{t('esg:factsPage.table.headers.metric')}</th>
              <th style={{ width: '20%' }}>{t('esg:factsPage.table.headers.period')}</th>
              <th style={{ width: '10%' }}>{t('esg:factsPage.table.headers.status')}</th>
              <th style={{ width: '10%' }}>{t('esg:factsPage.table.headers.evidence')}</th>
              <th style={{ width: '10%' }}>{t('esg:factsPage.table.headers.version')}</th>
              <th style={{ width: '18%' }}>{t('esg:factsPage.table.headers.key')}</th>
              <th style={{ width: '18%' }}>{t('esg:factsPage.table.headers.value')}</th>
              <th style={{ width: '14%' }} />
            </tr>
          </thead>
          <tbody>
            {factsQuery.isLoading && (
              <tr>
                <td colSpan={8} style={{ padding: '1rem' }}>
                  {t('common:common.loading')}
                </td>
              </tr>
            )}

            {!factsQuery.isLoading && facts.length === 0 && (
              <tr>
                <td colSpan={8} style={{ padding: '1rem' }}>
                  {t('esg:factsPage.empty')}
                </td>
              </tr>
            )}

            {facts.map((f) => {
              const metric = metricsById.get(f.metric_id)
              const metricLabel = metric ? metric.name : shortId(f.metric_id)
              const period = `${f.period_start} → ${f.period_end}${f.is_ytd ? ` (${t('esg:factsPage.period.ytd')})` : ''}`
              const primaryAction = (() => {
                if (f.status === 'draft') {
                  return canWrite
                    ? { label: t('common:actions.edit'), onClick: () => openEdit(f) }
                    : { label: t('esg:factsPage.actions.history'), onClick: () => setHistoryKey(f.logical_key_hash) }
                }
                if (f.status === 'in_review') {
                  return { label: t('esg:factsPage.actions.review'), onClick: () => setReviewFact(f) }
                }
                return { label: t('esg:factsPage.actions.history'), onClick: () => setHistoryKey(f.logical_key_hash) }
              })()

              const menuItems = [
                {
                  label: t('esg:factsPage.actions.history'),
                  onSelect: () => setHistoryKey(f.logical_key_hash),
                },
                {
                  label: t('esg:factsPage.actions.evidence'),
                  onSelect: () => setEvidenceFact(f),
                },
              ]

              if (f.status === 'draft') {
                if (canWrite) {
                  menuItems.push({
                    label: t('esg:factsPage.actions.submitForReview'),
                    onSelect: () => doSubmitReview(f.fact_id),
                  })
                }
                if (canPublish) {
                  menuItems.push({
                    label: t('esg:factsPage.actions.publish'),
                    onSelect: () => doPublish(f.fact_id),
                  })
                }
              }

              if (f.status === 'in_review' && canPublish) {
                menuItems.push(
                  {
                    label: t('esg:factsPage.actions.approvePublish'),
                    onSelect: () => doPublish(f.fact_id),
                  },
                  {
                    label: t('esg:factsPage.actions.requestChanges'),
                    onSelect: () => {
                      setRequestChangesFact(f)
                      setRequestChangesReason('')
                    },
                  }
                )
              }

              if ((f.status === 'published' || f.status === 'superseded') && canWrite) {
                menuItems.push({
                  label: t('esg:factsPage.actions.restate'),
                  onSelect: () => doRestate(f.fact_id),
                })
              }
              return (
                <tr key={f.fact_id}>
                  <td>{metricLabel}</td>
                  <td className={styles.mono}>{period}</td>
                  <td>{factStatusBadge(f.status, t)}</td>
                  <td>
                    <FactEvidenceBadge fact={f} metric={metric} onOpen={() => setEvidenceFact(f)} />
                  </td>
                  <td className={styles.mono}>{f.version_number}</td>
                  <td className={styles.mono}>{shortId(f.logical_key_hash)}</td>
                  <td className={styles.mono}>{renderValue(f)}</td>
                  <td>
                    <div className={styles.rowActions}>
                      <Button variant="secondary" size="sm" onClick={primaryAction.onClick}>
                        {primaryAction.label}
                      </Button>
                      <DropdownMenu
                        triggerLabel="⋯"
                        triggerAriaLabel={t('esg:factsPage.actions.moreActions')}
                        items={menuItems}
                      />
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
          {total === 0 ? t('esg:factsPage.pager.zeroResults') : t('esg:factsPage.pager.resultsRange', { from: showingFrom, to: showingTo, total })}
        </div>
        <div className={styles.pagerActions}>
          <Button
            variant="secondary"
            size="sm"
            disabled={!factsQuery.data?.has_prev || factsQuery.isLoading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            {t('esg:factsPage.pager.prev')}
          </Button>
          <div className={styles.pagerPage}>
            {t('esg:factsPage.pager.pageOf', { page: resolvedPage, totalPages })}
          </div>
          <Button
            variant="secondary"
            size="sm"
            disabled={!factsQuery.data?.has_next || factsQuery.isLoading}
            onClick={() => setPage((p) => p + 1)}
          >
            {t('esg:factsPage.pager.next')}
          </Button>
        </div>
      </div>

      <Modal
        isOpen={Boolean(historyKey)}
        onClose={() => setHistoryKey(null)}
        title={t('esg:factsPage.history.title')}
        size="lg"
      >
        {historyKey && (
          <>
            <p className={styles.modalMeta}>
              {t('esg:factsPage.history.logicalKey')}: <span className={styles.mono}>{historyKey}</span>
            </p>
            <h3 className={styles.modalSectionTitle}>{t('esg:factsPage.history.versions')}</h3>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th style={{ width: '10%' }}>{t('esg:factsPage.table.headers.version')}</th>
                    <th style={{ width: '16%' }}>{t('esg:factsPage.table.headers.status')}</th>
                    <th>{t('esg:factsPage.table.headers.value')}</th>
                    <th style={{ width: '24%' }}>{t('esg:factsPage.history.updatedAt')}</th>
                    <th style={{ width: '22%' }} />
                  </tr>
                </thead>
                <tbody>
                  {historyFactsQuery.isLoading && (
                    <tr>
                      <td colSpan={5} style={{ padding: '1rem' }}>
                        {t('common:common.loading')}
                      </td>
                    </tr>
                  )}
                  {!historyFactsQuery.isLoading &&
                    historyFacts.map((hf) => (
                      <tr key={hf.fact_id}>
                        <td className={styles.mono}>{hf.version_number}</td>
                        <td>{factStatusBadge(hf.status, t)}</td>
                        <td className={styles.mono}>{renderValue(hf)}</td>
                        <td className={styles.mono}>{hf.updated_at_utc}</td>
                        <td>
                          <div className={styles.rowActions}>
                            {(hf.status === 'published' || hf.status === 'superseded') && canWrite && (
                              <Button variant="secondary" size="sm" onClick={() => doRestate(hf.fact_id)}>
                                {t('esg:factsPage.actions.restate')}
                              </Button>
                            )}
                            {hf.status === 'draft' && canWrite && (
                              <Button variant="secondary" size="sm" onClick={() => openEdit(hf)}>
                                {t('common:actions.edit')}
                              </Button>
                            )}
                            {hf.status === 'draft' && canWrite && (
                              <Button variant="secondary" size="sm" onClick={() => doSubmitReview(hf.fact_id)}>
                                {t('esg:factsPage.actions.submitForReview')}
                              </Button>
                            )}
                            {(hf.status === 'draft' || hf.status === 'in_review') && canPublish && (
                              <Button size="sm" onClick={() => doPublish(hf.fact_id)}>
                                {hf.status === 'in_review' ? t('esg:factsPage.actions.approvePublish') : t('esg:factsPage.actions.publish')}
                              </Button>
                            )}
                            {hf.status === 'in_review' && canPublish && (
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => {
                                  setRequestChangesFact(hf)
                                  setRequestChangesReason('')
                                }}
                              >
                                {t('esg:factsPage.actions.requestChanges')}
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Modal>

      <Modal isOpen={Boolean(reviewFact)} onClose={() => setReviewFact(null)} title={t('esg:factsPage.review.title')} size="lg">
        {reviewFact && (
          <>
            <p className={styles.modalMeta}>
              {t('esg:factsPage.review.metricLabel')}: <strong>{metricsById.get(reviewFact.metric_id)?.name ?? shortId(reviewFact.metric_id)}</strong> | {t('esg:factsPage.review.versionLabel')}{' '}
              <span className={styles.mono}>{reviewFact.version_number}</span> | {t('esg:factsPage.review.statusLabel')} {factStatusBadge(reviewFact.status, t)}
            </p>

            <div className={styles.diffGrid}>
              <div className={styles.diffCard}>
                <div className={styles.diffLabel}>{t('esg:factsPage.review.beforePublished')}</div>
                <div className={styles.diffValue}>{reviewBaseline ? renderValue(reviewBaseline) : '—'}</div>
                <div className={styles.diffMeta}>
                  {reviewBaseline ? `v${reviewBaseline.version_number}` : t('esg:factsPage.review.noPublishedBaseline')}
                </div>
              </div>
              <div className={styles.diffCard}>
                <div className={styles.diffLabel}>{t('esg:factsPage.review.afterStatus', { status: reviewFact.status })}</div>
                <div className={styles.diffValue}>{renderValue(reviewFact)}</div>
                <div className={styles.diffMeta}>v{reviewFact.version_number}</div>
              </div>
            </div>

            {reviewFactsQuery.isLoading && <p className={styles.modalMeta}>{t('esg:factsPage.review.loadingHistory')}</p>}

            {reviewFact.status === 'in_review' && canPublish && (
              <div className={styles.modalActions}>
                <Button
                  variant="secondary"
                  onClick={() => {
                    setReviewFact(null)
                    setRequestChangesFact(reviewFact)
                    setRequestChangesReason('')
                  }}
                  disabled={publishFact.isPending || requestChanges.isPending}
                >
                  {t('esg:factsPage.actions.requestChanges')}
                </Button>
                <Button
                  onClick={() => void doPublish(reviewFact.fact_id).finally(() => setReviewFact(null))}
                  loading={publishFact.isPending}
                >
                  {t('esg:factsPage.actions.approvePublish')}
                </Button>
              </div>
            )}

            <div className={styles.reviewPanels}>
              <section className={styles.reviewPanel} aria-label={t('esg:factsPage.review.commentsAria')}>
                <div className={styles.panelHeader}>
                  <h3 className={styles.panelTitle}>{t('esg:factsPage.review.commentsTitle')}</h3>
                  <span className={styles.panelMeta}>{(reviewCommentsQuery.data ?? []).length}</span>
                </div>

                {reviewCommentsQuery.isLoading && <p className={styles.panelEmpty}>{t('esg:factsPage.review.loadingComments')}</p>}
                {!reviewCommentsQuery.isLoading && (reviewCommentsQuery.data ?? []).length === 0 && (
                  <p className={styles.panelEmpty}>{t('esg:factsPage.review.noComments')}</p>
                )}

                {(reviewCommentsQuery.data ?? []).length > 0 && (
                  <ul className={styles.commentList}>
                    {(reviewCommentsQuery.data ?? []).map((c) => (
                      <li key={c.comment_id} className={styles.commentItem}>
                        <div className={styles.commentMeta}>
                          <span className={styles.commentAuthor}>
                            {c.created_by_name || c.created_by_email || shortId(c.created_by || 'unknown')}
                          </span>
                          <span className={styles.commentTime}>{new Date(c.created_at_utc).toLocaleString()}</span>
                        </div>
                        <div className={styles.commentBody}>{renderCommentBody(c.body_md)}</div>
                      </li>
                    ))}
                  </ul>
                )}

                <div className={styles.commentComposer}>
                  <label className={styles.textareaLabel} htmlFor="esg-review-comment">
                    {t('esg:factsPage.review.addCommentLabel')}
                  </label>
                  <textarea
                    id="esg-review-comment"
                    ref={reviewCommentRef}
                    className={styles.textarea}
                    value={reviewCommentBody}
                    onChange={(e) => {
                      const next = e.target.value
                      setReviewCommentBody(next)
                      const cursor = e.target.selectionStart ?? next.length
                      setActiveMention(getActiveMentionAtCursor(next, cursor))
                    }}
                    onKeyUp={(e) => {
                      const el = e.currentTarget
                      const cursor = el.selectionStart ?? el.value.length
                      setActiveMention(getActiveMentionAtCursor(el.value, cursor))
                    }}
                    onBlur={() => setActiveMention(null)}
                    placeholder={t('esg:factsPage.review.addCommentPlaceholder')}
                    disabled={!canWrite || createReviewComment.isPending}
                  />

                  {activeMention && mentionCandidates.length > 0 && (
                    <div className={styles.mentionList} role="listbox" aria-label={t('esg:factsPage.review.mentionSuggestions')}>
                      {mentionCandidates.map((m) => (
                        <button
                          key={m.user_id}
                          type="button"
                          className={styles.mentionOption}
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => insertMention(m.email || m.name)}
                        >
                          <div className={styles.mentionName}>{m.name || m.email}</div>
                          {m.name && m.email && <div className={styles.mentionEmail}>{m.email}</div>}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className={styles.commentActions}>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        setReviewCommentBody('')
                        setActiveMention(null)
                      }}
                      disabled={createReviewComment.isPending}
                    >
                      {t('esg:factsPage.review.clearComment')}
                    </Button>
                    <Button size="sm" onClick={() => void doAddReviewComment()} loading={createReviewComment.isPending} disabled={!canWrite}>
                      {t('common:actions.add')}
                    </Button>
                  </div>
                </div>
              </section>

              <section className={styles.reviewPanel} aria-label={t('esg:factsPage.review.timelineAria')}>
                <div className={styles.panelHeader}>
                  <h3 className={styles.panelTitle}>{t('esg:factsPage.review.timelineTitle')}</h3>
                  <span className={styles.panelMeta}>{(reviewTimelineQuery.data ?? []).length}</span>
                </div>

                {reviewTimelineQuery.isLoading && <p className={styles.panelEmpty}>{t('esg:factsPage.review.loadingTimeline')}</p>}
                {!reviewTimelineQuery.isLoading && (reviewTimelineQuery.data ?? []).length === 0 && (
                  <p className={styles.panelEmpty}>{t('esg:factsPage.review.noTimeline')}</p>
                )}

                {(reviewTimelineQuery.data ?? []).length > 0 && (
                  <ul className={styles.timelineList}>
                    {(reviewTimelineQuery.data ?? [])
                      .slice()
                      .reverse()
                      .map((ev) => {
                        const meta = (ev.metadata_json ?? {}) as Record<string, unknown>
                        const version = typeof meta.version_number === 'number' ? `v${meta.version_number}` : null
                        const reason = typeof meta.reason === 'string' ? meta.reason : null
                        const who = ev.actor_name || ev.actor_email || shortId(ev.actor_id)
                        return (
                          <li key={ev.event_id} className={styles.timelineItem}>
                            <div className={styles.timelineTop}>
                              <span className={styles.timelineAction}>{formatTimelineAction(ev.action, t)}</span>
                              <span className={styles.timelineMeta}>
                                {version ? `${version} · ` : ''}
                                {who} · {new Date(ev.timestamp_utc).toLocaleString()}
                              </span>
                            </div>
                            {reason && <div className={styles.timelineReason}>{t('esg:factsPage.review.reasonLabel')}: {reason}</div>}
                          </li>
                        )
                      })}
                  </ul>
                )}
              </section>
            </div>
          </>
        )}
      </Modal>

      <Modal
        isOpen={Boolean(requestChangesFact)}
        onClose={() => setRequestChangesFact(null)}
        title={t('esg:factsPage.requestChanges.title')}
        size="lg"
      >
        {requestChangesFact && (
          <>
            <p className={styles.modalMeta}>
              {t('esg:factsPage.requestChanges.hintBefore')} <span className={styles.mono}>{t('esg:factsPage.status.draft')}</span> {t('esg:factsPage.requestChanges.hintAfter')}
            </p>
            <label className={styles.textareaLabel} htmlFor="request-changes-reason">
              {t('esg:factsPage.requestChanges.reasonLabel')}
            </label>
            <textarea
              id="request-changes-reason"
              className={styles.textarea}
              value={requestChangesReason}
              onChange={(e) => setRequestChangesReason(e.target.value)}
              placeholder={t('esg:factsPage.requestChanges.reasonPlaceholder')}
            />
            <div className={styles.modalActions}>
              <Button variant="secondary" onClick={() => setRequestChangesFact(null)} disabled={requestChanges.isPending}>
                {t('common:actions.cancel')}
              </Button>
              <Button
                onClick={() => {
                  const reason = requestChangesReason.trim()
                  if (!reason) {
                    toast.error(t('esg:factsPage.toast.reasonRequired'))
                    return
                  }
                  void doRequestChanges(requestChangesFact.fact_id, reason)
                }}
                loading={requestChanges.isPending}
              >
                {t('esg:factsPage.requestChanges.sendBack')}
              </Button>
            </div>
          </>
        )}
      </Modal>

      <EsgFactImportModal isOpen={importOpen} onClose={() => setImportOpen(false)} />

      {evidenceFact && (
        <EsgFactEvidenceModal
          isOpen={Boolean(evidenceFact)}
          companyId={companyId}
          factId={evidenceFact.fact_id}
          canWrite={canWrite}
          meta={`${metricsById.get(evidenceFact.metric_id)?.name ?? shortId(evidenceFact.metric_id)} · ${evidenceFact.period_start} → ${evidenceFact.period_end}${evidenceFact.is_ytd ? ` (${t('esg:factsPage.period.ytd')})` : ''}`}
          onClose={() => setEvidenceFact(null)}
        />
      )}

      <FactEditModal
        fact={editingFact}
        metric={editingFact ? metricsById.get(editingFact.metric_id) : undefined}
        onClose={() => setEditingFact(null)}
        onSubmit={doUpdate}
      />
    </EsgShell>
  )
}

function FactEvidenceBadge(props: { fact: EsgFact; metric: EsgMetric | undefined; onOpen: () => void }) {
  const { t } = useTranslation(['esg'])
  const count = typeof props.fact.evidence_count === 'number' ? props.fact.evidence_count : null
  const minItems = getEsgEvidenceMinItems(props.metric?.value_schema_json)

  const label = (() => {
    if (count === null) return '—'
    if (minItems) return `${count}/${minItems}`
    return String(count)
  })()

  const cls = (() => {
    if (count === null) return styles.evidenceBadgeLoading
    if (minItems) return count >= minItems ? styles.evidenceBadgeOk : styles.evidenceBadgeMissing
    return count > 0 ? styles.evidenceBadgeOk : ''
  })()

  const title = (() => {
    if (count === null) return ''
    if (minItems) return t('esg:factsPage.evidence.titleWithRequired', { count, required: minItems })
    return count > 0 ? t('esg:factsPage.evidence.titleWithCount', { count }) : t('esg:factsPage.evidence.titleNone')
  })()

  return (
    <button
      type="button"
      className={`${styles.evidenceBadge} ${cls}`}
      title={title}
      aria-label={t('esg:factsPage.actions.evidence')}
      onClick={props.onOpen}
    >
      {label}
    </button>
  )
}

function FactEditModal(props: {
  fact: EsgFact | null
  metric: EsgMetric | undefined
  onClose: () => void
  onSubmit: (
    factId: string,
    payload: {
      value_json?: unknown
      dataset_id?: string | null
      quality_json?: Record<string, unknown>
      sources_json?: Record<string, unknown>
    }
  ) => void | Promise<void>
}) {
  const fact = props.fact
  const metric = props.metric
  const { t } = useTranslation(['esg', 'common'])

  const [scalarValue, setScalarValue] = useState<string>('')
  const [boolValue, setBoolValue] = useState<string>('true')
  const [datasetId, setDatasetId] = useState<string | null>(null)
  const [showAdvancedJson, setShowAdvancedJson] = useState(false)

  const [qualityObj, setQualityObj] = useState<Record<string, unknown>>({})
  const [qualityJsonText, setQualityJsonText] = useState<string>('{}')
  const [qualityJsonError, setQualityJsonError] = useState<string | null>(null)

  const [sourcesObj, setSourcesObj] = useState<Record<string, unknown>>({})
  const [sourcesJsonText, setSourcesJsonText] = useState<string>('{}')
  const [sourcesJsonError, setSourcesJsonError] = useState<string | null>(null)

  const evidenceCount = typeof fact?.evidence_count === 'number' ? fact.evidence_count : null

  const requiredSourceFields = useMemo(() => getEsgRequiredSourceFields(metric?.value_schema_json), [metric?.value_schema_json])
  const evidenceMinItems = useMemo(() => getEsgEvidenceMinItems(metric?.value_schema_json), [metric?.value_schema_json])
  const rangeSpec = useMemo(() => getEsgRangeSpec(metric?.value_schema_json), [metric?.value_schema_json])

  useEffect(() => {
    if (!fact || !metric) return

    setShowAdvancedJson(false)

    setQualityObj(fact.quality_json ?? {})
    setQualityJsonText(JSON.stringify(fact.quality_json ?? {}, null, 2))
    setQualityJsonError(null)

    setSourcesObj(fact.sources_json ?? {})
    setSourcesJsonText(JSON.stringify(fact.sources_json ?? {}, null, 2))
    setSourcesJsonError(null)

    if (metric.value_type === 'dataset') {
      setDatasetId(fact.dataset_id ?? null)
      setScalarValue('')
      setBoolValue('true')
      return
    }

    setDatasetId(null)

    if (metric.value_type === 'boolean') {
      setBoolValue(fact.value_json === true ? 'true' : 'false')
      setScalarValue('')
      return
    }

    if (fact.value_json === null || typeof fact.value_json === 'undefined') {
      setScalarValue('')
      return
    }
    setScalarValue(String(fact.value_json))
  }, [fact, metric])

  if (!fact || !metric) return null

  const isDataset = metric.value_type === 'dataset'
  const isBoolean = metric.value_type === 'boolean'

  const updateSourceField = (key: string, value: string) => {
    setSourcesObj((prev) => {
      const next = { ...(prev ?? {}), [key]: value }
      setSourcesJsonText(JSON.stringify(next, null, 2))
      setSourcesJsonError(null)
      return next
    })
  }

  const handleSourcesJsonTextChange = (text: string) => {
    setSourcesJsonText(text)
    try {
      const parsed = text.trim() ? (JSON.parse(text) as unknown) : {}
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error(t('esg:factsPage.editModal.advanced.sourcesJsonMustBeObject'))
      }
      setSourcesObj(parsed as Record<string, unknown>)
      setSourcesJsonError(null)
    } catch (e) {
      setSourcesJsonError((e as Error).message || t('esg:factsPage.editModal.advanced.sourcesJsonInvalid'))
    }
  }

  const handleQualityJsonTextChange = (text: string) => {
    setQualityJsonText(text)
    try {
      const parsed = text.trim() ? (JSON.parse(text) as unknown) : {}
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error(t('esg:factsPage.editModal.advanced.qualityJsonMustBeObject'))
      }
      setQualityObj(parsed as Record<string, unknown>)
      setQualityJsonError(null)
    } catch (e) {
      setQualityJsonError((e as Error).message || t('esg:factsPage.editModal.advanced.qualityJsonInvalid'))
    }
  }

  const valuePreview = (() => {
    const unitHint = metric.unit ? t('esg:factsPage.editModal.value.hints.unit', { unit: metric.unit }) : null

    if (metric.value_type === 'dataset') {
      return {
        value_json: null as unknown,
        dataset_id: datasetId,
        error: datasetId ? null : t('esg:factsPage.editModal.validation.datasetRequired'),
        hint: unitHint,
      }
    }

    if (metric.value_type === 'boolean') {
      return { value_json: boolValue === 'true', dataset_id: null, error: null, hint: unitHint }
    }

    if (metric.value_type === 'integer') {
      if (!scalarValue.trim())
        return { value_json: null as unknown, dataset_id: null, error: t('esg:factsPage.editModal.validation.valueRequired'), hint: unitHint }
      const parsed = Number(scalarValue)
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        return { value_json: null as unknown, dataset_id: null, error: t('esg:factsPage.editModal.validation.expectedInteger'), hint: unitHint }
      }
      const hint =
        rangeSpec && (rangeSpec.min !== undefined || rangeSpec.max !== undefined)
          ? `${unitHint ? `${unitHint} | ` : ''}${t('esg:factsPage.editModal.value.hints.expectedRange', { min: rangeSpec.min ?? '…', max: rangeSpec.max ?? '…' })}`
          : unitHint
      return { value_json: parsed, dataset_id: null, error: null, hint }
    }

    if (metric.value_type === 'number') {
      if (!scalarValue.trim())
        return { value_json: null as unknown, dataset_id: null, error: t('esg:factsPage.editModal.validation.valueRequired'), hint: unitHint }
      const parsed = Number(scalarValue)
      if (!Number.isFinite(parsed)) {
        return { value_json: null as unknown, dataset_id: null, error: t('esg:factsPage.editModal.validation.expectedNumber'), hint: unitHint }
      }
      const hint =
        rangeSpec && (rangeSpec.min !== undefined || rangeSpec.max !== undefined)
          ? `${unitHint ? `${unitHint} | ` : ''}${t('esg:factsPage.editModal.value.hints.expectedRange', { min: rangeSpec.min ?? '…', max: rangeSpec.max ?? '…' })}`
          : unitHint
      return { value_json: parsed, dataset_id: null, error: null, hint }
    }

    if (!scalarValue.trim())
      return { value_json: null as unknown, dataset_id: null, error: t('esg:factsPage.editModal.validation.valueRequired'), hint: unitHint }
    return { value_json: scalarValue, dataset_id: null, error: null, hint: unitHint }
  })()

  const publishIssues = collectEsgFactQualityGateIssues({
    schema: metric.value_schema_json,
    fact: {
      value_json: valuePreview.value_json,
      dataset_id: valuePreview.dataset_id,
      sources_json: sourcesObj,
      evidence_count: evidenceCount,
    },
  })

  const submit = async () => {
    if (qualityJsonError) {
      toast.error(qualityJsonError)
      return
    }
    if (sourcesJsonError) {
      toast.error(sourcesJsonError)
      return
    }

    if (isDataset) {
      if (!datasetId) {
        toast.error(t('esg:factsPage.editModal.validation.datasetRequired'))
        return
      }
      await props.onSubmit(fact.fact_id, { dataset_id: datasetId, quality_json: qualityObj, sources_json: sourcesObj })
      return
    }

    if (valuePreview.error) {
      toast.error(valuePreview.error)
      return
    }

    await props.onSubmit(fact.fact_id, { value_json: valuePreview.value_json, quality_json: qualityObj, sources_json: sourcesObj })
  }

  return (
    <Modal isOpen={Boolean(fact)} onClose={props.onClose} title={t('esg:factsPage.editModal.title')} size="lg">
      <p className={styles.modalMeta}>
        {t('esg:factsPage.editModal.meta.metric')}: <strong>{metric.name}</strong> | {t('esg:factsPage.editModal.meta.version')}:{' '}
        <span className={styles.mono}>{fact.version_number}</span>
      </p>

      {isDataset ? (
        <>
          <DatasetPicker value={datasetId} onChange={setDatasetId} allowNull={false} />
          {valuePreview.error && <p className={styles.fieldError}>{valuePreview.error}</p>}
        </>
      ) : isBoolean ? (
        <Select
          label={t('esg:factsPage.editModal.fields.value')}
          value={boolValue}
          onChange={(e) => setBoolValue(e.target.value)}
          options={[
            { value: 'true', label: t('esg:factsPage.editModal.value.boolean.true') },
            { value: 'false', label: t('esg:factsPage.editModal.value.boolean.false') },
          ]}
        />
      ) : (
        <Input
          label={t('esg:factsPage.editModal.fields.value')}
          value={scalarValue}
          onChange={(e) => setScalarValue(e.target.value)}
          placeholder={metric.value_type === 'string' ? t('esg:factsPage.editModal.value.placeholders.text') : t('esg:factsPage.editModal.value.placeholders.number')}
          type={metric.value_type === 'string' ? 'text' : 'number'}
          error={valuePreview.error ?? undefined}
          hint={valuePreview.hint ?? undefined}
        />
      )}

      <div style={{ marginTop: '0.75rem' }}>
        <h3 className={styles.subTitle}>{t('esg:factsPage.editModal.sections.sourcesAndValidation')}</h3>
        {requiredSourceFields.length > 0 ? (
          <div className={styles.grid2}>
            {requiredSourceFields.map((key) => {
              const raw = sourcesObj[key]
              const value = typeof raw === 'string' ? raw : raw ? JSON.stringify(raw) : ''
              const missing = !value.trim()
              return (
                <Input
                  key={key}
                  label={key}
                  value={value}
                  onChange={(e) => updateSourceField(key, e.target.value)}
                  placeholder={t('esg:factsPage.editModal.sources.placeholder')}
                  error={missing ? t('esg:factsPage.editModal.sources.requiredForPublish') : undefined}
                />
              )
            })}
          </div>
        ) : (
          <p className={styles.panelEmpty}>{t('esg:factsPage.editModal.sources.noneConfigured')}</p>
        )}

        {(evidenceMinItems || rangeSpec) && (
          <div className={styles.requirementsRow}>
            {evidenceMinItems ? (
              <span>
                {t('esg:factsPage.editModal.requirements.expectedEvidence')}{' '}
                <strong>{evidenceMinItems}</strong>+ {t('esg:factsPage.editModal.requirements.evidenceItems')}{' '}
                {typeof evidenceCount === 'number' ? t('esg:factsPage.editModal.requirements.haveCount', { count: evidenceCount }) : ''}
              </span>
            ) : (
              <span />
            )}
            {rangeSpec && (rangeSpec.min !== undefined || rangeSpec.max !== undefined) && (
              <span>
                {t('esg:factsPage.editModal.requirements.expectedRange')}{' '}
                <strong>{rangeSpec.min ?? '…'}</strong>–<strong>{rangeSpec.max ?? '…'}</strong>
              </span>
            )}
          </div>
        )}

        {publishIssues.length > 0 && (
          <div className={styles.issueBox} aria-label={t('esg:factsPage.editModal.publishBlockers.aria')}>
            <div className={styles.issueTitle}>{t('esg:factsPage.editModal.publishBlockers.title')}</div>
            <ul className={styles.issueList}>
              {publishIssues.map((i) => (
                <li key={i.code} className={styles.issueItem}>
                  {i.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <label className={styles.advancedToggle}>
          <input type="checkbox" checked={showAdvancedJson} onChange={(e) => setShowAdvancedJson(e.target.checked)} />
          {t('esg:factsPage.editModal.advanced.toggle')}
        </label>

        {showAdvancedJson && (
          <>
            <div style={{ marginTop: '0.75rem' }}>
              <label className={styles.textareaLabel} htmlFor="sources_json">
                {t('esg:factsPage.editModal.advanced.sourcesJsonLabel')}
              </label>
              <textarea
                id="sources_json"
                className={styles.textarea}
                value={sourcesJsonText}
                onChange={(e) => handleSourcesJsonTextChange(e.target.value)}
              />
              {sourcesJsonError && <div className={styles.fieldError}>{sourcesJsonError}</div>}
            </div>
            <div style={{ marginTop: '0.75rem' }}>
              <label className={styles.textareaLabel} htmlFor="quality_json">
                {t('esg:factsPage.editModal.advanced.qualityJsonLabel')}
              </label>
              <textarea
                id="quality_json"
                className={styles.textarea}
                value={qualityJsonText}
                onChange={(e) => handleQualityJsonTextChange(e.target.value)}
              />
              {qualityJsonError && <div className={styles.fieldError}>{qualityJsonError}</div>}
            </div>
          </>
        )}
      </div>

      <div className={styles.modalActions}>
        <Button variant="secondary" onClick={props.onClose}>
          {t('common:actions.cancel')}
        </Button>
        <Button onClick={submit}>{t('common:actions.save')}</Button>
      </div>
    </Modal>
  )
}
