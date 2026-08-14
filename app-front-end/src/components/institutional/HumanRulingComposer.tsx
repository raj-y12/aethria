import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createHumanRuling, type HumanRulingDecision, type OverrideType } from '../../api/decisions';
import type { RecommendationState } from '../../api/evaluations';
import {
  defaultRulingForRecommendation,
  recommendationSemantics,
  rulingAlignsWithRecommendation,
} from '../../lib/recommendationSemantics';
import RulingConfirmation from './RulingConfirmation';

const DECISION_OPTIONS = [
  { value: 'advance', label: 'Advance' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'pass', label: 'Pass' },
] satisfies Array<{ value: HumanRulingDecision; label: string }>;

/** Attribution options, opt-out last — the learning loop's best signal should not be the default. */
const OVERRIDE_OPTIONS = [
  { value: 'evidence_correction', label: 'The evidence is wrong' },
  { value: 'missing_private_evidence', label: "I know something Aethria doesn't" },
  { value: 'policy_disagreement', label: 'I disagree with the scoring policy' },
  { value: 'founder_judgment', label: 'My read on the founders' },
  { value: 'market_judgment', label: 'My read on the market' },
  { value: 'timing', label: 'Timing' },
  { value: 'strategic_exception', label: 'Strategic exception' },
] satisfies Array<{ value: OverrideType; label: string }>;

/** Placeholder value — never submitted; keeps the select from pre-answering. */
const UNANSWERED = '__unanswered';

export default function HumanRulingComposer({
  opportunityId,
  recommendationId,
  recommendedDecision,
  companyName = null,
  onRecorded,
  readOnly = false,
}: {
  opportunityId: string;
  recommendationId?: string | null;
  recommendedDecision?: RecommendationState | null;
  /** Named in the confirmation so the operator sees who they are ruling on. */
  companyName?: string | null;
  /** Route onward once the ruling lands — typically closing the memo. */
  onRecorded?: () => void;
  readOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<HumanRulingDecision | null>(
    defaultRulingForRecommendation(recommendedDecision),
  );
  const [rationale, setRationale] = useState('');
  // `null` = not answered yet; `''` = explicitly declined (field is omitted either way).
  const [overrideType, setOverrideType] = useState<OverrideType | '' | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    setDecision(defaultRulingForRecommendation(recommendedDecision));
    setRationale('');
    setOverrideType(null);
    setConfirming(false);
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
        queryClient.invalidateQueries({ queryKey: ['startups', 'list'] }),
        queryClient.invalidateQueries({ queryKey: ['portfolio-decision-history'] }),
        queryClient.invalidateQueries({ queryKey: ['portfolio-positions'] }),
      ]);
      // The confirmation stays open on the `recorded` phase; it owns the reset.
    },
  });

  const committed = mutation.isSuccess;

  const closeConfirmation = () => {
    setConfirming(false);
    if (committed) {
      mutation.reset();
      setDecision(defaultRulingForRecommendation(recommendedDecision));
      setRationale('');
      setOverrideType(null);
    }
  };
  if (readOnly) return null;
  return (
    <section id="memo-ruling" className="memoDecisionCall" aria-label="Make your ruling">
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
            <select aria-label="Override attribution" value={overrideType ?? UNANSWERED} onChange={(event) => setOverrideType(event.target.value === UNANSWERED ? null : (event.target.value as OverrideType | ''))} className="mt-2 block min-h-[44px] w-full max-w-sm border border-oxford/15 bg-paper px-2 py-2">
              <option value={UNANSWERED} disabled>Choose a reason…</option>
              {OVERRIDE_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
              <option value="">Prefer not to say</option>
            </select>
          </label>
        ) : null}
        <div className="memoRulingSubmitRow">
          <button type="button" onClick={() => setConfirming(true)} disabled={!decision || rationale.trim().length < 5 || mutation.isPending} className="memoRulingSubmit">Review ruling</button>
          {mutation.isError ? (
            <span role="alert" className="memoRulingError">
              {mutation.error instanceof Error && mutation.error.message
                ? `The ruling was not recorded — ${mutation.error.message}`
                : 'The ruling was not recorded. Your rationale is still here; try again.'}
            </span>
          ) : null}
        </div>
      </div>
      {decision ? (
        <RulingConfirmation
          open={confirming}
          phase={committed ? 'recorded' : 'confirm'}
          companyName={companyName}
          decision={decision}
          rationale={rationale.trim()}
          systemLean={recommendedDecision ? recommendationSemantics(recommendedDecision).label : null}
          diverges={disagreesWithSystem}
          overrideLabel={
            OVERRIDE_OPTIONS.find((option) => option.value === overrideType)?.label ?? null
          }
          busy={mutation.isPending}
          onCancel={closeConfirmation}
          onConfirm={() => mutation.mutate()}
          onDone={onRecorded ? () => { closeConfirmation(); onRecorded(); } : undefined}
        />
      ) : null}
    </section>
  );
}
