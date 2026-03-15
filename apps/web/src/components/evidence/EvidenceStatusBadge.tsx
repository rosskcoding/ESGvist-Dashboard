/**
 * EvidenceStatusBadge — Status badge with dropdown for changing status.
 *
 * Only users with evidence:status:set permission can change status.
 */

import { useState } from 'react';
import styles from './EvidenceStatusBadge.module.css';

export type EvidenceStatus = 'provided' | 'reviewed' | 'issue' | 'resolved';

export interface EvidenceStatusBadgeProps {
  status: EvidenceStatus;
  onChange?: (newStatus: EvidenceStatus) => void;
  canChange?: boolean;
}

const STATUS_LABELS: Record<EvidenceStatus, string> = {
  provided: 'Provided',
  reviewed: 'Reviewed',
  issue: 'Issue',
  resolved: 'Resolved',
};

const STATUS_COLORS: Record<EvidenceStatus, string> = {
  provided: '#3b82f6', // blue
  reviewed: '#10b981', // green
  issue: '#ef4444', // red
  resolved: '#6b7280', // gray
};

export function EvidenceStatusBadge({
  status,
  onChange,
  canChange = false,
}: EvidenceStatusBadgeProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleChange = (newStatus: EvidenceStatus) => {
    if (onChange) {
      onChange(newStatus);
    }
    setIsOpen(false);
  };

  if (!canChange || !onChange) {
    return (
      <span
        className={styles.badge}
        style={{ backgroundColor: STATUS_COLORS[status] }}
      >
        {STATUS_LABELS[status]}
      </span>
    );
  }

  return (
    <div className={styles.dropdown}>
      <button
        className={styles.badge}
        style={{ backgroundColor: STATUS_COLORS[status] }}
        onClick={() => setIsOpen(!isOpen)}
        type="button"
      >
        {STATUS_LABELS[status]}
        <span className={styles.arrow}>▼</span>
      </button>

      {isOpen && (
        <>
          <div className={styles.backdrop} onClick={() => setIsOpen(false)} />
          <div className={styles.menu}>
            {(Object.keys(STATUS_LABELS) as EvidenceStatus[]).map((s) => (
              <button
                key={s}
                className={`${styles.option} ${s === status ? styles.active : ''}`}
                onClick={() => handleChange(s)}
                type="button"
              >
                <span
                  className={styles.colorDot}
                  style={{ backgroundColor: STATUS_COLORS[s] }}
                />
                {STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}


