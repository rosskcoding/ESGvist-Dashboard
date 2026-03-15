import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { useEsgGaps } from '@/api/hooks'
import { EsgFactEvidenceModal } from '@/components/esg/EsgFactEvidenceModal'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, Modal, Select } from '@/components/ui'
import { canWriteEsg, useAuthStore } from '@/stores/authStore'
import type { EsgGapFactAttention } from '@/types/api'

import styles from './EsgEvidencePage.module.css'

const REVIEW_SLA_DAYS = 7

function getDefaultYear() {
  const now = new Date()
  return now.getFullYear() - 1
}

function formatIsoDate(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

type EvidenceView = 'missing_evidence' | 'missing_sources' | 'out_of_range' | 'overdue' | 'all'

function resolveView(raw: string | null): EvidenceView {
  if (raw === 'missing_evidence' || raw === 'missing_sources' || raw === 'out_of_range' || raw === 'overdue' || raw === 'all') return raw
  return 'missing_evidence'
}

function statusBadge(status: string) {
  const cls =
    status === 'published'
      ? styles.badgePublished
      : status === 'in_review'
        ? styles.badgeInReview
        : status === 'superseded'
          ? styles.badgeSuperseded
          : styles.badgeDraft
  return <span className={`${styles.badge} ${cls}`}>{status}</span>
}

function issueChipLabel(code: string) {
  if (code === 'missing_evidence') return 'Evidence'
  if (code.startsWith('missing_source:')) return 'Source'
  if (code === 'range_below_min' || code === 'range_above_max') return 'Range'
  if (code === 'review_overdue') return 'Overdue'
  return code
}

export function EsgEvidencePage() {
  const { t } = useTranslation(['esg'])
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

  const view = resolveView(searchParams.get('view'))

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
      { value: 'missing_evidence', label: t('esg:evidencePage.filters.views.missingEvidence') },
      { value: 'missing_sources', label: t('esg:evidencePage.filters.views.missingSources') },
      { value: 'out_of_range', label: t('esg:evidencePage.filters.views.outOfRange') },
      { value: 'overdue', label: t('esg:evidencePage.filters.views.overdue') },
      { value: 'all', label: t('esg:evidencePage.filters.views.all') },
    ],
    [t]
  )

  const gapsQuery = useEsgGaps({
    periodType: 'year',
    periodStart,
    periodEnd,
    isYtd: false,
    reviewOverdueDays: REVIEW_SLA_DAYS,
    maxAttentionFacts: 500,
  })

  const attentionFacts = useMemo(() => gapsQuery.data?.attention_facts ?? [], [gapsQuery.data?.attention_facts])

  const counts = useMemo(() => {
    let missingEvidence = 0
    let missingSources = 0
    let outOfRange = 0
    let overdue = 0
    for (const f of attentionFacts) {
      const codes = new Set((f.issues ?? []).map((i) => i.code))
      if (codes.has('missing_evidence')) missingEvidence += 1
      if (Array.from(codes).some((c) => c.startsWith('missing_source:'))) missingSources += 1
      if (codes.has('range_below_min') || codes.has('range_above_max')) outOfRange += 1
      if (codes.has('review_overdue')) overdue += 1
    }
    return { missingEvidence, missingSources, outOfRange, overdue, total: attentionFacts.length }
  }, [attentionFacts])

  const filtered = useMemo(() => {
    if (view === 'all') return attentionFacts
    return attentionFacts.filter((f) => {
      const codes = new Set((f.issues ?? []).map((i) => i.code))
      if (view === 'missing_evidence') return codes.has('missing_evidence')
      if (view === 'missing_sources') return Array.from(codes).some((c) => c.startsWith('missing_source:'))
      if (view === 'out_of_range') return codes.has('range_below_min') || codes.has('range_above_max')
      if (view === 'overdue') return codes.has('review_overdue')
      return true
    })
  }, [attentionFacts, view])

  const [active, setActive] = useState<EsgGapFactAttention | null>(null)
  const [evidenceFactId, setEvidenceFactId] = useState<string | null>(null)

  const handleYearChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    nextParams.set('year', next)
    setSearchParams(nextParams, { replace: true })
  }

  const handleViewChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('view', next)
    else nextParams.delete('view')
    setSearchParams(nextParams, { replace: true })
  }

  const openIssues = () => navigate(`/esg/gaps?year=${resolvedYear}`)

  return (
    <EsgShell
      title={t('esg:evidencePage.title')}
      subtitle={t('esg:evidencePage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={openIssues}>
            {t('esg:evidencePage.actions.openIssues')}
          </Button>
        </div>
      }
    >
      <section className={styles.toolbar} aria-label={t('esg:evidencePage.filters.aria')}>
        <Select
          label={t('esg:evidencePage.filters.year')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <Select
          label={t('esg:evidencePage.filters.view')}
          value={view}
          onChange={(e) => handleViewChange(e.target.value)}
          options={viewOptions}
        />
        <div className={styles.toolbarMeta}>{t('esg:evidencePage.filters.period', { start: periodStart, end: periodEnd })}</div>
      </section>

      <div className={styles.summaryRow} aria-label={t('esg:evidencePage.summary.aria')}>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:evidencePage.summary.missingEvidence')}</div>
          <div className={styles.summaryValue}>{counts.missingEvidence}</div>
        </div>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:evidencePage.summary.missingSources')}</div>
          <div className={styles.summaryValue}>{counts.missingSources}</div>
        </div>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:evidencePage.summary.outOfRange')}</div>
          <div className={styles.summaryValue}>{counts.outOfRange}</div>
        </div>
        <div className={styles.summaryChip}>
          <div className={styles.summaryLabel}>{t('esg:evidencePage.summary.overdue')}</div>
          <div className={styles.summaryValue}>{counts.overdue}</div>
        </div>
      </div>

      {gapsQuery.isLoading && <div className={styles.loading}>{t('esg:evidencePage.loading')}</div>}
      {gapsQuery.error && <div className={styles.error}>{t('esg:evidencePage.error')}</div>}

      {!gapsQuery.isLoading && !gapsQuery.error && filtered.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyTitle}>{t('esg:evidencePage.empty.title')}</div>
          <div className={styles.emptyBody}>{t('esg:evidencePage.empty.body')}</div>
        </div>
      )}

      {filtered.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t('esg:evidencePage.table.headers.metric')}</th>
                <th style={{ width: '14%' }}>{t('esg:evidencePage.table.headers.status')}</th>
                <th>{t('esg:evidencePage.table.headers.issues')}</th>
                <th style={{ width: '18%' }}>{t('esg:evidencePage.table.headers.updated')}</th>
                <th style={{ width: '24%' }} />
              </tr>
            </thead>
            <tbody>
              {filtered.map((f) => {
                const code = f.metric.code
                const codes = Array.from(new Set((f.issues ?? []).map((i) => i.code)))
                return (
                  <tr key={f.fact_id}>
                    <td>
                      <div className={styles.metricName}>{f.metric.name}</div>
                      <div className={styles.metricMeta}>{code ? <span className={styles.metricCode}>{code}</span> : null}</div>
                    </td>
                    <td>{statusBadge(f.status)}</td>
                    <td>
                      <div className={styles.chips}>
                        {codes.map((c) => (
                          <span key={c} className={c === 'review_overdue' ? styles.chipWarn : styles.chip}>
                            {issueChipLabel(c)}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className={styles.updatedAt}>{formatIsoDate(f.updated_at_utc)}</td>
                    <td>
                      <div className={styles.rowActions}>
                        <Button variant="secondary" size="sm" onClick={() => setActive(f)}>
                          {t('esg:evidencePage.actions.open')}
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => setEvidenceFactId(f.fact_id)}
                          disabled={!canWrite}
                        >
                          {t('esg:evidencePage.actions.addEvidence')}
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <Modal isOpen={Boolean(active)} onClose={() => setActive(null)} title={t('esg:evidencePage.details.title')} size="lg">
        {active && (
          <>
            <div className={styles.detailTop}>
              <div>
                <div className={styles.detailMetricName}>{active.metric.name}</div>
                <div className={styles.detailMetricMeta}>
                  {active.metric.code ? <span className={styles.metricCode}>{active.metric.code}</span> : null}
                  {statusBadge(active.status)}
                </div>
              </div>
              <div className={styles.detailActions}>
                <Button variant="secondary" onClick={() => openIssues()}>
                  {t('esg:evidencePage.actions.openIssues')}
                </Button>
                <Button onClick={() => setEvidenceFactId(active.fact_id)} disabled={!canWrite}>
                  {t('esg:evidencePage.actions.addEvidence')}
                </Button>
              </div>
            </div>

            <div className={styles.detailCard}>
              <div className={styles.detailLabel}>{t('esg:evidencePage.details.updated')}</div>
              <div className={styles.detailValue}>{formatIsoDate(active.updated_at_utc)}</div>
            </div>

            <div className={styles.detailIssues}>
              <div className={styles.detailLabel}>{t('esg:evidencePage.details.issues')}</div>
              <ul className={styles.issueList}>
                {(active.issues ?? []).map((i, idx) => (
                  <li key={`${i.code}-${idx}`}>
                    <span className={styles.issueCode}>{i.code}</span>
                    <span className={styles.issueMsg}>{i.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </Modal>

      {evidenceFactId && (
        <EsgFactEvidenceModal
          isOpen={Boolean(evidenceFactId)}
          companyId={companyId}
          factId={evidenceFactId}
          canWrite={canWrite}
          onClose={() => setEvidenceFactId(null)}
        />
      )}
    </EsgShell>
  )
}
