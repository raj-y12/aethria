import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createHumanRuling, type HumanRulingDecision, type OverrideType } from '../../api/decisions';
import type { RecommendationState } from '../../api/evaluations';
import {
  defaultRulingForRecommendation,
  rulingAlignsWithRecommendation,
} from '../../lib/recommendationSemantics';

const DECISION_OPTIONS = [
  { value: 'advance', label: 'Advance' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'pass', label: 'Pass' },
  { value: 'invest', label: 'Invest' },
] satisfies Array<{ value: HumanRulingDecision; label: string }>;

export default function HumanRulingComposer({
  opportunityId,
  recommendationId,
  recommendedDecision,
  readOnly = false,
}: {
  opportunityId: string;
  recommendationId?: string | null;
  recommendedDecision?: RecommendationState | null;
  readOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<HumanRulingDecision | null>(
    defaultRulingForRecommendation(recommendedDecision),
  );
  const [rationale, setRationale] = useState('');
  const [overrideType, setOverrideType] = useState<OverrideType | ''>('');

  useEffect(() => {
    setDecision(defaultRulingForRecommendation(recommendedDecision));
    setRationale('');
    setOverrideType('');
  }, [opportunityId, recommendationId, recommendedDecision]);

  // The override reason only exists when the ruling disagrees with the system's lean.
  const disagreesWithSystem = Boolean(
    decision
      && recommendedDecision
      && !rulingAlignsWithRecommendation(recommendedDecision, decision),
  );

  const mutation = useMutation({
    mutationFn: () => createHumanRuling(opportunityId, {
      ...(recommendationId ? { recommendation_id: recommendationId } : {}),
      decision: decision!,
      rationale: rationale.trim(),
      ...(disagreesWithSystem && overrideType ? { override_type: overrideType } : {}),
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['institutional', 'opportunity'] }),
        queryClient.invalidateQueries({ queryKey: ['institutional', 'evaluation', opportunityId] }),
        queryClient.invalidateQueries({ queryKey: ['institutional', 'rulings', opportunityId] }),
        queryClient.invalidateQueries({ queryKey: ['institutional', 'actions', opportunityId] }),
      ]);
      setDecision(null);
      setRationale('');
      setOverrideType('');
    },
  });
  if (readOnly) return null;
  return (
    <section className="memoDecisionCall" aria-label="Make your ruling">
      <div className="memoDecisionCallHead">
        <p className="memoDecisionEyebrow">Make your call</p>
        <p className="memoDecisionMeta">Your rationale becomes part of the permanent decision record.</p>
      </div>
      <div className="memoRulingPanel">
        <div className="memoDecisionChoices" role="group" aria-label="Choose final ruling">
          {DECISION_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              aria-pressed={decision === value}
              onClick={() => setDecision(value)}
              disabled={mutation.isPending}
              className={`memoDecisionChoice memoDecisionChoice--${value}`}
            >
              {label}
            </button>
          ))}
        </div>
        <textarea
          aria-label="Ruling rationale"
          value={rationale}
          onChange={(event) => setRationale(event.target.value)}
          disabled={mutation.isPending}
          rows={2}
          placeholder="Rationale — what evidence or judgment supports this call?"
          className="memoRulingTextarea"
        />
        {disagreesWithSystem ? (
          <label className="type-action mt-phi-4 block border-t border-oxford/10 pt-phi-3">
            You're going against Aethria's lean — why?
            <select aria-label="Override attribution" value={overrideType} onChange={(event) => setOverrideType(event.target.value as OverrideType | '')} className="mt-2 block w-full max-w-sm border border-oxford/15 bg-paper px-2 py-2">
              <option value="">Prefer not to say</option>
              <option value="evidence_correction">The evidence is wrong</option>
              <option value="missing_private_evidence">I know something Aethria doesn't</option>
              <option value="policy_disagreement">I disagree with the scoring policy</option>
              <option value="founder_judgment">My read on the founders</option>
              <option value="market_judgment">My read on the market</option>
              <option value="timing">Timing</option>
              <option value="strategic_exception">Strategic exception</option>
            </select>
          </label>
        ) : null}
        <div className="memoRulingSubmitRow">
          <button type="button" onClick={() => mutation.mutate()} disabled={!decision || rationale.trim().length < 5 || mutation.isPending} className="memoRulingSubmit">{mutation.isPending ? 'Committing…' : 'Commit ruling'}</button>
          {mutation.isError ? <span role="alert" className="memoRulingError">The ruling was not recorded. Review the recommendation and try again.</span> : null}
          {mutation.isSuccess ? <span role="status" className="type-body text-oxford/60">Your ruling is recorded.</span> : null}
        </div>
      </div>
    </section>
  );
}
