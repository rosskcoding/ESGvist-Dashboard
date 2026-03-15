import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, ConfirmDialog, DropdownMenu, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { apiClient, ApiHttpError } from '@/api/client'
import { queryKeys, useCreateEsgMetric, useDeleteEsgMetric, useUpdateEsgMetric } from '@/api/hooks'
import type { EsgMetric, EsgMetricCreate, EsgMetricUpdate, EsgMetricValueType, PaginatedResponse } from '@/types/api'
import styles from './EsgMetricsPage.module.css'

const DEFAULT_PAGE_SIZE = 50
const FETCH_PAGE_SIZE = 100
const MAX_FETCH_PAGES = 20

type EsgPillar = 'E' | 'S' | 'G'

type MetricStandardMapping = {
  standard: string
  disclosure_id: string
  required?: boolean
}

const STANDARD_MAPPING_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'GRI', label: 'GRI' },
  { value: 'SASB', label: 'SASB' },
  { value: 'ISSB', label: 'ISSB' },
  { value: 'CSRD', label: 'CSRD' },
  { value: 'ESRS', label: 'ESRS' },
]

function metricStandardMappings(metric: EsgMetric): MetricStandardMapping[] {
  const schema = metric.value_schema_json as unknown
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return []
  const raw = (schema as Record<string, unknown>).standards
  if (!Array.isArray(raw)) return []

  const out: MetricStandardMapping[] = []
  for (const item of raw) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue
    const anyItem = item as Record<string, unknown>
    const standard = typeof anyItem.standard === 'string' ? anyItem.standard.trim().toUpperCase() : ''
    const disclosureId = typeof anyItem.disclosure_id === 'string' ? anyItem.disclosure_id.trim() : ''
    if (!standard || !disclosureId) continue
    out.push({
      standard,
      disclosure_id: disclosureId,
      required: anyItem.required === false ? false : true,
    })
  }
  return out
}

function mappingLabel(m: MetricStandardMapping): string {
  return `${m.standard} ${m.disclosure_id}`
}

function normalizePillar(value: unknown): EsgPillar | null {
  if (typeof value !== 'string') return null
  const s = value.trim().toUpperCase()
  if (s === 'E' || s === 'ENV' || s === 'ENVIRONMENT' || s === 'ENVIRONMENTAL') return 'E'
  if (s === 'S' || s === 'SOC' || s === 'SOCIAL') return 'S'
  if (s === 'G' || s === 'GOV' || s === 'GOVERNANCE') return 'G'
  return null
}

function metricPillar(metric: EsgMetric): EsgPillar | null {
  const schema = metric.value_schema_json as unknown
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) return null
  return normalizePillar((schema as Record<string, unknown>).pillar)
}

function useEsgMetricsAll(params: { search?: string; includeInactive: boolean; companyId?: string }) {
  return useQuery({
    queryKey: [
      ...queryKeys.esg.all,
      'metrics',
      'all',
      {
        search: params.search,
        include_inactive: params.includeInactive,
        company_id: params.companyId,
      },
    ] as const,
    queryFn: async () => {
      const items: EsgMetric[] = []
      let total = 0
      let totalPages = 1

      for (let page = 1; page <= totalPages && page <= MAX_FETCH_PAGES; page += 1) {
        const queryParams: Record<string, string> = {
          page: String(page),
          page_size: String(FETCH_PAGE_SIZE),
          include_inactive: String(params.includeInactive),
        }
        if (params.search) queryParams.search = params.search
        if (params.companyId) queryParams.company_id = params.companyId

        const { data } = await apiClient.get<PaginatedResponse<EsgMetric>>('/api/v1/esg/metrics', { params: queryParams })
        if (page === 1) {
          total = data.total
          totalPages = data.total_pages
        }
        items.push(...data.items)
        if (!data.has_next) break
      }

      return {
        items,
        total,
        truncated: totalPages > MAX_FETCH_PAGES,
      }
    },
  })
}

function metricToEditDefaults(metric: EsgMetric): EsgMetricUpdate & { value_type: EsgMetricValueType } {
  return {
    code: metric.code,
    name: metric.name,
    description: metric.description,
    value_type: metric.value_type,
    unit: metric.unit,
    value_schema_json: metric.value_schema_json,
    is_active: metric.is_active,
  }
}

