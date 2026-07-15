import type { SystemStatus } from '../../api/system';

export type ExecutionReadiness = 'healthy' | 'degraded' | 'blocked' | 'unavailable';

function countStatus(counts: Record<string, number>, status: string): number {
  return Object.entries(counts).reduce((sum, [key, value]) => key.endsWith(`:${status}`) ? sum + Number(value || 0) : sum, 0);
}

export function deriveExecutionReadiness(status: SystemStatus | null | undefined): ExecutionReadiness {
  if (!status) return 'unavailable';
  if (status.durable_jobs.required && !status.durable_jobs.ready) return 'blocked';
  const counts = status.durable_jobs.counts;
  if (countStatus(counts, 'dead_letter') > 0 || countStatus(counts, 'retry_wait') > 0) return 'degraded';
  return 'healthy';
}

function Readout({ label, value, tone = 'default' }: { label: string; value: number; tone?: 'default' | 'warning' }) {
  return (
    <div className="flex min-w-[4.5rem] flex-col gap-phi-1" aria-label={label}>
      <span className={`type-data text-xl tabular-nums ${tone === 'warning' && value > 0 ? 'text-escalation' : 'text-oxford'}`}>{value}</span>
      <span className="type-label-section">{label}</span>
    </div>
  );
}

export default function ExecutionReadinessPanel({
  status,
  loading = false,
  compact = false,
}: {
  status?: SystemStatus | null;
  loading?: boolean;
  compact?: boolean;
}) {
  const readiness = loading ? 'unavailable' : deriveExecutionReadiness(status);
  const counts = status?.durable_jobs.counts ?? {};
  const queued = countStatus(counts, 'accepted') + countStatus(counts, 'queued');
  const running = countStatus(counts, 'running');
  const retryWait = countStatus(counts, 'retry_wait');
  const deadLetter = countStatus(counts, 'dead_letter');
  const outbox = Number(counts['outbox:pending'] ?? 0);
  const label = readiness.replace(/^./, (character) => character.toUpperCase());
  const stateTone = readiness === 'blocked' || readiness === 'degraded' ? 'text-escalation' : readiness === 'healthy' ? 'text-oxford' : 'text-oxford/55';

  return (
    <section className={compact ? 'border-t border-oxford/[0.06] py-phi-4' : 'border-y border-oxford/10 bg-paper px-phi-5 py-phi-4'} aria-label="Execution readiness">
      <div className="flex flex-wrap items-start justify-between gap-phi-4">
        <div>
          <p className="type-label-section">Execution plane</p>
          <div className="mt-phi-2 flex items-center gap-phi-2"><span className={`h-1.5 w-1.5 rounded-none ${readiness === 'healthy' ? 'bg-oxford' : readiness === 'unavailable' ? 'bg-oxford/25' : 'bg-escalation'}`} aria-hidden /><span className={`type-status ${stateTone}`}>{label}</span></div>
          <p className="type-body mt-phi-2 max-w-2xl text-oxford/55">
            {loading ? 'Reading durable execution readiness…'
              : readiness === 'blocked' ? 'Durable execution is required, but its worker and repository are not ready. New work must remain blocked.'
                : readiness === 'degraded' ? 'The worker is ready, but retrying or terminal jobs need operational attention.'
                  : readiness === 'healthy' ? (status?.durable_jobs.required ? 'Durable execution is ready. Queue counts are persisted across restarts.' : 'The development execution path is ready; durable jobs are not required in this environment.')
                    : 'Execution readiness is unavailable. Agent enablement alone does not prove that work can run.'}
          </p>
          {readiness === 'blocked' && status?.durable_jobs.error ? <p className="type-meta mt-phi-2 text-escalation">Reason: {status.durable_jobs.error.replace(/_/g, ' ')}</p> : null}
        </div>
        {status ? <span className="type-meta">{status.durable_jobs.required ? 'Durable required' : 'Development mode'}</span> : null}
      </div>
      {status ? <div className="mt-phi-4 flex flex-wrap gap-x-phi-6 gap-y-phi-3 border-t border-oxford/[0.06] pt-phi-4">
        <Readout label="Queued" value={queued} /><Readout label="Running" value={running} /><Readout label="Retry wait" value={retryWait} tone="warning" /><Readout label="Dead letter" value={deadLetter} tone="warning" /><Readout label="Outbox" value={outbox} />
      </div> : null}
    </section>
  );
}
