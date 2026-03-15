import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, ConfirmDialog, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { useEsgEntities, useEsgGaps, useEsgLocations, useEsgSegments } from '@/api/hooks'
import styles from './EsgGapsPage.module.css'

function getDefaultYear() {
  const now = new Date()
  return now.getFullYear() - 1
}

function isUuid(value: string) {
  return /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$/.test(
    value
  )
}

function formatIsoDate(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

type EsgGapsSavedView = {
  id: string
  name: string
  filters: {
    year: number
    standard?: string
    entity_id?: string
    location_id?: string
    segment_id?: string
    include_inactive_metrics?: boolean
  }
}

const SAVED_VIEWS_KEY = 'esg.gaps.saved_views.v1'

const STANDARD_VALUES = new Set(['GRI', 'SASB', 'ISSB', 'CSRD', 'ESRS'])

function loadSavedViews(): EsgGapsSavedView[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(SAVED_VIEWS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((v): v is EsgGapsSavedView => {
      if (!v || typeof v !== 'object') return false
      const anyV = v as Record<string, unknown>
      if (typeof anyV.id !== 'string' || !anyV.id) return false
      if (typeof anyV.name !== 'string' || !anyV.name) return false
      if (!anyV.filters || typeof anyV.filters !== 'object') return false
      return true
    })
  } catch {
    return []
  }
}

function persistSavedViews(views: EsgGapsSavedView[]) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(views))
  } catch {
    // ignore (storage full / blocked)
  }
}

function filtersKey(filters: EsgGapsSavedView['filters']) {
  return JSON.stringify({
    year: filters.year,
    standard: (filters.standard || '').toUpperCase() || null,
    entity_id: filters.entity_id || null,
    location_id: filters.location_id || null,
    segment_id: filters.segment_id || null,
    include_inactive_metrics: Boolean(filters.include_inactive_metrics),
  })
}

