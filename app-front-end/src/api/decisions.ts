import { apiRequest, encodedId } from './client';

export type HumanRulingDecision = 'advance' | 'monitor' | 'pass' | 'invest';
export type OverrideType =
  | 'evidence_correction' | 'missing_private_evidence' | 'policy_disagreement'
  | 'founder_judgment' | 'market_judgment' | 'timing' | 'strategic_exception'
  | 'relationship_context' | 'confidence_disagreement';

export interface HumanRulingInput {
  recommendation_id?: string;
  decision: HumanRulingDecision;
  rationale: string;
  risk_acknowledgement?: string;
  mandate_exception?: string;
  investor_confidence?: number;
  override_type?: OverrideType;
  override_note?: string;
}

export interface HumanRuling extends HumanRulingInput {
  ruling_id: string;
  opportunity_id?: string;
  prior_ruling_id?: string | null;
  actor_id?: string;
  created_at?: string;
}

export type WorkflowActionType =
  | 'prepare_diligence_questions' | 'draft_information_request' | 'refresh_evidence'
  | 'schedule_monitor_review' | 'export_to_crm' | 'generate_decision_pack' | 'resolve_identity';

export interface WorkflowAction {
  workflow_action_id: string;
  opportunity_id: string;
  action_type: WorkflowActionType;
  status: string;
  generated_content: Record<string, unknown>;
  approved_content?: Record<string, unknown> | null;
  missing_evidence: string[];
  requires_approval: boolean;
  due_at?: string | null;
  external_destination?: string | null;
  failure_code?: string | null;
  created_at: string;
  updated_at: string;
}

export function createHumanRuling(opportunityId: string, input: HumanRulingInput): Promise<HumanRuling> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/rulings`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export async function listWorkflowActions(opportunityId: string, limit = 100): Promise<WorkflowAction[]> {
  const result = await apiRequest<{ actions?: WorkflowAction[] }>(
    `/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/actions?limit=${limit}`,
  );
  return Array.isArray(result.actions) ? result.actions : [];
}

export function createWorkflowAction(
  opportunityId: string,
  input: { action_type: WorkflowActionType; due_at?: string; external_destination?: string },
): Promise<WorkflowAction> {
  return apiRequest(`/api/opportunities/${encodedId(opportunityId, 'opportunityId')}/actions`, {
    method: 'POST', body: JSON.stringify(input),
  });
}

export function approveWorkflowAction(
  actionId: string,
  approvedContent?: Record<string, unknown>,
): Promise<WorkflowAction> {
  return apiRequest(`/api/actions/${encodedId(actionId, 'actionId')}/approve`, {
    method: 'POST', body: JSON.stringify({ approved_content: approvedContent ?? null }),
  });
}

