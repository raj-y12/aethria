import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === 'string' ? detail : fallback);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function detailFrom(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object') return payload;
  return (payload as { detail?: unknown }).detail ?? payload;
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
  fallback = 'The request could not be completed.',
): Promise<T> {
  const response = await authedFetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, detailFrom(payload), fallback);
  return payload as T;
}

export function encodedId(value: string, label: string): string {
  const id = value.trim();
  if (!id) throw new Error(`${label} is required`);
  return encodeURIComponent(id);
}

