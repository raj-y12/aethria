import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  approveCrmExport,
  crmRowToCsv,
  prepareCrmExport,
  type PreparedCrmExport,
} from '../../api/crmExport';

export default function CrmExportAction({
  opportunityId,
  companyName,
}: {
  opportunityId: string;
  companyName: string;
}) {
  const [action, setAction] = useState<PreparedCrmExport | null>(null);
  const prepare = useMutation({
    mutationFn: () => prepareCrmExport(opportunityId),
    onSuccess: setAction,
  });
  const approve = useMutation({
    mutationFn: (workflowActionId: string) => approveCrmExport(workflowActionId),
    onSuccess: () => {
      const row = action?.generated_content?.crm_row;
      if (!row) return;
      const url = URL.createObjectURL(new Blob([crmRowToCsv(row)], { type: 'text/csv' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `${row.dedupe_key}-aethria.csv`;
      link.click();
      URL.revokeObjectURL(url);
    },
  });

  const row = action?.generated_content?.crm_row;

  return (
    <div className="mt-phi-2">
      <button
        type="button"
        onClick={() => prepare.mutate()}
        disabled={prepare.isPending}
        className="type-status text-oxford/55 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
      >
        {prepare.isPending ? 'Preparing…' : 'Prepare CRM export'}
      </button>

      {prepare.isError ? (
        <p className="mt-phi-2 type-body-sm text-escalation">
          Could not prepare the export for {companyName}. Nothing was sent.
        </p>
      ) : null}

      {row ? (
        <div className="mt-phi-3 border-t border-oxford/[0.06] pt-phi-3">
          <dl className="flex flex-col gap-phi-1">
            {([
              ['Dedupe key', row.dedupe_key],
              ['Decision', row.decision],
              ['Rationale', row.rationale],
              ['Latest outcome', row.latest_outcome ?? '—'],
            ] as const).map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-phi-3">
                <dt className="type-label-section">{label}</dt>
                <dd className="type-body-sm min-w-0 truncate text-oxford/70">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-phi-2 type-meta text-oxford/55">
            Prepared only — nothing has been sent to your CRM yet.
          </p>
          <button
            type="button"
            onClick={() => approve.mutate(action!.workflow_action_id)}
            disabled={approve.isPending}
            className="mt-phi-3 type-status text-oxford transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
          >
            {approve.isPending ? 'Approving…' : 'Approve and download'}
          </button>
        </div>
      ) : null}
    </div>
  );
}
