import type { Startup } from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchStartups(): Promise<Startup[]> {
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    const { fixtureStartups } = await import('../fixtures/startups');
    return fixtureStartups;
  }
  const res = await authedFetch(`${API_BASE}/api/startups`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Startups API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

/** Full record for memo / detail panel (GET /api/startups/:id). */
export async function fetchStartupDetail(startupId: string): Promise<Startup | null> {
  if (import.meta.env.VITE_USE_FIXTURES === '1') {
    const { fixtureStartups } = await import('../fixtures/startups');
    return fixtureStartups.find((s) => s.id === startupId) ?? null;
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

export type LookupJobStatus = {
  lookup_id: string;
  failed: boolean;
  message?: string;
};

/** Poll after queueOnDemandLookup; failed=true if the worker recorded an error at any stage. */
export async function fetchLookupJobStatus(lookupId: string): Promise<LookupJobStatus> {
  const id = lookupId.trim();
  if (!id) {
    return { lookup_id: '', failed: false };
  }
  const params = new URLSearchParams({ lookup_id: id });
  const res = await authedFetch(`${API_BASE}/api/startups/lookup-status?${params}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    return {
      lookup_id: id,
      failed: true,
      message: 'Could not verify lookup status. Check your connection and try again.',
    };
  }
  const data = await res.json();
  return {
    lookup_id: typeof data?.lookup_id === 'string' ? data.lookup_id : id,
    failed: Boolean(data?.failed),
    message: typeof data?.message === 'string' ? data.message : undefined,
  };
}

export async function queueOnDemandLookup(
  lookupInput: string,
  lookupId: string,
  /** Optional operator-supplied background (private traction/team facts) to fill missing-evidence gaps. */
  additionalContext?: string
): Promise<{ status: string; companyName: string; lookupId: string; lookupInputType?: string }> {
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
  };
}

/** Re-review an existing startup with operator-supplied context — fetches supplied links, then re-runs review→decide in place. */
export async function queueLookupRerun(
  startupId: string,
  lookupId: string,
  additionalContext: string
): Promise<{ status: string; companyName: string; lookupId: string }> {
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
  };
}
