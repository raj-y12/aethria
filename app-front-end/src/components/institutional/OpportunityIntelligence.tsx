import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchCompany,
  fetchObservations,
  fetchOpportunityByLegacyStartup,
} from '../../api/identity';
import { fetchEvidenceLedger } from '../../api/evidence';
import { evaluateOpportunity, fetchCurrentEvaluation } from '../../api/evaluations';
import { listWorkflowActions } from '../../api/decisions';
import { fetchMonitoringStatus } from '../../api/monitoring';
import CompanyIdentityPanel from '../identity/CompanyIdentityPanel';
import SourceObservationsPanel from '../identity/SourceObservationsPanel';
import ClaimEvidenceLedger from './ClaimEvidenceLedger';
import ConfidentialArtifactIntake from './ConfidentialArtifactIntake';
import HumanRulingComposer from './HumanRulingComposer';
import MonitoringControl from './MonitoringControl';
import RecommendationPanel from './RecommendationPanel';
import WorkflowActionQueue from './WorkflowActionQueue';

type WorkspaceTab = 'evidence' | 'decision' | 'actions' | 'monitoring' | 'identity';

const TABS: Array<{ id: WorkspaceTab; label: string }> = [
  { id: 'evidence', label: 'Evidence' },
  { id: 'decision', label: 'Decision' },
  { id: 'actions', label: 'Actions' },
  { id: 'monitoring', label: 'Monitoring' },
  { id: 'identity', label: 'Identity' },
];

function nestedString(value: unknown, key: string): string | null {
  if (!value || typeof value !== 'object') return null;
  const candidate = (value as Record<string, unknown>)[key];
  return typeof candidate === 'string' ? candidate : null;
}