export function EsgGapsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { t } = useTranslation(['esg', 'common'])

  const resolvedYear = (() => {
    const raw = searchParams.get('year')
    const parsed = raw ? Number(raw) : NaN
    if (!Number.isFinite(parsed)) return getDefaultYear()
    if (!Number.isInteger(parsed)) return getDefaultYear()
    if (parsed < 2000 || parsed > 2100) return getDefaultYear()
    return parsed
  })()

  const periodStart = `${resolvedYear}-01-01`
  const periodEnd = `${resolvedYear}-12-31`

  const resolvedEntityId = (() => {
    const raw = searchParams.get('entity_id')
    if (!raw) return ''
    if (!isUuid(raw)) return ''
    return raw
  })()
  const resolvedLocationId = (() => {
    const raw = searchParams.get('location_id')
    if (!raw) return ''
    if (!isUuid(raw)) return ''
    return raw
  })()
  const resolvedSegmentId = (() => {
    const raw = searchParams.get('segment_id')
    if (!raw) return ''
    if (!isUuid(raw)) return ''
    return raw
  })()
  const includeInactiveMetrics = searchParams.get('include_inactive_metrics') === 'true'
  const resolvedStandard = (() => {
    const raw = searchParams.get('standard')
    if (!raw) return ''
    const cleaned = raw.trim().toUpperCase()
    if (!cleaned) return ''
    if (!STANDARD_VALUES.has(cleaned)) return ''
    return cleaned
  })()

  const entitiesQuery = useEsgEntities({ includeInactive: false, page: 1, pageSize: 200 })
  const locationsQuery = useEsgLocations({ includeInactive: false, page: 1, pageSize: 200 })
  const segmentsQuery = useEsgSegments({ includeInactive: false, page: 1, pageSize: 200 })

  const gapsQuery = useEsgGaps({
    periodType: 'year',
    periodStart,
    periodEnd,
    isYtd: false,
    standard: resolvedStandard || undefined,
    entityId: resolvedEntityId || undefined,
    locationId: resolvedLocationId || undefined,
    segmentId: resolvedSegmentId || undefined,
    includeInactiveMetrics: includeInactiveMetrics || undefined,
  })

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
      { value: '', label: t('esg:gapsPage.filters.allStandards') },
      { value: 'GRI', label: 'GRI' },
      { value: 'SASB', label: 'SASB' },
      { value: 'ISSB', label: 'ISSB' },
      { value: 'CSRD', label: 'CSRD' },
      { value: 'ESRS', label: 'ESRS' },
    ]
  }, [t])

  const data = gapsQuery.data

  const issueBadges = useMemo(() => {
    if (!data) return []
    const out: Array<{ code: string; count: number }> = []
    for (const [code, count] of Object.entries(data.issue_counts || {})) {
      out.push({ code, count })
    }
    out.sort((a, b) => b.count - a.count || a.code.localeCompare(b.code))
    return out
  }, [data])

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

  const handleEntityChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('entity_id', next)
    else nextParams.delete('entity_id')
    setSearchParams(nextParams, { replace: true })
  }

  const handleLocationChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('location_id', next)
    else nextParams.delete('location_id')
    setSearchParams(nextParams, { replace: true })
  }

  const handleSegmentChange = (next: string) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('segment_id', next)
    else nextParams.delete('segment_id')
    setSearchParams(nextParams, { replace: true })
  }

  const handleIncludeInactiveChange = (next: boolean) => {
    const nextParams = new URLSearchParams(searchParams)
    if (next) nextParams.set('include_inactive_metrics', 'true')
    else nextParams.delete('include_inactive_metrics')
    setSearchParams(nextParams, { replace: true })
  }

  const entityOptions = useMemo(() => {
    const items = entitiesQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:gapsPage.filters.allEntities') }]
    for (const e of items) {
      const label = e.code ? `${e.name} (${e.code})` : e.name
      opts.push({ value: e.entity_id, label })
    }
    return opts
  }, [entitiesQuery.data, t])

  const locationOptions = useMemo(() => {
    const items = locationsQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:gapsPage.filters.allLocations') }]
    for (const l of items) {
      const label = l.code ? `${l.name} (${l.code})` : l.name
      opts.push({ value: l.location_id, label })
    }
    return opts
  }, [locationsQuery.data, t])

  const segmentOptions = useMemo(() => {
    const items = segmentsQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:gapsPage.filters.allSegments') }]
    for (const s of items) {
      const label = s.code ? `${s.name} (${s.code})` : s.name
      opts.push({ value: s.segment_id, label })
    }
    return opts
  }, [segmentsQuery.data, t])

  const [savedViews, setSavedViews] = useState<EsgGapsSavedView[]>(() => loadSavedViews())
  const [isSaveOpen, setIsSaveOpen] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [deleteViewId, setDeleteViewId] = useState<string | null>(null)

  const currentFilters: EsgGapsSavedView['filters'] = useMemo(
    () => ({
      year: resolvedYear,
      standard: resolvedStandard || undefined,
      entity_id: resolvedEntityId || undefined,
      location_id: resolvedLocationId || undefined,
      segment_id: resolvedSegmentId || undefined,
      include_inactive_metrics: includeInactiveMetrics || undefined,
    }),
    [resolvedYear, resolvedStandard, resolvedEntityId, resolvedLocationId, resolvedSegmentId, includeInactiveMetrics]
  )

  const activeView = useMemo(() => {
    const key = filtersKey(currentFilters)
    return savedViews.find((v) => filtersKey(v.filters) === key) ?? null
  }, [savedViews, currentFilters])

  const savedViewOptions = useMemo(() => {
    const opts: Array<{ value: string; label: string }> = [{ value: '__custom__', label: t('esg:gapsPage.savedViews.custom') }]
    for (const v of savedViews) {
      opts.push({ value: v.id, label: v.name })
    }
    return opts
  }, [savedViews, t])

  const handleSavedViewChange = (id: string) => {
    if (id === '__custom__') return
    const view = savedViews.find((v) => v.id === id)
    if (!view) return
    const next = new URLSearchParams()
    next.set('year', String(view.filters.year))
    if (view.filters.standard) next.set('standard', view.filters.standard.toUpperCase())
    if (view.filters.entity_id) next.set('entity_id', view.filters.entity_id)
    if (view.filters.location_id) next.set('location_id', view.filters.location_id)
    if (view.filters.segment_id) next.set('segment_id', view.filters.segment_id)
    if (view.filters.include_inactive_metrics) next.set('include_inactive_metrics', 'true')
    setSearchParams(next, { replace: true })
  }

  const openSaveModal = () => {
    const fallback = t('esg:gapsPage.savedViews.fallbackName', { year: resolvedYear })
    setSaveName(fallback)
    setIsSaveOpen(true)
  }

  const handleSave = () => {
    const name = saveName.trim()
    if (!name) {
      toast.error(t('esg:gapsPage.toast.viewNameRequired'))
      return
    }
    const next: EsgGapsSavedView = {
      id: crypto?.randomUUID ? crypto.randomUUID() : String(Date.now()),
      name,
      filters: currentFilters,
    }
    const updated = [next, ...savedViews]
    setSavedViews(updated)
    persistSavedViews(updated)
    setIsSaveOpen(false)
    toast.success(t('esg:gapsPage.toast.savedViewAdded'))
  }

  const handleDelete = () => {
    if (!deleteViewId) return
    const updated = savedViews.filter((v) => v.id !== deleteViewId)
    setSavedViews(updated)
    persistSavedViews(updated)
    setDeleteViewId(null)
    toast.success(t('esg:gapsPage.toast.savedViewDeleted'))
  }

  const factsLinkParams = useMemo(() => {
    const p = new URLSearchParams()
    p.set('period_from', periodStart)
    p.set('period_to', periodEnd)
    p.set('latest_only', 'true')
    if (resolvedEntityId) p.set('entity_id', resolvedEntityId)
    if (resolvedLocationId) p.set('location_id', resolvedLocationId)
    if (resolvedSegmentId) p.set('segment_id', resolvedSegmentId)
    return p
  }, [periodStart, periodEnd, resolvedEntityId, resolvedLocationId, resolvedSegmentId])

  const factsLink = `/esg/facts?${factsLinkParams.toString()}`

  const newFactLinkParams = useMemo(() => {
    const p = new URLSearchParams()
    p.set('year', String(resolvedYear))
    if (resolvedEntityId) p.set('entity_id', resolvedEntityId)
    if (resolvedLocationId) p.set('location_id', resolvedLocationId)
    if (resolvedSegmentId) p.set('segment_id', resolvedSegmentId)
    return p
  }, [resolvedYear, resolvedEntityId, resolvedLocationId, resolvedSegmentId])

  const newFactLink = `/esg/facts/new?${newFactLinkParams.toString()}`

  const advancedFiltersCount =
    (resolvedEntityId ? 1 : 0) +
    (resolvedLocationId ? 1 : 0) +
    (resolvedSegmentId ? 1 : 0) +
    (includeInactiveMetrics ? 1 : 0)

  const [advancedOpen, setAdvancedOpen] = useState(advancedFiltersCount > 0)

  return (
    <EsgShell
      title={t('esg:gapsPage.title')}
      subtitle={t('esg:gapsPage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button variant="secondary" onClick={() => navigate(factsLink)}>
            {t('esg:gapsPage.actions.browseFacts')}
          </Button>
          <Button onClick={() => navigate(newFactLink)}>
            {t('esg:gapsPage.actions.newFact')}
          </Button>
        </div>
      }
    >
      <section className={styles.toolbar} aria-label={t('esg:gapsPage.filters.aria')}>
        <Select
          label={t('esg:gapsPage.filters.savedView')}
          value={activeView ? activeView.id : '__custom__'}
          onChange={(e) => handleSavedViewChange(e.target.value)}
          options={savedViewOptions}
        />
        <Select
          label={t('esg:gapsPage.filters.reportingYear')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <Select
          label={t('esg:gapsPage.filters.standard')}
          value={resolvedStandard}
          onChange={(e) => handleStandardChange(e.target.value)}
          options={standardOptions}
        />
        <details
          className={styles.advancedFilters}
          open={advancedOpen}
          onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className={styles.advancedSummary}>
            {t('esg:gapsPage.filters.advanced')}
            {advancedFiltersCount ? <span className={styles.advancedCount}>{advancedFiltersCount}</span> : null}
          </summary>
          <div className={styles.advancedBody}>
            <Select
              label={t('esg:gapsPage.filters.entity')}
              value={resolvedEntityId}
              onChange={(e) => handleEntityChange(e.target.value)}
              options={entityOptions}
            />
            <Select
              label={t('esg:gapsPage.filters.location')}
              value={resolvedLocationId}
              onChange={(e) => handleLocationChange(e.target.value)}
              options={locationOptions}
            />
            <Select
              label={t('esg:gapsPage.filters.segment')}
              value={resolvedSegmentId}
              onChange={(e) => handleSegmentChange(e.target.value)}
              options={segmentOptions}
            />
            <label className={styles.advancedCheckbox}>
              <input
                type="checkbox"
                checked={includeInactiveMetrics}
                onChange={(e) => handleIncludeInactiveChange(e.target.checked)}
              />
              {t('esg:gapsPage.filters.includeInactiveMetrics')}
            </label>
          </div>
        </details>
        <Button variant="secondary" onClick={openSaveModal}>
          {t('esg:gapsPage.actions.saveView')}
        </Button>
        {activeView && (
          <Button variant="secondary" onClick={() => setDeleteViewId(activeView.id)}>
            {t('esg:gapsPage.actions.deleteView')}
          </Button>
        )}
        <div className={styles.toolbarMeta}>
          {t('esg:gapsPage.filters.period')} <strong>{periodStart}</strong> {t('esg:gapsPage.filters.periodTo')} <strong>{periodEnd}</strong>
        </div>
      </section>

      {gapsQuery.isLoading && <div className={styles.loading}>{t('esg:gapsPage.loading')}</div>}
      {gapsQuery.error && <div className={styles.error}>{t('esg:gapsPage.error')}</div>}

      {data && (
        <>
          <section className={styles.summary} aria-label={t('esg:gapsPage.summary.aria')}>
            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>{t('esg:gapsPage.summary.missingPublishedLabel')}</div>
              <div className={styles.summaryValue}>{data.metrics_missing_published}</div>
              <div className={styles.summaryMeta}>{t('esg:gapsPage.summary.missingPublishedMeta', { total: data.metrics_total })}</div>
            </div>

            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>{t('esg:gapsPage.summary.attentionFactsLabel')}</div>
              <div className={styles.summaryValue}>{data.attention_facts.length}</div>
              <div className={styles.summaryMeta}>
                {issueBadges.length ? (
                  <div className={styles.badgeRow}>
                    {issueBadges.slice(0, 4).map((b) => (
                      <span key={b.code} className={styles.badge}>
                        {b.code}: {b.count}
                      </span>
                    ))}
                  </div>
                ) : (
                  t('esg:gapsPage.summary.noIssues')
                )}
              </div>
            </div>

            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>{t('esg:gapsPage.summary.overdueReviewLabel')}</div>
              <div className={styles.summaryValue}>{data.in_review_overdue}</div>
              <div className={styles.summaryMeta}>{t('esg:gapsPage.summary.overdueReviewMeta')}</div>
            </div>
          </section>

          <section className={styles.section} aria-label={t('esg:gapsPage.missing.aria')}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>{t('esg:gapsPage.missing.title')}</h2>
              <span className={styles.sectionMeta}>{t('esg:gapsPage.missing.meta')}</span>
            </div>

            {data.missing_metrics.length === 0 ? (
              <div className={styles.empty}>{t('esg:gapsPage.missing.empty')}</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>{t('esg:gapsPage.missing.table.code')}</th>
                      <th>{t('esg:gapsPage.missing.table.metric')}</th>
                      <th>{t('esg:gapsPage.missing.table.type')}</th>
                      <th>{t('esg:gapsPage.missing.table.unit')}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.missing_metrics.map((m) => (
                      <tr key={m.metric_id}>
                        <td className={styles.mono}>{m.code || '—'}</td>
                        <td>{m.name}</td>
                        <td className={styles.mono}>{m.value_type}</td>
                        <td className={styles.mono}>{m.unit || '—'}</td>
                        <td className={styles.tableActions}>
                          <Button
                            size="sm"
                            onClick={() =>
                              navigate(
                                `/esg/facts/new?metric_id=${encodeURIComponent(m.metric_id)}&year=${encodeURIComponent(
                                  String(resolvedYear)
                                )}${resolvedEntityId ? `&entity_id=${encodeURIComponent(resolvedEntityId)}` : ''}${
                                  resolvedLocationId ? `&location_id=${encodeURIComponent(resolvedLocationId)}` : ''
                                }${resolvedSegmentId ? `&segment_id=${encodeURIComponent(resolvedSegmentId)}` : ''}`
                              )
                            }
                          >
                            {t('esg:gapsPage.missing.actions.createDraft')}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className={styles.section} aria-label={t('esg:gapsPage.attention.aria')}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>{t('esg:gapsPage.attention.title')}</h2>
              <span className={styles.sectionMeta}>{t('esg:gapsPage.attention.meta')}</span>
            </div>

            {data.attention_facts.length === 0 ? (
              <div className={styles.empty}>{t('esg:gapsPage.attention.empty')}</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>{t('esg:gapsPage.attention.table.metric')}</th>
                      <th>{t('esg:gapsPage.attention.table.status')}</th>
                      <th>{t('esg:gapsPage.attention.table.updated')}</th>
                      <th>{t('esg:gapsPage.attention.table.issues')}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {data.attention_facts.map((f) => (
                      <tr key={f.fact_id}>
                        <td>
                          <div className={styles.metricName}>{f.metric.name}</div>
                          <div className={styles.metricMeta}>
                            <span className={styles.mono}>{f.metric.code || '—'}</span>
                            <span className={styles.metaSep}>|</span>
                            <span className={styles.mono}>{f.metric.value_type}</span>
                          </div>
                        </td>
                        <td className={styles.mono}>{f.status}</td>
                        <td className={styles.mono}>{formatIsoDate(f.updated_at_utc)}</td>
                        <td>
                          <div className={styles.issueList}>
                            {f.issues.slice(0, 3).map((i) => (
                              <div key={i.code} className={styles.issueItem} title={i.message}>
                                <span className={styles.issueCode}>{i.code}</span>
                                <span className={styles.issueMsg}>{i.message}</span>
                              </div>
                            ))}
                            {f.issues.length > 3 && (
                              <div className={styles.moreIssues}>
                                {t('esg:gapsPage.attention.moreIssues', { count: f.issues.length - 3 })}
                              </div>
                            )}
                          </div>
                        </td>
                        <td className={styles.tableActions}>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              navigate(
                                `/esg/facts?metric_id=${encodeURIComponent(
                                  f.metric.metric_id
                                )}&status=${encodeURIComponent(f.status)}&period_from=${encodeURIComponent(
                                  periodStart
                                )}&period_to=${encodeURIComponent(periodEnd)}&latest_only=true${
                                  resolvedEntityId ? `&entity_id=${encodeURIComponent(resolvedEntityId)}` : ''
                                }${resolvedLocationId ? `&location_id=${encodeURIComponent(resolvedLocationId)}` : ''}${
                                  resolvedSegmentId ? `&segment_id=${encodeURIComponent(resolvedSegmentId)}` : ''
                                }`
                              )
                            }
                          >
                            {t('esg:gapsPage.attention.actions.openFacts')}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      <Modal isOpen={isSaveOpen} onClose={() => setIsSaveOpen(false)} title={t('esg:gapsPage.saveModal.title')}>
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <Input
            label={t('esg:gapsPage.saveModal.nameLabel')}
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder={t('esg:gapsPage.saveModal.namePlaceholder')}
          />
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <Button variant="secondary" onClick={() => setIsSaveOpen(false)}>
              {t('common:actions.cancel')}
            </Button>
            <Button onClick={handleSave}>{t('common:actions.save')}</Button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        isOpen={deleteViewId !== null}
        title={t('esg:gapsPage.deleteConfirm.title')}
        message={t('esg:gapsPage.deleteConfirm.message')}
        confirmLabel={t('common:actions.delete')}
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setDeleteViewId(null)}
      />
    </EsgShell>
  )
}
