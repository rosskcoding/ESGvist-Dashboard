import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { useEsgEntities, useEsgLocations, useEsgSegments, useEsgSnapshot } from '@/api/hooks'
import type { EsgFact } from '@/types/api'
import styles from './EsgSnapshotPage.module.css'

function getDefaultYear() {
  const now = new Date()
  return now.getFullYear() - 1
}

function isUuid(value: string) {
  return /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$/.test(
    value
  )
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

function formatIsoDate(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

const STANDARD_VALUES = new Set(['GRI', 'SASB', 'ISSB', 'CSRD', 'ESRS'])

export function EsgSnapshotPage() {
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

  const snapshotQuery = useEsgSnapshot({
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
      { value: '', label: t('esg:snapshotPage.filters.allStandards') },
      { value: 'GRI', label: 'GRI' },
      { value: 'SASB', label: 'SASB' },
      { value: 'ISSB', label: 'ISSB' },
      { value: 'CSRD', label: 'CSRD' },
      { value: 'ESRS', label: 'ESRS' },
    ]
  }, [t])

  const entityOptions = useMemo(() => {
    const items = entitiesQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:snapshotPage.filters.allEntities') }]
    for (const e of items) {
      const label = e.code ? `${e.name} (${e.code})` : e.name
      opts.push({ value: e.entity_id, label })
    }
    return opts
  }, [entitiesQuery.data, t])

  const locationOptions = useMemo(() => {
    const items = locationsQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:snapshotPage.filters.allLocations') }]
    for (const l of items) {
      const label = l.code ? `${l.name} (${l.code})` : l.name
      opts.push({ value: l.location_id, label })
    }
    return opts
  }, [locationsQuery.data, t])

  const segmentOptions = useMemo(() => {
    const items = segmentsQuery.data?.items ?? []
    const opts: Array<{ value: string; label: string }> = [{ value: '', label: t('esg:snapshotPage.filters.allSegments') }]
    for (const s of items) {
      const label = s.code ? `${s.name} (${s.code})` : s.name
      opts.push({ value: s.segment_id, label })
    }
    return opts
  }, [segmentsQuery.data, t])

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

  const data = snapshotQuery.data

  const gapsLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('year', String(resolvedYear))
    if (resolvedStandard) p.set('standard', resolvedStandard)
    if (resolvedEntityId) p.set('entity_id', resolvedEntityId)
    if (resolvedLocationId) p.set('location_id', resolvedLocationId)
    if (resolvedSegmentId) p.set('segment_id', resolvedSegmentId)
    if (includeInactiveMetrics) p.set('include_inactive_metrics', 'true')
    return `/esg/gaps?${p.toString()}`
  }, [resolvedYear, resolvedStandard, resolvedEntityId, resolvedLocationId, resolvedSegmentId, includeInactiveMetrics])

  const factsLink = useMemo(() => {
    const p = new URLSearchParams()
    p.set('status', 'published')
    p.set('period_from', periodStart)
    p.set('period_to', periodEnd)
    p.set('latest_only', 'true')
    if (resolvedEntityId) p.set('entity_id', resolvedEntityId)
    if (resolvedLocationId) p.set('location_id', resolvedLocationId)
    if (resolvedSegmentId) p.set('segment_id', resolvedSegmentId)
    return `/esg/facts?${p.toString()}`
  }, [periodStart, periodEnd, resolvedEntityId, resolvedLocationId, resolvedSegmentId])

  const [exportOpen, setExportOpen] = useState(false)

  const handleCopyHash = async () => {
    if (!data?.snapshot_hash) return
    try {
      await navigator.clipboard.writeText(data.snapshot_hash)
      toast.success(t('esg:snapshotPage.toast.hashCopied'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:snapshotPage.toast.copyFailed'))
    }
  }

  const snapshotJson = data ? JSON.stringify(data, null, 2) : ''

  const advancedFiltersCount =
    (resolvedEntityId ? 1 : 0) +
    (resolvedLocationId ? 1 : 0) +
    (resolvedSegmentId ? 1 : 0) +
    (includeInactiveMetrics ? 1 : 0)

  const [advancedOpen, setAdvancedOpen] = useState(advancedFiltersCount > 0)

  return (
    <EsgShell
      title={t('esg:snapshotPage.title')}
      subtitle={t('esg:snapshotPage.subtitle')}
      actions={
        <div className={styles.headerActions}>
          <Button onClick={() => navigate(`/esg/reports?year=${encodeURIComponent(String(resolvedYear))}`)}>
            {t('esg:snapshotPage.actions.useForReport')}
          </Button>
          <Button variant="secondary" onClick={() => navigate(gapsLink)}>
            {t('esg:snapshotPage.actions.checkGaps')}
          </Button>
          <Button variant="secondary" onClick={() => navigate(factsLink)}>
            {t('esg:snapshotPage.actions.browseFacts')}
          </Button>
          <Button variant="secondary" onClick={() => void handleCopyHash()} disabled={!data?.snapshot_hash}>
            {t('esg:snapshotPage.actions.copyHash')}
          </Button>
          <Button onClick={() => setExportOpen(true)} disabled={!data}>
            {t('esg:snapshotPage.actions.exportJson')}
          </Button>
        </div>
      }
    >
      <section className={styles.toolbar} aria-label={t('esg:snapshotPage.filters.aria')}>
        <Select
          label={t('esg:snapshotPage.filters.reportingYear')}
          value={String(resolvedYear)}
          onChange={(e) => handleYearChange(e.target.value)}
          options={yearOptions}
        />
        <Select
          label={t('esg:snapshotPage.filters.standard')}
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
            {t('esg:snapshotPage.filters.advanced')}
            {advancedFiltersCount ? <span className={styles.advancedCount}>{advancedFiltersCount}</span> : null}
          </summary>
          <div className={styles.advancedBody}>
            <Select
              label={t('esg:snapshotPage.filters.entity')}
              value={resolvedEntityId}
              onChange={(e) => handleEntityChange(e.target.value)}
              options={entityOptions}
            />
            <Select
              label={t('esg:snapshotPage.filters.location')}
              value={resolvedLocationId}
              onChange={(e) => handleLocationChange(e.target.value)}
              options={locationOptions}
            />
            <Select
              label={t('esg:snapshotPage.filters.segment')}
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
              {t('esg:snapshotPage.filters.includeInactiveMetrics')}
            </label>
          </div>
        </details>
        <div className={styles.toolbarMeta}>
          {t('esg:snapshotPage.filters.period')} <strong>{periodStart}</strong> {t('esg:snapshotPage.filters.periodTo')}{' '}
          <strong>{periodEnd}</strong>
        </div>
      </section>

      {snapshotQuery.isLoading && <div className={styles.loading}>{t('esg:snapshotPage.loading')}</div>}
      {snapshotQuery.error && <div className={styles.error}>{t('esg:snapshotPage.error')}</div>}

      {data && (
        <>
          <section className={styles.summary} aria-label={t('esg:snapshotPage.summary.aria')}>
            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>{t('esg:snapshotPage.summary.publishedFactsLabel')}</div>
              <div className={styles.summaryValueBig}>{data.facts_published}</div>
              <div className={styles.summaryMeta}>{t('esg:snapshotPage.summary.publishedFactsMeta', { total: data.metrics_total })}</div>
            </div>

            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>{t('esg:snapshotPage.summary.missingMetricsLabel')}</div>
              <div className={styles.summaryValueBig}>{data.missing_metrics.length}</div>
              <div className={styles.summaryMeta}>{t('esg:snapshotPage.summary.missingMetricsMeta')}</div>
            </div>

            <div className={styles.summaryCard}>
              <div className={styles.summaryLabel}>{t('esg:snapshotPage.summary.snapshotHashLabel')}</div>
              <div className={styles.summaryValue}>{data.snapshot_hash.slice(0, 16)}…</div>
              <div className={styles.summaryMeta}>
                <details className={styles.technicalDetails}>
                  <summary className={styles.technicalSummary}>{t('esg:snapshotPage.summary.snapshotHashAdvanced')}</summary>
                  <div className={styles.hashRow}>
                    <span className={styles.hash}>{data.snapshot_hash}</span>
                  </div>
                </details>
              </div>
            </div>
          </section>

          <section className={styles.section} aria-label={t('esg:snapshotPage.published.aria')}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>{t('esg:snapshotPage.published.title')}</h2>
              <span className={styles.sectionMeta}>
                {t('esg:snapshotPage.published.generatedAt', { date: formatIsoDate(data.generated_at_utc) })}
              </span>
            </div>

            {data.facts.length === 0 ? (
              <div className={styles.empty}>{t('esg:snapshotPage.published.empty')}</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>{t('esg:snapshotPage.published.table.metric')}</th>
                      <th>{t('esg:snapshotPage.published.table.value')}</th>
                      <th>{t('esg:snapshotPage.published.table.published')}</th>
                      <th>{t('esg:snapshotPage.published.table.fact')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.facts.map((item) => (
                      <tr key={item.fact.fact_id}>
                        <td>
                          <div className={styles.metricName}>{item.metric.name}</div>
                          <div className={styles.metricMeta}>
                            <span className={styles.mono}>{item.metric.code || '—'}</span>
                            <span className={styles.metaSep}>|</span>
                            <span className={styles.mono}>{item.metric.value_type}</span>
                            {item.metric.unit && (
                              <>
                                <span className={styles.metaSep}>|</span>
                                <span className={styles.mono}>{item.metric.unit}</span>
                              </>
                            )}
                          </div>
                        </td>
                        <td className={styles.mono}>{renderFactValue(item.fact)}</td>
                        <td className={styles.mono}>{formatIsoDate(item.fact.published_at_utc)}</td>
                        <td className={styles.tableActions}>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              navigate(
                                `/esg/facts?metric_id=${encodeURIComponent(
                                  item.metric.metric_id
                                )}&status=published&period_from=${encodeURIComponent(periodStart)}&period_to=${encodeURIComponent(
                                  periodEnd
                                )}&latest_only=true${resolvedEntityId ? `&entity_id=${encodeURIComponent(resolvedEntityId)}` : ''}${
                                  resolvedLocationId ? `&location_id=${encodeURIComponent(resolvedLocationId)}` : ''
                                }${resolvedSegmentId ? `&segment_id=${encodeURIComponent(resolvedSegmentId)}` : ''}`
                              )
                            }
                          >
                            {t('esg:snapshotPage.actions.open')}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className={styles.section} aria-label={t('esg:snapshotPage.missing.aria')}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>{t('esg:snapshotPage.missing.title')}</h2>
              <span className={styles.sectionMeta}>{t('esg:snapshotPage.missing.meta')}</span>
            </div>

            {data.missing_metrics.length === 0 ? (
              <div className={styles.empty}>{t('esg:snapshotPage.missing.empty')}</div>
            ) : (
              <div className={styles.tableWrap}>
                <table className={styles.table}>
                  <thead>
                    <tr>
                      <th>{t('esg:snapshotPage.missing.table.code')}</th>
                      <th>{t('esg:snapshotPage.missing.table.metric')}</th>
                      <th>{t('esg:snapshotPage.missing.table.type')}</th>
                      <th>{t('esg:snapshotPage.missing.table.unit')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.missing_metrics.map((m) => (
                      <tr key={m.metric_id}>
                        <td className={styles.mono}>{m.code || '—'}</td>
                        <td>{m.name}</td>
                        <td className={styles.mono}>{m.value_type}</td>
                        <td className={styles.mono}>{m.unit || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

      <Modal isOpen={exportOpen} onClose={() => setExportOpen(false)} title={t('esg:snapshotPage.exportModal.title')} size="xl">
        <pre className={styles.codeBlock}>{snapshotJson}</pre>
        <div className={styles.modalActions}>
          <Button variant="secondary" onClick={() => setExportOpen(false)}>
            {t('common:actions.close')}
          </Button>
          <Button
            onClick={() => {
              if (!snapshotJson) return
              void navigator.clipboard
                .writeText(snapshotJson)
                .then(() => toast.success(t('esg:snapshotPage.toast.jsonCopied')))
                .catch((e) => toast.error((e as Error).message || t('esg:snapshotPage.toast.copyFailed')))
            }}
            disabled={!snapshotJson}
          >
            {t('esg:snapshotPage.exportModal.copyJson')}
          </Button>
        </div>
      </Modal>
    </EsgShell>
  )
}