export default function OpportunityIntelligence({ startupId, readOnly = false }: { startupId: string; readOnly?: boolean }) {
  const [tab, setTab] = useState<WorkspaceTab>('evidence');
  const queryClient = useQueryClient();
  const opportunity = useQuery({
    queryKey: ['institutional', 'opportunity', 'legacy', startupId],
    queryFn: () => fetchOpportunityByLegacyStartup(startupId),
    staleTime: 30_000,
  });
  const opportunityId = opportunity.data?.opportunity_id;
  const companyId = opportunity.data?.company_id;

  const company = useQuery({
    queryKey: ['institutional', 'company', companyId],
    queryFn: () => fetchCompany(companyId!),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });
  const observations = useQuery({
    queryKey: ['institutional', 'observations', companyId],
    queryFn: () => fetchObservations(undefined, 200),
    enabled: Boolean(companyId && tab === 'identity'),
    staleTime: 30_000,
  });
  const evidence = useQuery({
    queryKey: ['institutional', 'evidence', opportunityId],
    queryFn: () => fetchEvidenceLedger(opportunityId!),
    enabled: Boolean(opportunityId),
    staleTime: 15_000,
  });
  const evaluation = useQuery({
    queryKey: ['institutional', 'evaluation', opportunityId],
    queryFn: () => fetchCurrentEvaluation(opportunityId!),
    enabled: Boolean(opportunityId),
    retry: false,
    staleTime: 15_000,
  });
  const actions = useQuery({
    queryKey: ['institutional', 'actions', opportunityId],
    queryFn: () => listWorkflowActions(opportunityId!),
    enabled: Boolean(opportunityId),
    staleTime: 10_000,
  });
  const monitoring = useQuery({
    queryKey: ['institutional', 'monitoring', opportunityId],
    queryFn: () => fetchMonitoringStatus(opportunityId!),
    enabled: Boolean(opportunityId && tab === 'monitoring'),
    staleTime: 10_000,
  });
  const evaluate = useMutation({
    mutationFn: () => evaluateOpportunity(opportunityId!),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['institutional', 'evaluation', opportunityId] }),
        queryClient.invalidateQueries({ queryKey: ['institutional', 'opportunity', 'legacy', startupId] }),
      ]);
    },
  });

  const companyObservations = useMemo(
    () => (observations.data ?? []).filter((item) => item.company_id === companyId),
    [companyId, observations.data],
  );
  const recommendationId = opportunity.data?.current_recommendation_id
    ?? nestedString(evaluation.data?.recommendation, 'recommendation_id');

  if (opportunity.isLoading) {
    return <section className="mt-phi-8 border-y border-oxford/10 py-phi-6" aria-label="Opportunity intelligence"><p className="type-label-section">Institutional record</p><p className="type-body mt-phi-2 text-oxford/55">Resolving the canonical opportunity…</p></section>;
  }
  if (opportunity.isError || !opportunity.data) {
    return (
      <section className="mt-phi-8 border-y border-oxford/10 py-phi-6" aria-label="Opportunity intelligence unavailable">
        <p className="type-label-section">Institutional record unavailable</p>
        <p className="type-body mt-phi-2 text-oxford/55">
          This legacy memo has not been linked to a canonical opportunity. Existing memo evidence remains visible; institutional rulings and orchestration stay disabled until reconciliation completes.
        </p>
      </section>
    );
  }

  return (
    <section className="mt-phi-8 border-t-2 border-oxford pt-phi-6" aria-label="Opportunity intelligence">
      <div className="flex flex-wrap items-start justify-between gap-phi-4">
        <div>
          <p className="type-label-section">Opportunity intelligence</p>
          <h2 className="mt-phi-2 font-display text-3xl font-medium leading-tight text-oxford">
            Evidence, judgment, and action
          </h2>
          <p className="type-body mt-phi-2 max-w-2xl text-oxford/55">
            Canonical record · immutable evaluation · attributed human rulings · approval-gated workflow.
          </p>
        </div>
        <div className="text-right">
          <p className="type-status">{opportunity.data.decision_state.replace(/_/g, ' ')}</p>
          <p className="type-meta mt-1 text-oxford/45">{opportunity.data.opportunity_id}</p>
        </div>
      </div>

      <nav className="mt-phi-6 flex gap-phi-5 overflow-x-auto border-b border-oxford/10" role="tablist" aria-label="Opportunity intelligence views">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            onClick={() => setTab(item.id)}
            className={`type-label-tab shrink-0 border-b pb-phi-3 ${tab === item.id ? 'border-oxford text-oxford' : 'border-transparent text-oxford/50'}`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="py-phi-6">
        {tab === 'evidence' ? (
          evidence.isLoading ? <p className="type-body text-oxford/55">Loading the claim ledger…</p>
            : evidence.isError || !evidence.data ? <p role="alert" className="type-body text-signal">The evidence ledger is unavailable. No claims were inferred from the memo fallback.</p>
              : <><ClaimEvidenceLedger ledger={evidence.data} readOnly={readOnly} />{!readOnly ? <ConfidentialArtifactIntake opportunityId={opportunity.data.opportunity_id} /> : null}</>
        ) : null}

        {tab === 'decision' ? (
          <>
            <RecommendationPanel evaluation={evaluation.data ?? null} />
            {!readOnly ? (
              <button type="button" onClick={() => evaluate.mutate()} disabled={evaluate.isPending} className="type-action mt-phi-4 border border-oxford/15 px-3 py-2 text-oxford disabled:opacity-35">
                {evaluate.isPending ? 'Evaluating…' : 'Create new immutable evaluation'}
              </button>
            ) : null}
            <HumanRulingComposer opportunityId={opportunity.data.opportunity_id} recommendationId={recommendationId} readOnly={readOnly} />
          </>
        ) : null}

        {tab === 'actions' ? (
          actions.isLoading ? <p className="type-body text-oxford/55">Loading workflow actions…</p>
            : actions.isError ? <p role="alert" className="type-body text-signal">Workflow actions are unavailable.</p>
              : <WorkflowActionQueue opportunityId={opportunity.data.opportunity_id} actions={actions.data ?? []} readOnly={readOnly} />
        ) : null}

        {tab === 'monitoring' ? (
          monitoring.isLoading ? <p className="type-body text-oxford/55">Loading monitoring state…</p>
            : monitoring.isError || !monitoring.data ? <p role="alert" className="type-body text-signal">Monitoring state is unavailable.</p>
              : <MonitoringControl opportunityId={opportunity.data.opportunity_id} status={monitoring.data} serviceLevel={opportunity.data.service_level} readOnly={readOnly} />
        ) : null}

        {tab === 'identity' ? (
          company.isLoading ? <p className="type-body text-oxford/55">Loading canonical company…</p>
            : company.isError || !company.data ? <p role="alert" className="type-body text-signal">Canonical company identity is unavailable.</p>
              : <div className="space-y-phi-6"><CompanyIdentityPanel company={company.data} opportunity={opportunity.data} /><SourceObservationsPanel observations={companyObservations} /></div>
        ) : null}
      </div>
    </section>
  );
}
