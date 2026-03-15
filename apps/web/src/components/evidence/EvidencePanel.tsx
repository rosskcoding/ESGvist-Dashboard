/**
 * EvidencePanel — List of evidence items with filters.
 *
 * Features:
 * - Filter by type (file/link/note)
 * - Pagination
 * - Add new evidence button
 */

import { useState } from 'react';
import { useEvidenceItems } from '@/api/hooks';
import type { EvidenceItem as EvidenceItemDTO, EvidenceType } from '@/types/api';
import styles from './EvidencePanel.module.css';
import { IconLink, IconPaperclip } from '@/components/ui';

export interface EvidencePanelProps {
  companyId: string;
  reportId?: string;
  scopeType?: 'report' | 'section' | 'block';
  scopeId?: string;
  onAddEvidence?: () => void;
  canCreate?: boolean;
}

export function EvidencePanel({
  companyId,
  reportId,
  scopeType,
  scopeId,
  onAddEvidence,
  canCreate = false,
}: EvidencePanelProps) {
  const [typeFilter, setTypeFilter] = useState<'all' | EvidenceType>('all');

  const { data: evidenceResp, isLoading } = useEvidenceItems(companyId, {
    report_id: reportId,
    scope_type: scopeType,
    scope_id: scopeId,
    evidence_type: typeFilter === 'all' ? undefined : typeFilter,
    page_size: 100,
  });
  const evidences = evidenceResp?.items ?? [];
  const total = evidenceResp?.total ?? evidences.length;

  const counts = {
    all: total,
    file: evidences.filter((e) => e.type === 'file').length,
    link: evidences.filter((e) => e.type === 'link').length,
    note: evidences.filter((e) => e.type === 'note').length,
  } as const;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3>Evidence ({counts.all})</h3>
        {canCreate && (
          <button className={styles.addButton} onClick={onAddEvidence}>
            + Add Evidence
          </button>
        )}
      </div>

      {/* Type Filter */}
      <div className={styles.filters}>
        <div className={styles.statusTabs}>
          {Object.entries(counts).map(([type, count]) => (
            <button
              key={type}
              className={`${styles.statusTab} ${
                typeFilter === type ? styles.active : ''
              }`}
              onClick={() => setTypeFilter(type as 'all' | EvidenceType)}
            >
              {type === 'all' ? 'All' : type.charAt(0).toUpperCase() + type.slice(1)}
              <span className={styles.count}>({count})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Evidence List */}
      <div className={styles.list}>
        {isLoading ? (
          <div className={styles.loading}>Loading...</div>
        ) : evidences.length === 0 ? (
          <div className={styles.empty}>
            No evidence items found.
            {canCreate && (
              <button className={styles.emptyAction} onClick={onAddEvidence}>
                Add your first evidence
              </button>
            )}
          </div>
        ) : (
          evidences.map((evidence) => (
            <EvidenceCard key={evidence.evidence_id} evidence={evidence} />
          ))
        )}
      </div>
    </div>
  );
}

function EvidenceCard({ evidence }: { evidence: EvidenceItemDTO }) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <h4 className={styles.cardTitle}>{evidence.title}</h4>
        <span className={styles.statusBadge}>{evidence.type}</span>
      </div>

      {evidence.description ? (
        <p className={styles.description}>{evidence.description}</p>
      ) : null}

      <div className={styles.metadata}>
        <span className={styles.metaItem}>
          <strong>Type:</strong> {evidence.type}
        </span>
        <span className={styles.metaItem}>
          <strong>Visibility:</strong> {evidence.visibility}
        </span>
        {evidence.locale ? (
          <span className={styles.metaItem}>
            <strong>Locale:</strong> {evidence.locale}
          </span>
        ) : null}
      </div>

      {evidence.type === 'link' && evidence.url ? (
        <div className={styles.anchor}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <IconLink size={16} />
            {evidence.url}
          </span>
        </div>
      ) : null}
      {evidence.type === 'file' && evidence.asset_id ? (
        <div className={styles.anchor}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <IconPaperclip size={16} />
            Asset: {evidence.asset_id}
          </span>
        </div>
      ) : null}
    </div>
  );
}
