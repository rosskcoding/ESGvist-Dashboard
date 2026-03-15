import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import { Button, Input, Modal } from '@/components/ui'
import { toast } from '@/components/ui/toast'
import type { EsgFactImportConfirm, EsgFactImportPreview } from '@/types/api'
import styles from './EsgFactImportModal.module.css'

type Step = 'upload' | 'preview'

export function EsgFactImportModal(props: { isOpen: boolean; onClose: () => void; onImported?: () => void }) {
  const queryClient = useQueryClient()

  const [step, setStep] = useState<Step>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<EsgFactImportPreview | null>(null)
  const [skipRows, setSkipRows] = useState(0)
  const [sheetName, setSheetName] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isXlsx = file?.name.toLowerCase().endsWith('.xlsx') ?? false
  const isCsv = file?.name.toLowerCase().endsWith('.csv') ?? false

  const reset = () => {
    setStep('upload')
    setFile(null)
    setPreview(null)
    setSkipRows(0)
    setSheetName('')
    setLoading(false)
    setError(null)
  }

  const close = () => {
    reset()
    props.onClose()
  }

  const doPreview = async (selected: File) => {
    setLoading(true)
    setError(null)
    setPreview(null)

    try {
      const fd = new FormData()
      fd.append('file', selected)
      fd.append('skip_rows', String(skipRows))
      if (selected.name.toLowerCase().endsWith('.xlsx') && sheetName.trim()) {
        fd.append('sheet_name', sheetName.trim())
      }

      const path = selected.name.toLowerCase().endsWith('.xlsx')
        ? '/api/v1/esg/facts/import/xlsx/preview'
        : '/api/v1/esg/facts/import/csv/preview'

      const { data } = await apiClient.post<EsgFactImportPreview>(path, fd)
      setPreview(data)
      setStep('preview')
    } catch (e) {
      setError((e as Error).message || 'Preview failed')
    } finally {
      setLoading(false)
    }
  }

  const doConfirm = async () => {
    if (!file) return

    setLoading(true)
    setError(null)

    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('skip_rows', String(skipRows))
      if (file.name.toLowerCase().endsWith('.xlsx') && sheetName.trim()) {
        fd.append('sheet_name', sheetName.trim())
      }

      const path = file.name.toLowerCase().endsWith('.xlsx')
        ? '/api/v1/esg/facts/import/xlsx/confirm'
        : '/api/v1/esg/facts/import/csv/confirm'

      const { data } = await apiClient.post<EsgFactImportConfirm>(path, fd)

      const summary = `Created ${data.created}, skipped ${data.skipped}, errors ${data.error_rows}`
      if (data.error_rows > 0) {
        toast.error(summary)
      } else {
        toast.success(summary)
      }

      queryClient.invalidateQueries({ queryKey: ['esg', 'facts'] })
      props.onImported?.()
      close()
    } catch (e) {
      setError((e as Error).message || 'Import failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal isOpen={props.isOpen} onClose={close} title="Import facts" size="xl">
      {error && (
        <div className={styles.error}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {step === 'upload' && (
        <div className={styles.section}>
          <p className={styles.help}>
            Upload a <span className={styles.mono}>.csv</span> or <span className={styles.mono}>.xlsx</span> file.
            Required columns: <span className={styles.mono}>metric_code</span>, <span className={styles.mono}>period_type</span>,{' '}
            <span className={styles.mono}>period_start</span>, <span className={styles.mono}>period_end</span>, and either{' '}
            <span className={styles.mono}>value</span> (scalar) or <span className={styles.mono}>dataset_id</span> (dataset metrics).
          </p>

          <div className={styles.grid}>
            <Input
              label="Skip rows before header"
              type="number"
              value={String(skipRows)}
              onChange={(e) => setSkipRows(Math.max(0, Number(e.target.value) || 0))}
            />
            <Input
              label="Sheet name (XLSX only)"
              value={sheetName}
              onChange={(e) => setSheetName(e.target.value)}
              placeholder="Sheet1"
            />
          </div>

          <label className={styles.filePick}>
            <input
              type="file"
              accept=".csv,.xlsx"
              disabled={loading}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null
                if (!f) return
                setFile(f)
                void doPreview(f)
              }}
            />
            <div className={styles.filePickInner}>
              <div className={styles.filePickTitle}>{loading ? 'Loading…' : 'Select a file'}</div>
              <div className={styles.filePickHint}>CSV or XLSX</div>
            </div>
          </label>
        </div>
      )}

      {step === 'preview' && file && preview && (
        <div className={styles.section}>
          <div className={styles.previewHeader}>
            <div>
              <div className={styles.previewTitle}>{file.name}</div>
              <div className={styles.previewMeta}>
                Rows: <strong>{preview.total_rows}</strong> | Create: <strong>{preview.create_rows}</strong> | Skip:{' '}
                <strong>{preview.skip_rows}</strong> | Errors: <strong>{preview.error_rows}</strong>
              </div>
            </div>
            <div className={styles.previewActions}>
              <Button variant="secondary" onClick={() => setStep('upload')} disabled={loading}>
                Back
              </Button>
              <Button onClick={doConfirm} disabled={loading || (!isCsv && !isXlsx)}>
                Import
              </Button>
            </div>
          </div>

          {preview.errors.length > 0 && (
            <div className={styles.errorsList}>
              <div className={styles.errorsTitle}>Errors</div>
              <ul className={styles.errorsUl}>
                {preview.errors.slice(0, 200).map((er) => (
                  <li key={`${er.row_number}-${er.message}`} className={styles.errorRow}>
                    <span className={styles.mono}>Row {er.row_number}</span> {er.message}
                  </li>
                ))}
              </ul>
              {preview.errors.length > 200 && <div className={styles.more}>Showing first 200 errors</div>}
            </div>
          )}

          <div className={styles.rowsTable}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: '10%' }}>Row</th>
                  <th style={{ width: '18%' }}>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 200).map((r) => (
                  <tr key={r.row_number}>
                    <td className={styles.mono}>{r.row_number}</td>
                    <td>
                      <span className={`${styles.actionBadge} ${styles[`action_${r.action}`]}`}>{r.action}</span>
                    </td>
                    <td className={styles.mono}>{r.message || r.logical_key_hash || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.rows.length > 200 && <div className={styles.more}>Showing first 200 rows</div>}
          </div>
        </div>
      )}
    </Modal>
  )
}

