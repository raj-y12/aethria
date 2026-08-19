import { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { importCsv, type ImportResult, type ImportSource } from '../../api/channelsOutcomes';
import { transitionOrReduced } from '../../design-system/motion';
import { usePrefersReducedMotion } from '../../hooks';
import { useFocusTrap } from '../../hooks/useFocusTrap';

const MAX_IMPORT_ROWS = 500;

type CsvPreview = {
  headers: string[];
  rows: string[][];
};

function parseCsvLine(line: string): string[] {
  const fields: string[] = [];
  let field = '';
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    if (character === '"') {
      if (quoted && line[index + 1] === '"') {
        field += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (character === ',' && !quoted) {
      fields.push(field.trim());
      field = '';
    } else {
      field += character;
    }
  }
  if (quoted) throw new Error('A quoted field is not closed.');
  fields.push(field.trim());
  return fields;
}

export function previewCsv(csvText: string, nameField: string): CsvPreview {
  const lines = csvText.replace(/^\uFEFF/, '').split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) throw new Error('Include a header and at least one company row.');
  const headers = parseCsvLine(lines[0]);
  if (!headers.includes(nameField)) throw new Error(`The company-name field “${nameField}” is not in the header.`);
  const rows = lines.slice(1).map(parseCsvLine);
  if (rows.length > MAX_IMPORT_ROWS) throw new Error(`Imports are bounded to ${MAX_IMPORT_ROWS} companies at a time.`);
  if (rows.some((row) => row.length !== headers.length)) throw new Error('Every row must contain the same number of fields as the header.');
  const nameIndex = headers.indexOf(nameField);
  if (rows.some((row) => !row[nameIndex]?.trim())) throw new Error('Every row needs a company name.');
  return { headers, rows };
}

function makeImportKey(): string {
  const id = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `csv-${id}`;
}

function resultBatch(result: ImportResult): { id: string; status: string; resolved: number; review: number; errors: number } {
  const batch = result.batch;
  return {
    id: batch?.import_batch_id ?? String(result.import_batch_id ?? 'unknown'),
    status: batch?.status ?? String(result.status ?? 'accepted'),
    resolved: Number(batch?.resolved_count ?? result.resolved_rows ?? 0),
    review: Number(batch?.review_count ?? result.review_rows ?? 0),
    errors: Number(batch?.error_count ?? 0),
  };
}

export default function CsvImportDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const reduceMotion = usePrefersReducedMotion();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<ImportSource>('csv');
  const [csvText, setCsvText] = useState('');
  const [nameField, setNameField] = useState('company_name');
  const [domainField, setDomainField] = useState('website');
  const [externalIdField, setExternalIdField] = useState('');
  const [verifyDomains, setVerifyDomains] = useState(false);
  const [preview, setPreview] = useState<CsvPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);
  const panelRef = useRef<HTMLElement | null>(null);
  useFocusTrap(open, panelRef);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const commit = useMutation({
    mutationFn: () => importCsv({
      source,
      idempotency_key: idempotencyKey!,
      csv_text: csvText,
      name_field: nameField,
      domain_field: domainField.trim() || null,
      external_id_field: externalIdField.trim() || null,
      verify_domains: verifyDomains,
    }),
    onSuccess: async () => Promise.all([
      queryClient.invalidateQueries({ queryKey: ['startups', 'list'] }),
      queryClient.invalidateQueries({ queryKey: ['identity', 'cases'] }),
      queryClient.invalidateQueries({ queryKey: ['identity', 'observations'] }),
    ]),
  });

  const batch = useMemo(() => commit.data ? resultBatch(commit.data) : null, [commit.data]);
  const runPreview = () => {
    try {
      setPreview(previewCsv(csvText, nameField.trim()));
      setIdempotencyKey(makeImportKey());
      setPreviewError(null);
      commit.reset();
    } catch (error) {
      setPreview(null);
      setIdempotencyKey(null);
      setPreviewError(error instanceof Error ? error.message : 'CSV preview failed.');
    }
  };

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="csv-import"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[80] flex justify-end bg-oxford/20 backdrop-blur-[2px]"
          role="dialog"
          aria-modal="true"
          aria-label="Import company channels"
        >
          <motion.aside
            initial={{ x: 32 }}
            animate={{ x: 0 }}
            exit={{ x: 32 }}
            transition={transitionOrReduced(reduceMotion, { duration: 0.18 })}
            className="flex h-full w-full max-w-3xl flex-col border-l border-oxford/10 bg-paper shadow-2xl"
            ref={panelRef}
          >
            <header className="flex items-start justify-between gap-phi-5 border-b border-oxford/10 px-phi-6 py-phi-5">
              <div>
                <p className="type-label-section">Cross-channel intake</p>
                <h2 className="mt-phi-2 font-display text-3xl font-medium text-oxford">Import observed companies</h2>
                <p className="type-body mt-phi-2 max-w-xl text-oxford/65">Preview a bounded batch before it enters canonical identity resolution. Raw unmapped fields are not retained.</p>
              </div>
              <button type="button" onClick={onClose} className="type-action border-b border-oxford/15">Close</button>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto px-phi-6 py-phi-5">
              <div className="grid gap-phi-4 sm:grid-cols-2">
                <label className="type-action">Channel
                  <select aria-label="Import channel" value={source} onChange={(event) => { setSource(event.target.value as ImportSource); setPreview(null); }} className="mt-phi-2 block w-full border border-oxford/15 bg-paper px-3 py-2">
                    <option value="csv">General CSV</option><option value="crm_csv">CRM export</option><option value="event_csv">Event list</option><option value="referral_csv">Referral list</option>
                  </select>
                </label>
                <label className="type-action">Company-name field
                  <input aria-label="Company-name field" value={nameField} onChange={(event) => { setNameField(event.target.value); setPreview(null); }} className="mt-phi-2 block w-full border border-oxford/15 bg-transparent px-3 py-2" />
                </label>
                <label className="type-action">Domain field
                  <input aria-label="Domain field" value={domainField} onChange={(event) => { setDomainField(event.target.value); setPreview(null); }} className="mt-phi-2 block w-full border border-oxford/15 bg-transparent px-3 py-2" />
                </label>
                <label className="type-action">External ID field <span className="text-oxford/65">optional</span>
                  <input aria-label="External ID field" value={externalIdField} onChange={(event) => { setExternalIdField(event.target.value); setPreview(null); }} className="mt-phi-2 block w-full border border-oxford/15 bg-transparent px-3 py-2" />
                </label>
              </div>
              <label className="type-action mt-phi-4 flex items-center gap-phi-2"><input type="checkbox" checked={verifyDomains} onChange={(event) => { setVerifyDomains(event.target.checked); setPreview(null); }} className="accent-oxford" />Verify domains during identity admission</label>
              <label htmlFor="csv-import-data" className="type-action mt-phi-5 block">CSV data</label>
              <textarea id="csv-import-data" aria-label="CSV data" value={csvText} onChange={(event) => { setCsvText(event.target.value); setPreview(null); setIdempotencyKey(null); commit.reset(); }} rows={10} spellCheck={false} placeholder="company_name,website&#10;Acme,acme.com" className="mt-phi-2 w-full resize-y border border-oxford/15 bg-transparent p-3 font-mono text-xs leading-relaxed text-oxford" />

              <button type="button" onClick={runPreview} className="type-action mt-phi-3 border border-oxford/15 px-4 py-3 text-oxford">Preview import</button>
              {previewError ? <p role="alert" className="type-body mt-phi-3 text-escalation">{previewError}</p> : null}

              {preview ? (
                <section className="mt-phi-6 border-y border-oxford/10 py-phi-4" aria-label="Import preview">
                  <div className="flex flex-wrap items-baseline justify-between gap-phi-3"><h3 className="font-display text-xl font-medium text-oxford">{preview.rows.length} rows ready for bounded import</h3><span className="type-meta">Maximum {MAX_IMPORT_ROWS}</span></div>
                  <div className="mt-phi-3 overflow-x-auto"><table className="w-full min-w-[32rem] border-collapse text-left"><thead><tr>{preview.headers.map((header) => <th key={header} className="border-b border-oxford/15 py-2 pr-4 type-label-section">{header}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 5).map((row, rowIndex) => <tr key={`${rowIndex}-${row[0]}`}>{row.map((field, fieldIndex) => <td key={`${rowIndex}-${fieldIndex}`} className="border-b border-oxford/[0.06] py-2 pr-4 type-body-sm text-oxford/65">{field || '—'}</td>)}</tr>)}</tbody></table></div>
                  {preview.rows.length > 5 ? <p className="type-meta mt-phi-2">First 5 rows shown.</p> : null}
                  <button type="button" onClick={() => commit.mutate()} disabled={!idempotencyKey || commit.isPending || commit.isSuccess} className="type-action mt-phi-4 bg-oxford px-4 py-3 text-paper disabled:opacity-35">{commit.isPending ? 'Importing…' : 'Commit import'}</button>
                </section>
              ) : null}

              {batch ? <section className="mt-phi-5 border-l-2 border-oxford pl-phi-4" aria-live="polite"><p className="type-label-section">Import {batch.status.replace(/_/g, ' ')}</p><p className="type-body mt-phi-2 text-oxford/65">Batch {batch.id} · {batch.resolved} resolved · {batch.review} need identity review · {batch.errors} errors.</p>{commit.data?.idempotent_replay ? <p className="type-meta mt-phi-2">This was a safe replay of the existing import.</p> : null}</section> : null}
              {commit.isError ? <p role="alert" className="type-body mt-phi-4 text-escalation">The batch was not committed. Your preview remains available to correct or retry.</p> : null}
            </div>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
