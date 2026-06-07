import type { Startup } from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchStartups(): Promise<Startup[]> {
  const res = await authedFetch(`${API_BASE}/api/startups`, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`Startups API error: ${res.status}`);
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

/** Full record for memo / detail panel (GET /api/startups/:id). */
export async function fetchStartupDetail(startupId: string): Promise<Startup | null> {
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
    error: typeof data?.error === 'string' ? data.error : data?.error ?? null,
  };
}

export type LookupJobStatus = {
  lookup_id: string;
  failed: boolean;
  message?: string;
};

/** Poll after queueOnDemandLookup when no matching startup row yet; failed=true if worker recorded an error. */
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
  lookupId: string
): Promise<{ status: string; companyName: string; lookupId: string; lookupInputType?: string }> {
  const input = lookupInput.trim();
  const id = lookupId.trim();
  if (!input) {
    throw new Error('Lookup input is required');
  }
  if (!id) {
    throw new Error('lookupId is required');
  }
  const res = await authedFetch(`${API_BASE}/api/startups/lookup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      lookup_input: input,
      lookup_id: id,
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

export async function cancelOnDemandLookups(lookupIds: string[]): Promise<void> {
  const ids = Array.from(
    new Set(lookupIds.map((id) => id.trim()).filter(Boolean))
  );
  if (ids.length === 0) return;
  await authedFetch(`${API_BASE}/api/startups/lookup/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({ lookup_ids: ids }),
  }).catch(() => undefined);
}
