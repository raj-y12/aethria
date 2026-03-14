import type { RejectionAnalytics, WatchlistAnalytics, ConcentrationAnalytics } from '../types/startup';
import { getAuthHeaders } from './auth';

const API_BASE = typeof window !== 'undefined' ? '' : 'http://localhost:8000';

export async function fetchRejectionAnalytics(): Promise<RejectionAnalytics> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/analytics/rejections`, { headers });
  if (!res.ok) return { most_common_red_flags: [], rejection_by_sector: {}, avg_scores_at_rejection: {}, most_common_fail_dimensions: [] };
  return res.json();
}

export async function fetchWatchlistAnalytics(): Promise<WatchlistAnalytics> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/analytics/watchlist`, { headers });
  if (!res.ok) return { total: 0, stale: 0, avg_days: 0 };
  return res.json();
}

export async function fetchConcentrationAnalytics(): Promise<ConcentrationAnalytics> {
  const headers = { Accept: 'application/json', ...(await getAuthHeaders()) };
  const res = await fetch(`${API_BASE}/api/analytics/concentration`, { headers });
  if (!res.ok) return { by_sector: {}, most_concentrated_sector: '', most_concentrated_theme: '', last_updated: '' };
  return res.json();
}
