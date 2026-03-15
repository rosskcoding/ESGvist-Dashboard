import { useMemo, useState } from 'react'
import { apiClient } from '@/api/client'
import { getDatasetRevision } from '@/api/datasets'
import { Button, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import { useAuthStore } from '@/stores/authStore'
import type { BlockType, EsgFact, EsgMetric, EsgMetricValueType } from '@/types/api'
import { useCompareEsgFacts, useEsgEntities, useEsgFacts, useEsgMetrics } from '@/api/hooks'
import { getEsgSourceMetaFromDataJson, QA_FLAG_DATA_PENDING, withoutDataPending } from '@/utils/esgReportIntegration'
import styles from './EsgSourcePanel.module.css'

type RequiredFactKind = 'scalar' | 'dataset'

function shortId(id: string) {
  return id.length > 10 ? `${id.slice(0, 8)}…` : id
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

function inferValueTypeFromFact(fact: EsgFact): EsgMetricValueType {
  if (fact.dataset_id) return 'dataset'
  const v = fact.value_json
  if (typeof v === 'boolean') return 'boolean'
  if (typeof v === 'number') return 'number'
  if (typeof v === 'string') return 'string'
  return 'string'
}

function buildEsgSourceMeta(fact: EsgFact, valueType: EsgMetricValueType | null | undefined) {
  const resolvedValueType = valueType ?? inferValueTypeFromFact(fact)
  const base: Record<string, unknown> = {
    logical_key_hash: fact.logical_key_hash,
    fact_id: fact.fact_id,
    version_number: fact.version_number,
    status_at_capture: fact.status,
    captured_at_utc: new Date().toISOString(),
    value_type: resolvedValueType,
  }

  if (fact.dataset_id) {
    base.dataset_id = fact.dataset_id
    base.dataset_revision_id = fact.dataset_revision_id
  }

  return base
}

async function importDatasetToTable(
  dataJson: Record<string, unknown>,
  fact: EsgFact,
  valueType: EsgMetricValueType | null | undefined
) {
  if (!fact.dataset_revision_id) {
    throw new Error('Dataset fact must be published (dataset_revision_id is missing)')
  }

  const revision = await getDatasetRevision(fact.dataset_revision_id)
  const dsCols = revision.schema_json?.columns ?? []
  const dsRows = revision.rows_json ?? []

  const columns = dsCols.map((c, idx) => ({
    key: c.key || `col_${idx}`,
    header: c.key || `Column ${idx + 1}`,
    type: c.type || 'text',
    width: 150,
    format: c.format ?? undefined,
  }))

  const rows = dsRows.map((row) => {
    const out: Record<string, string | number | null> = {}
    for (let i = 0; i < columns.length; i += 1) {
      const key = columns[i].key as string
      const value = Array.isArray(row) ? (row[i] ?? null) : null
      out[key] = (value as string | number | null) ?? null
    }
    return out
  })

  return {
    ...dataJson,
    columns,
    rows,
    esg_source: buildEsgSourceMeta(fact, valueType),
  }
}

async function importDatasetToChart(
  dataJson: Record<string, unknown>,
  fact: EsgFact,
  valueType: EsgMetricValueType | null | undefined
) {
  if (!fact.dataset_revision_id) {
    throw new Error('Dataset fact must be published (dataset_revision_id is missing)')
  }

  const revision = await getDatasetRevision(fact.dataset_revision_id)
  const dsCols = revision.schema_json?.columns ?? []
  const dsRows = revision.rows_json ?? []

  const columns = dsCols.map((c) => c.key)
  const rows = dsRows

  return {
    ...dataJson,
    data_source: {
      type: 'inline',
      inline_data: { columns, rows },
    },
    esg_source: buildEsgSourceMeta(fact, valueType),
  }
}

function importScalarToKpi(
  dataJson: Record<string, unknown>,
  fact: EsgFact,
  valueType: EsgMetricValueType | null | undefined
) {
  if (fact.dataset_id) {
    throw new Error('KPI blocks require scalar facts (dataset_id must be null)')
  }
  if (fact.value_json === null || typeof fact.value_json === 'undefined') {
    throw new Error('Scalar fact has no value_json')
  }

  const raw = fact.value_json
  const value: string | number =
    typeof raw === 'number' || typeof raw === 'string'
      ? raw
      : typeof raw === 'boolean'
        ? raw
          ? 'true'
          : 'false'
        : JSON.stringify(raw)

  const currentItemsRaw = (dataJson as Record<string, unknown>).items
  const currentItems: Array<Record<string, unknown>> = Array.isArray(currentItemsRaw)
    ? (currentItemsRaw as Array<Record<string, unknown>>)
    : []
  const nextItems = currentItems.length
    ? [...currentItems]
    : [{ item_id: `kpi-${Date.now()}`, value: 0, unit: '', period: '' }]

  nextItems[0] = { ...nextItems[0], value }

  return {
    ...dataJson,
    items: nextItems,
    esg_source: buildEsgSourceMeta(fact, valueType),
  }
}

export function EsgSourcePanel(props: {
  blockType: BlockType
  companyId: string
  dataJson: Record<string, unknown>
  onDataJsonChange: (next: Record<string, unknown>) => void
  qaFlagsGlobal: string[]
  onQaFlagsGlobalChange: (next: string[]) => void
}) {
  const user = useAuthStore((s) => s.user)
  const sourceMeta = useMemo(() => getEsgSourceMetaFromDataJson(props.dataJson), [props.dataJson])
  const isPending = props.qaFlagsGlobal.includes(QA_FLAG_DATA_PENDING)

  const canManageLink = useMemo(() => {
    if (!user) return true // fail-open (backend enforces)
    if (user.isSuperuser) return true
    if (!props.companyId) return true // fail-open (legacy)
    const membership = user.memberships.find((m) => m.isActive && m.companyId === props.companyId)
    if (!membership) return true // fail-open (legacy)
    return membership.isCorporateLead
  }, [props.companyId, user])

  const requiredKind: RequiredFactKind = props.blockType === 'kpi_cards' ? 'scalar' : 'dataset'

  const [pickerOpen, setPickerOpen] = useState(false)
  const [isApplying, setIsApplying] = useState(false)

  const compareFacts = useCompareEsgFacts()

  const applyFact = async (fact: EsgFact, valueType: EsgMetricValueType | null | undefined) => {
    setIsApplying(true)
    try {
      let nextDataJson: Record<string, unknown>

      if (props.blockType === 'table') {
        nextDataJson = await importDatasetToTable(props.dataJson, fact, valueType)
      } else if (props.blockType === 'chart') {
        nextDataJson = await importDatasetToChart(props.dataJson, fact, valueType)
      } else if (props.blockType === 'kpi_cards') {
        nextDataJson = importScalarToKpi(props.dataJson, fact, valueType)
      } else {
        throw new Error('Unsupported block type for ESG source')
      }

      props.onDataJsonChange(nextDataJson)
      props.onQaFlagsGlobalChange(withoutDataPending(props.qaFlagsGlobal))
      toast.success('Imported from ESG Dashboard (pending save)')
    } catch (e) {
      toast.error((e as Error).message || 'Failed to import ESG fact')
    } finally {
      setIsApplying(false)
    }
  }

  const handleUpdateToLatest = async () => {
    if (!sourceMeta) return

    setIsApplying(true)
    try {
      const items = await compareFacts.mutateAsync({
        data: { logical_key_hashes: [sourceMeta.logical_key_hash] },
        companyId: props.companyId,
      })
      const latest = items[0]?.latest
      if (!latest) {
        toast.error('No latest fact found for this logical key')
        return
      }
      if (latest.fact_id === sourceMeta.fact_id) {
        props.onQaFlagsGlobalChange(withoutDataPending(props.qaFlagsGlobal))
        toast.success('Already up to date')
        return
      }

      const { data: fact } = await apiClient.get<EsgFact>(`/api/v1/esg/facts/${latest.fact_id}`)
      await applyFact(fact, sourceMeta.value_type)
    } catch (e) {
      toast.error((e as Error).message || 'Failed to update from ESG')
    } finally {
      setIsApplying(false)
    }
  }

  const handleUnlink = () => {
    const next = { ...props.dataJson }
    delete (next as Record<string, unknown>).esg_source
    props.onDataJsonChange(next)
    props.onQaFlagsGlobalChange(withoutDataPending(props.qaFlagsGlobal))
    toast.success('ESG source unlinked (pending save)')
  }

  const subtitle =
    props.blockType === 'table'
      ? 'Link this block to a published ESG dataset fact. Import copies the dataset snapshot into the table.'
      : props.blockType === 'chart'
        ? 'Link this block to a published ESG dataset fact. Import copies the dataset snapshot into inline chart data.'
        : 'Link this block to a published ESG scalar fact. Import updates the first KPI item value.'

  return (
    <div className={styles.panel}>
      <div className={styles.headerRow}>
        <div>
          <p className={styles.title}>ESG Source</p>
          <p className={styles.subtitle}>{subtitle}</p>
        </div>
        <div className={styles.actions}>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setPickerOpen(true)}
            disabled={isApplying || !canManageLink}
          >
            {sourceMeta ? 'Change' : 'Link fact'}
          </Button>
          {sourceMeta && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleUnlink}
              disabled={isApplying || !canManageLink}
            >
              Unlink
            </Button>
          )}
          {sourceMeta && isPending && (
            <Button size="sm" onClick={() => void handleUpdateToLatest()} disabled={isApplying || compareFacts.isPending}>
              Update from ESG
            </Button>
          )}
        </div>
      </div>

      {!canManageLink && (
        <div className={styles.accessNote}>
          {sourceMeta
            ? 'This block is linked to ESG. Data is read-only while linked. Only Corporate Lead can unlink or change the ESG source.'
            : 'Only Corporate Lead can link this block to an ESG fact.'}
        </div>
      )}

      {sourceMeta ? (
        <div className={styles.metaRow}>
          <span>
            Fact: <span className={styles.mono}>{shortId(sourceMeta.fact_id)}</span>
          </span>
          <span>
            Version: <span className={styles.mono}>{sourceMeta.version_number}</span>
          </span>
          <span>
            Key: <span className={styles.mono}>{shortId(sourceMeta.logical_key_hash)}</span>
          </span>
          {isPending && <span className={styles.badge}>{QA_FLAG_DATA_PENDING}</span>}
        </div>
      ) : (
        <div className={styles.metaRow}>
          <span>No ESG fact linked.</span>
        </div>
      )}

      {sourceMeta && isPending && (
        <div className={styles.warning}>
          ESG Dashboard data has changed for this logical key. Click "Update from ESG" to import the latest published
          fact snapshot into this block.
        </div>
      )}

      <EsgFactPickerModal
        isOpen={pickerOpen}
        onClose={() => setPickerOpen(false)}
        companyId={props.companyId}
        requiredKind={requiredKind}
        onSelect={(fact, valueType) => {
          setPickerOpen(false)
          void applyFact(fact, valueType)
        }}
      />
    </div>
  )
}

