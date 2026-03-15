import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { EsgShell } from '@/components/esg/EsgShell'
import { Button, ConfirmDialog, Input, Modal, Select } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import {
  useCreateEsgFact,
  useCreateEsgFactEvidence,
  useDeleteEsgFactEvidence,
  useEsgEntities,
  useEsgFactEvidence,
  useEsgLocations,
  useEsgMetrics,
  useEsgSegments,
  useUploadAsset,
  getAssetSignedUrl,
} from '@/api/hooks'
import type { EsgFact, EsgFactCreate, EsgFactEvidenceItem, EsgFactEvidenceType, EsgMetric, EsgMetricValueType } from '@/types/api'
import { DatasetImportModal } from '@/components/datasets/DatasetImportModal'
import { DatasetPicker } from '@/components/datasets/DatasetPicker'
import {
  collectEsgFactQualityGateIssues,
  getEsgEvidenceMinItems,
  getEsgRangeSpec,
  getEsgRequiredSourceFields,
} from '@/utils/esgFactSchema'
import styles from './EsgFactCreatePage.module.css'

function parseTags(input: string): string[] {
  return input
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
}

export function EsgFactCreatePage() {
  const { t } = useTranslation(['esg', 'common'])
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const initialMetricId = searchParams.get('metric_id') ?? ''
  const initialIsYtd = searchParams.get('is_ytd') === 'true'
  const initialEntityId = searchParams.get('entity_id') ?? ''
  const initialLocationId = searchParams.get('location_id') ?? ''
  const initialSegmentId = searchParams.get('segment_id') ?? ''

  const resolvedInitialPeriod = (() => {
    const rawType = (searchParams.get('period_type') ?? 'year').trim().toLowerCase()
    const periodType = ['day', 'month', 'quarter', 'year', 'custom'].includes(rawType) ? rawType : 'year'

    const explicitStart = searchParams.get('period_start') ?? ''
    const explicitEnd = searchParams.get('period_end') ?? ''
    if (explicitStart && explicitEnd) {
      return { periodType, periodStart: explicitStart, periodEnd: explicitEnd }
    }

    const rawYear = (searchParams.get('year') ?? '').trim()
    if (/^[0-9]{4}$/.test(rawYear)) {
      return { periodType: 'year', periodStart: `${rawYear}-01-01`, periodEnd: `${rawYear}-12-31` }
    }

    return { periodType: 'year', periodStart: '', periodEnd: '' }
  })()

  const [metricId, setMetricId] = useState<string>(initialMetricId)
  const [periodType, setPeriodType] = useState<string>(resolvedInitialPeriod.periodType)
  const [periodStart, setPeriodStart] = useState<string>(resolvedInitialPeriod.periodStart)
  const [periodEnd, setPeriodEnd] = useState<string>(resolvedInitialPeriod.periodEnd)
  const [isYtd, setIsYtd] = useState<boolean>(initialIsYtd)

  const [entityId, setEntityId] = useState<string>(initialEntityId)
  const [locationId, setLocationId] = useState<string>(initialLocationId)
  const [segmentId, setSegmentId] = useState<string>(initialSegmentId)
  const [consolidationApproach, setConsolidationApproach] = useState<string>('')
  const [ghgScope, setGhgScope] = useState<string>('')
  const [scope2Method, setScope2Method] = useState<string>('')
  const [scope3Category, setScope3Category] = useState<string>('')
  const [tags, setTags] = useState<string>('')

  const [scalarValue, setScalarValue] = useState<string>('')
  const [boolValue, setBoolValue] = useState<string>('true')
  const [datasetId, setDatasetId] = useState<string | null>(null)
  const [isImportOpen, setIsImportOpen] = useState(false)

  const [showAdvancedJson, setShowAdvancedJson] = useState(false)

  const [qualityObj, setQualityObj] = useState<Record<string, unknown>>({})
  const [qualityJsonText, setQualityJsonText] = useState<string>('{}')
  const [qualityJsonError, setQualityJsonError] = useState<string | null>(null)

  const [sourcesObj, setSourcesObj] = useState<Record<string, unknown>>({})
  const [sourcesJsonText, setSourcesJsonText] = useState<string>('{}')
  const [sourcesJsonError, setSourcesJsonError] = useState<string | null>(null)

  const [createdFact, setCreatedFact] = useState<EsgFact | null>(null)

  const [newEvidenceType, setNewEvidenceType] = useState<EsgFactEvidenceType>('file')
  const [newEvidenceTitle, setNewEvidenceTitle] = useState<string>('')
  const [newEvidenceDescription, setNewEvidenceDescription] = useState<string>('')
  const [newEvidenceUrl, setNewEvidenceUrl] = useState<string>('')
  const [newEvidenceNote, setNewEvidenceNote] = useState<string>('')
  const [newEvidenceFile, setNewEvidenceFile] = useState<File | null>(null)
  const [deleteEvidenceId, setDeleteEvidenceId] = useState<string | null>(null)
  const [notePreview, setNotePreview] = useState<EsgFactEvidenceItem | null>(null)

  const periodTypeOptions = useMemo(
    () => [
      { value: 'day', label: t('esg:factCreatePage.period.types.day') },
      { value: 'month', label: t('esg:factCreatePage.period.types.month') },
      { value: 'quarter', label: t('esg:factCreatePage.period.types.quarter') },
      { value: 'year', label: t('esg:factCreatePage.period.types.year') },
      { value: 'custom', label: t('esg:factCreatePage.period.types.custom') },
    ],
    [t]
  )

  const booleanValueOptions = useMemo(
    () => [
      { value: 'true', label: t('esg:factCreatePage.value.boolean.true') },
      { value: 'false', label: t('esg:factCreatePage.value.boolean.false') },
    ],
    [t]
  )

  const evidenceTypeOptions = useMemo(
    () => [
      { value: 'file', label: t('esg:factCreatePage.evidence.types.file') },
      { value: 'link', label: t('esg:factCreatePage.evidence.types.link') },
      { value: 'note', label: t('esg:factCreatePage.evidence.types.note') },
    ],
    [t]
  )

  const metricsQuery = useEsgMetrics({ includeInactive: false, page: 1, pageSize: 200 })
  const entitiesQuery = useEsgEntities({ includeInactive: false, page: 1, pageSize: 200 })
  const locationsQuery = useEsgLocations({ includeInactive: false, page: 1, pageSize: 200 })
  const segmentsQuery = useEsgSegments({ includeInactive: false, page: 1, pageSize: 200 })

  const metrics = useMemo(() => metricsQuery.data?.items ?? [], [metricsQuery.data?.items])
  const entities = useMemo(() => entitiesQuery.data?.items ?? [], [entitiesQuery.data?.items])
  const locations = useMemo(() => locationsQuery.data?.items ?? [], [locationsQuery.data?.items])
  const segments = useMemo(() => segmentsQuery.data?.items ?? [], [segmentsQuery.data?.items])

  const selectedMetric: EsgMetric | undefined = useMemo(
    () => metrics.find((m) => m.metric_id === metricId),
    [metrics, metricId]
  )

  // Reset JSON blobs when switching metrics to avoid carrying incompatible schema fields.
  useEffect(() => {
    setSourcesFromObj({})
    setQualityFromObj({})
  }, [selectedMetric?.metric_id])

  const requiredSourceFields = useMemo(
    () => getEsgRequiredSourceFields(selectedMetric?.value_schema_json),
    [selectedMetric?.value_schema_json]
  )

  const evidenceMinItems = useMemo(
    () => getEsgEvidenceMinItems(selectedMetric?.value_schema_json),
    [selectedMetric?.value_schema_json]
  )

  const rangeSpec = useMemo(
    () => getEsgRangeSpec(selectedMetric?.value_schema_json),
    [selectedMetric?.value_schema_json]
  )

  const metricOptions = useMemo(() => {
    const opts = [{ value: '', label: t('esg:factCreatePage.metric.selectPlaceholder') }]
    opts.push(
      ...metrics.map((m) => ({
        value: m.metric_id,
        label: `${m.name}${m.unit ? ` (${m.unit})` : ''}`,
      }))
    )
    return opts
  }, [metrics, t])

  const entityOptions = useMemo(() => {
    const opts = [{ value: '', label: t('esg:factCreatePage.select.none') }]
    opts.push(...entities.map((e) => ({ value: e.entity_id, label: e.name })))
    return opts
  }, [entities, t])

  const locationOptions = useMemo(() => {
    const opts = [{ value: '', label: t('esg:factCreatePage.select.none') }]
    opts.push(...locations.map((l) => ({ value: l.location_id, label: l.name })))
    return opts
  }, [locations, t])

  const segmentOptions = useMemo(() => {
    const opts = [{ value: '', label: t('esg:factCreatePage.select.none') }]
    opts.push(...segments.map((s) => ({ value: s.segment_id, label: s.name })))
    return opts
  }, [segments, t])

  const createFact = useCreateEsgFact()

  const evidenceList = useEsgFactEvidence(createdFact?.fact_id || '')
  const createEvidence = useCreateEsgFactEvidence()
  const deleteEvidence = useDeleteEsgFactEvidence()
  const uploadAsset = useUploadAsset()

  const setSourcesFromObj = (next: Record<string, unknown>) => {
    setSourcesObj(next)
    setSourcesJsonText(JSON.stringify(next ?? {}, null, 2))
    setSourcesJsonError(null)
  }

  const setQualityFromObj = (next: Record<string, unknown>) => {
    setQualityObj(next)
    setQualityJsonText(JSON.stringify(next ?? {}, null, 2))
    setQualityJsonError(null)
  }

  const handleSourcesJsonTextChange = (text: string) => {
    setSourcesJsonText(text)
    try {
      const parsed = text.trim() ? (JSON.parse(text) as unknown) : {}
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error(t('esg:factCreatePage.advanced.sourcesJsonMustBeObject'))
      }
      setSourcesObj(parsed as Record<string, unknown>)
      setSourcesJsonError(null)
    } catch (e) {
      setSourcesJsonError((e as Error).message || t('esg:factCreatePage.advanced.sourcesJsonInvalid'))
    }
  }

  const handleQualityJsonTextChange = (text: string) => {
    setQualityJsonText(text)
    try {
      const parsed = text.trim() ? (JSON.parse(text) as unknown) : {}
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error(t('esg:factCreatePage.advanced.qualityJsonMustBeObject'))
      }
      setQualityObj(parsed as Record<string, unknown>)
      setQualityJsonError(null)
    } catch (e) {
      setQualityJsonError((e as Error).message || t('esg:factCreatePage.advanced.qualityJsonInvalid'))
    }
  }

  const updateSourceField = (key: string, value: string) => {
    setSourcesObj((prev) => {
      const next = { ...(prev ?? {}), [key]: value }
      setSourcesJsonText(JSON.stringify(next, null, 2))
      setSourcesJsonError(null)
      return next
    })
  }

  const validateAndBuildPayload = (): EsgFactCreate | null => {
    if (!selectedMetric) {
      toast.error(t('esg:factCreatePage.validation.metricRequired'))
      return null
    }
    if (!periodStart || !periodEnd) {
      toast.error(t('esg:factCreatePage.validation.periodRequired'))
      return null
    }

    if (qualityJsonError) {
      toast.error(qualityJsonError)
      return null
    }
    if (sourcesJsonError) {
      toast.error(sourcesJsonError)
      return null
    }
    const quality = qualityObj
    const sources = sourcesObj

    const valueType: EsgMetricValueType = selectedMetric.value_type
    const isDataset = valueType === 'dataset'

    let valueJson: unknown | null = null
    let dsId: string | null = null

    if (isDataset) {
      if (!datasetId) {
        toast.error(t('esg:factCreatePage.validation.datasetRequiredForDatasetMetric'))
        return null
      }
      dsId = datasetId
    } else if (valueType === 'boolean') {
      valueJson = boolValue === 'true'
    } else if (valueType === 'integer') {
      const parsed = Number(scalarValue)
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        toast.error(t('esg:factCreatePage.validation.expectedInteger'))
        return null
      }
      valueJson = parsed
    } else if (valueType === 'number') {
      const parsed = Number(scalarValue)
      if (!Number.isFinite(parsed)) {
        toast.error(t('esg:factCreatePage.validation.expectedNumber'))
        return null
      }
      valueJson = parsed
    } else {
      if (!scalarValue.trim()) {
        toast.error(t('esg:factCreatePage.validation.valueRequired'))
        return null
      }
      valueJson = scalarValue
    }

    return {
      metric_id: selectedMetric.metric_id,
      period_type: periodType as EsgFactCreate['period_type'],
      period_start: periodStart,
      period_end: periodEnd,
      is_ytd: isYtd,
      entity_id: entityId || null,
      location_id: locationId || null,
      segment_id: segmentId || null,
      consolidation_approach: consolidationApproach.trim() || null,
      ghg_scope: ghgScope.trim() || null,
      scope2_method: scope2Method.trim() || null,
      scope3_category: scope3Category.trim() || null,
      tags: tags.trim() ? parseTags(tags) : null,
      value_json: isDataset ? null : valueJson,
      dataset_id: isDataset ? dsId : null,
      quality_json: quality,
      sources_json: sources,
    }
  }

  const handleCreate = async () => {
    const payload = validateAndBuildPayload()
    if (!payload) return

    try {
      const fact = await createFact.mutateAsync(payload)
      toast.success(t('esg:factCreatePage.toast.createdDraft'))
      setCreatedFact(fact)
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.createFailed'))
    }
  }

  const handleUploadEvidence = async (file: File, opts?: { title?: string; description?: string }) => {
    if (!createdFact) return

    try {
      const uploaded = await uploadAsset.mutateAsync({ file, kind: 'attachment' })
      await createEvidence.mutateAsync({
        factId: createdFact.fact_id,
        data: {
          type: 'file',
          title: opts?.title?.trim() || file.name,
          description: opts?.description?.trim() || null,
          asset_id: uploaded.asset.asset_id,
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceUploaded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceUploadFailed'))
    }
  }

  const handleDeleteEvidence = async (evidenceId: string) => {
    if (!createdFact) return
    try {
      await deleteEvidence.mutateAsync({ factId: createdFact.fact_id, evidenceId })
      toast.success(t('esg:factCreatePage.toast.evidenceDeleted'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceDeleteFailed'))
    }
  }

  const handleCreateLinkEvidence = async (payload: { title: string; url: string; description?: string }) => {
    if (!createdFact) return

    let parsedUrl: URL
    try {
      parsedUrl = new URL(payload.url)
    } catch {
      toast.error(t('esg:factCreatePage.validation.invalidUrl'))
      return
    }
    if (parsedUrl.protocol !== 'https:' && parsedUrl.protocol !== 'http:') {
      toast.error(t('esg:factCreatePage.validation.urlMustBeHttp'))
      return
    }

    try {
      await createEvidence.mutateAsync({
        factId: createdFact.fact_id,
        data: {
          type: 'link',
          title: payload.title,
          description: payload.description?.trim() || null,
          url: parsedUrl.toString(),
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceLinkAdded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceLinkAddFailed'))
    }
  }

  const handleCreateNoteEvidence = async (payload: { title: string; note_md: string; description?: string }) => {
    if (!createdFact) return
    if (!payload.note_md.trim()) {
      toast.error(t('esg:factCreatePage.validation.noteRequired'))
      return
    }

    try {
      await createEvidence.mutateAsync({
        factId: createdFact.fact_id,
        data: {
          type: 'note',
          title: payload.title,
          description: payload.description?.trim() || null,
          note_md: payload.note_md,
        },
      })
      toast.success(t('esg:factCreatePage.toast.evidenceNoteAdded'))
    } catch (e) {
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceNoteAddFailed'))
    }
  }

  const resetEvidenceForm = () => {
    setNewEvidenceTitle('')
    setNewEvidenceDescription('')
    setNewEvidenceUrl('')
    setNewEvidenceNote('')
    setNewEvidenceFile(null)
  }

  const submitNewEvidence = async () => {
    if (!createdFact) return
    if (!newEvidenceTitle.trim()) {
      toast.error(t('esg:factCreatePage.validation.evidenceTitleRequired'))
      return
    }

    if (newEvidenceType === 'file') {
      if (!newEvidenceFile) {
        toast.error(t('esg:factCreatePage.validation.evidenceFileRequired'))
        return
      }
      await handleUploadEvidence(newEvidenceFile, { title: newEvidenceTitle, description: newEvidenceDescription })
      resetEvidenceForm()
      return
    }

    if (newEvidenceType === 'link') {
      if (!newEvidenceUrl.trim()) {
        toast.error(t('esg:factCreatePage.validation.evidenceUrlRequired'))
        return
      }
      await handleCreateLinkEvidence({
        title: newEvidenceTitle.trim(),
        url: newEvidenceUrl.trim(),
        description: newEvidenceDescription,
      })
      resetEvidenceForm()
      return
    }

    await handleCreateNoteEvidence({
      title: newEvidenceTitle.trim(),
      note_md: newEvidenceNote,
      description: newEvidenceDescription,
    })
    resetEvidenceForm()
  }

  const handleDownloadEvidence = async (assetId: string) => {
    // Open a tab synchronously to avoid popup blockers, then redirect once we have the signed URL.
    const w = window.open('about:blank', '_blank', 'noopener,noreferrer')
    try {
      const url = await getAssetSignedUrl(assetId, 300)
      if (w) {
        w.location.href = url
      } else {
        window.location.href = url
      }
    } catch (e) {
      if (w) w.close()
      toast.error((e as Error).message || t('esg:factCreatePage.toast.evidenceDownloadFailed'))
    }
  }

  const evidenceCount = createdFact ? (evidenceList.data ?? []).length : null

  const valuePreview = (() => {
    if (!selectedMetric) {
      return { value_json: null as unknown, dataset_id: null as string | null, error: null as string | null, hint: null as string | null }
    }

    const unitHint = selectedMetric.unit ? t('esg:factCreatePage.value.hints.unit', { unit: selectedMetric.unit }) : null

    if (selectedMetric.value_type === 'dataset') {
      return {
        value_json: null as unknown,
        dataset_id: datasetId,
        error: datasetId ? null : t('esg:factCreatePage.validation.datasetRequired'),
        hint: unitHint,
      }
    }

    if (selectedMetric.value_type === 'boolean') {
      return { value_json: boolValue === 'true', dataset_id: null, error: null, hint: unitHint }
    }

    if (selectedMetric.value_type === 'integer') {
      if (!scalarValue.trim()) return { value_json: null as unknown, dataset_id: null, error: t('esg:factCreatePage.validation.valueRequired'), hint: unitHint }
      const parsed = Number(scalarValue)
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        return { value_json: null as unknown, dataset_id: null, error: t('esg:factCreatePage.validation.expectedInteger'), hint: unitHint }
      }
      const hint =
        rangeSpec && (rangeSpec.min !== undefined || rangeSpec.max !== undefined)
          ? `${unitHint ? `${unitHint} | ` : ''}${t('esg:factCreatePage.value.hints.expectedRange', { min: rangeSpec.min ?? '…', max: rangeSpec.max ?? '…' })}`
          : unitHint
      return { value_json: parsed, dataset_id: null, error: null, hint }
    }

    if (selectedMetric.value_type === 'number') {
      if (!scalarValue.trim()) return { value_json: null as unknown, dataset_id: null, error: t('esg:factCreatePage.validation.valueRequired'), hint: unitHint }
      const parsed = Number(scalarValue)
      if (!Number.isFinite(parsed)) {
        return { value_json: null as unknown, dataset_id: null, error: t('esg:factCreatePage.validation.expectedNumber'), hint: unitHint }
      }
      const hint =
        rangeSpec && (rangeSpec.min !== undefined || rangeSpec.max !== undefined)
          ? `${unitHint ? `${unitHint} | ` : ''}${t('esg:factCreatePage.value.hints.expectedRange', { min: rangeSpec.min ?? '…', max: rangeSpec.max ?? '…' })}`
          : unitHint
      return { value_json: parsed, dataset_id: null, error: null, hint }
    }

    if (!scalarValue.trim()) return { value_json: null as unknown, dataset_id: null, error: t('esg:factCreatePage.validation.valueRequired'), hint: unitHint }
    return { value_json: scalarValue, dataset_id: null, error: null, hint: unitHint }
  })()

  const publishIssues = selectedMetric
    ? collectEsgFactQualityGateIssues({
        schema: selectedMetric.value_schema_json,
        fact: {
          value_json: valuePreview.value_json,
          dataset_id: valuePreview.dataset_id,
          sources_json: sourcesObj,
          evidence_count: evidenceCount,
        },
      })
    : []

  return (
    <EsgShell
      title={t('esg:factCreatePage.title')}
      subtitle={t('esg:factCreatePage.subtitle')}
      actions={
        <Button variant="secondary" onClick={() => navigate('/esg/facts')}>
          {t('esg:factCreatePage.actions.backToFacts')}
        </Button>
      }
    >
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('esg:factCreatePage.sections.metric')}</h2>
        <div className={styles.grid}>
          <div className={styles.gridFull}>
            <Select label={t('esg:factCreatePage.fields.metric')} value={metricId} onChange={(e) => setMetricId(e.target.value)} options={metricOptions} />
          </div>
        </div>
        {selectedMetric && (
          <p className={styles.help}>
            {t('esg:factCreatePage.metric.valueTypeLabel')}: <strong>{selectedMetric.value_type}</strong>
            {selectedMetric.unit ? ` | ${t('esg:factCreatePage.metric.unitLabel')}: ${selectedMetric.unit}` : ''}
          </p>
        )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('esg:factCreatePage.sections.period')}</h2>
        <div className={styles.grid}>
          <Select
            label={t('esg:factCreatePage.fields.periodType')}
            value={periodType}
            onChange={(e) => setPeriodType(e.target.value)}
            options={periodTypeOptions}
          />
          <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', paddingTop: '1.75rem' }}>
            <input type="checkbox" checked={isYtd} onChange={(e) => setIsYtd(e.target.checked)} />
            {t('esg:factCreatePage.fields.isYtd')}
          </label>
          <Input label={t('esg:factCreatePage.fields.startDate')} type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
          <Input label={t('esg:factCreatePage.fields.endDate')} type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('esg:factCreatePage.sections.context')}</h2>
        <div className={styles.grid}>
          <Select label={t('esg:factCreatePage.fields.entity')} value={entityId} onChange={(e) => setEntityId(e.target.value)} options={entityOptions} />
          <Select label={t('esg:factCreatePage.fields.location')} value={locationId} onChange={(e) => setLocationId(e.target.value)} options={locationOptions} />
          <Select label={t('esg:factCreatePage.fields.segment')} value={segmentId} onChange={(e) => setSegmentId(e.target.value)} options={segmentOptions} />
          <Input label={t('esg:factCreatePage.fields.consolidationApproach')} value={consolidationApproach} onChange={(e) => setConsolidationApproach(e.target.value)} />
          <Input label={t('esg:factCreatePage.fields.ghgScope')} value={ghgScope} onChange={(e) => setGhgScope(e.target.value)} placeholder={t('esg:factCreatePage.fields.ghgScopePlaceholder')} />
          <Input label={t('esg:factCreatePage.fields.scope2Method')} value={scope2Method} onChange={(e) => setScope2Method(e.target.value)} />
          <Input label={t('esg:factCreatePage.fields.scope3Category')} value={scope3Category} onChange={(e) => setScope3Category(e.target.value)} />
          <div className={styles.gridFull}>
            <Input label={t('esg:factCreatePage.fields.tags')} value={tags} onChange={(e) => setTags(e.target.value)} placeholder={t('esg:factCreatePage.fields.tagsPlaceholder')} />
          </div>
        </div>
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('esg:factCreatePage.sections.value')}</h2>
        {!selectedMetric && <p className={styles.help}>{t('esg:factCreatePage.value.selectMetricFirst')}</p>}
        {selectedMetric?.value_type === 'dataset' && (
          <>
            <DatasetPicker
              value={datasetId}
              onChange={setDatasetId}
              allowNull={false}
              onCreateNew={() => setIsImportOpen(true)}
            />
            <DatasetImportModal
              isOpen={isImportOpen}
              onClose={() => setIsImportOpen(false)}
              onSuccess={(id) => setDatasetId(id)}
            />
            {valuePreview.error && <p className={styles.fieldError}>{valuePreview.error}</p>}
          </>
        )}
        {selectedMetric?.value_type === 'boolean' && (
          <Select
            label={t('esg:factCreatePage.fields.value')}
            value={boolValue}
            onChange={(e) => setBoolValue(e.target.value)}
            options={booleanValueOptions}
          />
        )}
        {selectedMetric &&
          selectedMetric.value_type !== 'dataset' &&
          selectedMetric.value_type !== 'boolean' && (
            <Input
              label={t('esg:factCreatePage.fields.value')}
              value={scalarValue}
              onChange={(e) => setScalarValue(e.target.value)}
              type={selectedMetric.value_type === 'string' ? 'text' : 'number'}
              placeholder={selectedMetric.value_type === 'string' ? t('esg:factCreatePage.value.placeholders.text') : t('esg:factCreatePage.value.placeholders.number')}
              error={valuePreview.error ?? undefined}
              hint={valuePreview.hint ?? undefined}
            />
          )}
      </div>

      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>{t('esg:factCreatePage.sections.sources')}</h2>
        <p className={styles.help}>
          {t('esg:factCreatePage.sources.helpBefore')} <span className={styles.monoInline}>metric.value_schema_json</span>. {t('esg:factCreatePage.sources.helpAfter')}
        </p>

        {requiredSourceFields.length > 0 ? (
          <>
            <h3 className={styles.subTitle}>{t('esg:factCreatePage.sources.requiredTitle')}</h3>
            <div className={styles.grid}>
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
                    placeholder={t('esg:factCreatePage.sources.placeholder')}
                    error={missing ? t('esg:factCreatePage.sources.requiredForPublish') : undefined}
                  />
                )
              })}
            </div>
          </>
        ) : (
          <p className={styles.help}>{t('esg:factCreatePage.sources.noneConfigured')}</p>
        )}

        {(evidenceMinItems || rangeSpec) && (
          <div className={styles.requirementsRow}>
            {evidenceMinItems ? (
              <span>
                {t('esg:factCreatePage.sources.expectedEvidence')} <strong>{evidenceMinItems}</strong>+ {t('esg:factCreatePage.sources.evidenceItems')}
              </span>
            ) : (
              <span />
            )}
            {rangeSpec && (rangeSpec.min !== undefined || rangeSpec.max !== undefined) && (
              <span>
                {t('esg:factCreatePage.sources.expectedRange')}{' '}
                <strong>{rangeSpec.min ?? '…'}</strong>–<strong>{rangeSpec.max ?? '…'}</strong>
              </span>
            )}
          </div>
        )}

        {publishIssues.length > 0 && (
          <div className={styles.issueBox} aria-label={t('esg:factCreatePage.sources.publishBlockersAria')}>
            <div className={styles.issueTitle}>{t('esg:factCreatePage.sources.publishBlockersTitle')}</div>
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
          <input
            type="checkbox"
            checked={showAdvancedJson}
            onChange={(e) => setShowAdvancedJson(e.target.checked)}
          />
          {t('esg:factCreatePage.advanced.toggle')}
        </label>

        {showAdvancedJson && (
          <div className={styles.grid}>
            <div className={styles.gridFull}>
              <label className={styles.textareaLabel} htmlFor="esg-fact-sources-json-advanced">
                {t('esg:factCreatePage.advanced.sourcesJsonLabel')}
              </label>
              <textarea
                id="esg-fact-sources-json-advanced"
                className={styles.textarea}
                value={sourcesJsonText}
                onChange={(e) => handleSourcesJsonTextChange(e.target.value)}
              />
              {sourcesJsonError && <div className={styles.fieldError}>{sourcesJsonError}</div>}
            </div>
            <div className={styles.gridFull}>
              <label className={styles.textareaLabel} htmlFor="esg-fact-quality-json-advanced">
                {t('esg:factCreatePage.advanced.qualityJsonLabel')}
              </label>
              <textarea
                id="esg-fact-quality-json-advanced"
                className={styles.textarea}
                value={qualityJsonText}
                onChange={(e) => handleQualityJsonTextChange(e.target.value)}
              />
              {qualityJsonError && <div className={styles.fieldError}>{qualityJsonError}</div>}
            </div>
          </div>
        )}
      </div>

      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => navigate('/esg/facts')}>
          {t('common:actions.cancel')}
        </Button>
        <Button onClick={handleCreate} disabled={createFact.isPending || Boolean(createdFact)}>
          {createdFact ? t('esg:factCreatePage.actions.created') : t('esg:factCreatePage.actions.createDraft')}
        </Button>
      </div>

      {createdFact && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>{t('esg:factCreatePage.sections.evidence')}</h2>
          <p className={styles.help}>
            {t('esg:factCreatePage.evidence.help')}
          </p>

          <div className={styles.evidenceComposer}>
            <Select
              label={t('esg:factCreatePage.evidence.fields.type')}
              value={newEvidenceType}
              onChange={(e) => {
                setNewEvidenceType(e.target.value as EsgFactEvidenceType)
                resetEvidenceForm()
              }}
              options={evidenceTypeOptions}
            />
            <Input
              label={t('esg:factCreatePage.evidence.fields.title')}
              value={newEvidenceTitle}
              onChange={(e) => setNewEvidenceTitle(e.target.value)}
              placeholder={newEvidenceType === 'file' ? t('esg:factCreatePage.evidence.placeholders.fileTitle') : t('esg:factCreatePage.evidence.placeholders.shortTitle')}
            />
            <Input
              label={t('esg:factCreatePage.evidence.fields.description')}
              value={newEvidenceDescription}
              onChange={(e) => setNewEvidenceDescription(e.target.value)}
              placeholder={t('esg:factCreatePage.evidence.placeholders.description')}
            />

            {newEvidenceType === 'file' && (
              <div className={styles.evidenceFile}>
                <input
                  type="file"
                  onChange={(e) => {
                    const file = e.target.files?.[0] ?? null
                    setNewEvidenceFile(file)
                    if (file && !newEvidenceTitle.trim()) {
                      setNewEvidenceTitle(file.name)
                    }
                    e.currentTarget.value = ''
                  }}
                />
                {newEvidenceFile && (
                  <div className={styles.evidenceFileName} title={newEvidenceFile.name}>
                    {t('esg:factCreatePage.evidence.selectedFile')}: <span className={styles.monoInline}>{newEvidenceFile.name}</span>
                  </div>
                )}
              </div>
            )}

            {newEvidenceType === 'link' && (
              <Input
                label={t('esg:factCreatePage.evidence.fields.url')}
                value={newEvidenceUrl}
                onChange={(e) => setNewEvidenceUrl(e.target.value)}
                placeholder={t('esg:factCreatePage.evidence.placeholders.url')}
              />
            )}

            {newEvidenceType === 'note' && (
              <div className={styles.gridFull}>
                <label className={styles.textareaLabel}>{t('esg:factCreatePage.evidence.fields.note')}</label>
                <textarea
                  className={styles.textarea}
                  value={newEvidenceNote}
                  onChange={(e) => setNewEvidenceNote(e.target.value)}
                  placeholder={t('esg:factCreatePage.evidence.placeholders.note')}
                />
              </div>
            )}

            <div className={styles.evidenceComposerActions}>
              <Button
                variant="secondary"
                onClick={resetEvidenceForm}
                disabled={createEvidence.isPending || uploadAsset.isPending}
              >
                {t('esg:factCreatePage.evidence.actions.clear')}
              </Button>
              <Button
                onClick={() => void submitNewEvidence()}
                disabled={createEvidence.isPending || uploadAsset.isPending}
              >
                {t('esg:factCreatePage.evidence.actions.add')}
              </Button>
            </div>
          </div>

          <ul className={styles.evidenceList}>
            {(evidenceList.data ?? []).map((ev) => (
              <li key={ev.evidence_id} className={styles.evidenceItem}>
                <div className={styles.evidenceMeta}>
                  <div className={styles.evidenceTitle}>{ev.title}</div>
                  <div className={styles.evidenceSub}>
                    {ev.type}
                    {ev.url ? ` | ${ev.url}` : ''}
                    {ev.description ? ` | ${ev.description}` : ''}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {ev.type === 'file' && ev.asset_id && (
                    <Button variant="secondary" size="sm" onClick={() => void handleDownloadEvidence(ev.asset_id!)}>
                      {t('esg:factCreatePage.evidence.actions.download')}
                    </Button>
                  )}
                  {ev.type === 'link' && ev.url && (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => window.open(ev.url!, '_blank', 'noopener,noreferrer')}
                    >
                      {t('esg:factCreatePage.evidence.actions.open')}
                    </Button>
                  )}
                  {ev.type === 'note' && (
                    <Button variant="secondary" size="sm" onClick={() => setNotePreview(ev)}>
                      {t('esg:factCreatePage.evidence.actions.view')}
                    </Button>
                  )}
                  <Button variant="secondary" size="sm" onClick={() => setDeleteEvidenceId(ev.evidence_id)}>
                    {t('common:actions.delete')}
                  </Button>
                </div>
              </li>
            ))}
          </ul>

          <ConfirmDialog
            isOpen={Boolean(deleteEvidenceId)}
            title={t('esg:factCreatePage.evidence.confirmDeleteTitle')}
            message={t('esg:factCreatePage.evidence.confirmDeleteMessage')}
            confirmLabel={t('common:actions.delete')}
            confirmLoading={deleteEvidence.isPending}
            onCancel={() => setDeleteEvidenceId(null)}
            onConfirm={() => {
              if (!deleteEvidenceId) return
              void handleDeleteEvidence(deleteEvidenceId).finally(() => setDeleteEvidenceId(null))
            }}
          />

          <Modal isOpen={Boolean(notePreview)} onClose={() => setNotePreview(null)} title={t('esg:factCreatePage.evidence.noteModalTitle')} size="lg">
            {notePreview && (
              <div className={styles.notePreview}>
                <div className={styles.notePreviewTitle}>{notePreview.title}</div>
                {notePreview.description && (
                  <div className={styles.notePreviewMeta}>{notePreview.description}</div>
                )}
                <pre className={styles.notePreviewBody}>{notePreview.note_md ?? ''}</pre>
              </div>
            )}
          </Modal>
        </div>
      )}
    </EsgShell>
  )
}
