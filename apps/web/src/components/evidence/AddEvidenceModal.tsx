/**
 * AddEvidenceModal — Form for creating new evidence.
 *
 * Features:
 * - Evidence type selector (file/link/note)
 * - Sub-anchor fields (table/chart/datapoint)
 * - Period date range
 * - Owner assignment
 */

import { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';
import { IconFileText, IconLink, IconPencil } from '@/components/ui';
import styles from './AddEvidenceModal.module.css';

export interface AddEvidenceData {
  report_id: string;
  scope_type: 'report' | 'section' | 'block';
  scope_id: string;
  type: 'file' | 'link' | 'note';
  title: string;
  description?: string;
  sub_anchor_type?: 'table' | 'chart' | 'datapoint' | 'audit_check_item';
  sub_anchor_key?: string;
  sub_anchor_label?: string;
  owner_user_id?: string;
  period_start?: string;
  period_end?: string;
  version_label?: string;
  asset_id?: string;
  url?: string;
  note_md?: string;
}

export interface AddEvidenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: AddEvidenceData) => Promise<void>;
  reportId: string;
  scopeType: 'report' | 'section' | 'block';
  scopeId: string;
}

export function AddEvidenceModal({
  isOpen,
  onClose,
  onSubmit,
  reportId,
  scopeType,
  scopeId,
}: AddEvidenceModalProps) {
  const [evidenceType, setEvidenceType] = useState<'file' | 'link' | 'note'>('file');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [subAnchorType, setSubAnchorType] = useState('');
  const [subAnchorLabel, setSubAnchorLabel] = useState('');
  const [url, setUrl] = useState('');
  const [note, setNote] = useState('');
  const [versionLabel, setVersionLabel] = useState('');
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title.trim()) return;

    setSubmitting(true);
    
    try {
      const data: AddEvidenceData = {
        report_id: reportId,
        scope_type: scopeType,
        scope_id: scopeId,
        type: evidenceType,
        title: title.trim(),
        description: description.trim() || undefined,
        sub_anchor_type: (subAnchorType && ['table', 'chart', 'datapoint', 'audit_check_item'].includes(subAnchorType) ? subAnchorType : undefined) as 'table' | 'chart' | 'datapoint' | 'audit_check_item' | undefined,
        sub_anchor_label: subAnchorLabel.trim() || undefined,
        version_label: versionLabel.trim() || undefined,
        period_start: periodStart || undefined,
        period_end: periodEnd || undefined,
      };

      if (evidenceType === 'link') {
        data.url = url.trim();
      } else if (evidenceType === 'note') {
        data.note_md = note.trim();
      }
      // TODO: Handle file upload

      await onSubmit(data);
      onClose();
      
      // Reset form
      setTitle('');
      setDescription('');
      setUrl('');
      setNote('');
      setSubAnchorLabel('');
      setVersionLabel('');
      setPeriodStart('');
      setPeriodEnd('');
    } catch (error) {
      console.error('Failed to create evidence:', error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add Evidence">
      <form onSubmit={handleSubmit} className={styles.form}>
        {/* Evidence Type */}
        <div className={styles.field}>
          <label>Evidence Type</label>
          <div className={styles.typeSelector}>
            {(['file', 'link', 'note'] as const).map((type) => (
              <button
                key={type}
                type="button"
                className={`${styles.typeButton} ${
                  evidenceType === type ? styles.active : ''
                }`}
                onClick={() => setEvidenceType(type)}
              >
                {type === 'file' && (
                  <span className={styles.typeLabel}>
                    <span className={styles.typeIcon} aria-hidden="true"><IconFileText size={16} /></span>
                    File
                  </span>
                )}
                {type === 'link' && (
                  <span className={styles.typeLabel}>
                    <span className={styles.typeIcon} aria-hidden="true"><IconLink size={16} /></span>
                    Link
                  </span>
                )}
                {type === 'note' && (
                  <span className={styles.typeLabel}>
                    <span className={styles.typeIcon} aria-hidden="true"><IconPencil size={16} /></span>
                    Note
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Title */}
        <div className={styles.field}>
          <label>Title *</label>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. 'Emissions data 2024'"
            required
          />
        </div>

        {/* Description */}
        <div className={styles.field}>
          <label>Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description"
            className={styles.textarea}
            rows={3}
          />
        </div>

        {/* Type-specific fields */}
        {evidenceType === 'link' && (
          <div className={styles.field}>
            <label>URL *</label>
            <Input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/document.pdf"
              required
            />
          </div>
        )}

        {evidenceType === 'note' && (
          <div className={styles.field}>
            <label>Note *</label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Enter your note (markdown supported)"
              className={styles.textarea}
              rows={6}
              required
            />
          </div>
        )}

        {/* Sub-anchor (optional) */}
        <div className={styles.field}>
          <label>Anchor Point (optional)</label>
          <Select
            value={subAnchorType}
            onChange={(e) => setSubAnchorType(e.target.value)}
            options={[
              { value: '', label: 'Select anchor type' },
              { value: 'table', label: 'Table' },
              { value: 'chart', label: 'Chart' },
              { value: 'datapoint', label: 'Data Point' },
              { value: 'audit_check_item', label: 'Audit Check Item' },
            ]}
          />
        </div>

        {subAnchorType && (
          <div className={styles.field}>
            <label>Anchor Label</label>
            <Input
              value={subAnchorLabel}
              onChange={(e) => setSubAnchorLabel(e.target.value)}
              placeholder="e.g. 'Emissions Table Q4'"
            />
          </div>
        )}

        {/* Period */}
        <div className={styles.fieldRow}>
          <div className={styles.field}>
            <label>Period Start</label>
            <Input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
            />
          </div>
          <div className={styles.field}>
            <label>Period End</label>
            <Input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
            />
          </div>
        </div>

        {/* Version Label */}
        <div className={styles.field}>
          <label>Version Label</label>
          <Input
            value={versionLabel}
            onChange={(e) => setVersionLabel(e.target.value)}
            placeholder="e.g. 'ERP export v2'"
          />
        </div>

        {/* Actions */}
        <div className={styles.actions}>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={submitting || !title.trim()}>
            {submitting ? 'Creating...' : 'Add Evidence'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