function EsgFactPickerModal(props: {
  isOpen: boolean
  onClose: () => void
  companyId: string
  requiredKind: RequiredFactKind
  onSelect: (fact: EsgFact, valueType: EsgMetricValueType | null) => void
}) {
  const [metricId, setMetricId] = useState<string>('')
  const [entityId, setEntityId] = useState<string>('')
  const [periodFrom, setPeriodFrom] = useState<string>('')
  const [periodTo, setPeriodTo] = useState<string>('')

  const metricsQuery = useEsgMetrics({
    includeInactive: false,
    companyId: props.companyId,
    page: 1,
    pageSize: 200,
    enabled: props.isOpen,
  })
  const entitiesQuery = useEsgEntities({
    includeInactive: false,
    companyId: props.companyId,
    page: 1,
    pageSize: 200,
    enabled: props.isOpen,
  })

  const factsQuery = useEsgFacts({
    metric_id: metricId || undefined,
    entity_id: entityId || undefined,
    period_from: periodFrom || undefined,
    period_to: periodTo || undefined,
    status: 'published',
    latest_only: true,
    companyId: props.companyId,
    page: 1,
    pageSize: 50,
    enabled: props.isOpen,
  })

  const metrics = useMemo(() => metricsQuery.data?.items ?? [], [metricsQuery.data?.items])
  const entities = useMemo(() => entitiesQuery.data?.items ?? [], [entitiesQuery.data?.items])
  const facts = useMemo(() => factsQuery.data?.items ?? [], [factsQuery.data?.items])

  const metricsById = useMemo(() => {
    const m = new Map<string, EsgMetric>()
    metrics.forEach((x) => m.set(x.metric_id, x))
    return m
  }, [metrics])

  const metricOptions = useMemo(() => {
    const opts = [{ value: '', label: 'All metrics' }]
    opts.push(
      ...metrics.map((m) => ({ value: m.metric_id, label: `${m.name}${m.code ? ` (${m.code})` : ''}` }))
    )
    return opts
  }, [metrics])

  const entityOptions = useMemo(() => {
    const opts = [{ value: '', label: 'All entities' }]
    opts.push(...entities.map((e) => ({ value: e.entity_id, label: e.name })))
    return opts
  }, [entities])

  const isCompatible = (fact: EsgFact): boolean => {
    if (props.requiredKind === 'dataset') {
      return Boolean(fact.dataset_id) && Boolean(fact.dataset_revision_id)
    }
    return !fact.dataset_id && fact.value_json !== null && typeof fact.value_json !== 'undefined'
  }

  const compatibilityHint = props.requiredKind === 'dataset' ? 'Dataset (published snapshot)' : 'Scalar value'

  return (
    <Modal isOpen={props.isOpen} onClose={props.onClose} title="Select ESG fact" size="xl">
      <div className={styles.pickerToolbar}>
        <Select label="Metric" value={metricId} onChange={(e) => setMetricId(e.target.value)} options={metricOptions} />
        <Select label="Entity" value={entityId} onChange={(e) => setEntityId(e.target.value)} options={entityOptions} />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          <Input label="From" type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
          <Input label="To" type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
        </div>
      </div>

      <div style={{ color: '#475569', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
        Required: <strong>{compatibilityHint}</strong>
      </div>

      <div className={styles.pickerTableWrap}>
        <table className={styles.pickerTable}>
          <thead>
            <tr>
              <th>Metric</th>
              <th style={{ width: '22%' }}>Period</th>
              <th style={{ width: '12%' }}>Status</th>
              <th style={{ width: '10%' }}>Version</th>
              <th>Value</th>
              <th style={{ width: '14%' }} />
            </tr>
          </thead>
          <tbody>
            {factsQuery.isLoading && (
              <tr>
                <td colSpan={6} className={styles.pickerEmpty}>
                  Loading...
                </td>
              </tr>
            )}

            {!factsQuery.isLoading && facts.length === 0 && (
              <tr>
                <td colSpan={6} className={styles.pickerEmpty}>
                  No facts found.
                </td>
              </tr>
            )}

            {facts.map((f) => {
              const metric = metricsById.get(f.metric_id)
              const metricLabel = metric ? metric.name : shortId(f.metric_id)
              const period = `${f.period_start} → ${f.period_end}${f.is_ytd ? ' (YTD)' : ''}`
              const compatible = isCompatible(f)
              const valueType: EsgMetricValueType | null = metric?.value_type ?? null
              return (
                <tr key={f.fact_id}>
                  <td>{metricLabel}</td>
                  <td className={styles.mono}>{period}</td>
                  <td>{statusBadge(f.status)}</td>
                  <td className={styles.mono}>{f.version_number}</td>
                  <td className={styles.mono}>{renderValue(f)}</td>
                  <td>
                    <Button size="sm" disabled={!compatible} onClick={() => props.onSelect(f, valueType)}>
                      Select
                    </Button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end' }}>
        <Button variant="secondary" onClick={props.onClose}>
          Close
        </Button>
      </div>
    </Modal>
  )
}
