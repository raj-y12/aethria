import type { Startup } from '../types/startup';
import { authedFetch } from './auth';
import type { OpportunityDecisionView } from './identity';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchStartups(): Promise<Startup[]> {
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    const { fixtureStartups } = await import('../fixtures/startups');
    return fixtureStartups;
  }
  const authorityRes = await authedFetch(`${API_BASE}/api/authority/status`, { headers: { Accept: 'application/json' } });
  if (authorityRes.ok) {
    const authority = await authorityRes.json() as { mode?: string; canonical_reads_allowed?: boolean };
    if (authority.mode === 'canonical_read' && authority.canonical_reads_allowed === true) {
      const canonicalRes = await authedFetch(`${API_BASE}/api/opportunities?limit=250`, { headers: { Accept: 'application/json' } });
      if (!canonicalRes.ok) throw new Error(`Canonical opportunities API error: ${canonicalRes.status}`);
      const data = await canonicalRes.json() as { opportunities?: OpportunityDecisionView[] };
      return (data.opportunities ?? []).map(canonicalOpportunityToStartup);
    }
  }
  const res = await authedFetch(`${API_BASE}/api/startups`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Startups API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

/** Compatibility shape for existing queue components; source of truth is canonical. */
export function canonicalOpportunityToStartup(opportunity: OpportunityDecisionView): Startup {
  const recommendation = String(opportunity.recommended_state ?? '').trim().toLowerCase();
  // Compatibility follows the backend contract: canonical advance is a
  // recommendation to continue diligence, not an operator investment ruling.
  const partnerRecommendation = recommendation === 'pass' ? 'PASS' : 'MONITOR';
  return {
    id: opportunity.legacy_startup_id ?? opportunity.opportunity_id,
    canonical_opportunity_id: opportunity.opportunity_id,
    scout: {
      id: opportunity.opportunity_id,
      scout_type: 'canonical',
      name: opportunity.canonical_name,
      one_line: opportunity.canonical_domain ? `${opportunity.canonical_name} · ${opportunity.canonical_domain}` : opportunity.canonical_name,
      sector: '',
      why_now: '',
      confidence: 1,
      lookup_website: opportunity.canonical_domain ?? undefined,
    },
    partner: {
      recommendation: partnerRecommendation,
      confidence: opportunity.recommendation_confidence ?? undefined,
      decision_drivers: opportunity.decision_drivers ?? [],
      risks: opportunity.principal_risks ?? [],
      human_review_required: true,
    },
    queue_reason: opportunity.workflow_state ?? opportunity.decision_state,
    priority_reason: opportunity.attention_priority != null ? `Priority ${opportunity.attention_priority}` : null,
  };
}

/**
 * Seed deal flow during the post-password welcome screen. The global auth
 * getter may not be wired to the newly-created Clerk session yet, so this path
 * accepts that session's token directly and remains best-effort.
 */
export async function fetchStartupsWithToken(
  token: string,
  timeoutMs = 8_000,
): Promise<Startup[] | null> {
  const t = token.trim();
  if (!t) return null;
  try {
    const res = await fetch(`${API_BASE}/api/startups`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${t}` },
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) return null;
    const data: unknown = await res.json();
    return Array.isArray(data) ? (data as Startup[]) : null;
  } catch {
    return null;
  }
}

/** Full record for memo / detail panel (GET /api/startups/:id). */
export async function fetchStartupDetail(
  startupId: string,
  canonicalOpportunityId?: string,
): Promise<Startup | null> {
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    const { fixtureStartups } = await import('../fixtures/startups');
    return fixtureStartups.find((s) => s.id === startupId) ?? null;
  }
  const authorityRes = await authedFetch(`${API_BASE}/api/authority/status`, { headers: { Accept: 'application/json' } });
  if (authorityRes.ok) {
    const authority = await authorityRes.json() as { mode?: string; canonical_reads_allowed?: boolean };
    if (authority.mode === 'canonical_read' && authority.canonical_reads_allowed === true) {
      let opportunityId = canonicalOpportunityId?.trim() || startupId;
      let canonicalRes = await authedFetch(
        `${API_BASE}/api/opportunities/${encodeURIComponent(opportunityId)}/decision-view`,
        { headers: { Accept: 'application/json' } },
      );
      if (!canonicalRes.ok && !canonicalOpportunityId) {
        const linkRes = await authedFetch(
          `${API_BASE}/api/startups/${encodeURIComponent(startupId)}/opportunity`,
          { headers: { Accept: 'application/json' } },
        );
        if (linkRes.ok) {
          const link = await linkRes.json() as { opportunity_id?: string };
          if (typeof link.opportunity_id === 'string' && link.opportunity_id.trim()) {
            opportunityId = link.opportunity_id.trim();
            canonicalRes = await authedFetch(
              `${API_BASE}/api/opportunities/${encodeURIComponent(opportunityId)}/decision-view`,
              { headers: { Accept: 'application/json' } },
            );
          }
        }
      }
      if (!canonicalRes.ok) return null;
      return canonicalOpportunityToStartup(await canonicalRes.json() as OpportunityDecisionView);
    }
  }
  const res = await authedFetch(
    `${API_BASE}/api/startups/${encodeURIComponent(startupId)}`,
    { headers: { Accept: 'application/json' } }
  );
  if (!res.ok) return null;
  const data = await res.json();
  return data && typeof data === 'object' && typeof data.id === 'string' ? (data as Startup) : null;
}

export async function acknowledgeStartup(startupId: string): Promise<Startup | null> {
  const res = await authedFetch(
    `${API_BASE}/api/startups/${encodeURIComponent(startupId)}/acknowledge`,
    {
      method: 'POST',
      headers: { Accept: 'application/json' },
    }
  );
  if (!res.ok) return null;
  const data = await res.json();
  return data && typeof data === 'object' && typeof data.id === 'string' ? (data as Startup) : null;
}

export type MemoPartialPayload = {
  scout: Startup['scout'];
  review: Startup['review'] | null;
  partner: Startup['partner'] | null;
  financials?: Startup['financials'];
  agent_trace?: Startup['agent_trace'];
};

export type MemoApiResponse = {
  status: 'ready' | 'generating' | 'failed';
  memo: string | null;
  partial: MemoPartialPayload | null;
  pipeline_run_id?: string | null;
  pipeline_status?: string | null;
  error?: string | null;
};

function parseMemoPartial(data: unknown): MemoPartialPayload | null {
  if (!data || typeof data !== 'object') return null;
  const o = data as Record<string, unknown>;
  const scout = o.scout;
  if (!scout || typeof scout !== 'object') return null;
  return {
    scout: scout as Startup['scout'],
    review: (o.review as Startup['review'] | null) ?? null,
    partner: (o.partner as Startup['partner'] | null) ?? null,
    financials: (o.financials as Startup['financials']) ?? null,
    agent_trace: (o.agent_trace as Startup['agent_trace']) ?? null,
  };
}

/** Memo readiness + persisted markdown; partial scout/review/partner while status === generating. */
export async function fetchMemo(startupId: string): Promise<MemoApiResponse | null> {
  const res = await authedFetch(`${API_BASE}/api/startups/${encodeURIComponent(startupId)}/memo`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) return null;
  const data = await res.json();
  const status = data?.status;
  if (status !== 'ready' && status !== 'generating' && status !== 'failed') return null;
  return {
    status,
    memo: typeof data?.memo === 'string' ? data.memo : null,
    partial: parseMemoPartial(data?.partial),
    pipeline_run_id:
      data?.pipeline_run_id != null && data.pipeline_run_id !== ''
        ? String(data.pipeline_run_id)
        : null,
    pipeline_status:
      data?.pipeline_status != null && data.pipeline_status !== ''
        ? String(data.pipeline_status)
        : null,
    error: typeof data?.error === 'string' ? data.error : data?.error ?? null,
  };
}

export const LOOKUP_EXECUTION_STATUSES = [
  'pending',
  'accepted',
  'completed',
  'blocked',
  'skipped',
  'failed_stage',
  'failed',
  'already_in_deal_flow',
] as const;

export type LookupExecutionStatus = (typeof LOOKUP_EXECUTION_STATUSES)[number];

const LOOKUP_ATTEMPT_DISPOSITIONS = [
  'accepted',
  'succeeded',
  'blocked',
  'skipped',
  'cancelled',
  'retryable_failure',
  'terminal_failure',
] as const;

export type LookupAttemptDisposition = (typeof LOOKUP_ATTEMPT_DISPOSITIONS)[number];

const LOOKUP_TERMINAL_STATUSES = new Set<LookupExecutionStatus>([
  'completed',
  'blocked',
  'skipped',
  'failed_stage',
  'failed',
  'already_in_deal_flow',
]);

const LOOKUP_FAILURE_STATUSES = new Set<LookupExecutionStatus>([
  'blocked',
  'failed_stage',
  'failed',
]);

export function isLookupTerminalStatus(
  status: LookupExecutionStatus | undefined,
): boolean {
  return status != null && LOOKUP_TERMINAL_STATUSES.has(status);
}

function isLookupExecutionStatus(value: unknown): value is LookupExecutionStatus {
  return typeof value === 'string'
    && (LOOKUP_EXECUTION_STATUSES as readonly string[]).includes(value);
}

export type LookupJobStatus = {
  lookup_id: string;
  failed: boolean;
  terminal: boolean;
  status: LookupExecutionStatus;
  job_id?: string;
  pipeline_run_id?: string;
  attempt?: number;
  disposition?: LookupAttemptDisposition;
  recorded_at?: string;
  startup_id?: string;
  code?: string;
  failed_stage?: string;
  detail?: string;
  recovery_action?: string;
  message?: string;
};

/** Poll after queueOnDemandLookup; failed=true if the worker recorded an error at any stage. */
export async function fetchLookupJobStatus(lookupId: string): Promise<LookupJobStatus> {
  const id = lookupId.trim();
  if (!id) {
    return { lookup_id: '', failed: false, terminal: false, status: 'pending' };
  }
  const params = new URLSearchParams({ lookup_id: id });
  const res = await authedFetch(`${API_BASE}/api/startups/lookup-status?${params}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    return {
      lookup_id: id,
      failed: true,
      terminal: true,
      status: 'failed',
      code: 'lookup_status_unavailable',
      detail: 'Could not verify lookup status. Check your connection and try again.',
      message: 'Could not verify lookup status. Check your connection and try again.',
    };
  }
  const data = await res.json();
  if (!isLookupExecutionStatus(data?.status)) {
    return {
      lookup_id: typeof data?.lookup_id === 'string' ? data.lookup_id : id,
      failed: true,
      terminal: true,
      status: 'failed',
      code: 'lookup_status_invalid',
      detail: 'The lookup worker returned an unsupported status. Retry the lookup.',
      message: 'The lookup worker returned an unsupported status. Retry the lookup.',
    };
  }
  const status = data.status;
  const detail = typeof data?.detail === 'string'
    ? data.detail
    : typeof data?.message === 'string'
      ? data.message
      : undefined;
  return {
    lookup_id: typeof data?.lookup_id === 'string' ? data.lookup_id : id,
    failed: typeof data?.failed === 'boolean'
      ? data.failed
      : LOOKUP_FAILURE_STATUSES.has(status),
    terminal: typeof data?.terminal === 'boolean'
      ? data.terminal
      : isLookupTerminalStatus(status),
    status,
    job_id: typeof data?.job_id === 'string' ? data.job_id : undefined,
    pipeline_run_id:
      typeof data?.pipeline_run_id === 'string' ? data.pipeline_run_id : undefined,
    attempt:
      typeof data?.attempt === 'number' && Number.isInteger(data.attempt) && data.attempt >= 1
        ? data.attempt
        : undefined,
    disposition:
      typeof data?.disposition === 'string'
      && (LOOKUP_ATTEMPT_DISPOSITIONS as readonly string[]).includes(data.disposition)
        ? data.disposition as LookupAttemptDisposition
        : undefined,
    recorded_at: typeof data?.recorded_at === 'string' ? data.recorded_at : undefined,
    startup_id: typeof data?.startup_id === 'string' ? data.startup_id : undefined,
    code: typeof data?.code === 'string' ? data.code : undefined,
    failed_stage: typeof data?.failed_stage === 'string' ? data.failed_stage : undefined,
    detail,
    recovery_action:
      typeof data?.recovery_action === 'string' ? data.recovery_action : undefined,
    message: typeof data?.message === 'string' ? data.message : detail,
  };
}

export async function queueOnDemandLookup(
  lookupInput: string,
  lookupId: string,
  /** Optional operator-supplied background (private traction/team facts) to fill missing-evidence gaps. */
  additionalContext?: string,
  /** Opaque, short-lived server token returned by resolveLookupCandidates. */
  resolutionToken?: string | null,
): Promise<{
  status: string;
  companyName: string;
  lookupId: string;
  lookupInputType?: string;
  jobId?: string;
  acceptedAt?: string;
  pipelineRunId?: string;
}> {
  const input = lookupInput.trim();
  const id = lookupId.trim();
  if (!input) {
    throw new Error('Lookup input is required');
  }
  if (!id) {
    throw new Error('lookupId is required');
  }
  const context = additionalContext?.trim().slice(0, 2000);
  const res = await authedFetch(`${API_BASE}/api/startups/lookup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      lookup_input: input,
      lookup_id: id,
      ...(context ? { additional_context: context } : {}),
      ...(resolutionToken?.trim() ? { resolution_token: resolutionToken.trim() } : {}),
    }),
  });
  if (!res.ok) {
    throw new Error(`Lookup API error: ${res.status}`);
  }
  const data = await res.json();
  const resolvedId = typeof data?.lookup_id === 'string' ? data.lookup_id : id;
  return {
    status: typeof data?.status === 'string' ? data.status : 'queued',
    companyName: typeof data?.company_name === 'string' ? data.company_name : input,
    lookupId: resolvedId,
    lookupInputType: typeof data?.lookup_input_type === 'string' ? data.lookup_input_type : undefined,
    jobId: typeof data?.job_id === 'string' ? data.job_id : undefined,
    acceptedAt: typeof data?.accepted_at === 'string' ? data.accepted_at : undefined,
    pipelineRunId: typeof data?.pipeline_run_id === 'string' ? data.pipeline_run_id : undefined,
  };
}

/** Re-review an existing startup with operator-supplied context — fetches supplied links, then re-runs review→decide in place. */
export async function queueLookupRerun(
  startupId: string,
  lookupId: string,
  additionalContext: string
): Promise<{
  status: string;
  companyName: string;
  lookupId: string;
  jobId?: string;
  acceptedAt?: string;
  pipelineRunId?: string;
}> {
  const id = lookupId.trim();
  const context = additionalContext.trim().slice(0, 2000);
  if (!startupId.trim()) throw new Error('startupId is required');
  if (!id) throw new Error('lookupId is required');
  if (!context) throw new Error('additionalContext is required');
  const res = await authedFetch(`${API_BASE}/api/startups/${encodeURIComponent(startupId)}/rerun`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ additional_context: context, lookup_id: id }),
  });
  if (!res.ok) {
    throw new Error(`Rerun API error: ${res.status}`);
  }
  const data = await res.json();
  return {
    status: typeof data?.status === 'string' ? data.status : 'queued',
    companyName: typeof data?.company_name === 'string' ? data.company_name : '',
    lookupId: typeof data?.lookup_id === 'string' ? data.lookup_id : id,
    jobId: typeof data?.job_id === 'string' ? data.job_id : undefined,
    acceptedAt: typeof data?.accepted_at === 'string' ? data.accepted_at : undefined,
    pipelineRunId: typeof data?.pipeline_run_id === 'string' ? data.pipeline_run_id : undefined,
  };
}

export async function cancelOnDemandLookups(lookupIds: string[]): Promise<boolean> {
  const ids = Array.from(
    new Set(lookupIds.map((id) => id.trim()).filter(Boolean))
  );
  if (ids.length === 0) return true;
  const response = await authedFetch(`${API_BASE}/api/startups/lookup/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ lookup_ids: ids }),
  }).catch(() => null);
  return Boolean(response?.ok);
}

