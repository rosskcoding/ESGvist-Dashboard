/**
 * DatasetImportModal component.
 * 
 * Multi-step wizard for importing CSV/XLSX files:
 * 1. Upload file
 * 2. Preview with auto-detected schema
 * 3. Adjust column types
 * 4. Confirm and import
 */

import { useState } from 'react';
import {
  importCSVPreview,
  importCSVConfirm,
  importXLSXPreview,
  importXLSXConfirm,
  type DatasetImportPreview,
  type ColumnSchema,
} from '@/api/datasets';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { IconAlertTriangle, IconArrowLeft, IconArrowRight, IconFolder } from '@/components/ui';
import styles from './DatasetImportModal.module.css';

interface DatasetImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (datasetId: string) => void;
}

type Step = 'upload' | 'preview' | 'confirm';

export function DatasetImportModal({
  isOpen,
  onClose,
  onSuccess,
}: DatasetImportModalProps) {
  const [step, setStep] = useState<Step>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<DatasetImportPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form data
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [columns, setColumns] = useState<ColumnSchema[]>([]);
  const [skipRows, setSkipRows] = useState(0);

  const handleFileSelect = async (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);
    setLoading(true);

    try {
      let previewData: DatasetImportPreview;
      
      if (selectedFile.name.endsWith('.csv')) {
        previewData = await importCSVPreview(selectedFile);
      } else if (selectedFile.name.endsWith('.xlsx') || selectedFile.name.endsWith('.xls')) {
        previewData = await importXLSXPreview({ file: selectedFile });
      } else {
        throw new Error('Unsupported file format');
      }

      setPreview(previewData);
      setColumns(previewData.detected_columns);
      setName(selectedFile.name.replace(/\.(csv|xlsx|xls)$/i, ''));
      setStep('preview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!file || !preview) return;

    setLoading(true);
    setError(null);

    try {
      const isXlsx = file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.xls');

      const result = isXlsx
        ? await importXLSXConfirm({
            file,
            name,
            description,
            schema_json: { columns },
            skip_rows: skipRows,
          })
        : await importCSVConfirm({
            file,
            name,
            description,
            schema_json: { columns },
            skip_rows: skipRows,
          });

      onSuccess(result.dataset_id);
      handleClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setStep('upload');
    setFile(null);
    setPreview(null);
    setName('');
    setDescription('');
    setColumns([]);
    setSkipRows(0);
    setError(null);
    onClose();
  };

  const updateColumnType = (index: number, type: ColumnSchema['type']) => {
    const newColumns = [...columns];
    newColumns[index] = { ...newColumns[index], type };
    setColumns(newColumns);
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Data import" size="xl">
      {error && (
        <div className={styles.error}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {step === 'upload' && (
        <div className={styles.uploadArea}>
          <label className={styles.fileLabel}>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => {
                const selectedFile = e.target.files?.[0];
                if (selectedFile) handleFileSelect(selectedFile);
              }}
              disabled={loading}
            />
            <div className={styles.uploadPrompt}>
              <div className={styles.uploadIcon} aria-hidden="true">
                <IconFolder size={28} />
              </div>
              <div className={styles.uploadText}>
                {loading ? 'Loading...' : 'Select a CSV or XLSX file'}
              </div>
              <div className={styles.uploadHint}>
                or drag and drop a file here
              </div>
            </div>
          </label>
        </div>
      )}

      {step === 'preview' && preview && (
        <div className={styles.section}>
          <h3>Data preview</h3>
          
          {preview.warnings.length > 0 && (
            <div className={styles.warnings}>
              {preview.warnings.map((w, i) => (
                <div key={i} className={styles.warning}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <IconAlertTriangle size={16} />
                    {w}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className={styles.stats}>
            <span>Total rows: {preview.total_rows}</span>
            <span>Columns: {preview.detected_columns.length}</span>
          </div>

          <div className={styles.previewTable}>
            <table>
              <thead>
                <tr>
                  {columns.map((col, i) => (
                    <th key={i}>
                      <div className={styles.columnHeader}>
                        <span>{col.key}</span>
                        <select
                          value={col.type}
                          onChange={(e) =>
                            updateColumnType(i, e.target.value as ColumnSchema['type'])
                          }
                          className={styles.typeSelect}
                        >
                          <option value="text">Text</option>
                          <option value="number">Number</option>
                          <option value="percent">Percent</option>
                          <option value="currency">Currency</option>
                          <option value="date">Date</option>
                        </select>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.preview_rows.slice(0, 10).map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td key={ci}>{cell !== null ? String(cell) : '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.actions}>
            <Button variant="primary" onClick={() => setStep('confirm')}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                Next
                <IconArrowRight size={16} />
              </span>
            </Button>
          </div>
        </div>
      )}

      {step === 'confirm' && (
        <div className={styles.section}>
          <h3>Import settings</h3>

          <Input
            label="Dataset name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Financial metrics Q1 2024"
            required
          />

          <div className={styles.field}>
            <label className={styles.fieldLabel}>Description (optional)</label>
            <textarea
              className={styles.textarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Quarterly financial data..."
              rows={3}
            />
          </div>

          <Input
            label="Skip rows after header"
            type="number"
            value={String(skipRows)}
            onChange={(e) => setSkipRows(parseInt(e.target.value) || 0)}
            min="0"
          />

          <div className={styles.actions}>
            <Button variant="secondary" onClick={() => setStep('preview')}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <IconArrowLeft size={16} />
                Back
              </span>
            </Button>
            <Button
              variant="primary"
              onClick={handleConfirm}
              disabled={loading || !name.trim()}
            >
              {loading ? 'Importing...' : 'Create dataset'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
