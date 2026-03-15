/**
 * AuditReadinessDashboard — Audit readiness overview.
 *
 * Shows:
 * - Audit check summary (counts + coverage)
 * - Evidence counters (by type)
 * - Open comment threads count
 * - Generate Audit Pack button
 */

import { useMemo, useState } from 'react';
import { useAuditChecks, useAuditCheckSummary, useCommentThreads, useCreateAuditPack, useAuditPackJob, useDownloadAuditPackArtifact, useEvidenceItems, useReport } from '@/api/hooks';
import { IconDownload, IconFileText, IconLink, IconPackage } from '@/components/ui';
import styles from './AuditReadinessDashboard.module.css';

export interface AuditReadinessDashboardProps {
  reportId: string;
  onGenerateAuditPack?: () => void;
  canGenerate?: boolean;
}

export function AuditReadinessDashboard({
  reportId,
  onGenerateAuditPack,
  canGenerate = false,
}: AuditReadinessDashboardProps) {
  const { data: report } = useReport(reportId);
  const companyId = report?.company_id || '';

  // Audit checks: list and summary
  const { data: auditChecks = [] } = useAuditChecks(companyId, { report_id: reportId });
  const { data: summary } = useAuditCheckSummary(companyId, reportId);
  
  const { data: openThreads } = useCommentThreads(reportId, { thread_status: 'open' });
  const openThreadsCount = openThreads?.total ?? 0;

  const { data: evidenceResp } = useEvidenceItems(companyId, { report_id: reportId, page_size: 100 });
  const evidenceCounts = useMemo(() => {
    const items = evidenceResp?.items ?? [];
    return {
      file: items.filter(e => e.type === 'file').length,
      link: items.filter(e => e.type === 'link').length,
      note: items.filter(e => e.type === 'note').length,
      total: evidenceResp?.total ?? items.length,
    };
  }, [evidenceResp]);

  const createAuditPack = useCreateAuditPack(reportId);
  const downloadAuditPackArtifact = useDownloadAuditPackArtifact();
  const [jobId, setJobId] = useState<string>('');
  const { data: job } = useAuditPackJob(reportId, jobId);

  const statusCounts = summary?.by_status || {};
  const notStarted = statusCounts.not_started || 0;
  const inReview = statusCounts.in_review || 0;
  const reviewed = statusCounts.reviewed || 0;
  const flagged = statusCounts.flagged || 0;
  const needsInfo = statusCounts.needs_info || 0;

  // Filter flagged audit checks for quick view
  const flaggedChecks = useMemo(() => {
    return auditChecks.filter(c => c.status === 'flagged');
  }, [auditChecks]);

  return (
    <div className={styles.dashboard}>
      <h2 className={styles.title}>Audit Readiness</h2>

      {/* Audit Checks */}
      <div className={styles.section}>
        <h3>Audit Checks</h3>
        <div className={styles.counters}>
          <Counter label="Not started" value={notStarted} color="#6b7280" />
          <Counter label="In review" value={inReview} color="#3b82f6" />
          <Counter label="Reviewed" value={reviewed} color="#10b981" />
          <Counter label="Flagged" value={flagged} color="#ef4444" />
        </div>
        <div className={styles.metric} style={{ marginTop: 12 }}>
          <span className={styles.metricValue}>{summary?.coverage_percent ?? 0}%</span>
          <span className={styles.metricLabel}>
            Coverage • needs info: {needsInfo}
          </span>
        </div>
      </div>

      {/* Flagged Issues */}
      {flaggedChecks.length > 0 && (
        <div className={styles.section}>
          <h3>Flagged Issues ({flaggedChecks.length})</h3>
          <div className={styles.issues}>
            {flaggedChecks.slice(0, 5).map((check) => (
              <div key={check.check_id} className={styles.issue}>
                <span style={{ 
                  color: check.severity === 'critical' ? '#dc2626' : 
                         check.severity === 'major' ? '#ea580c' : '#6b7280' 
                }}>
                  [{check.severity?.toUpperCase() || 'N/A'}]
                </span>{' '}
                {check.target_type}: {check.comment?.slice(0, 50) || 'No comment'}
                {check.comment && check.comment.length > 50 ? '...' : ''}
              </div>
            ))}
            {flaggedChecks.length > 5 && (
              <div className={styles.allClear}>
                +{flaggedChecks.length - 5} more flagged items
              </div>
            )}
          </div>
        </div>
      )}

      {/* Comment Threads */}
      <div className={styles.section}>
        <h3>Discussions</h3>
        <div className={styles.metric}>
          <span className={styles.metricValue}>{openThreadsCount}</span>
          <span className={styles.metricLabel}>Open comment threads</span>
        </div>
      </div>

      {/* Evidence */}
      <div className={styles.section}>
        <h3>Evidence</h3>
        <div className={styles.issues}>
          <div className={styles.issue}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconFileText size={16} />
              Files: {evidenceCounts.file}
            </span>
          </div>
          <div className={styles.issue}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconLink size={16} />
              Links: {evidenceCounts.link}
            </span>
          </div>
          <div className={styles.issue}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              <IconFileText size={16} />
              Notes: {evidenceCounts.note}
            </span>
          </div>
          {evidenceCounts.total === 0 && <div className={styles.allClear}>No evidence items yet</div>}
        </div>
      </div>

      {/* Generate Button */}
      {canGenerate && (
        <button
          className={styles.generateButton}
          onClick={async () => {
            if (onGenerateAuditPack) {
              onGenerateAuditPack();
              return;
            }
            const job = await createAuditPack.mutateAsync({});
            setJobId(job.job_id);
          }}
          disabled={createAuditPack.isPending}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
            <IconPackage size={18} />
            Generate Audit Pack
          </span>
        </button>
      )}

      {job ? (
        <div className={styles.section}>
          <h3>Audit Pack Status</h3>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{job.status}</span>
            <span className={styles.metricLabel}>
              {job.error_message ? `Error: ${job.error_message}` : `${job.artifacts.length} artifacts`}
            </span>
          </div>
          {job.artifacts.length > 0 && (
            <div style={{ marginTop: 10 }}>
              {job.artifacts.map((a) => (
                <div key={a.artifact_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginTop: 6 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {a.filename}
                  </span>
                  <button
                    className={styles.generateButton}
                    onClick={() =>
                      downloadAuditPackArtifact.mutate({
                        reportId,
                        jobId: job.job_id,
                        artifactId: a.artifact_id,
                        filename: a.filename,
                      })
                    }
                    disabled={downloadAuditPackArtifact.isPending}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                      <IconDownload size={16} />
                      Download
                    </span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function Counter({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={styles.counter}>
      <div className={styles.counterValue} style={{ color }}>
        {value}
      </div>
      <div className={styles.counterLabel}>{label}</div>
    </div>
  );
}
