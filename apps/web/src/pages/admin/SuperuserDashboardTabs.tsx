/**
 * Superuser Dashboard Tabs — Individual tab implementations.
 * 
 * These are functional implementations demonstrating the concept.
 * Full styling and UX polish can be added later.
 */

import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '@/api/client'
import {
  useCompanies,
  useCreateCompany,
  useUpdateCompany,
  useDeleteCompany,
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
} from '@/api/hooks'
import {
  Button,
  IconAlertTriangle,
  IconBuilding,
  IconCheck,
  IconDownload,
  IconEye,
  IconFileText,
  IconLightbulb,
  IconPackage,
  IconPencil,
  IconRefresh,
  IconSearch,
  IconTrash,
  IconUser,
  Input,
  Modal,
  toast,
} from '@/components/ui'
import type { Company, User } from '@/types/api'
import { useAuthStore } from '@/stores/authStore'
import styles from './AdminPage.module.css'

const API_PREFIX = '/api/v1/admin'

// =============================================================================
// Attention Inbox Tab
// =============================================================================

interface AttentionItem {
  type: string
  entity_id: string
  company_id: string | null
  company_slug: string | null
  status: string
  error_code: string | null
  error_message: string | null
  occurred_at: string
}

interface IncidentHelpResponse {
  meaning: string
  possible_causes: string[]
  recommended_checks: string[]
}

interface ClearInboxResponse {
  cleared_builds: number
  cleared_artifacts: number
  cleared_translations: number
  total_cleared: number
}

