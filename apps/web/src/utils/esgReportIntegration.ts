import type { Block } from '@/types/api'
import type { EsgFactCompareItem, EsgFactLatest, EsgMetricValueType } from '@/types/api'

export const QA_FLAG_DATA_PENDING = 'DATA_PENDING'

export interface EsgSourceRef {
  fact_id: string
  logical_key_hash: string
  version_number: number
}

export interface EsgSourceMeta extends EsgSourceRef {
  // Spec-aligned fields (optional / best-effort for legacy records)
  status_at_capture: string | null
  captured_at_utc: string | null
  value_type: EsgMetricValueType | null
  dataset_id: string | null
  dataset_revision_id: string | null
}

const LOGICAL_KEY_HASH_RE = /^[0-9a-f]{64}$/
const VALUE_TYPE_SET = new Set<EsgMetricValueType>(['number', 'integer', 'boolean', 'string', 'dataset'])

export function isValidLogicalKeyHash(hash: string): boolean {
  return LOGICAL_KEY_HASH_RE.test(hash.trim().toLowerCase())
}

function parsePositiveInt(raw: unknown): number | null {
  if (typeof raw === 'number') {
    if (!Number.isFinite(raw)) return null
    if (!Number.isInteger(raw)) return null
    if (raw < 1) return null
    return raw
  }

  if (typeof raw === 'string') {
    const trimmed = raw.trim()
    if (!trimmed) return null
    if (!/^[0-9]+$/.test(trimmed)) return null
    const parsed = Number(trimmed)
    if (!Number.isFinite(parsed)) return null
    if (!Number.isInteger(parsed)) return null
    if (parsed < 1) return null
    return parsed
  }

  return null
}

function parseValueType(raw: unknown): EsgMetricValueType | null {
  if (typeof raw !== 'string') return null
  const normalized = raw.trim()
  if (!normalized) return null
  if (!VALUE_TYPE_SET.has(normalized as EsgMetricValueType)) return null
  return normalized as EsgMetricValueType
}

function getNullableString(obj: Record<string, unknown>, key: string): string | null {
  const v = obj[key]
  if (typeof v !== 'string') return null
  const t = v.trim()
  return t ? t : null
}

export function getEsgSourceMetaFromDataJson(dataJson: unknown): EsgSourceMeta | null {
  if (!dataJson || typeof dataJson !== 'object') return null
  const source = (dataJson as Record<string, unknown>).esg_source
  if (!source || typeof source !== 'object') return null
  const src = source as Record<string, unknown>

  const factId = src.fact_id
  const logicalKeyHash = src.logical_key_hash
  const versionNumber = src.version_number

  if (typeof factId !== 'string' || !factId.trim()) return null
  if (typeof logicalKeyHash !== 'string' || !isValidLogicalKeyHash(logicalKeyHash)) return null

  const parsedVersion = parsePositiveInt(versionNumber)
  if (parsedVersion === null) return null

  // Backward compatible: accept legacy keys used in early implementation.
  const statusAtCapture = getNullableString(src, 'status_at_capture') ?? getNullableString(src, 'status')
  const capturedAtUtc = getNullableString(src, 'captured_at_utc') ?? getNullableString(src, 'imported_at_utc')
  const valueType = parseValueType(src.value_type)

  const datasetId = getNullableString(src, 'dataset_id')
  const datasetRevisionId = getNullableString(src, 'dataset_revision_id')

  return {
    fact_id: factId,
    logical_key_hash: logicalKeyHash.trim().toLowerCase(),
    version_number: parsedVersion,
    status_at_capture: statusAtCapture,
    captured_at_utc: capturedAtUtc,
    value_type: valueType,
    dataset_id: datasetId,
    dataset_revision_id: datasetRevisionId,
  }
}

export function getEsgSourceRefFromDataJson(dataJson: unknown): EsgSourceRef | null {
  const meta = getEsgSourceMetaFromDataJson(dataJson)
  if (!meta) return null
  return { fact_id: meta.fact_id, logical_key_hash: meta.logical_key_hash, version_number: meta.version_number }
}

export function getEsgSourceRef(block: Block): EsgSourceRef | null {
  return getEsgSourceRefFromDataJson(block.data_json)
}

export function blocksWithEsgSource(blocks: Block[]): Array<{ block: Block; ref: EsgSourceRef }> {
  const out: Array<{ block: Block; ref: EsgSourceRef }> = []
  for (const block of blocks) {
    const ref = getEsgSourceRef(block)
    if (ref) out.push({ block, ref })
  }
  return out
}

export function uniqueLogicalKeyHashes(refs: Array<{ ref: EsgSourceRef }>): string[] {
  const seen = new Set<string>()
  const hashes: string[] = []
  for (const { ref } of refs) {
    const h = ref.logical_key_hash
    if (seen.has(h)) continue
    seen.add(h)
    hashes.push(h)
  }
  hashes.sort()
  return hashes
}

export function latestByHash(compareItems: EsgFactCompareItem[]): Map<string, EsgFactLatest | null> {
  const m = new Map<string, EsgFactLatest | null>()
  for (const item of compareItems) {
    m.set(item.logical_key_hash, item.latest)
  }
  return m
}

export function shouldMarkDataPending(ref: EsgSourceRef, latest: EsgFactLatest | null): boolean {
  if (!latest) return true
  return latest.fact_id !== ref.fact_id
}

export function withDataPending(flags: string[]): string[] {
  if (flags.includes(QA_FLAG_DATA_PENDING)) return flags
  return [...flags, QA_FLAG_DATA_PENDING]
}

export function withoutDataPending(flags: string[]): string[] {
  return flags.filter((f) => f !== QA_FLAG_DATA_PENDING)
}
