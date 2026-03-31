import type { MetaCycleReport, ScoutWeights, CalibrationState } from '../types/startup';
import { authedFetch } from './auth';

const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function fetchMetaReports(): Promise<MetaCycleReport[]> {
  const res = await authedFetch(`${API_BASE}/api/meta/reports`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

export async function fetchScoutWeights(): Promise<ScoutWeights> {
  const res = await authedFetch(`${API_BASE}/api/meta/weights`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return { MarketDrivenScout: 0.25, BuilderTechnicalScout: 0.25, PainPointScout: 0.25, ContrarianScout: 0.25 };
  return res.json();
}

export async function fetchCalibrationState(): Promise<CalibrationState> {
  const res = await authedFetch(`${API_BASE}/api/meta/calibration`, { headers: { Accept: 'application/json' } });
  if (!res.ok) return { confidence_threshold_override: null, reviewer_weak_threshold_override: null, reviewer_strong_threshold_override: null, last_calibrated_at: null, last_calibrated_cycle: 0, calibration_history: [] };
  return res.json();
}

export async function triggerMetaCycle(): Promise<{ status: string; cycle_number: number }> {
  const res = await authedFetch(`${API_BASE}/api/meta/trigger`, {
    method: 'POST',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`Trigger failed: ${res.status}`);
  return res.json();
}
