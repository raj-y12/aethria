import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { approveWorkflowAction, createWorkflowAction, type WorkflowAction, type WorkflowActionType } from '../../api/decisions';

const ACTION_LABELS: Record<WorkflowActionType, string> = {
  prepare_diligence_questions: 'Prepare diligence questions',
  draft_information_request: 'Draft information request',
  refresh_evidence: 'Refresh evidence',
  schedule_monitor_review: 'Schedule monitor review',
  export_to_crm: 'Export to CRM',
  generate_decision_pack: 'Generate decision pack',
  resolve_identity: 'Resolve identity',
};

export default function WorkflowActionQueue({ opportunityId, actions, readOnly = false }: { opportunityId: string; actions: WorkflowAction[]; readOnly?: boolean }) {
  const queryClient = useQueryClient();
  const [actionType, setActionType] = useState<WorkflowActionType>('prepare_diligence_questions');
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['institutional', 'actions', opportunityId] });
  const create = useMutation({ mutationFn: () => createWorkflowAction(opportunityId, { action_type: actionType }), onSuccess: invalidate });
  const approve = useMutation({ mutationFn: (action: WorkflowAction) => approveWorkflowAction(action.workflow_action_id, action.generated_content), onSuccess: invalidate });
  return (
    <section aria-label="Workflow actions">
      <div className="flex items-baseline justify-between gap-phi-4"><p className="type-label-section">Workflow actions</p><span className="type-meta text-oxford/50">Human approval before external execution</span></div>
      {!readOnly ? (
        <div className="mt-phi-3 flex flex-col gap-phi-2 sm:flex-row">
          <select aria-label="New workflow action" value={actionType} onChange={(event) => setActionType(event.target.value as WorkflowActionType)} className="min-w-0 flex-1 border border-oxford/15 bg-paper px-3 py-2 type-action">{Object.entries(ACTION_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <button type="button" onClick={() => create.mutate()} disabled={create.isPending} className="type-action bg-oxford px-4 py-2 text-paper disabled:opacity-35">Create draft</button>
        </div>
      ) : null}
      {actions.length === 0 ? <p className="type-body mt-phi-4 text-oxford/55">No workflow actions have been created.</p> : (
        <div className="mt-phi-4 divide-y divide-oxford/10 border-y border-oxford/10">
          {actions.map((action) => (
            <article key={action.workflow_action_id} className="py-phi-4">
              <div className="flex flex-wrap items-start justify-between gap-phi-3"><div><h3 className="font-sans text-sm font-semibold text-oxford">{ACTION_LABELS[action.action_type]}</h3><p className="type-meta mt-1 text-oxford/50">{action.status.replace(/_/g, ' ')}</p></div>{action.requires_approval && action.status === 'pending_approval' ? <span className="type-status">Approval required</span> : null}</div>
              {action.missing_evidence.length ? <p className="type-body mt-phi-2 text-oxford/60">Missing: {action.missing_evidence.join(', ')}</p> : null}
              {Object.keys(action.generated_content).length ? <pre className="mt-phi-3 max-h-48 overflow-auto border-l border-oxford/15 pl-phi-3 font-mono text-xs leading-relaxed text-oxford/60">{JSON.stringify(action.generated_content, null, 2)}</pre> : null}
              {!readOnly && action.requires_approval && action.status === 'pending_approval' ? <button type="button" onClick={() => approve.mutate(action)} disabled={approve.isPending} className="type-action mt-phi-3 border border-oxford/15 px-3 py-2 text-oxford">Approve action</button> : null}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

