import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { requestEvidenceRefresh, setOpportunityServiceLevel, type MonitoringStatus, type RefreshReason } from '../../api/monitoring';
import { ApiError } from '../../api/client';

const SERVICE_LEVELS = [['0', 'Archive'], ['1', 'Discovered'], ['2', 'Active review'], ['3', 'Monitor'], ['4', 'Diligence'], ['5', 'Portfolio']] as const;

export default function MonitoringControl({ opportunityId, status, serviceLevel, readOnly = false }: { opportunityId: string; status: MonitoringStatus; serviceLevel: number; readOnly?: boolean }) {
  const queryClient = useQueryClient();
  const [level, setLevel] = useState(String(serviceLevel));
  const [lifecycleReason, setLifecycleReason] = useState('');
  const [refreshReason, setRefreshReason] = useState<RefreshReason>('human_request');
  const [estimatedCost, setEstimatedCost] = useState(0.25);
  const invalidate = () => Promise.all([queryClient.invalidateQueries({ queryKey: ['institutional', 'monitoring', opportunityId] }), queryClient.invalidateQueries({ queryKey: ['institutional', 'opportunity', opportunityId] })]);
  const serviceMutation = useMutation({ mutationFn: () => setOpportunityServiceLevel(opportunityId, { service_level: Number(level), lifecycle_reason: lifecycleReason.trim() }), onSuccess: invalidate });
  const refreshMutation = useMutation({ mutationFn: () => requestEvidenceRefresh(opportunityId, { reason: refreshReason, request_key: crypto.randomUUID(), envelope: { estimated_cost_usd: estimatedCost } }), onSuccess: invalidate });
  const errorText = (error: unknown) => error instanceof ApiError && error.status === 429 ? 'Refresh budget exceeded. No work was queued.' : 'The monitoring change was not accepted.';
  return (
    <section aria-label="Monitoring control">
      <div className="flex items-baseline justify-between gap-phi-4"><p className="type-label-section">Monitoring</p><span className="type-status">Service level {serviceLevel}</span></div>
      <pre className="mt-phi-3 max-h-40 overflow-auto border-y border-oxford/10 py-phi-3 font-mono text-xs leading-relaxed text-oxford/55">{JSON.stringify(status, null, 2)}</pre>
      {!readOnly ? (
        <div className="mt-phi-5 grid gap-phi-6 lg:grid-cols-2">
          <div><p className="type-label-section">Attention level</p><select aria-label="Service level" value={level} onChange={(event) => setLevel(event.target.value)} className="mt-phi-2 w-full border border-oxford/15 bg-paper px-3 py-2 type-action">{SERVICE_LEVELS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><textarea aria-label="Lifecycle reason" value={lifecycleReason} onChange={(event) => setLifecycleReason(event.target.value)} rows={2} placeholder="Why this attention level changed" className="mt-phi-2 w-full resize-none border border-oxford/15 bg-transparent p-3 text-sm text-oxford" /><button type="button" onClick={() => serviceMutation.mutate()} disabled={lifecycleReason.trim().length < 3 || serviceMutation.isPending} className="type-action mt-phi-2 border border-oxford/15 px-3 py-2 disabled:opacity-35">Update service level</button></div>
          <div><p className="type-label-section">Evidence refresh</p><select aria-label="Refresh reason" value={refreshReason} onChange={(event) => setRefreshReason(event.target.value as RefreshReason)} className="mt-phi-2 w-full border border-oxford/15 bg-paper px-3 py-2 type-action"><option value="human_request">Human request</option><option value="missing_policy_evidence">Missing policy evidence</option><option value="stale_decisive_evidence">Stale decisive evidence</option><option value="monitor_due">Monitor due</option><option value="verified_external_signal">Verified external signal</option></select><label className="type-action mt-phi-3 block">Maximum estimated cost · ${estimatedCost.toFixed(2)}<input aria-label="Maximum estimated refresh cost" type="range" min="0.05" max="2" step="0.05" value={estimatedCost} onChange={(event) => setEstimatedCost(Number(event.target.value))} className="mt-2 block w-full accent-oxford" /></label><button type="button" onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending} className="type-action mt-phi-2 bg-oxford px-3 py-2 text-paper disabled:opacity-35">Reserve budget and refresh</button>{refreshMutation.data ? <p role="status" className="type-body mt-phi-2 text-oxford/60">Refresh accepted · job {refreshMutation.data.job_id} · reservation recorded.</p> : null}</div>
        </div>
      ) : null}
      {serviceMutation.isError || refreshMutation.isError ? <p role="alert" className="type-body mt-phi-3 text-signal">{errorText(serviceMutation.error || refreshMutation.error)}</p> : null}
    </section>
  );
}