export function AttentionInboxTab() {
  const [items, setItems] = useState<AttentionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [aiHelp, setAiHelp] = useState<IncidentHelpResponse | null>(null)
  const [clearing, setClearing] = useState(false)
  const [clearConfirm, setClearConfirm] = useState(false)

  async function fetchInbox() {
    try {
      const res = await apiClient.get<{ items: AttentionItem[] }>(
        `${API_PREFIX}/attention-inbox`,
      )
      setItems(res.data.items)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchInbox()
  }, [])

  async function clearInbox() {
    if (!clearConfirm) {
      setClearConfirm(true)
      setTimeout(() => setClearConfirm(false), 5000)
      return
    }
    
    setClearing(true)
    setClearConfirm(false)
    try {
      const res = await apiClient.delete<ClearInboxResponse>(
        `${API_PREFIX}/attention-inbox/clear`,
      )
      toast.success(`Cleared: ${res.data.total_cleared} records (builds: ${res.data.cleared_builds}, artifacts: ${res.data.cleared_artifacts}, translations: ${res.data.cleared_translations})`)
      // Refresh the inbox
      await fetchInbox()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to clear inbox')
    } finally {
      setClearing(false)
    }
  }

  async function getHelp(item: AttentionItem) {
    const res = await apiClient.post<IncidentHelpResponse>(
      `${API_PREFIX}/incidents/help`,
      {
        incident_type: item.type,
        error_code: item.error_code,
        status: item.status,
      },
    )
    setAiHelp(res.data)
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ margin: 0 }}>Attention Inbox{!loading ? ` (${items.length} items)` : ''}</h2>
        {!loading && items.length > 0 && (
          <button
            onClick={clearInbox}
            disabled={clearing}
            style={{
              padding: '8px 16px',
              background: clearConfirm ? 'rgba(239, 68, 68, 0.3)' : 'rgba(239, 68, 68, 0.15)',
              border: `1px solid ${clearConfirm ? 'rgba(239, 68, 68, 0.7)' : 'rgba(239, 68, 68, 0.4)'}`,
              borderRadius: '8px',
              color: clearConfirm ? '#fca5a5' : '#f87171',
              cursor: clearing ? 'not-allowed' : 'pointer',
              fontWeight: clearConfirm ? 'bold' : 'normal',
              opacity: clearing ? 0.6 : 1,
              transition: 'all 0.2s ease',
            }}
          >
            {clearing ? 'Clearing...' : clearConfirm ? 'Confirm clear' : 'Clear all'}
          </button>
        )}
      </div>
      {loading ? (
        <div>Loading incidents...</div>
      ) : items.length === 0 ? (
        <p style={{ color: '#16a34a', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
          <IconCheck size={16} />
          No incidents requiring attention
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '20px' }}>
          {items.map((item) => (
            <div
              key={item.entity_id}
              style={{
                padding: '16px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <strong style={{ color: '#fca5a5' }}>{item.type.replace(/_/g, ' ').toUpperCase()}</strong>
                <button
                  onClick={() => getHelp(item)}
                  style={{
                    padding: '4px 12px',
                    background: 'rgba(59, 130, 246, 0.2)',
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                    borderRadius: '4px',
                    color: '#60a5fa',
                    cursor: 'pointer',
                  }}
                >
                  ? AI Help
                </button>
              </div>
              <div style={{ fontSize: '14px', color: '#475569' }}>
                <div>Company: {item.company_slug || 'N/A'}</div>
                <div>Status: {item.status}</div>
                {item.error_message && <div>Error: {item.error_message}</div>}
                <div style={{ marginTop: '4px', fontSize: '12px', color: '#64748b' }}>
                  {new Date(item.occurred_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        isOpen={!!aiHelp}
        onClose={() => setAiHelp(null)}
        title="AI incident help"
      >
        {aiHelp ? (
          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ fontSize: '14px', color: '#475569' }}>
              <strong>Meaning:</strong> {aiHelp.meaning}
            </div>
            <div style={{ fontSize: '14px', color: '#475569' }}>
              <strong>Possible causes:</strong>
              <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.25rem' }}>
                {aiHelp.possible_causes.map((c: string, i: number) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
            <div style={{ fontSize: '14px', color: '#475569' }}>
              <strong>Recommended checks:</strong>
              <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.25rem' }}>
                {aiHelp.recommended_checks.map((c: string, i: number) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setAiHelp(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

// =============================================================================
// Builds Tab
// =============================================================================

interface Build {
  build_id: string
  company_slug: string
  build_type: string
  status: string
  error_message: string | null
  created_at: string
}

export function BuildsTab() {
  const [builds, setBuilds] = useState<Build[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchBuilds() {
      try {
        const res = await apiClient.get<{ items: Build[] }>(`${API_PREFIX}/builds`, {
          params: { page: '1', page_size: '20' },
        })
        setBuilds(res.data.items)
      } finally {
        setLoading(false)
      }
    }
    fetchBuilds()
  }, [])

  async function retryBuild(buildId: string) {
    await apiClient.post(`${API_PREFIX}/builds/${buildId}/retry`)
    alert('Build queued for retry')
  }

  return (
    <div>
      <h2>Builds</h2>
      {loading ? (
        <div>Loading builds...</div>
      ) : (
        <div className={styles.simpleTableWrap}>
          <table className={styles.simpleTable}>
            <thead>
              <tr>
                <th>Company</th>
                <th>Type</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {builds.map((build) => (
                <tr key={build.build_id}>
                  <td>{build.company_slug}</td>
                  <td>{build.build_type}</td>
                  <td>
                    <span
                      className={`${styles.pill} ${
                        build.status === 'failed'
                          ? styles.pillRed
                          : build.status === 'success'
                            ? styles.pillGreen
                            : styles.pillAmber
                      }`}
                    >
                      {build.status}
                    </span>
                  </td>
                  <td className={styles.tableSmall}>
                    {new Date(build.created_at).toLocaleString()}
                  </td>
                  <td>
                    {build.status === 'failed' ? (
                      <Button variant="secondary" onClick={() => retryBuild(build.build_id)}>
                        Retry
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Artifacts Tab
// =============================================================================

interface Artifact {
  artifact_id: string
  build_id: string
  company_slug: string
  format: string
  locale: string | null
  profile: string | null
  status: string
  error_code: string | null
  error_message: string | null
  created_at: string
}

export function ArtifactsTab() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchArtifacts() {
      try {
        const res = await apiClient.get<{ items: Artifact[] }>(`${API_PREFIX}/artifacts`, {
          params: { page: '1', page_size: '20' },
        })
        setArtifacts(res.data.items)
      } finally {
        setLoading(false)
      }
    }
    fetchArtifacts()
  }, [])

  return (
    <div>
      <h2>Artifacts</h2>
      {loading ? (
        <div>Loading artifacts...</div>
      ) : artifacts.length === 0 ? (
        <p className={styles.subtle}>No artifacts found</p>
      ) : (
        <div className={styles.simpleTableWrap}>
          <table className={styles.simpleTable}>
            <thead>
              <tr>
                <th>Company</th>
                <th>Format</th>
                <th>Locale</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {artifacts.map((artifact) => (
                <tr key={artifact.artifact_id}>
                  <td>{artifact.company_slug}</td>
                  <td>{artifact.format}</td>
                  <td>{artifact.locale || '-'}</td>
                  <td>
                    <span
                      className={`${styles.pill} ${
                        artifact.status === 'failed'
                          ? styles.pillRed
                          : artifact.status === 'ready'
                            ? styles.pillGreen
                            : styles.pillAmber
                      }`}
                    >
                      {artifact.status}
                    </span>
                  </td>
                  <td className={styles.tableSmall}>
                    {new Date(artifact.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Translation Jobs Tab
// =============================================================================

interface TranslationJob {
  job_id: string
  company_slug: string
  source_locale: string
  target_locales: string[]
  status: string
  error_log: Record<string, unknown> | null
  created_at: string
  finished_at: string | null
}

interface PlatformOpenAISettings {
  has_key: boolean
  key_status: 'active' | 'invalid' | 'disabled'
  key_last_validated_at: string | null
  key_last4: string | null
  model: string
}

interface TranslationPrompts {
  reporting_prompt: string
  marketing_prompt: string
  reporting_is_custom: boolean
  marketing_is_custom: boolean
}

export function TranslationsTab() {
  const [jobs, setJobs] = useState<TranslationJob[]>([])
  const [loading, setLoading] = useState(true)
  const [openai, setOpenai] = useState<PlatformOpenAISettings | null>(null)
  const [openaiLoading, setOpenaiLoading] = useState(true)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState(false)
  
  // Prompts state
  const [prompts, setPrompts] = useState<TranslationPrompts | null>(null)
  const [promptsLoading, setPromptsLoading] = useState(true)
  const [editingPrompt, setEditingPrompt] = useState<'reporting' | 'marketing' | null>(null)
  const [promptDraft, setPromptDraft] = useState('')
  const [savingPrompt, setSavingPrompt] = useState(false)

  useEffect(() => {
    async function fetchJobs() {
      try {
        const res = await apiClient.get<{ items: TranslationJob[] }>(`${API_PREFIX}/translations`, {
          params: { page: '1', page_size: '20' },
        })
        setJobs(res.data.items)
      } finally {
        setLoading(false)
      }
    }
    fetchJobs()

    // Poll so the dashboard reflects updates without manual refresh.
    // This is especially important for RUNNING → SUCCESS/FAILED transitions.
    const id = window.setInterval(fetchJobs, 10_000)
    return () => window.clearInterval(id)
  }, [])

  async function refreshOpenAI() {
    const res = await apiClient.get<PlatformOpenAISettings>(`${API_PREFIX}/openai/settings`)
    setOpenai(res.data)
  }

  useEffect(() => {
    async function fetchOpenAI() {
      try {
        await refreshOpenAI()
      } finally {
        setOpenaiLoading(false)
      }
    }
    fetchOpenAI()
  }, [])

  // Load prompts
  async function refreshPrompts() {
    try {
      const res = await apiClient.get<TranslationPrompts>(`${API_PREFIX}/translation-prompts`)
      setPrompts(res.data)
    } catch (e) {
      console.error('Failed to load prompts:', e)
    }
  }

  useEffect(() => {
    async function fetchPrompts() {
      try {
        await refreshPrompts()
      } finally {
        setPromptsLoading(false)
      }
    }
    fetchPrompts()
  }, [])

  const modelOptions = useMemo(
    () => [
      { value: 'gpt-4.1', label: 'GPT-4.1 - max accuracy / complex texts' },
      { value: 'gpt-4o', label: 'GPT-4o - best quality/speed balance' },
      { value: 'gpt-4.1-mini', label: 'GPT-4.1-mini - high-quality draft' },
      { value: 'gpt-4o-mini', label: 'GPT-4o-mini - bulk auto-translation' },
    ],
    []
  )

  async function handleSaveKey() {
    const key = apiKeyInput.trim()
    if (!key) return
    try {
      await apiClient.post(`${API_PREFIX}/openai/key`, { api_key: key })
      toast.success('OpenAI key saved (status: disabled until validation)')
      setApiKeyInput('')
      await refreshOpenAI()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save key')
    }
  }

  async function handleValidateKey() {
    try {
      const res = await apiClient.post<PlatformOpenAISettings>(`${API_PREFIX}/openai/key/validate`)
      setOpenai(res.data)
      if (res.data.key_status === 'active') {
        toast.success('OpenAI key is valid (active)')
      } else {
        toast.error('OpenAI key is invalid')
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to validate key')
    }
  }

  async function handleDeleteKey() {
    if (!deleteConfirm) {
      setDeleteConfirm(true)
      setTimeout(() => setDeleteConfirm(false), 5000)
      return
    }
    try {
      await apiClient.delete(`${API_PREFIX}/openai/key`)
      toast.success('OpenAI key deleted')
      setDeleteConfirm(false)
      await refreshOpenAI()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to delete key')
    }
  }

  async function handleModelChange(model: string) {
    try {
      const res = await apiClient.post<PlatformOpenAISettings>(`${API_PREFIX}/openai/model`, { model })
      setOpenai(res.data)
      toast.success(`Model set: ${model}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to set model')
    }
  }

  function startEditPrompt(mode: 'reporting' | 'marketing') {
    if (!prompts) return
    setEditingPrompt(mode)
    setPromptDraft(mode === 'reporting' ? prompts.reporting_prompt : prompts.marketing_prompt)
  }

  async function savePrompt() {
    if (!editingPrompt) return
    setSavingPrompt(true)
    try {
      const payload = editingPrompt === 'reporting'
        ? { reporting_prompt: promptDraft }
        : { marketing_prompt: promptDraft }
      
      const res = await apiClient.post<TranslationPrompts>(`${API_PREFIX}/translation-prompts`, payload)
      setPrompts(res.data)
      setEditingPrompt(null)
      setPromptDraft('')
      toast.success('Prompt saved')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to save prompt'
      toast.error(msg)
    } finally {
      setSavingPrompt(false)
    }
  }

  async function resetPrompt(mode: 'reporting' | 'marketing') {
    try {
      const payload = mode === 'reporting'
        ? { reporting_prompt: '' }
        : { marketing_prompt: '' }
      
      const res = await apiClient.post<TranslationPrompts>(`${API_PREFIX}/translation-prompts`, payload)
      setPrompts(res.data)
      toast.success(`Prompt "${mode}" reset to default`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to reset prompt')
    }
  }

  async function resetAllPrompts() {
    try {
      const res = await apiClient.post<TranslationPrompts>(`${API_PREFIX}/translation-prompts/reset`)
      setPrompts(res.data)
      toast.success('All prompts reset to defaults')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to reset prompts')
    }
  }

  return (
    <div>
      <h2>Translation Jobs</h2>

      {/* Platform OpenAI Settings */}
      <div
        className={styles.statCard}
        style={{ marginTop: '16px', marginBottom: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
          <h3 className={styles.metricLabel} style={{ margin: 0 }}>
            OpenAI (platform)
          </h3>
          {openaiLoading ? (
            <span style={{ color: '#64748b', fontSize: '12px' }}>Loading…</span>
          ) : openai ? (
            <span style={{ fontSize: '12px', color: openai.key_status === 'active' ? '#15803d' : openai.key_status === 'invalid' ? '#b91c1c' : '#64748b' }}>
              {openai.has_key ? `key: ${openai.key_status}` : 'key: not set'}
              {openai.key_last4 ? ` (…${openai.key_last4})` : ''}
            </span>
          ) : null}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px' }}>
          <div>
            <label className={styles.selectLabel}>OpenAI API key</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Input
                label=""
                placeholder="sk-…"
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                type="password"
              />
              <Button onClick={handleSaveKey} disabled={!apiKeyInput.trim()}>
                Save
              </Button>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px', alignItems: 'center' }}>
              <Button variant="secondary" onClick={handleValidateKey} disabled={!openai?.has_key}>
                Validate
              </Button>
              <Button
                variant="danger"
                onClick={handleDeleteKey}
                disabled={!openai?.has_key}
              >
                {deleteConfirm ? 'Confirm delete' : 'Delete key'}
              </Button>
              {openai?.key_last_validated_at && (
                <span style={{ fontSize: '12px', color: '#64748b' }}>
                  last validated: {new Date(openai.key_last_validated_at).toLocaleString()}
                </span>
              )}
            </div>
          </div>

          <div className={styles.selectField}>
            <label className={styles.selectLabel}>Default model</label>
            <select
              value={openai?.model || 'gpt-4o-mini'}
              onChange={(e) => handleModelChange(e.target.value)}
              className={styles.selectInput}
            >
              {modelOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p style={{ marginTop: '8px', marginBottom: 0, fontSize: '12px', color: '#64748b' }}>
              Note: the key is stored encrypted in the DB and is never returned to the client.
            </p>
          </div>
        </div>
      </div>

      {/* Translation Prompts Section */}
      <div
        className={styles.statCard}
        style={{ marginBottom: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginBottom: '16px' }}>
          <h3 className={styles.metricLabel} style={{ margin: 0 }}>
            Translation prompts
          </h3>
          {promptsLoading ? (
            <span style={{ color: '#64748b', fontSize: '12px' }}>Loading…</span>
          ) : (
            <Button variant="secondary" onClick={resetAllPrompts} style={{ fontSize: '12px' }}>
              Reset all to defaults
            </Button>
          )}
        </div>

        {prompts && !promptsLoading && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Reporting Prompt */}
            <div style={{ 
              padding: '16px', 
              background: 'rgba(15, 23, 42, 0.03)', 
              borderRadius: '8px',
              border: prompts.reporting_is_custom ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid rgba(15, 23, 42, 0.12)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <strong style={{ color: '#0f172a' }}>Mode: reporting</strong>
                  {prompts.reporting_is_custom ? (
                    <span style={{ marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: 'rgba(34, 197, 94, 0.2)', borderRadius: '4px', color: '#22c55e' }}>
                      custom
                    </span>
                    ) : (
                      <span style={{ marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: 'rgba(100, 116, 139, 0.2)', borderRadius: '4px', color: '#64748b' }}>
                        default
                      </span>
                    )}
                  </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => startEditPrompt('reporting')}
                    style={{
                      padding: '4px 12px',
                      background: 'rgba(99, 102, 241, 0.2)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      borderRadius: '4px',
                      color: '#818cf8',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                      <IconPencil size={14} />
                      Edit
                    </span>
                  </button>
                  {prompts.reporting_is_custom && (
                    <button
                      onClick={() => resetPrompt('reporting')}
                      style={{
                        padding: '4px 12px',
                        background: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '4px',
                        color: '#f87171',
                        cursor: 'pointer',
                        fontSize: '12px',
                      }}
                    >
                      Reset
                    </button>
                  )}
                </div>
              </div>
              <pre style={{ 
                margin: 0, 
                padding: '12px', 
                background: 'rgba(15, 23, 42, 0.03)', 
                borderRadius: '6px',
                fontSize: '11px',
                color: '#475569',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: '150px',
                overflow: 'auto',
              }}>
                {prompts.reporting_prompt}
              </pre>
            </div>

            {/* Marketing Prompt */}
            <div style={{ 
              padding: '16px', 
              background: 'rgba(15, 23, 42, 0.03)', 
              borderRadius: '8px',
              border: prompts.marketing_is_custom ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid rgba(15, 23, 42, 0.12)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <strong style={{ color: '#0f172a' }}>Mode: marketing</strong>
                  {prompts.marketing_is_custom ? (
                    <span style={{ marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: 'rgba(34, 197, 94, 0.2)', borderRadius: '4px', color: '#22c55e' }}>
                      custom
                    </span>
                    ) : (
                      <span style={{ marginLeft: '8px', fontSize: '11px', padding: '2px 8px', background: 'rgba(100, 116, 139, 0.2)', borderRadius: '4px', color: '#64748b' }}>
                        default
                      </span>
                    )}
                  </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    onClick={() => startEditPrompt('marketing')}
                    style={{
                      padding: '4px 12px',
                      background: 'rgba(99, 102, 241, 0.2)',
                      border: '1px solid rgba(99, 102, 241, 0.3)',
                      borderRadius: '4px',
                      color: '#818cf8',
                      cursor: 'pointer',
                      fontSize: '12px',
                    }}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                      <IconPencil size={14} />
                      Edit
                    </span>
                  </button>
                  {prompts.marketing_is_custom && (
                    <button
                      onClick={() => resetPrompt('marketing')}
                      style={{
                        padding: '4px 12px',
                        background: 'rgba(239, 68, 68, 0.2)',
                        border: '1px solid rgba(239, 68, 68, 0.3)',
                        borderRadius: '4px',
                        color: '#f87171',
                        cursor: 'pointer',
                        fontSize: '12px',
                      }}
                    >
                      Reset
                    </button>
                  )}
                </div>
              </div>
              <pre style={{ 
                margin: 0, 
                padding: '12px', 
                background: 'rgba(15, 23, 42, 0.03)', 
                borderRadius: '6px',
                fontSize: '11px',
                color: '#475569',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                maxHeight: '150px',
                overflow: 'auto',
              }}>
                {prompts.marketing_prompt}
              </pre>
            </div>

            {/* Placeholders Info */}
            <div style={{ 
              padding: '12px', 
              background: 'rgba(59, 130, 246, 0.1)', 
              border: '1px solid rgba(59, 130, 246, 0.2)',
              borderRadius: '8px',
              fontSize: '12px',
              color: '#475569',
            }}>
              <strong style={{ color: '#0f172a' }}>Required placeholders:</strong>
              <div style={{ marginTop: '8px', fontFamily: 'monospace', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                <code style={{ padding: '2px 6px', background: 'rgba(15, 23, 42, 0.06)', borderRadius: '4px' }}>{'{source_lang}'}</code>
                <code style={{ padding: '2px 6px', background: 'rgba(15, 23, 42, 0.06)', borderRadius: '4px' }}>{'{target_lang}'}</code>
                <code style={{ padding: '2px 6px', background: 'rgba(15, 23, 42, 0.06)', borderRadius: '4px' }}>{'{text}'}</code>
                <code style={{ padding: '2px 6px', background: 'rgba(15, 23, 42, 0.06)', borderRadius: '4px' }}>{'{glossary_section}'}</code>
              </div>
            </div>
          </div>
        )}
      </div>

      <Modal
        isOpen={!!editingPrompt}
        onClose={() => setEditingPrompt(null)}
        title={`Edit prompt: ${editingPrompt === 'reporting' ? 'Reporting' : 'Marketing'}`}
      >
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <textarea
            value={promptDraft}
            onChange={(e) => setPromptDraft(e.target.value)}
            style={{
              width: '100%',
              height: '360px',
              padding: '12px',
              background: '#ffffff',
              border: '1px solid rgba(15, 23, 42, 0.12)',
              borderRadius: '10px',
              color: '#0f172a',
              fontSize: '13px',
              fontFamily: 'monospace',
              resize: 'vertical',
              outline: 'none',
            }}
            placeholder="Enter translation prompt..."
          />

          <div
            style={{
              padding: '12px',
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.22)',
              borderRadius: '10px',
              fontSize: '12px',
              color: '#92400e',
            }}
          >
            <strong style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <IconAlertTriangle size={16} />
              Important:
            </strong>{' '}
            Prompt must include all required placeholders:
            <code style={{ marginLeft: '6px' }}>{'{source_lang}'}</code>,
            <code style={{ marginLeft: '6px' }}>{'{target_lang}'}</code>,
            <code style={{ marginLeft: '6px' }}>{'{text}'}</code>,
            <code style={{ marginLeft: '6px' }}>{'{glossary_section}'}</code>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <Button variant="secondary" onClick={() => setEditingPrompt(null)}>
              Cancel
            </Button>
            <Button onClick={savePrompt} disabled={savingPrompt}>
              {savingPrompt ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </Modal>

      {loading ? (
        <div>Loading translation jobs...</div>
      ) : jobs.length === 0 ? (
        <p style={{ color: '#666' }}>No translation jobs found</p>
      ) : (
        <div className={styles.simpleTableWrap}>
          <table className={styles.simpleTable}>
            <thead>
              <tr>
                <th>Company</th>
                <th>Source</th>
                <th>Targets</th>
                <th>Status</th>
                <th>Error</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => {
                const statusPill =
                  job.status === 'failed'
                    ? styles.pillRed
                    : job.status === 'success'
                      ? styles.pillGreen
                      : styles.pillAmber

                return (
                  <tr key={job.job_id}>
                    <td>{job.company_slug}</td>
                    <td>{job.source_locale}</td>
                    <td>{job.target_locales.join(', ')}</td>
                    <td>
                      <span className={`${styles.pill} ${statusPill}`}>{job.status}</span>
                    </td>
                    <td className={styles.tableSmall}>
                      {job.error_log
                        ? (
                            job.error_log.error ||
                            job.error_log.message ||
                            (Array.isArray(job.error_log.top_errors) && job.error_log.top_errors[0]?.error) ||
                            ''
                          )
                        : ''}
                    </td>
                    <td className={styles.tableSmall}>
                      {new Date(job.created_at).toLocaleString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Audit Log Tab
// =============================================================================

interface AuditEvent {
  event_id: string
  timestamp_utc: string
  actor_type: string
  actor_id: string
  action: string
  entity_type: string
  entity_id: string
  company_slug: string | null
  ip_address: string | null
}

export function AuditLogTab() {
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchEvents() {
      try {
        const res = await apiClient.get<{ items: AuditEvent[] }>(`${API_PREFIX}/audit-events`, {
          params: { page: '1', page_size: '50' },
        })
        setEvents(res.data.items)
      } finally {
        setLoading(false)
      }
    }
    fetchEvents()
  }, [])

  const [exporting, setExporting] = useState(false)
  
  async function exportCSV() {
    setExporting(true)
    try {
      const res = await apiClient.get<Blob>(`${API_PREFIX}/audit-events/export`, {
        params: { limit: 1000 },
        responseType: 'blob',
      })
      
      // Create download link
      const blob = res.data
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      
      // Extract filename from Content-Disposition header or use default
      const contentDisposition = res.headers['content-disposition']
      const filenameMatch = contentDisposition?.match(/filename="?([^";\n]+)"?/)
      link.download = filenameMatch ? filenameMatch[1] : `audit_events_${new Date().toISOString().split('T')[0]}.csv`
      
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Export failed:', error)
      alert('Failed to export audit events')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Audit Log</h2>
        <Button
          onClick={exportCSV}
          variant="secondary"
          loading={exporting}
          icon={<IconDownload size={16} />}
        >
          Export CSV
        </Button>
      </div>
      {loading ? (
        <div>Loading audit events...</div>
      ) : events.length === 0 ? (
        <p style={{ color: '#666' }}>No audit events found</p>
      ) : (
        <div className={styles.simpleTableWrap}>
          <table className={styles.simpleTable}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Company</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.event_id}>
                  <td className={styles.tableSmall}>
                    {new Date(event.timestamp_utc).toLocaleString()}
                  </td>
                  <td className={styles.tableSmall}>
                    <span className={styles.tableSmall}>{event.actor_type}:</span> {event.actor_id.slice(0, 8)}...
                  </td>
                  <td>
                    <span className={styles.pill}>{event.action}</span>
                  </td>
                  <td className={styles.tableSmall}>
                    {event.entity_type}: {event.entity_id.slice(0, 8)}...
                  </td>
                  <td className={styles.tableSmall}>
                    {event.company_slug || 'Platform'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// AI Usage Tab
// =============================================================================

interface AIUsageStats {
  total_events: number
  total_cost_usd: string
  by_feature: Record<string, { count: number; cost_usd: string; tokens: number }>
  by_company: Array<{ company_id: string; count: number; cost_usd: string }>
}

export function AIUsageTab() {
  const [stats, setStats] = useState<AIUsageStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchStats() {
      try {
        const res = await apiClient.get<AIUsageStats>(`${API_PREFIX}/ai-usage`)
        setStats(res.data)
      } finally {
        setLoading(false)
      }
    }
    fetchStats()
  }, [])

  if (loading) {
    return <div><h2>AI Usage & Costs</h2><p style={{ color: '#666' }}>Loading usage statistics...</p></div>
  }

  if (!stats) {
    return <div><h2>AI Usage & Costs</h2><p style={{ color: '#666' }}>No usage data available</p></div>
  }

  return (
    <div>
      <h2>AI Usage & Costs</h2>
      
      {/* Summary */}
      <div className={styles.metricGrid}>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>Total events</div>
          <div className={styles.metricValue}>{stats.total_events.toLocaleString()}</div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.metricLabel}>Total cost</div>
          <div className={styles.metricValue}>${parseFloat(stats.total_cost_usd).toFixed(4)}</div>
        </div>
      </div>

      {/* By Feature */}
      {Object.keys(stats.by_feature).length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h3 className={styles.metricLabel} style={{ marginBottom: '12px' }}>Usage by Feature</h3>
          <div className={styles.simpleTableWrap} style={{ marginTop: 0 }}>
            <table className={styles.simpleTable} style={{ minWidth: 0 }}>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th className={styles.tableRight}>Calls</th>
                  <th className={styles.tableRight}>Tokens</th>
                  <th className={styles.tableRight}>Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.by_feature).map(([feature, data]) => (
                  <tr key={feature}>
                    <td>{feature.replace(/_/g, ' ')}</td>
                    <td className={styles.tableRight}>{data.count}</td>
                    <td className={styles.tableRight}>{data.tokens.toLocaleString()}</td>
                    <td className={styles.tableRight}>${parseFloat(data.cost_usd).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* By Company */}
      {stats.by_company.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h3 className={styles.metricLabel} style={{ marginBottom: '12px' }}>Top Companies by Usage</h3>
          <div className={styles.simpleTableWrap} style={{ marginTop: 0 }}>
            <table className={styles.simpleTable} style={{ minWidth: 0 }}>
              <thead>
                <tr>
                  <th>Company ID</th>
                  <th className={styles.tableRight}>Calls</th>
                  <th className={styles.tableRight}>Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {stats.by_company.map((company) => (
                  <tr key={company.company_id}>
                    <td className={`${styles.mono} ${styles.tableSmall}`}>{company.company_id.slice(0, 8)}...</td>
                    <td className={styles.tableRight}>{company.count}</td>
                    <td className={styles.tableRight}>${parseFloat(company.cost_usd).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Companies Tab
// =============================================================================

export function CompaniesTab() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newCompanyName, setNewCompanyName] = useState('')
  const [editingCompany, setEditingCompany] = useState<Company | null>(null)
  const [editName, setEditName] = useState('')
  const [editStatus, setEditStatus] = useState<'active' | 'disabled'>('active')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: companiesData, isLoading, error, refetch } = useCompanies()
  const createCompany = useCreateCompany()
  const updateCompany = useUpdateCompany()
  const deleteCompany = useDeleteCompany()

  const companies = useMemo(() => companiesData?.items ?? [], [companiesData?.items])

  // Filtered companies based on search
  const filteredCompanies = useMemo(() => {
    if (!searchQuery.trim()) return companies
    const query = searchQuery.toLowerCase()
    return companies.filter(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.status.toLowerCase().includes(query)
    )
  }, [companies, searchQuery])

  const handleCreateCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newCompanyName.trim()) return

    try {
      await createCompany.mutateAsync({ name: newCompanyName.trim() })
      toast.success(`Company "${newCompanyName.trim()}" created successfully`)
      setNewCompanyName('')
      setIsCreateModalOpen(false)
    } catch (err) {
      toast.error('Failed to create company')
      console.error('Failed to create company:', err)
    }
  }

  const openEditModal = (company: Company) => {
    setEditingCompany(company)
    setEditName(company.name)
    setEditStatus(company.status as 'active' | 'disabled')
  }

  const handleEditCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingCompany || !editName.trim()) return

    try {
      await updateCompany.mutateAsync({
        companyId: editingCompany.company_id,
        data: {
          name: editName.trim(),
          status: editStatus,
        },
      })
      toast.success(`Company "${editName.trim()}" updated`)
      setEditingCompany(null)
    } catch (err) {
      toast.error('Failed to update company')
      console.error('Failed to update company:', err)
    }
  }

  const handleDeleteCompany = async (companyId: string, companyName: string) => {
    if (deleteConfirm === companyId) {
      try {
        await deleteCompany.mutateAsync(companyId)
        toast.success(`Company "${companyName}" deleted`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to delete company'
        toast.error(errorMessage)
        console.error('Failed to delete company:', err)
      }
    } else {
      setDeleteConfirm(companyId)
      setTimeout(() => setDeleteConfirm(null), 5000)
    }
  }

  return (
    <div>
      <div className={styles.infoBox}>
        <div className={styles.infoBoxHeader}>
          <span className={styles.infoBoxIcon} aria-hidden="true">
            <IconBuilding size={18} />
          </span>
          <h3 className={styles.infoBoxTitle}>Company management (Platform level)</h3>
        </div>
        <p className={styles.infoBoxContent}>
          You are in the company management section at the <strong>platform level</strong>.
          Here you can:
        </p>
        <ul className={styles.infoBoxList}>
          <li><strong>Create</strong> new companies (tenants) in the system</li>
          <li><strong>Edit</strong> company names and statuses</li>
          <li><strong>Manage members</strong> by adding users to companies</li>
          <li><strong>Assign roles</strong> and configure access rights per company</li>
          <li><strong>Delete</strong> companies (with confirmation)</li>
        </ul>
      </div>

      <div className={styles.toolbar}>
        <h2 className={styles.pageTitle}>
          Companies
          {companiesData && (
            <span className={styles.count}>{companiesData.total}</span>
          )}
        </h2>
        <Button onClick={() => setIsCreateModalOpen(true)}>
          + Create company
        </Button>
      </div>

      {!isLoading && !error && companies.length > 0 && (
        <div className={styles.searchBox}>
          <div className={styles.searchWrapper}>
            <span className={styles.searchIcon} aria-hidden="true">
              <IconSearch size={18} />
            </span>
            <input
              type="text"
              placeholder="Search by name or status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
            />
          </div>
          {searchQuery && (
            <span className={styles.searchCount}>
              Found: {filteredCompanies.length} of {companies.length}
            </span>
          )}
        </div>
      )}

      {isLoading && (
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <span>Loading companies...</span>
        </div>
      )}

      {error && (
        <div className={styles.errorState}>
          <div className={styles.errorIcon} aria-hidden="true">
            <IconAlertTriangle size={22} />
          </div>
          <h2 className={styles.errorTitle}>Loading error</h2>
          <p className={styles.errorText}>
            {error instanceof Error ? error.message : 'Failed to load companies'}
          </p>
          <Button onClick={() => refetch()} variant="secondary">
            Retry
          </Button>
        </div>
      )}

      {!isLoading && !error && companies.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyIcon} aria-hidden="true">
            <IconBuilding size={26} />
          </div>
          <h2 className={styles.emptyTitle}>No companies</h2>
          <p className={styles.emptyText}>
            Create your first company to get started
          </p>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            + Create company
          </Button>
        </div>
      )}

      {!isLoading && !error && companies.length > 0 && (
        <div className={styles.table}>
          <div className={styles.tableHeader}>
            <div className={styles.tableCell}>Name</div>
            <div className={styles.tableCell}>Status</div>
            <div className={styles.tableCell}>Created</div>
            <div className={styles.tableCell}>Actions</div>
          </div>
          {filteredCompanies.map((company) => (
            <div key={company.company_id} className={styles.tableRow}>
              <div className={styles.tableCell}>
                <Link 
                  to={`/admin/platform/companies/${company.slug}/members`}
                  className={styles.companyNameLink}
                >
                  {company.name}
                </Link>
              </div>
              <div className={styles.tableCell}>
                <span className={`${styles.statusBadge} ${styles[company.status]}`}>
                  {company.status === 'active' ? 'Active' : 'Disabled'}
                </span>
              </div>
              <div className={styles.tableCell}>
                {new Date(company.created_at_utc).toLocaleDateString('ru-RU')}
              </div>
              <div className={styles.tableCell}>
                <div className={styles.actions}>
                  <button
                    onClick={() => openEditModal(company)}
                    className={styles.actionBtn}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                      <IconPencil size={14} />
                      Edit
                    </span>
                  </button>
                  <Link
                    to={`/admin/platform/companies/${company.slug}/members`}
                    className={styles.actionBtn}
                  >
                    Members
                  </Link>
                  <Link
                    to={`/admin/platform/companies/${company.slug}/roles`}
                    className={styles.actionBtn}
                  >
                    Roles
                  </Link>
                  <button
                    onClick={() => handleDeleteCompany(company.company_id, company.name)}
                    className={`${styles.actionBtn} ${styles.danger} ${deleteConfirm === company.company_id ? styles.confirmDelete : ''}`}
                  >
                    {deleteConfirm === company.company_id ? (
                      'Confirm delete'
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                        <IconTrash size={14} />
                        Delete
                      </span>
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
          {filteredCompanies.length === 0 && searchQuery && (
            <div className={styles.empty} style={{ border: 'none', padding: '3rem' }}>
              <p className={styles.emptyText}>No results for "{searchQuery}"</p>
            </div>
          )}
        </div>
      )}

      {deleteConfirm && (
        <div className={styles.deleteConfirm}>
          <span>Click again to delete</span>
          <button onClick={() => setDeleteConfirm(null)} className={styles.cancelDelete}>
            Cancel
          </button>
        </div>
      )}

      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create company"
      >
        <form onSubmit={handleCreateCompany} className={styles.form}>
          <Input
            label="Company name"
            value={newCompanyName}
            onChange={(e) => setNewCompanyName(e.target.value)}
            placeholder="Company LLC"
            required
          />
          <div className={styles.formActions}>
            <Button type="button" variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createCompany.isPending}>
              {createCompany.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={!!editingCompany}
        onClose={() => setEditingCompany(null)}
        title="Edit company"
      >
        <form onSubmit={handleEditCompany} className={styles.form}>
          <Input
            label="Company name"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            placeholder="Company LLC"
            required
          />
          <div className={styles.selectField}>
            <label className={styles.selectLabel}>Status</label>
            <select
              value={editStatus}
              onChange={(e) => setEditStatus(e.target.value as 'active' | 'disabled')}
              className={styles.selectInput}
            >
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
          <div className={styles.formActions}>
            <Button type="button" variant="secondary" onClick={() => setEditingCompany(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateCompany.isPending}>
              {updateCompany.isPending ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// =============================================================================
// Users Tab
// =============================================================================

export function UsersTab() {
  const currentUser = useAuthStore((s) => s.user)
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const [newEmail, setNewEmail] = useState('')
  const [newFullName, setNewFullName] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newIsSuperuser, setNewIsSuperuser] = useState(false)

  const [editEmail, setEditEmail] = useState('')
  const [editFullName, setEditFullName] = useState('')
  const [editPassword, setEditPassword] = useState('')
  const [editIsActive, setEditIsActive] = useState(true)
  const [editIsSuperuser, setEditIsSuperuser] = useState(false)

  const { data: usersData, isLoading, error, refetch } = useUsers()
  const createUser = useCreateUser()
  const updateUser = useUpdateUser()
  const deleteUser = useDeleteUser()

  const users = useMemo(() => usersData?.items ?? [], [usersData?.items])

  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users
    const query = searchQuery.toLowerCase()
    return users.filter(
      (u) =>
        u.email.toLowerCase().includes(query) ||
        u.full_name.toLowerCase().includes(query) ||
        (u.is_superuser && 'superuser'.includes(query))
    )
  }, [users, searchQuery])

  const resetCreateForm = () => {
    setNewEmail('')
    setNewFullName('')
    setNewPassword('')
    setNewIsSuperuser(false)
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newEmail.trim() || !newFullName.trim() || !newPassword.trim()) return

    if (newPassword.length < 12) {
      toast.error('Password must be at least 12 characters long')
      return
    }
    if (!/[A-Z]/.test(newPassword)) {
      toast.error('Password must include at least one uppercase letter')
      return
    }
    if (!/[a-z]/.test(newPassword)) {
      toast.error('Password must include at least one lowercase letter')
      return
    }
    if (!/[0-9]/.test(newPassword)) {
      toast.error('Password must include at least one digit')
      return
    }
    if (!/[^A-Za-z0-9]/.test(newPassword)) {
      toast.error('Password must include at least one special character')
      return
    }

    try {
      await createUser.mutateAsync({
        email: newEmail.trim(),
        full_name: newFullName.trim(),
        password: newPassword,
        is_superuser: newIsSuperuser,
      })
      toast.success(`User "${newEmail}" created`)
      resetCreateForm()
      setIsCreateModalOpen(false)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create user'
      toast.error(errorMessage)
      console.error('Failed to create user:', err)
    }
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setEditEmail(user.email)
    setEditFullName(user.full_name)
    setEditPassword('')
    setEditIsActive(user.is_active)
    setEditIsSuperuser(user.is_superuser)
  }

  const handleEditUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return

    try {
      const updateData: {
        email?: string
        full_name?: string
        password?: string
        is_active?: boolean
        is_superuser?: boolean
      } = {}

      if (editEmail !== editingUser.email) updateData.email = editEmail
      if (editFullName !== editingUser.full_name) updateData.full_name = editFullName
      if (editPassword) updateData.password = editPassword
      if (editIsActive !== editingUser.is_active) updateData.is_active = editIsActive
      if (editIsSuperuser !== editingUser.is_superuser) updateData.is_superuser = editIsSuperuser

      await updateUser.mutateAsync({
        userId: editingUser.user_id,
        data: updateData,
      })
      toast.success(`User "${editEmail}" updated`)
      setEditingUser(null)
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update user'
      toast.error(errorMessage)
      console.error('Failed to update user:', err)
    }
  }

  const handleDeleteUser = async (userId: string, userEmail: string) => {
    if (deleteConfirm === userId) {
      try {
        await deleteUser.mutateAsync(userId)
        toast.success(`User "${userEmail}" deleted`)
        setDeleteConfirm(null)
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to delete user'
        toast.error(errorMessage)
        console.error('Failed to delete user:', err)
      }
    } else {
      setDeleteConfirm(userId)
      setTimeout(() => setDeleteConfirm(null), 5000)
    }
  }

  return (
    <div>
      <div className={styles.infoBox}>
        <div className={styles.infoBoxHeader}>
          <span className={styles.infoBoxIcon} aria-hidden="true">
            <IconUser size={18} />
          </span>
          <h3 className={styles.infoBoxTitle}>User management (Platform level)</h3>
        </div>
        <p className={styles.infoBoxContent}>
          Here you manage <strong>all system users</strong>.
          User creation is available only to superusers.
        </p>
        <ul className={styles.infoBoxList}>
          <li><strong>Create</strong> new users with passwords</li>
          <li><strong>Grant superuser</strong> for full platform access</li>
          <li><strong>Edit</strong> email, name, role, and password</li>
          <li><strong>Deactivate</strong> users (disable access)</li>
          <li><strong>Delete</strong> users (with confirmation)</li>
        </ul>
      </div>

      <div className={styles.toolbar}>
        <h2 className={styles.pageTitle}>
          Users
          {usersData && (
            <span className={styles.count}>{usersData.total}</span>
          )}
        </h2>
        <Button onClick={() => setIsCreateModalOpen(true)}>
          + Create user
        </Button>
      </div>

      {!isLoading && !error && users.length > 0 && (
        <div className={styles.searchBox}>
          <div className={styles.searchWrapper}>
            <span className={styles.searchIcon} aria-hidden="true">
              <IconSearch size={18} />
            </span>
            <input
              type="text"
              placeholder="Search by email, name, or superuser..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
            />
          </div>
          {searchQuery && (
            <span className={styles.searchCount}>
              Found: {filteredUsers.length} of {users.length}
            </span>
          )}
        </div>
      )}

      {isLoading && (
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <span>Loading users...</span>
        </div>
      )}

      {error && (
        <div className={styles.errorState}>
          <div className={styles.errorIcon} aria-hidden="true">
            <IconAlertTriangle size={22} />
          </div>
          <h2 className={styles.errorTitle}>Loading error</h2>
          <p className={styles.errorText}>
            {error instanceof Error ? error.message : 'Failed to load users'}
          </p>
          <Button onClick={() => refetch()} variant="secondary">
            Retry
          </Button>
        </div>
      )}

      {!isLoading && !error && users.length === 0 && (
        <div className={styles.empty}>
          <div className={styles.emptyIcon} aria-hidden="true">
            <IconUser size={26} />
          </div>
          <h2 className={styles.emptyTitle}>No users</h2>
          <p className={styles.emptyText}>
            Create your first user
          </p>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            + Create user
          </Button>
        </div>
      )}

      {!isLoading && !error && users.length > 0 && (
        <div className={styles.table}>
          <div className={styles.tableHeader}>
            <div className={styles.tableCell}>Email</div>
            <div className={styles.tableCell}>Name</div>
            <div className={styles.tableCell}>Status</div>
            <div className={styles.tableCell}>Actions</div>
          </div>
          {filteredUsers.map((user) => (
            <div key={user.user_id} className={styles.tableRow}>
              <div className={styles.tableCell}>
                <span className={styles.companyName}>{user.email}</span>
                {user.is_superuser && (
                  <span className={styles.superuserBadge} style={{ marginLeft: '8px' }}>
                    superuser
                  </span>
                )}
              </div>
              <div className={styles.tableCell}>
                {user.full_name}
              </div>
              <div className={styles.tableCell}>
                <span className={`${styles.statusBadge} ${user.is_active ? styles.active : styles.disabled}`}>
                  {user.is_active ? 'Active' : 'Disabled'}
                </span>
              </div>
              <div className={styles.tableCell}>
                <div className={styles.actions}>
                  <button
                    onClick={() => openEditModal(user)}
                    className={styles.actionBtn}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                      <IconPencil size={14} />
                      Edit
                    </span>
                  </button>
                  {user.user_id !== currentUser?.userId && (
                    <button
                      onClick={() => handleDeleteUser(user.user_id, user.email)}
                      className={`${styles.actionBtn} ${styles.danger} ${deleteConfirm === user.user_id ? styles.confirmDelete : ''}`}
                    >
                      {deleteConfirm === user.user_id ? (
                        'Confirm delete'
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                          <IconTrash size={14} />
                          Delete
                        </span>
                      )}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
          {filteredUsers.length === 0 && searchQuery && (
            <div className={styles.empty} style={{ border: 'none', padding: '3rem' }}>
              <p className={styles.emptyText}>No results for "{searchQuery}"</p>
            </div>
          )}
        </div>
      )}

      {deleteConfirm && (
        <div className={styles.deleteConfirm}>
          <span>Click again to delete</span>
          <button onClick={() => setDeleteConfirm(null)} className={styles.cancelDelete}>
            Cancel
          </button>
        </div>
      )}

      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => {
          setIsCreateModalOpen(false)
          resetCreateForm()
        }}
        title="Create user"
      >
        <form onSubmit={handleCreateUser} className={styles.form}>
          <Input
            label="Email"
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            placeholder="user@example.com"
            required
          />
          <Input
            label="Full name"
            value={newFullName}
            onChange={(e) => setNewFullName(e.target.value)}
            placeholder="John Smith"
            required
          />
          <Input
            label="Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Min. 12 chars, A-Z, a-z, 0-9, special char"
            required
          />
          <div className={styles.checkboxField}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={newIsSuperuser}
                onChange={(e) => setNewIsSuperuser(e.target.checked)}
                className={styles.checkboxInput}
              />
              <span className={styles.checkboxText}>
                Superuser (full platform access)
              </span>
            </label>
          </div>
          <div className={styles.infoBoxSmall}>
            <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <IconLightbulb size={16} />
                <strong>How roles work:</strong>
              </span>
              <br />
              1. Create a user here<br />
              2. Add them to a company (Companies → Members)<br />
              3. Assign a role in the company (Companies → Roles)
            </p>
          </div>
          <div className={styles.formActions}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setIsCreateModalOpen(false)
                resetCreateForm()
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createUser.isPending}>
              {createUser.isPending ? 'Creating...' : 'Create'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={!!editingUser}
        onClose={() => setEditingUser(null)}
        title="Edit user"
      >
        <form onSubmit={handleEditUser} className={styles.form}>
          <Input
            label="Email"
            type="email"
            value={editEmail}
            onChange={(e) => setEditEmail(e.target.value)}
            placeholder="user@example.com"
            required
          />
          <Input
            label="Full name"
            value={editFullName}
            onChange={(e) => setEditFullName(e.target.value)}
            placeholder="John Smith"
            required
          />
          <Input
            label="New password (leave empty to keep current)"
            type="password"
            value={editPassword}
            onChange={(e) => setEditPassword(e.target.value)}
            placeholder="Min. 12 chars..."
          />
          <div className={styles.infoBoxSmall} style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
            <p style={{ fontSize: '0.85rem', color: '#64748b', margin: 0 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <IconLightbulb size={16} />
                <strong>Roles are assigned via company:</strong>
              </span>
              <br />
              Companies → Members → Roles
            </p>
          </div>
          <div className={styles.selectField}>
            <label className={styles.selectLabel}>Status</label>
            <select
              value={editIsActive ? 'active' : 'disabled'}
              onChange={(e) => setEditIsActive(e.target.value === 'active')}
              className={styles.selectInput}
            >
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
          <div className={styles.checkboxField}>
            <label className={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={editIsSuperuser}
                onChange={(e) => setEditIsSuperuser(e.target.checked)}
                className={styles.checkboxInput}
              />
              <span className={styles.checkboxText}>
                Superuser (full platform access)
              </span>
            </label>
          </div>
          <div className={styles.formActions}>
            <Button type="button" variant="secondary" onClick={() => setEditingUser(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateUser.isPending}>
              {updateUser.isPending ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

// =============================================================================
// Storage Tab — Build files cleanup management
// =============================================================================

interface CleanupResult {
  deleted_builds: number
  deleted_zips: number
  deleted_manifests: number
  freed_mb: number
  errors: string[]
  dry_run: boolean
}

interface OrphanedFilesResult {
  orphaned_zips: string[]
  orphaned_manifests: string[]
  total_orphaned_mb: number
  deleted: boolean
}

export function StorageTab() {
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null)
  const [orphanedResult, setOrphanedResult] = useState<OrphanedFilesResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [orphanedLoading, setOrphanedLoading] = useState(false)
  const [retentionDays, setRetentionDays] = useState(30)
  const [dryRun, setDryRun] = useState(true)

  // Check for orphaned files on mount
  useEffect(() => {
    checkOrphanedFiles()
  }, [])

  async function checkOrphanedFiles() {
    setOrphanedLoading(true)
    try {
      const res = await apiClient.post<OrphanedFilesResult>(
        `${API_PREFIX}/builds/cleanup-orphaned`,
        null,
        { params: { dry_run: true } }
      )
      setOrphanedResult(res.data)
    } catch (err) {
      console.error('Failed to check orphaned files:', err)
    } finally {
      setOrphanedLoading(false)
    }
  }

  async function runCleanup(isDryRun: boolean) {
    setLoading(true)
    setCleanupResult(null)
    try {
      const res = await apiClient.post<CleanupResult>(
        `${API_PREFIX}/builds/cleanup`,
        null,
        { params: { retention_days: retentionDays, dry_run: isDryRun } }
      )
      setCleanupResult(res.data)
      
      if (!isDryRun) {
        toast.success(`Cleared ${res.data.deleted_builds} builds, freed ${res.data.freed_mb.toFixed(2)} MB`)
        // Refresh orphaned files count
        checkOrphanedFiles()
      }
    } catch (err) {
      toast.error('Error while cleaning builds')
      console.error('Cleanup failed:', err)
    } finally {
      setLoading(false)
    }
  }

  async function cleanupOrphaned(isDryRun: boolean) {
    setOrphanedLoading(true)
    try {
      const res = await apiClient.post<OrphanedFilesResult>(
        `${API_PREFIX}/builds/cleanup-orphaned`,
        null,
        { params: { dry_run: isDryRun } }
      )
      setOrphanedResult(res.data)
      
      if (!isDryRun) {
        const deletedCount = res.data.orphaned_zips.length + res.data.orphaned_manifests.length
        toast.success(`Deleted ${deletedCount} orphaned files, freed ${res.data.total_orphaned_mb.toFixed(2)} MB`)
      }
    } catch (err) {
      toast.error('Error while cleaning orphaned files')
      console.error('Orphaned cleanup failed:', err)
    } finally {
      setOrphanedLoading(false)
    }
  }

  const totalOrphanedFiles = orphanedResult 
    ? orphanedResult.orphaned_zips.length + orphanedResult.orphaned_manifests.length 
    : 0

  return (
    <div>
      <h2>Storage Management</h2>
      <p style={{ color: '#475569', marginBottom: '24px' }}>
        Build file management (ZIP, manifests). Cleanup of old DRAFT builds and orphaned files.
      </p>

      {/* Orphaned Files Section */}
      <div style={{
        padding: '20px',
        background: totalOrphanedFiles > 0 ? 'rgba(251, 191, 36, 0.1)' : 'rgba(34, 197, 94, 0.1)',
        border: `1px solid ${totalOrphanedFiles > 0 ? 'rgba(251, 191, 36, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
        borderRadius: '12px',
        marginBottom: '24px',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ margin: '0 0 8px 0', color: totalOrphanedFiles > 0 ? '#fbbf24' : '#22c55e' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                {totalOrphanedFiles > 0 ? <IconAlertTriangle size={18} /> : <IconCheck size={18} />}
                {totalOrphanedFiles > 0 ? 'Orphaned files' : 'No orphaned files'}
              </span>
            </h3>
            <p style={{ margin: 0, color: '#475569', fontSize: '14px' }}>
              Files on disk without DB records (from crashed builds or manual operations)
            </p>
          </div>
          {orphanedLoading ? (
            <span style={{ color: '#64748b' }}>Checking...</span>
          ) : (
            <button
              onClick={() => checkOrphanedFiles()}
              style={{
                padding: '6px 12px',
                background: 'rgba(15, 23, 42, 0.03)',
                border: '1px solid rgba(15, 23, 42, 0.12)',
                borderRadius: '6px',
                color: '#0f172a',
                cursor: 'pointer',
                fontSize: '12px',
              }}
            >
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <IconRefresh size={14} />
                Refresh
              </span>
            </button>
          )}
        </div>

        {orphanedResult && totalOrphanedFiles > 0 && (
          <div style={{ marginTop: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px' }}>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', borderRadius: '10px', border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{orphanedResult.orphaned_zips.length}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>ZIP files</div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', borderRadius: '10px', border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{orphanedResult.orphaned_manifests.length}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>Manifests</div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', borderRadius: '10px', border: '1px solid rgba(15, 23, 42, 0.08)' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{orphanedResult.total_orphaned_mb.toFixed(2)}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>MB</div>
              </div>
            </div>

            {/* File list (collapsible) */}
            {(orphanedResult.orphaned_zips.length > 0 || orphanedResult.orphaned_manifests.length > 0) && (
              <details style={{ marginBottom: '16px' }}>
                <summary style={{ cursor: 'pointer', color: '#475569', fontSize: '14px' }}>
                  Show files ({totalOrphanedFiles})
                </summary>
                <div style={{ 
                  marginTop: '8px', 
                  maxHeight: '200px', 
                  overflow: 'auto',
                  padding: '12px',
                  background: 'rgba(15, 23, 42, 0.03)',
                  border: '1px solid rgba(15, 23, 42, 0.08)',
                  borderRadius: '10px',
                  fontSize: '12px',
                  fontFamily: 'monospace',
                }}>
                  {orphanedResult.orphaned_zips.map(f => (
                    <div key={f} style={{ color: '#dc2626', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <IconPackage size={14} />
                      {f}
                    </div>
                  ))}
                  {orphanedResult.orphaned_manifests.map(f => (
                    <div key={f} style={{ color: '#b45309', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <IconFileText size={14} />
                      {f}
                    </div>
                  ))}
                </div>
              </details>
            )}

            <button
              onClick={() => cleanupOrphaned(false)}
              disabled={orphanedLoading}
              style={{
                padding: '10px 20px',
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                borderRadius: '8px',
                color: '#ef4444',
                cursor: orphanedLoading ? 'not-allowed' : 'pointer',
                fontWeight: 'bold',
                opacity: orphanedLoading ? 0.5 : 1,
              }}
            >
              {orphanedLoading ? (
                'Deleting...'
              ) : (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                  <IconTrash size={16} />
                  Delete orphaned files
                </span>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Retention Cleanup Section */}
      <div style={{
        padding: '20px',
        background: 'rgba(99, 102, 241, 0.1)',
        border: '1px solid rgba(99, 102, 241, 0.3)',
        borderRadius: '12px',
        marginBottom: '24px',
      }}>
        <h3 style={{ margin: '0 0 8px 0', color: '#818cf8' }}>
          Retention policy cleanup
        </h3>
        <p style={{ margin: '0 0 16px 0', color: '#475569', fontSize: '14px' }}>
          Deleting old <strong>DRAFT</strong> builds (release builds are not deleted)
        </p>

        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ color: '#475569', fontSize: '14px' }}>Retention (days):</label>
            <input
              type="number"
              min={1}
              max={365}
              value={retentionDays}
              onChange={(e) => setRetentionDays(Number(e.target.value))}
              style={{
                width: '80px',
                padding: '8px 12px',
                background: '#ffffff',
                border: '1px solid rgba(15, 23, 42, 0.12)',
                borderRadius: '6px',
                color: '#0f172a',
                fontSize: '14px',
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                style={{ width: '16px', height: '16px' }}
              />
              <span style={{ color: '#475569', fontSize: '14px' }}>Dry run (preview only)</span>
            </label>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            onClick={() => runCleanup(true)}
            disabled={loading}
            style={{
              padding: '10px 20px',
              background: 'rgba(99, 102, 241, 0.2)',
              border: '1px solid rgba(99, 102, 241, 0.5)',
              borderRadius: '8px',
              color: '#818cf8',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              opacity: loading ? 0.5 : 1,
            }}
          >
            {loading ? (
              'Checking...'
            ) : (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <IconEye size={16} />
                Preview (what will be deleted)
              </span>
            )}
          </button>
          
          <button
            onClick={() => runCleanup(false)}
            disabled={loading || dryRun}
            style={{
              padding: '10px 20px',
              background: dryRun ? 'rgba(100, 100, 100, 0.2)' : 'rgba(239, 68, 68, 0.2)',
              border: `1px solid ${dryRun ? 'rgba(100, 100, 100, 0.3)' : 'rgba(239, 68, 68, 0.5)'}`,
              borderRadius: '8px',
              color: dryRun ? '#64748b' : '#ef4444',
              cursor: (loading || dryRun) ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              opacity: (loading || dryRun) ? 0.5 : 1,
            }}
            title={dryRun ? 'Disable "Dry run" to delete' : 'Delete old DRAFT builds'}
          >
            {loading ? (
              'Deleting...'
            ) : (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                <IconTrash size={16} />
                Delete
              </span>
            )}
          </button>
        </div>

        {cleanupResult && (
          <div style={{
            marginTop: '16px',
            padding: '16px',
            background: cleanupResult.dry_run ? 'rgba(251, 191, 36, 0.1)' : 'rgba(34, 197, 94, 0.1)',
            border: `1px solid ${cleanupResult.dry_run ? 'rgba(251, 191, 36, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            borderRadius: '8px',
          }}>
            <div style={{ 
              marginBottom: '12px', 
              fontWeight: 'bold',
              color: cleanupResult.dry_run ? '#fbbf24' : '#22c55e',
            }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
                {cleanupResult.dry_run ? <IconEye size={16} /> : <IconCheck size={16} />}
                {cleanupResult.dry_run ? 'Preview results' : 'Cleanup completed'}
              </span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px' }}>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', border: '1px solid rgba(15, 23, 42, 0.08)', borderRadius: '10px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{cleanupResult.deleted_builds}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>Builds</div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', border: '1px solid rgba(15, 23, 42, 0.08)', borderRadius: '10px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{cleanupResult.deleted_zips}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>ZIP</div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', border: '1px solid rgba(15, 23, 42, 0.08)', borderRadius: '10px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{cleanupResult.deleted_manifests}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>Manifests</div>
              </div>
              <div style={{ padding: '12px', background: 'rgba(15, 23, 42, 0.03)', border: '1px solid rgba(15, 23, 42, 0.08)', borderRadius: '10px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{cleanupResult.freed_mb.toFixed(2)}</div>
                <div style={{ fontSize: '12px', color: '#64748b' }}>MB</div>
              </div>
            </div>

            {cleanupResult.errors.length > 0 && (
              <div style={{ marginTop: '12px', color: '#f87171', fontSize: '14px' }}>
                <strong>Errors:</strong>
                <ul style={{ margin: '4px 0 0 0', paddingLeft: '20px' }}>
                  {cleanupResult.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Info Box */}
      <div style={{
        padding: '16px',
        background: 'rgba(15, 23, 42, 0.03)',
        border: '1px solid rgba(15, 23, 42, 0.12)',
        borderRadius: '8px',
        fontSize: '14px',
        color: '#475569',
      }}>
        <strong style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', color: '#0f172a' }}>
          <IconLightbulb size={16} />
          Tip:
        </strong>
        <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
          <li><strong>Orphaned files</strong> — ZIP/manifests without DB records (from crashed builds)</li>
          <li><strong>Retention cleanup</strong> — deletes only DRAFT builds older than N days</li>
          <li><strong>RELEASE builds</strong> — are not deleted automatically (manual only)</li>
          <li>It is recommended to run <strong>Preview</strong> first for review</li>
        </ul>
      </div>
    </div>
  )
}
