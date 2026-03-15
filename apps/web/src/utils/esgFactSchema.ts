export type EsgRangeSpec = { min?: number; max?: number }

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function getEsgRequiredSourceFields(schema: Record<string, unknown> | null | undefined): string[] {
  if (!schema || !isPlainObject(schema)) return []
  const req = schema.requirements
  if (!isPlainObject(req)) return []
  const sources = req.sources
  if (!isPlainObject(sources)) return []
  const raw = sources.required_fields
  if (!Array.isArray(raw)) return []
  return raw
    .filter((x) => typeof x === 'string')
    .map((x) => x.trim())
    .filter(Boolean)
}

export function getEsgEvidenceMinItems(schema: Record<string, unknown> | null | undefined): number | null {
  if (!schema || !isPlainObject(schema)) return null
  const req = schema.requirements
  if (!isPlainObject(req)) return null
  const evidence = req.evidence
  if (!isPlainObject(evidence)) return null
  const min = evidence.min_items
  return typeof min === 'number' && Number.isInteger(min) && min > 0 ? min : null
}

export function getEsgRangeSpec(schema: Record<string, unknown> | null | undefined): EsgRangeSpec | null {
  if (!schema || !isPlainObject(schema)) return null
  const checks = schema.checks
  const range = (isPlainObject(checks) && isPlainObject(checks.range) ? checks.range : null) ?? (isPlainObject(schema.range) ? schema.range : null)
  if (!range) return null
  const min = range.min
  const max = range.max
  const out: EsgRangeSpec = {}
  if (typeof min === 'number' && Number.isFinite(min)) out.min = min
  if (typeof max === 'number' && Number.isFinite(max)) out.max = max
  return out.min === undefined && out.max === undefined ? null : out
}

export function collectEsgFactQualityGateIssues(args: {
  schema: Record<string, unknown> | null | undefined
  fact: {
    value_json: unknown | null | undefined
    dataset_id: string | null | undefined
    sources_json: Record<string, unknown> | null | undefined
    evidence_count?: number | null | undefined
  }
}): { code: string; message: string }[] {
  const { schema, fact } = args
  const issues: { code: string; message: string }[] = []

  const requiredSources = getEsgRequiredSourceFields(schema)
  if (requiredSources.length) {
    const sources = fact.sources_json ?? {}
    for (const key of requiredSources) {
      const v = sources[key]
      const missing =
        v === null ||
        typeof v === 'undefined' ||
        (typeof v === 'string' && !v.trim()) ||
        (Array.isArray(v) && v.length === 0) ||
        (isPlainObject(v) && Object.keys(v).length === 0)
      if (missing) {
        issues.push({ code: `missing_source:${key}`, message: `sources_json.${key} is required` })
      }
    }
  }

  const minEvidence = getEsgEvidenceMinItems(schema)
  if (minEvidence) {
    const count = typeof fact.evidence_count === 'number' ? fact.evidence_count : null
    if (count !== null && count < minEvidence) {
      issues.push({ code: 'missing_evidence', message: `At least ${minEvidence} evidence item(s) required (have ${count})` })
    }
  }

  const range = getEsgRangeSpec(schema)
  if (range && !fact.dataset_id && fact.value_json !== null && typeof fact.value_json !== 'undefined') {
    const v = fact.value_json
    if (typeof v === 'number' && Number.isFinite(v)) {
      if (typeof range.min === 'number' && v < range.min) {
        issues.push({ code: 'range_below_min', message: `value_json is below min (${v} < ${range.min})` })
      }
      if (typeof range.max === 'number' && v > range.max) {
        issues.push({ code: 'range_above_max', message: `value_json is above max (${v} > ${range.max})` })
      }
    }
  }

  return issues
}

