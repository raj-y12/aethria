import { apiRequest, encodedId } from './client';

export interface EvaluationRecord {
  evaluation?: Record<string, unknown>;
  recommendation?: Record<string, unknown> | null;
  manifest?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export function fetchCurrentEvaluation(opportunityId: string): Promise<EvaluationRecord> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluation`);
}

export function evaluateOpportunity(opportunityId: string): Promise<EvaluationRecord> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/evaluate`, { method: 'POST' });
}

