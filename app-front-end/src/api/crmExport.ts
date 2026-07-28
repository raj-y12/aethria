import { apiRequest } from './client';

export interface CrmRow {
  dedupe_key: string;
  company_name: string;
  domain?: string | null;
  decision: string;
  rationale: string;
  investor_confidence?: number;
  ruled_at?: string | null;
  override_type?: string | null;
  entered_at?: string | null;
  latest_outcome?: string | null;
  outcome_count?: number;
}

export interface PreparedCrmExport {
  workflow_action_id: string;
  status: string;
  generated_content: { crm_row?: CrmRow; external_write_performed: boolean };
}

export function prepareCrmExport(opportunityId: string): Promise<PreparedCrmExport> {
  return apiRequest(`/api/opportunities/${opportunityId}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action_type: 'export_to_crm', external_destination: 'csv' }),
  });
}

export function approveCrmExport(
  workflowActionId: string,
  approvedContent: Record<string, unknown> | null = null,
): Promise<PreparedCrmExport> {
  return apiRequest(`/api/actions/${workflowActionId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_content: approvedContent }),
  });
}

export function crmRowToCsv(row: CrmRow): string {
  const columns: (keyof CrmRow)[] = [
    'dedupe_key', 'company_name', 'domain', 'decision', 'rationale',
    'investor_confidence', 'ruled_at', 'override_type', 'entered_at',
    'latest_outcome', 'outcome_count',
  ];
  const escape = (value: unknown) => {
    const raw = String(value ?? '');
    // Neutralize CSV formula injection: a leading =, +, -, or @ executes as a
    // formula when opened in Excel/Sheets. Free text here (company names,
    // rationales) can come from LLM output or web sources, so it is untrusted.
    const safe = /^[=+\-@]/.test(raw) ? `'${raw}` : raw;
    return `"${safe.replace(/"/g, '""')}"`;
  };
  return `${columns.join(',')}\n${columns.map((column) => escape(row[column])).join(',')}`;
}
