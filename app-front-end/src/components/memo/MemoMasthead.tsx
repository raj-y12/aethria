import type { Startup } from '../../types/startup';
import MemoTags from './MemoTags';
import { renderWithMonoNumbers } from './memoContentHelpers';

interface MemoMastheadProps {
  startup: Startup;
  onAddContext?: () => void;
  onDownloadPDF: () => void;
  onClose?: () => void;
  /** Share link / co-GP view: keeps the PDF, hides Add context. */
  readOnly?: boolean;
  /** Under a Decision Stage cover the stage owns name/location — the masthead
   *  keeps only the action band and classification tags. */
  compact?: boolean;
}

/**
 * The dossier masthead — one owner for the memo's identity and document
 * actions on every viewport. Replaces the old split where desktop actions
 * lived in the Decision Stage's action slot and mobile actions in a separate
 * header row inside the memo body.
 */
export default function MemoMasthead({
  startup,
  onAddContext,
  onDownloadPDF,
  onClose,
  readOnly = false,
  compact = false,
}: MemoMastheadProps) {
  const companyName = startup.scout.name?.trim() || '';
  const location = startup.scout.location?.trim() || '';
  return (
    <header className="memoMasthead">
      <div className="memoMastheadBand">
        <p className="memoMastheadKicker">Investment Memo</p>
        <div className="memoMastheadActions">
          {!readOnly && onAddContext ? (
            <button
              type="button"
              className="memoMastheadPrimary"
              onClick={onAddContext}
              aria-label={`Add context and re-review ${companyName || 'this company'}`}
            >
              Add context
            </button>
          ) : null}
          <button
            type="button"
            className="memoAction"
            onClick={onDownloadPDF}
            aria-label="Download IC pack as PDF"
          >
            IC pack (PDF)
          </button>
          {onClose ? (
            <button type="button" className="memoAction" onClick={onClose}>
              Close
            </button>
          ) : null}
        </div>
      </div>
      {!compact ? (
        <>
          <h1 className="memoCoverCompany memoMastheadCompany" id="memo-title">
            {companyName || '—'}
          </h1>
          {location ? (
            <p className="memoMeta memoMastheadLocation">{renderWithMonoNumbers(location)}</p>
          ) : null}
        </>
      ) : null}
      <MemoTags startup={startup} />
    </header>
  );
}
