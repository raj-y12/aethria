import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchOpportunityByLegacyStartup } from '../../api/identity';
import {
  createOutcome,
  fetchOutcomeCoverage,
  fetchOutcomes,
  type OutcomeType,
  type OutcomeValence,
} from '../../api/channelsOutcomes';

function coveragePercent(coverage: Awaited<ReturnType<typeof fetchOutcomeCoverage>> | undefined): number {
  const raw = Number(coverage?.coverage_ratio ?? coverage?.coverage_rate ?? 0);
  return Math.round((raw <= 1 ? raw * 100 : raw));
}

function readable(value: string): string {
  return value.replace(/_/g, ' ').replace(/^./, (character) => character.toUpperCase());
}

const OUTCOME_TYPES: OutcomeType[] = ['financing', 'revenue_milestone', 'customer_milestone', 'product_launch', 'acquisition', 'shutdown', 'leadership_change', 'follow_on_decision', 'other'];
const VALENCES: OutcomeValence[] = ['positive', 'negative', 'neutral', 'mixed'];

export default function OutcomePanel({ startupId }: { startupId: string }) {
  const queryClient = useQueryClient();
  const [outcomeType, setOutcomeType] = useState<OutcomeType>('financing');
  const [valence, setValence] = useState<OutcomeValence>('positive');
  const [summary, setSummary] = useState('');
  const [materiality, setMateriality] = useState(3);
  const [verificationState, setVerificationState] = useState<'unverified' | 'verified' | 'disputed'>('unverified');
  const [effectiveAt, setEffectiveAt] = useState('');
  const opportunity = useQuery({
    queryKey: ['institutional', 'opportunity', 'legacy', startupId],
    queryFn: () => fetchOpportunityByLegacyStartup(startupId),
    enabled: Boolean(startupId),
    retry: false,
  });
  const companyId = opportunity.data?.company_id;
  const outcomes = useQuery({
    queryKey: ['outcomes', companyId],
    queryFn: () => fetchOutcomes(companyId!),
    enabled: Boolean(companyId),
    retry: false,
  });
  const coverage = useQuery({
    queryKey: ['outcomes', 'coverage'],
    queryFn: fetchOutcomeCoverage,
    retry: false,
  });
  const recordOutcome = useMutation({
    mutationFn: () => createOutcome(companyId!, {
      opportunity_id: opportunity.data!.opportunity_id,
      outcome_type: outcomeType,
      valence,
      summary: summary.trim(),
      materiality,
      verification_state: verificationState,
      ...(effectiveAt ? { effective_at: new Date(`${effectiveAt}T12:00:00Z`).toISOString() } : {}),
    }),
    onSuccess: async () => {
      setSummary('');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['outcomes', companyId] }),
        queryClient.invalidateQueries({ queryKey: ['outcomes', 'coverage'] }),
        queryClient.invalidateQueries({ queryKey: ['fund-intelligence'] }),
      ]);
    },
  });
  const percentage = coveragePercent(coverage.data);

  return (
    <section className="border-y border-oxford/10 bg-paper py-phi-5" aria-label="Outcome learning">
      <header className="flex flex-wrap items-start justify-between gap-phi-4">
        <div><p className="type-label-section">Institutional learning</p><h3 className="mt-phi-2 font-display text-2xl font-medium text-oxford">Company outcome record</h3><p className="type-body mt-phi-2 max-w-2xl text-oxford/65">Observed outcomes are attributed to the canonical company. They inform governed proposals; they do not prove a decision caused the result.</p></div>
        {coverage.isSuccess ? <div className="text-right"><span className="type-data text-2xl text-oxford">{percentage}% coverage</span><p className="type-meta mt-1">{Number(coverage.data?.observed_opportunity_count ?? coverage.data?.companies_with_outcomes ?? 0)} of {Number(coverage.data?.eligible_opportunity_count ?? coverage.data?.total_companies ?? 0)} eligible records</p></div> : null}
      </header>

      {opportunity.isLoading ? <p className="type-body mt-phi-4 text-oxford/65">Resolving canonical company…</p> : opportunity.isError || !opportunity.data ? <p role="alert" className="type-body mt-phi-4 text-signal">Outcome recording is unavailable until this deal has a canonical company record.</p> : (
        <div className="mt-phi-5 grid gap-phi-7 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
          <div>
            <p className="type-label-section">Outcome timeline</p>
            {outcomes.isLoading ? <p className="type-body mt-phi-3 text-oxford/65">Loading observations…</p> : outcomes.isError ? <p role="alert" className="type-body mt-phi-3 text-signal">Outcome observations could not be loaded.</p> : (outcomes.data?.length ?? 0) === 0 ? <p className="type-body mt-phi-3 text-oxford/65">No attributed outcomes have been recorded for this company.</p> : <ol className="mt-phi-3 divide-y divide-oxford/10 border-t border-oxford/10">{outcomes.data!.map((entry) => <li key={entry.outcome.outcome_observation_id} className="py-phi-3"><div className="flex flex-wrap items-baseline justify-between gap-phi-3"><span className="type-status">{readable(entry.outcome.outcome_type)}</span><span className="type-meta">{entry.outcome.verification_state ?? 'unverified'} · materiality {entry.outcome.materiality}/5</span></div><p className="type-body mt-phi-2 text-oxford/70">{entry.outcome.summary}</p><p className="type-meta mt-phi-2">Observed {new Date(entry.outcome.observed_at).toLocaleDateString()}</p></li>)}</ol>}
          </div>

          <form onSubmit={(event) => { event.preventDefault(); recordOutcome.mutate(); }} className="border-l border-oxford/10 pl-phi-5">
            <p className="type-label-section">Record observation</p>
            <div className="mt-phi-3 grid gap-phi-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <label className="type-action">Outcome type<select aria-label="Outcome type" value={outcomeType} onChange={(event) => setOutcomeType(event.target.value as OutcomeType)} className="mt-phi-2 block w-full border border-oxford/15 bg-paper px-3 py-2">{OUTCOME_TYPES.map((value) => <option key={value} value={value}>{readable(value)}</option>)}</select></label>
              <label className="type-action">Valence<select aria-label="Outcome valence" value={valence} onChange={(event) => setValence(event.target.value as OutcomeValence)} className="mt-phi-2 block w-full border border-oxford/15 bg-paper px-3 py-2">{VALENCES.map((value) => <option key={value} value={value}>{readable(value)}</option>)}</select></label>
              <label className="type-action">Outcome materiality<select aria-label="Outcome materiality" value={materiality} onChange={(event) => setMateriality(Number(event.target.value))} className="mt-phi-2 block w-full border border-oxford/15 bg-paper px-3 py-2">{[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value} / 5</option>)}</select></label>
              <label className="type-action">Verification<select aria-label="Outcome verification" value={verificationState} onChange={(event) => setVerificationState(event.target.value as typeof verificationState)} className="mt-phi-2 block w-full border border-oxford/15 bg-paper px-3 py-2"><option value="unverified">Unverified</option><option value="verified">Verified</option><option value="disputed">Disputed</option></select></label>
            </div>
            <label className="type-action mt-phi-3 block">Effective date <span className="text-oxford/65">optional</span><input aria-label="Outcome effective date" type="date" value={effectiveAt} onChange={(event) => setEffectiveAt(event.target.value)} className="mt-phi-2 block w-full border border-oxford/15 bg-transparent px-3 py-2" /></label>
            <label htmlFor={`outcome-summary-${startupId}`} className="type-action mt-phi-3 block">Outcome summary</label>
            <textarea id={`outcome-summary-${startupId}`} aria-label="Outcome summary" value={summary} onChange={(event) => setSummary(event.target.value)} rows={4} maxLength={2000} placeholder="Observable event and source confidence" className="mt-phi-2 w-full resize-none border border-oxford/15 bg-transparent p-3 text-sm leading-relaxed text-oxford" />
            <button type="submit" disabled={!companyId || summary.trim().length < 3 || recordOutcome.isPending} className="type-action mt-phi-3 bg-oxford px-4 py-3 text-paper disabled:opacity-35">Record outcome</button>
            {recordOutcome.isSuccess ? <p role="status" className="type-body mt-phi-2 text-oxford/65">Outcome recorded with operator attribution.</p> : null}
            {recordOutcome.isError ? <p role="alert" className="type-body mt-phi-2 text-signal">The outcome was not recorded. Confirm the company and try again.</p> : null}
          </form>
        </div>
      )}
      {coverage.data?.limitations?.length ? <p className="type-meta mt-phi-5 border-t border-oxford/10 pt-phi-3">Coverage limitation: {coverage.data.limitations.join(' ')}</p> : null}
    </section>
  );
}
