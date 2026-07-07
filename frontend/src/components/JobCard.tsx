import type { Job, JobAction } from '../types';

interface JobCardProps {
  job: Job;
  title?: string;
  onAction: (jobId: string, action: JobAction) => void;
}

function actionFor(status: string): JobAction | null {
  if (status === 'running' || status === 'queued') return 'pause';
  if (status === 'paused' || status === 'failed') return 'resume';
  return null;
}

export function JobCard({ job, title, onAction }: JobCardProps) {
  const action = actionFor(job.status);
  return (
    <article className="job-card">
      <header>
        <div>
          <p className="eyebrow">{job.backend}</p>
          <h3>{title ?? `Job ${job.id.slice(0, 8)}`}</h3>
        </div>
        <span className={`status status-${job.status}`}>{job.status}</span>
      </header>
      <div className="progress-meta">
        <span>
          {job.progress.processed} / {job.progress.total} chunks
        </span>
        <strong>{Math.round(job.progress.percent)}%</strong>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-label={`${title ?? 'Audiobook'} progress`}
        aria-valuenow={job.progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span style={{ width: `${job.progress.percent}%` }} />
      </div>
      <p className="job-settings">
        {job.voice} · {job.chunking_mode} · {job.character_limit.toLocaleString()} chars
      </p>
      {job.error && <p className="inline-error">{job.error}</p>}
      <footer>
        {action && (
          <button className="text-button" onClick={() => onAction(job.id, action)}>
            {action === 'pause' ? 'Pause' : 'Resume'}
          </button>
        )}
        {!['completed', 'cancelled'].includes(job.status) && (
          <button className="text-button danger" onClick={() => onAction(job.id, 'cancel')}>
            Cancel
          </button>
        )}
        {job.output_available && (
          <a className="download-button" href={`/api/v1/jobs/${job.id}/download`}>
            Download MP3
          </a>
        )}
      </footer>
    </article>
  );
}