export interface LookupCandidate {
  name: string;
  website: string;
  description: string;
  confidence: number;
  source_badges: string[];
}

export type LookupResolveStatus = 'resolved' | 'ambiguous' | 'not_found';

export interface LookupResolveResult {
  status: LookupResolveStatus;
  canonicalName: string;
  companyName: string;
  websiteHint: string | null;
  candidates: LookupCandidate[];
  resolutionToken: string | null;
}

/**
 * Cheap pre-flight: resolve a typed name into distinct company candidates
 * (LLM-free). Drives the dispatch disambiguation picker before we queue the
 * expensive scout/reviewer/partner pipeline.
 */
export async function resolveLookupCandidates(
  lookupInput: string,
  websiteHint?: string,
): Promise<LookupResolveResult> {
  const input = lookupInput.trim();
  if (!input) throw new Error('lookupInput is required');
  const res = await authedFetch(`${API_BASE}/api/startups/lookup/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ lookup_input: input, website_hint: websiteHint?.trim() || undefined }),
  });
  if (!res.ok) throw new Error(`Resolve API error: ${res.status}`);
  const data = await res.json();
  const candidates: LookupCandidate[] = Array.isArray(data?.candidates)
    ? data.candidates.map((c: Record<string, unknown>) => ({
        name: String(c?.name ?? ''),
        website: String(c?.website ?? ''),
        description: String(c?.description ?? ''),
        confidence: typeof c?.confidence === 'number' ? c.confidence : 0,
        source_badges: Array.isArray(c?.source_badges) ? (c.source_badges as string[]) : [],
      }))
    : [];
  const status: LookupResolveStatus =
    data?.status === 'ambiguous' || data?.status === 'not_found' ? data.status : 'resolved';
  return {
    status,
    canonicalName: String(data?.canonical_name ?? input),
    companyName: String(data?.company_name ?? input),
    websiteHint: typeof data?.website_hint === 'string' ? data.website_hint : null,
    candidates,
    resolutionToken:
      typeof data?.resolution_token === 'string' && data.resolution_token
        ? data.resolution_token
        : null,
  };
}
