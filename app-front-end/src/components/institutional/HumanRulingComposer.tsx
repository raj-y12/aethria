import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createHumanRuling, type HumanRulingDecision, type OverrideType } from '../../api/decisions';

export default function HumanRulingComposer({
  opportunityId,
  recommendationId,
  readOnly = false,
}: {
  opportunityId: string;
  recommendationId?: string | null;
  readOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<HumanRulingDecision | null>(null);
  const [rationale, setRationale] = useState('');
  const [confidence, setConfidence] = useState(60);
  const [overrideType, setOverrideType] = useState<OverrideType | ''>('');
  const mutation = useMutation({
    mutationFn: () => createHumanRuling(opportunityId, {
      ...(recommendationId ? { recommendation_id: recommendationId } : {}),
      decision: decision!,
      rationale: rationale.trim(),
      investor_confidence: confidence / 100,
      ...(overrideType ? { override_type: overrideType } : {}),
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['institutional', 'opportunity', opportunityId] }),
        queryClient.invalidateQueries({ queryKey: ['institutional', 'evaluation', opportunityId] }),
      ]);
      setDecision(null);
      setRationale('');
    },
  });
  if (readOnly) return null;
  return (
    <section className="mt-phi-6" aria-label="Human ruling">
      <p className="type-label-section">Human ruling</p>
      <div className="mt-phi-3 grid grid-cols-2 gap-phi-2 sm:grid-cols-4">
        {([['invest', 'Invest'], ['advance', 'Advance'], ['monitor', 'Monitor'], ['pass', 'Pass']] as const).map(([value, label]) => (
          <button key={value} type="button" aria-pressed={decision === value} onClick={() => setDecision(value)} className={`type-action border px-3 py-2 ${decision === value ? 'border-oxford bg-oxford text-paper' : 'border-oxford/15 text-oxford'}`}>{label}</button>
        ))}
      </div>
      <textarea aria-label="Ruling rationale" value={rationale} onChange={(event) => setRationale(event.target.value)} rows={3} placeholder="Evidence and judgment supporting this ruling" className="mt-phi-3 w-full resize-none border border-oxford/15 bg-transparent p-3 text-sm leading-relaxed text-oxford" />
      <div className="mt-phi-3 grid gap-phi-3 sm:grid-cols-2">
        <label className="type-action">Investor confidence · {confidence}%<input aria-label="Investor confidence" type="range" min="0" max="100" value={confidence} onChange={(event) => setConfidence(Number(event.target.value))} className="mt-2 block w-full accent-oxford" /></label>
        <label className="type-action">Override attribution<select aria-label="Override attribution" value={overrideType} onChange={(event) => setOverrideType(event.target.value as OverrideType | '')} className="mt-2 block w-full border border-oxford/15 bg-paper px-2 py-2"><option value="">No override</option><option value="evidence_correction">Evidence correction</option><option value="missing_private_evidence">Missing private evidence</option><option value="policy_disagreement">Policy disagreement</option><option value="founder_judgment">Founder judgment</option><option value="market_judgment">Market judgment</option><option value="timing">Timing</option><option value="strategic_exception">Strategic exception</option></select></label>
      </div>
      <button type="button" onClick={() => mutation.mutate()} disabled={!decision || rationale.trim().length < 3 || mutation.isPending} className="type-action mt-phi-4 bg-oxford px-4 py-3 text-paper disabled:cursor-not-allowed disabled:opacity-35">Record ruling</button>
      {mutation.isError ? <p role="alert" className="type-body mt-phi-2 text-signal">The ruling was not recorded. Review the current recommendation and retry.</p> : null}
      {mutation.isSuccess ? <p role="status" className="type-body mt-phi-2 text-oxford/60">Ruling recorded with its evidence and policy context.</p> : null}
    </section>
  );
}

