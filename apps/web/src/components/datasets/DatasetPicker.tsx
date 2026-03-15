/**
 * DatasetPicker component.
 * 
 * Allows selecting an existing dataset or creating a new one.
 */

import { useState, useEffect } from 'react';
import { listDatasets, type DatasetListItem } from '@/api/datasets';
import { Button } from '@/components/ui/Button';
import styles from './DatasetPicker.module.css';

interface DatasetPickerProps {
  value?: string | null;
  onChange: (datasetId: string | null) => void;
  onCreateNew?: () => void;
  allowNull?: boolean;
}

export function DatasetPicker({
  value,
  onChange,
  onCreateNew,
  allowNull = true,
}: DatasetPickerProps) {
  const [datasets, setDatasets] = useState<DatasetListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listDatasets({ limit: 100 });
      setDatasets(response.items);
    } catch (err) {
      setError('Failed to load datasets');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <label className={styles.label}>Data source</label>
        {onCreateNew && (
          <Button variant="secondary" size="sm" onClick={onCreateNew}>
            + Create new
          </Button>
        )}
      </div>

      {loading && <div className={styles.loading}>Loading...</div>}
      
      {error && <div className={styles.error}>{error}</div>}

      {!loading && !error && (
        <select
          className={styles.select}
          value={value || ''}
          onChange={(e) => onChange(e.target.value || null)}
        >
          {allowNull && <option value="">— Manual input —</option>}
          {datasets.map((ds) => (
            <option key={ds.dataset_id} value={ds.dataset_id}>
              {ds.name} ({ds.row_count} rows, {ds.column_count} columns)
            </option>
          ))}
        </select>
      )}

      {value && (
        <div className={styles.info}>
          {(() => {
            const selected = datasets.find((d) => d.dataset_id === value);
            if (!selected) return null;
            return (
              <div className={styles.selectedInfo}>
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Name:</span>
                  <span>{selected.name}</span>
                </div>
                {selected.description && (
                  <div className={styles.infoRow}>
                    <span className={styles.infoLabel}>Description:</span>
                    <span>{selected.description}</span>
                  </div>
                )}
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Data:</span>
                  <span>
                    {selected.row_count} rows × {selected.column_count} columns
                  </span>
                </div>
                <div className={styles.infoRow}>
                  <span className={styles.infoLabel}>Version:</span>
                  <span>rev {selected.current_revision}</span>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}