export function EsgMetricsPage() {
  const { t } = useTranslation(['esg', 'common'])
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState<{ key: 'name' | 'code' | 'status'; dir: 'asc' | 'desc' }>({
    key: 'name',
    dir: 'asc',
  })
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editing, setEditing] = useState<EsgMetric | null>(null)
  const [previewing, setPreviewing] = useState<EsgMetric | null>(null)
  const [confirmAction, setConfirmAction] = useState<
    | { kind: 'delete'; metric: EsgMetric }
    | { kind: 'deactivate'; metric: EsgMetric }
    | { kind: 'activate'; metric: EsgMetric }
    | null
  >(null)

  const pillarParam = searchParams.get('pillar')
  const selectedPillar = normalizePillar(pillarParam)
  const pillarFilter: EsgPillar | 'all' | null = selectedPillar ? selectedPillar : pillarParam === 'all' ? 'all' : null

  const setPillar = (next: EsgPillar | 'all' | null) => {
    const updated = new URLSearchParams(searchParams)
    if (!next) updated.delete('pillar')
    else updated.set('pillar', next)
    setSearchParams(updated, { replace: true })
  }

  const showTable = pillarFilter !== null

  const metricsQuery = useEsgMetricsAll({
    search: search.trim() || undefined,
    includeInactive,
  })

  const allMetrics = useMemo(() => metricsQuery.data?.items ?? [], [metricsQuery.data?.items])
  const pillarCounts = useMemo(() => {
    const counts: Record<EsgPillar, number> = { E: 0, S: 0, G: 0 }
    let unassigned = 0
    for (const metric of allMetrics) {
      const p = metricPillar(metric)
      if (p) counts[p] += 1
      else unassigned += 1
    }
    return { ...counts, unassigned }
  }, [allMetrics])
  const unassignedCount = pillarCounts.unassigned

  const createMetric = useCreateEsgMetric()
  const updateMetric = useUpdateEsgMetric()
  const deleteMetric = useDeleteEsgMetric()

  useEffect(() => {
    if (searchParams.get('new') !== '1') return
    setIsCreateOpen(true)
    const next = new URLSearchParams(searchParams)
    next.delete('new')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  useEffect(() => {
    setPage(1)
  }, [includeInactive, pillarFilter, search])

  const toggleSort = (key: 'name' | 'code' | 'status') => {
    setSort((prev) => {
      if (prev.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      }
      return { key, dir: 'asc' }
    })
  }

  const sortIcon = (key: 'name' | 'code' | 'status') => {
    if (sort.key !== key) return null
    return sort.dir === 'asc' ? '▲' : '▼'
  }

  const filteredMetrics = useMemo(() => {
    if (pillarFilter === 'all') return allMetrics
    if (pillarFilter === null) return []
    return allMetrics.filter((m) => metricPillar(m) === pillarFilter)
  }, [allMetrics, pillarFilter])

  const canSubmit = !createMetric.isPending && !updateMetric.isPending

  const handleCreate = async (data: EsgMetricCreate) => {
    try {
      await createMetric.mutateAsync(data)
      toast.success(t('esg:metricsPage.toast.created'))
      setIsCreateOpen(false)
    } catch (e) {
      toast.error((e as Error).message || t('esg:metricsPage.toast.createFailed'))
    }
  }

  const handleUpdate = async (metricId: string, data: EsgMetricUpdate) => {
    try {
      await updateMetric.mutateAsync({ metricId, data })
      toast.success(t('esg:metricsPage.toast.updated'))
      setEditing(null)
    } catch (e) {
      toast.error((e as Error).message || t('esg:metricsPage.toast.updateFailed'))
    }
  }

  const handleSetActive = async (metric: EsgMetric, isActive: boolean) => {
    try {
      await updateMetric.mutateAsync({ metricId: metric.metric_id, data: { is_active: isActive } })
      toast.success(isActive ? t('esg:metricsPage.toast.activated') : t('esg:metricsPage.toast.deactivated'))
      setConfirmAction(null)
    } catch (e) {
      toast.error((e as Error).message || t('esg:metricsPage.toast.updateFailed'))
    }
  }

  const handleDelete = async (metric: EsgMetric) => {
    try {
      await deleteMetric.mutateAsync(metric.metric_id)
      toast.success(t('esg:metricsPage.toast.deleted'))
      setConfirmAction(null)
    } catch (e) {
      if (e instanceof ApiHttpError && e.status === 409) {
        toast.error(t('esg:metricsPage.toast.deleteBlockedHasFacts'))
        setConfirmAction({ kind: 'deactivate', metric })
        return
      }
      toast.error((e as Error).message || t('esg:metricsPage.toast.deleteFailed'))
    }
  }

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(t('esg:metricsPage.toast.copied'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:metricsPage.toast.copyFailed'))
    }
  }

  const metricRows = useMemo(() => {
    const rows = filteredMetrics.map((m) => ({
      id: m.metric_id,
      code: m.code || '—',
      name: m.name,
      pillar: metricPillar(m),
      type: m.value_type,
      unit: m.unit || '—',
      is_active: m.is_active,
      metric: m,
    }))

    const dir = sort.dir === 'asc' ? 1 : -1
    rows.sort((a, b) => {
      if (sort.key === 'name') {
        return a.name.localeCompare(b.name) * dir
      }
      if (sort.key === 'code') {
        const aCode = (a.metric.code || '').toLowerCase()
        const bCode = (b.metric.code || '').toLowerCase()
        if (!aCode && !bCode) return 0
        if (!aCode) return 1 * dir
        if (!bCode) return -1 * dir
        return aCode.localeCompare(bCode) * dir
      }
      const aStatus = a.is_active ? 0 : 1
      const bStatus = b.is_active ? 0 : 1
      return (aStatus - bStatus) * dir
    })

    return rows
  }, [filteredMetrics, sort.dir, sort.key])

  const total = metricRows.length
  const totalPages = Math.max(1, Math.ceil(total / DEFAULT_PAGE_SIZE))
  const resolvedPage = Math.min(page, totalPages)
  const showingFrom = total === 0 ? 0 : (resolvedPage - 1) * DEFAULT_PAGE_SIZE + 1
  const showingTo = total === 0 ? 0 : Math.min(resolvedPage * DEFAULT_PAGE_SIZE, total)

  useEffect(() => {
    if (page <= totalPages) return
    setPage(totalPages)
  }, [page, totalPages])

  const pageRows = useMemo(() => {
    const start = (resolvedPage - 1) * DEFAULT_PAGE_SIZE
    return metricRows.slice(start, start + DEFAULT_PAGE_SIZE)
  }, [metricRows, resolvedPage])

  return (
    <EsgShell
      title={t('esg:metricsPage.title')}
      subtitle={t('esg:metricsPage.subtitle')}
      actions={
        <Button onClick={() => setIsCreateOpen(true)}>
          {t('esg:metricsPage.actions.newMetric')}
        </Button>
      }
    >
      {!showTable && (
        <section className={styles.pillarChooser} aria-label={t('esg:metricsPage.pillars.aria')}>
          <div className={styles.pillarChooserHeader}>
            <div>
              <h2 className={styles.pillarChooserTitle}>{t('esg:metricsPage.pillars.title')}</h2>
              <p className={styles.pillarChooserHint}>{t('esg:metricsPage.pillars.hint')}</p>
            </div>
            <Button variant="secondary" onClick={() => setPillar('all')}>
              {t('esg:metricsPage.pillars.showAll')}
            </Button>
          </div>

          <div className={styles.pillarGrid}>
            <button type="button" className={`${styles.pillarCard} ${styles.pillarCardE}`} onClick={() => setPillar('E')}>
              <div className={styles.pillarCardTop}>
                <div className={styles.pillarLetter}>E</div>
                <div className={styles.pillarCardTitle}>{t('esg:metricsPage.pillars.environmental')}</div>
              </div>
              <div className={styles.pillarCardCount}>{metricsQuery.isLoading ? '…' : pillarCounts.E.toLocaleString()}</div>
              <div className={styles.pillarCardHint}>{t('esg:metricsPage.pillars.environmentalHint')}</div>
            </button>

            <button type="button" className={`${styles.pillarCard} ${styles.pillarCardS}`} onClick={() => setPillar('S')}>
              <div className={styles.pillarCardTop}>
                <div className={styles.pillarLetter}>S</div>
                <div className={styles.pillarCardTitle}>{t('esg:metricsPage.pillars.social')}</div>
              </div>
              <div className={styles.pillarCardCount}>{metricsQuery.isLoading ? '…' : pillarCounts.S.toLocaleString()}</div>
              <div className={styles.pillarCardHint}>{t('esg:metricsPage.pillars.socialHint')}</div>
            </button>

            <button type="button" className={`${styles.pillarCard} ${styles.pillarCardG}`} onClick={() => setPillar('G')}>
              <div className={styles.pillarCardTop}>
                <div className={styles.pillarLetter}>G</div>
                <div className={styles.pillarCardTitle}>{t('esg:metricsPage.pillars.governance')}</div>
              </div>
              <div className={styles.pillarCardCount}>{metricsQuery.isLoading ? '…' : pillarCounts.G.toLocaleString()}</div>
              <div className={styles.pillarCardHint}>{t('esg:metricsPage.pillars.governanceHint')}</div>
            </button>
          </div>

          {!metricsQuery.isLoading && allMetrics.length === 0 && (
            <div className={styles.pillarEmpty}>{t('esg:metricsPage.table.empty')}</div>
          )}

          {!metricsQuery.isLoading && allMetrics.length > 0 && unassignedCount > 0 && (
            <div className={styles.pillarNote}>{t('esg:metricsPage.pillars.unassigned', { count: unassignedCount })}</div>
          )}
        </section>
      )}

      {showTable && (
        <>
          <div className={styles.pillarTabs} aria-label={t('esg:metricsPage.pillars.aria')}>
            <Button variant="secondary" size="sm" onClick={() => setPillar(null)}>
              {t('esg:metricsPage.pillars.back')}
            </Button>
            <div className={styles.pillarTabGroup}>
              <button
                type="button"
                className={`${styles.pillarTab} ${pillarFilter === 'all' ? styles.pillarTabActive : ''}`}
                onClick={() => setPillar('all')}
              >
                {t('esg:metricsPage.pillars.all')} <span className={styles.pillarTabCount}>{allMetrics.length.toLocaleString()}</span>
              </button>
              <button
                type="button"
                className={`${styles.pillarTab} ${pillarFilter === 'E' ? styles.pillarTabActive : ''}`}
                onClick={() => setPillar('E')}
              >
                E <span className={styles.pillarTabCount}>{pillarCounts.E.toLocaleString()}</span>
              </button>
              <button
                type="button"
                className={`${styles.pillarTab} ${pillarFilter === 'S' ? styles.pillarTabActive : ''}`}
                onClick={() => setPillar('S')}
              >
                S <span className={styles.pillarTabCount}>{pillarCounts.S.toLocaleString()}</span>
              </button>
              <button
                type="button"
                className={`${styles.pillarTab} ${pillarFilter === 'G' ? styles.pillarTabActive : ''}`}
                onClick={() => setPillar('G')}
              >
                G <span className={styles.pillarTabCount}>{pillarCounts.G.toLocaleString()}</span>
              </button>
            </div>
          </div>

          <div className={styles.toolbar}>
            <Input
              label={t('esg:metricsPage.filters.search.label')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('esg:metricsPage.filters.search.placeholder')}
            />
            <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', paddingBottom: '0.25rem' }}>
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => setIncludeInactive(e.target.checked)}
              />
              {t('esg:metricsPage.filters.includeInactive')}
            </label>
          </div>

          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th style={{ width: '14%' }}>
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort('code')}>
                      {t('esg:metricsPage.table.headers.code')} <span className={styles.sortIcon}>{sortIcon('code')}</span>
                    </button>
                  </th>
                  <th>
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort('name')}>
                      {t('esg:metricsPage.table.headers.name')} <span className={styles.sortIcon}>{sortIcon('name')}</span>
                    </button>
                  </th>
                  <th style={{ width: '10%' }}>{t('esg:metricsPage.table.headers.pillar')}</th>
                  <th style={{ width: '20%' }}>{t('esg:metricsPage.table.headers.standards')}</th>
                  <th style={{ width: '12%' }}>{t('esg:metricsPage.table.headers.type')}</th>
                  <th style={{ width: '10%' }}>{t('esg:metricsPage.table.headers.unit')}</th>
                  <th style={{ width: '10%' }}>
                    <button type="button" className={styles.sortButton} onClick={() => toggleSort('status')}>
                      {t('esg:metricsPage.table.headers.status')} <span className={styles.sortIcon}>{sortIcon('status')}</span>
                    </button>
                  </th>
                  <th style={{ width: '14%' }} />
                </tr>
              </thead>
              <tbody>
                {metricsQuery.isLoading && (
                  <tr>
                    <td colSpan={8} style={{ padding: '1rem' }}>
                      {t('common:common.loading')}
                    </td>
                  </tr>
                )}

                {!metricsQuery.isLoading && total === 0 && (
                  <tr>
                    <td colSpan={8} style={{ padding: '1rem' }}>
                      {pillarFilter && pillarFilter !== 'all' ? t('esg:metricsPage.table.emptyPillar') : t('esg:metricsPage.table.empty')}
                    </td>
                  </tr>
                )}

                {pageRows.map((row) => {
                  const mappings = metricStandardMappings(row.metric)
                  return (
                    <tr key={row.id}>
                      <td className={styles.mono}>
                        <div className={styles.codeCell}>
                          <span className={styles.codeText} title={row.metric.code || undefined}>
                            {row.code}
                          </span>
                          {row.metric.code && (
                            <button
                              type="button"
                              className={styles.codeCopyBtn}
                              title={t('common:actions.copy')}
                              aria-label={t('esg:metricsPage.actions.copyCode')}
                              onClick={() => void copyToClipboard(row.metric.code || '')}
                            >
                              {t('common:actions.copy')}
                            </button>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className={styles.nameCell}>
                          <div className={styles.nameTitle}>{row.name}</div>
                        </div>
                      </td>
                      <td>
                        {row.pillar ? (
                          <span
                            className={`${styles.pillarBadge} ${row.pillar === 'E' ? styles.pillarBadgeE : row.pillar === 'S' ? styles.pillarBadgeS : styles.pillarBadgeG}`}
                            title={row.pillar}
                          >
                            {row.pillar}
                          </span>
                        ) : (
                          <span className={styles.muted}>{t('esg:metricsPage.table.unassigned')}</span>
                        )}
                      </td>
                      <td>
                        {mappings.length > 0 ? (
                          <div className={styles.stdBadges} aria-label={t('esg:metricsPage.table.standardsMappingAria')}>
                            {mappings.slice(0, 3).map((m) => (
                              <span key={mappingLabel(m)} className={styles.stdBadge} title={mappingLabel(m)}>
                                {mappingLabel(m)}
                              </span>
                            ))}
                            {mappings.length > 3 && (
                              <span className={styles.stdMore}>
                                {t('esg:metricsPage.table.standardsMappingMore', { count: mappings.length - 3 })}
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className={styles.muted}>{t('esg:metricsPage.table.noStandard')}</span>
                        )}
                      </td>
                      <td>
                        <span className={styles.badge}>{row.type}</span>
                      </td>
                      <td>{row.unit}</td>
                      <td>
                        <span className={`${styles.badge} ${row.is_active ? '' : styles.badgeInactive}`}>
                          {row.is_active ? t('common:status.active') : t('common:status.inactive')}
                        </span>
                      </td>
                      <td>
                        <div className={styles.rowActions}>
                          <Button variant="secondary" size="sm" onClick={() => setEditing(row.metric)}>
                            {t('common:actions.edit')}
                          </Button>
                          <DropdownMenu
                            triggerLabel="⋯"
                            triggerAriaLabel={t('esg:metricsPage.actions.moreActions')}
                            items={[
                              { label: t('esg:metricsPage.actions.preview'), onSelect: () => setPreviewing(row.metric) },
                              {
                                label: row.is_active ? t('esg:metricsPage.actions.deactivate') : t('esg:metricsPage.actions.activate'),
                                onSelect: () =>
                                  setConfirmAction({
                                    kind: row.is_active ? 'deactivate' : 'activate',
                                    metric: row.metric,
                                  }),
                              },
                              { type: 'divider' },
                              {
                                label: t('common:actions.delete'),
                                variant: 'danger',
                                onSelect: () => setConfirmAction({ kind: 'delete', metric: row.metric }),
                              },
                            ]}
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
              {total === 0
                ? t('esg:metricsPage.pager.zeroResults')
                : t('esg:metricsPage.pager.resultsRange', { from: showingFrom, to: showingTo, total })}
            </div>
            <div className={styles.pagerActions}>
              <Button
                variant="secondary"
                size="sm"
                disabled={resolvedPage <= 1 || metricsQuery.isLoading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                {t('esg:metricsPage.pager.prev')}
              </Button>
              <div className={styles.pagerPage}>
                {t('esg:metricsPage.pager.pageOf', { page: resolvedPage, totalPages })}
              </div>
              <Button
                variant="secondary"
                size="sm"
                disabled={resolvedPage >= totalPages || metricsQuery.isLoading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                {t('esg:metricsPage.pager.next')}
              </Button>
            </div>
          </div>
        </>
      )}

      <MetricModal
        isOpen={isCreateOpen}
        title={t('esg:metricModal.newTitle')}
        submitLabel={t('common:actions.create')}
        disabled={!canSubmit}
        initial={pillarFilter && pillarFilter !== 'all' ? { value_schema_json: { pillar: pillarFilter } } : undefined}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreate}
      />

      <MetricModal
        isOpen={Boolean(editing)}
        title={t('esg:metricModal.editTitle')}
        submitLabel={t('common:actions.save')}
        disabled={!canSubmit || !editing}
        initial={editing ? metricToEditDefaults(editing) : undefined}
        onClose={() => setEditing(null)}
        onSubmit={(data) => {
          if (!editing) return
          return handleUpdate(editing.metric_id, data)
        }}
      />

      <MetricPreviewModal metric={previewing} onClose={() => setPreviewing(null)} />

      <ConfirmDialog
        isOpen={Boolean(confirmAction)}
        title={
          confirmAction?.kind === 'delete'
            ? t('esg:metricsPage.confirm.deleteTitle')
            : confirmAction?.kind === 'deactivate'
              ? t('esg:metricsPage.confirm.deactivateTitle')
              : confirmAction?.kind === 'activate'
                ? t('esg:metricsPage.confirm.activateTitle')
                : undefined
        }
        message={
          (() => {
            if (!confirmAction) return ''
            const codeSuffix = confirmAction.metric.code ? ` (${confirmAction.metric.code})` : ''
            if (confirmAction.kind === 'delete') {
              return t('esg:metricsPage.confirm.deleteMessage', { name: confirmAction.metric.name, codeSuffix })
            }
            if (confirmAction.kind === 'deactivate') {
              return t('esg:metricsPage.confirm.deactivateMessage', { name: confirmAction.metric.name, codeSuffix })
            }
            return t('esg:metricsPage.confirm.activateMessage', { name: confirmAction.metric.name, codeSuffix })
          })()
        }
        confirmLabel={
          confirmAction?.kind === 'delete'
            ? t('common:actions.delete')
            : confirmAction?.kind === 'deactivate'
              ? t('esg:metricsPage.actions.deactivate')
              : confirmAction?.kind === 'activate'
                ? t('esg:metricsPage.actions.activate')
                : t('esg:metricsPage.confirm.ok')
        }
        confirmLoading={deleteMetric.isPending || updateMetric.isPending}
        variant={confirmAction?.kind === 'delete' ? 'danger' : 'warning'}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (!confirmAction) return

          if (confirmAction.kind === 'delete') {
            void handleDelete(confirmAction.metric)
            return
          }

          if (confirmAction.kind === 'deactivate') {
            void handleSetActive(confirmAction.metric, false)
            return
          }

          if (confirmAction.kind === 'activate') {
            void handleSetActive(confirmAction.metric, true)
          }
        }}
      />
    </EsgShell>
  )
}

function MetricModal(props: {
  isOpen: boolean
  onClose: () => void
  title: string
  submitLabel: string
  disabled: boolean
  initial?: Partial<EsgMetricCreate>
  onSubmit: (data: EsgMetricCreate) => void | Promise<void>
}) {
  const { t } = useTranslation(['esg', 'common'])
  const [code, setCode] = useState(props.initial?.code ?? '')
  const [name, setName] = useState(props.initial?.name ?? '')
  const [description, setDescription] = useState(props.initial?.description ?? '')
  const [valueType, setValueType] = useState<EsgMetricValueType>((props.initial?.value_type as EsgMetricValueType) ?? 'number')
  const [unit, setUnit] = useState(props.initial?.unit ?? '')
  const [isActive, setIsActive] = useState(props.initial?.is_active ?? true)
  const [schemaJson, setSchemaJson] = useState<string>(JSON.stringify(props.initial?.value_schema_json ?? {}, null, 2))
  const [schemaError, setSchemaError] = useState<string | null>(null)
  const [standardMappings, setStandardMappings] = useState<Array<{ standard: string; disclosure_id: string; required: boolean }>>([])
  const [pillar, setPillar] = useState<EsgPillar | ''>('')

  const valueTypeOptions = useMemo(
    () =>
      [
        { value: 'number', label: t('esg:metricModal.valueTypes.number') },
        { value: 'integer', label: t('esg:metricModal.valueTypes.integer') },
        { value: 'boolean', label: t('esg:metricModal.valueTypes.boolean') },
        { value: 'string', label: t('esg:metricModal.valueTypes.string') },
        { value: 'dataset', label: t('esg:metricModal.valueTypes.dataset') },
      ] satisfies Array<{ value: EsgMetricValueType; label: string }>,
    [t]
  )

  const parseSchemaObject = (text: string): Record<string, unknown> | null => {
    if (!text.trim()) return {}
    try {
      const parsed = JSON.parse(text) as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
      return parsed as Record<string, unknown>
    } catch {
      return null
    }
  }

  const extractMappings = (schema: Record<string, unknown> | null | undefined) => {
    if (!schema) return []
    const raw = schema.standards
    if (!Array.isArray(raw)) return []
    const out: Array<{ standard: string; disclosure_id: string; required: boolean }> = []
    for (const item of raw) {
      if (!item || typeof item !== 'object' || Array.isArray(item)) continue
      const anyItem = item as Record<string, unknown>
      const standard = typeof anyItem.standard === 'string' ? anyItem.standard.trim().toUpperCase() : ''
      const disclosureId = typeof anyItem.disclosure_id === 'string' ? anyItem.disclosure_id.trim() : ''
      if (!standard || !disclosureId) continue
      out.push({ standard, disclosure_id: disclosureId, required: anyItem.required === false ? false : true })
    }
    return out
  }

  const extractPillar = (schema: Record<string, unknown> | null | undefined): EsgPillar | '' => {
    if (!schema) return ''
    return normalizePillar(schema.pillar) ?? ''
  }

  const applyMappingsToSchemaJson = (next: Array<{ standard: string; disclosure_id: string; required: boolean }>) => {
    setStandardMappings(next)

    const parsed = parseSchemaObject(schemaJson)
    if (parsed === null) {
      setSchemaError(t('esg:metricModal.schema.invalidJson'))
      return
    }

    const cleaned = next
      .map((m) => ({
        standard: m.standard.trim().toUpperCase(),
        disclosure_id: m.disclosure_id.trim(),
        required: Boolean(m.required),
      }))
      .filter((m) => m.standard && m.disclosure_id)

    const nextSchema: Record<string, unknown> = { ...parsed }
    if (cleaned.length > 0) nextSchema.standards = cleaned
    else delete nextSchema.standards

    setSchemaJson(JSON.stringify(nextSchema, null, 2))
    setSchemaError(null)
  }

  const applyPillarToSchemaJson = (nextPillar: EsgPillar | '') => {
    setPillar(nextPillar)

    const parsed = parseSchemaObject(schemaJson)
    if (parsed === null) {
      setSchemaError(t('esg:metricModal.schema.invalidJson'))
      return
    }

    const nextSchema: Record<string, unknown> = { ...parsed }
    if (nextPillar) nextSchema.pillar = nextPillar
    else delete nextSchema.pillar

    setSchemaJson(JSON.stringify(nextSchema, null, 2))
    setSchemaError(null)
  }

  useEffect(() => {
    if (!props.isOpen) return
    setCode(props.initial?.code ?? '')
    setName(props.initial?.name ?? '')
    setDescription(props.initial?.description ?? '')
    setValueType((props.initial?.value_type as EsgMetricValueType) ?? 'number')
    setUnit(props.initial?.unit ?? '')
    setIsActive(props.initial?.is_active ?? true)
    const schema = props.initial?.value_schema_json ?? {}
    setSchemaJson(JSON.stringify(schema, null, 2))
    setStandardMappings(extractMappings(schema as unknown as Record<string, unknown>))
    setPillar(extractPillar(schema as unknown as Record<string, unknown>))
    setSchemaError(null)
  }, [props.isOpen, props.initial])

  const submit = async () => {
    if (props.disabled) return
    if (!name.trim()) {
      toast.error(t('esg:metricModal.validation.nameRequired'))
      return
    }

    let parsedSchema: Record<string, unknown> = {}
    if (schemaJson.trim()) {
      try {
        parsedSchema = JSON.parse(schemaJson) as Record<string, unknown>
        setSchemaError(null)
      } catch {
        setSchemaError(t('esg:metricModal.schema.invalidJson'))
        return
      }
    }

    const invalidMapping = standardMappings.find((m) => {
      const s = m.standard.trim()
      const d = m.disclosure_id.trim()
      return (s && !d) || (!s && d)
    })
    if (invalidMapping) {
      toast.error(t('esg:metricModal.standards.validationRow'))
      return
    }

    const cleanedMappings = standardMappings
      .map((m) => ({
        standard: m.standard.trim().toUpperCase(),
        disclosure_id: m.disclosure_id.trim(),
        required: Boolean(m.required),
      }))
      .filter((m) => m.standard && m.disclosure_id)

    if (cleanedMappings.length > 0) parsedSchema.standards = cleanedMappings
    else delete (parsedSchema as Record<string, unknown>).standards

    if (pillar) parsedSchema.pillar = pillar
    else delete (parsedSchema as Record<string, unknown>).pillar

    await props.onSubmit({
      code: code.trim() || null,
      name: name.trim(),
      description: description.trim() || null,
      value_type: valueType,
      unit: unit.trim() || null,
      value_schema_json: parsedSchema,
      is_active: isActive,
    })
  }

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title={props.title} size="lg">
      <div className={styles.formGrid}>
        <Input
          label={t('esg:metricModal.fields.name.label')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('esg:metricModal.fields.name.placeholder')}
        />
        <Input
          label={t('esg:metricModal.fields.code.label')}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={t('esg:labels.optional')}
        />
        <div className={styles.formGridFull}>
          <Select
            label={t('esg:metricModal.fields.valueType.label')}
            value={valueType}
            onChange={(e) => setValueType(e.target.value as EsgMetricValueType)}
            options={valueTypeOptions}
          />
        </div>
        <div className={styles.formGridFull}>
          <Select
            label={t('esg:metricModal.fields.pillar.label')}
            value={pillar}
            onChange={(e) => applyPillarToSchemaJson(normalizePillar(e.target.value) ?? '')}
            options={[
              { value: '', label: t('esg:metricModal.fields.pillar.unassigned') },
              { value: 'E', label: t('esg:metricModal.fields.pillar.options.environmental') },
              { value: 'S', label: t('esg:metricModal.fields.pillar.options.social') },
              { value: 'G', label: t('esg:metricModal.fields.pillar.options.governance') },
            ]}
          />
        </div>
        <Input
          label={t('esg:metricModal.fields.unit.label')}
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          placeholder={t('esg:metricModal.fields.unit.placeholder')}
        />
        <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', paddingTop: '1.75rem' }}>
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          {t('common:status.active')}
        </label>
        <div className={styles.formGridFull}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#475569', marginBottom: '0.5rem' }}>
            {t('esg:metricModal.fields.description.label')}
          </label>
          <textarea
            className={styles.textarea}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t('esg:labels.optional')}
          />
        </div>

        <div className={styles.formGridFull}>
          <div className={styles.standardsHeaderRow}>
            <div>
              <div className={styles.standardsTitle}>{t('esg:metricModal.standards.title')}</div>
              <div className={styles.standardsHint}>{t('esg:metricModal.standards.hint')}</div>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => applyMappingsToSchemaJson([...standardMappings, { standard: 'GRI', disclosure_id: '', required: true }])}
            >
              {t('esg:metricModal.standards.add')}
            </Button>
          </div>

          {standardMappings.length === 0 ? (
            <div className={styles.standardsEmpty}>{t('esg:metricModal.standards.empty')}</div>
          ) : (
            <div className={styles.standardsTableWrap}>
              <table className={styles.standardsTable}>
                <thead>
                  <tr>
                    <th style={{ width: '22%' }}>{t('esg:metricModal.standards.headers.standard')}</th>
                    <th>{t('esg:metricModal.standards.headers.disclosureId')}</th>
                    <th style={{ width: '14%' }}>{t('esg:metricModal.standards.headers.required')}</th>
                    <th style={{ width: '10%' }} />
                  </tr>
                </thead>
                <tbody>
                  {standardMappings.map((m, idx) => (
                    <tr key={`${idx}-${m.standard}-${m.disclosure_id}`}>
                      <td>
                        <select
                          className={styles.standardsSelect}
                          value={m.standard}
                          onChange={(e) => {
                            const next = [...standardMappings]
                            next[idx] = { ...next[idx], standard: e.target.value }
                            applyMappingsToSchemaJson(next)
                          }}
                        >
                          {STANDARD_MAPPING_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <input
                          className={styles.standardsInput}
                          value={m.disclosure_id}
                          onChange={(e) => {
                            const next = [...standardMappings]
                            next[idx] = { ...next[idx], disclosure_id: e.target.value }
                            applyMappingsToSchemaJson(next)
                          }}
                          placeholder={t('esg:metricModal.standards.disclosurePlaceholder')}
                        />
                      </td>
                      <td>
                        <label className={styles.standardsRequiredLabel}>
                          <input
                            type="checkbox"
                            checked={Boolean(m.required)}
                            onChange={(e) => {
                              const next = [...standardMappings]
                              next[idx] = { ...next[idx], required: e.target.checked }
                              applyMappingsToSchemaJson(next)
                            }}
                          />
                          <span>{t('esg:metricModal.standards.requiredYes')}</span>
                        </label>
                      </td>
                      <td>
                        <button
                          type="button"
                          className={styles.standardsRemoveBtn}
                          onClick={() => {
                            const next = standardMappings.filter((_x, i) => i !== idx)
                            applyMappingsToSchemaJson(next)
                          }}
                          aria-label={t('esg:metricModal.standards.removeAria')}
                        >
                          {t('esg:metricModal.standards.remove')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className={styles.formGridFull}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#475569', marginBottom: '0.5rem' }}>
            {t('esg:metricModal.schema.label')}
          </label>
          <textarea
            className={styles.textarea}
            value={schemaJson}
            onChange={(e) => {
              const next = e.target.value
              setSchemaJson(next)
              const parsed = parseSchemaObject(next)
              if (parsed === null) return
              setStandardMappings(extractMappings(parsed))
              setPillar(extractPillar(parsed))
              setSchemaError(null)
            }}
            placeholder={t('esg:metricModal.schema.placeholder')}
          />
          {schemaError && <div style={{ color: '#dc2626', fontSize: '0.8125rem', marginTop: '0.35rem' }}>{schemaError}</div>}
        </div>
      </div>
      <div className={styles.modalActions}>
        <Button variant="secondary" onClick={props.onClose}>
          {t('common:actions.cancel')}
        </Button>
        <Button onClick={submit}>
          {props.submitLabel}
        </Button>
      </div>
    </Modal>
  )
}

function MetricPreviewModal(props: { metric: EsgMetric | null; onClose: () => void }) {
  const { t } = useTranslation(['esg', 'common'])
  const metric = props.metric
  const [activeTab, setActiveTab] = useState<'details' | 'example'>('details')

  useEffect(() => {
    if (!metric) return
    setActiveTab('details')
  }, [metric])

  if (!metric) return null

  const nowYear = new Date().getUTCFullYear()
  const examplePeriodStart = `${nowYear - 1}-01-01`
  const examplePeriodEnd = `${nowYear - 1}-12-31`

  const exampleValue =
    metric.value_type === 'boolean'
      ? true
      : metric.value_type === 'integer'
        ? 123
        : metric.value_type === 'number'
          ? 123.45
          : metric.value_type === 'string'
            ? 'Example text value'
            : null

  const exampleFactPayload = {
    metric_id: metric.metric_id,
    period_type: 'year',
    period_start: examplePeriodStart,
    period_end: examplePeriodEnd,
    is_ytd: false,
    entity_id: null,
    location_id: null,
    segment_id: null,
    consolidation_approach: null,
    ghg_scope: null,
    scope2_method: null,
    scope3_category: null,
    tags: null,
    value_json: metric.value_type === 'dataset' ? null : exampleValue,
    dataset_id: metric.value_type === 'dataset' ? '00000000-0000-0000-0000-000000000000' : null,
    quality_json: { confidence: 'medium', methodology: 'Describe your method', qa: 'Reviewed by responsible owner' },
    sources_json: {
      source_type: 'internal',
      system: 'System of record',
      notes: 'Evidence references go to ESG fact evidence items',
    },
  }

  const prettySchema = JSON.stringify(metric.value_schema_json ?? {}, null, 2)
  const prettyExample = JSON.stringify(exampleFactPayload, null, 2)

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success(t('esg:metricsPage.toast.copied'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:metricsPage.toast.copyFailed'))
    }
  }

  return (
    <Modal isOpen={Boolean(metric)} onClose={props.onClose} title={t('esg:metricPreview.title')} size="lg">
      <div className={styles.previewHeader}>
        <div>
          <div className={styles.previewTitleRow}>
            <div className={styles.previewTitle}>{metric.name}</div>
            <span className={styles.badge}>{metric.value_type}</span>
            {metric.unit && <span className={styles.previewUnit}>{metric.unit}</span>}
          </div>
          <div className={styles.previewMeta}>
            <span className={styles.previewMetaItem}>
              {t('esg:metricPreview.codeLabel')}: <span className={styles.mono}>{metric.code || '—'}</span>
            </span>
            <span className={styles.previewMetaItem}>
              {t('esg:metricPreview.statusLabel')}: <strong>{metric.is_active ? t('common:status.active') : t('common:status.inactive')}</strong>
            </span>
          </div>
        </div>
        <div className={styles.previewTabs}>
          <button
            type="button"
            className={`${styles.previewTab} ${activeTab === 'details' ? styles.previewTabActive : ''}`}
            onClick={() => setActiveTab('details')}
          >
            {t('esg:metricPreview.tabs.details')}
          </button>
          <button
            type="button"
            className={`${styles.previewTab} ${activeTab === 'example' ? styles.previewTabActive : ''}`}
            onClick={() => setActiveTab('example')}
          >
            {t('esg:metricPreview.tabs.example')}
          </button>
        </div>
      </div>

      {activeTab === 'details' ? (
        <div className={styles.previewSection}>
          {metric.description && (
            <div className={styles.previewBlock}>
              <div className={styles.previewBlockTitle}>{t('esg:metricPreview.descriptionTitle')}</div>
              <div className={styles.previewBlockBody}>{metric.description}</div>
            </div>
          )}

          <div className={styles.previewBlock}>
            <div className={styles.previewBlockTitle}>{t('esg:metricPreview.schemaTitle')}</div>
            <pre className={styles.codeBlock}>{prettySchema}</pre>
            <div className={styles.previewBlockActions}>
              <Button variant="secondary" size="sm" onClick={() => copyToClipboard(prettySchema)}>
                {t('esg:metricPreview.copySchema')}
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <div className={styles.previewSection}>
          <div className={styles.previewBlock}>
            <div className={styles.previewBlockTitle}>{t('esg:metricPreview.exampleTitle')}</div>
            <div className={styles.previewHint}>{t('esg:metricPreview.exampleHint')}</div>
            <pre className={styles.codeBlock}>{prettyExample}</pre>
            <div className={styles.previewBlockActions}>
              <Button variant="secondary" size="sm" onClick={() => copyToClipboard(prettyExample)}>
                {t('esg:metricPreview.copyJson')}
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className={styles.modalActions}>
        <Button variant="secondary" onClick={props.onClose}>
          {t('common:actions.close')}
        </Button>
      </div>
    </Modal>
  )
}
