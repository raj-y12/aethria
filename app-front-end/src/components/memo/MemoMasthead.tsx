import type { Startup } from '../../types/startup';
import { useCopyToClipboard } from '../../hooks';
import MemoTags from './MemoTags';
import { renderWithMonoNumbers } from './memoContentHelpers';

interface MemoMastheadProps {
  startup: Startup;
  /** Kept for call-site compatibility; recommendation is rendered once below the masthead. */
  brief?: unknown;
  onAddContext?: () => void;
  onDownloadPDF?: () => void;
  onClose?: () => void;
  /** Scrolls straight to the ruling composer — skips the reading for triage. */
  onJumpToRuling?: () => void;
  /** Share link / co-GP view: hides Add context. */
  readOnly?: boolean;
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
  onJumpToRuling,
  readOnly = false,
}: MemoMastheadProps) {
  const companyName = startup.scout.name?.trim() || '';
  const { copied, copy } = useCopyToClipboard();
  const location = startup.scout.location?.trim() || '';
  const descriptor = startup.scout.one_line?.trim() || '';
  const discoveredAt = startup.timestamps?.discovered_at;
  const issueDate = discoveredAt
    ? new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(discoveredAt))
    : '';
  return (
    <header className="memoMasthead">
      <div className="memoMastheadFolio">
        {issueDate ? <time className="memoMastheadDate" dateTime={discoveredAt}>{issueDate}</time> : <span />}
        <div className="memoMastheadActions" aria-label="Memo actions">
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
          {onJumpToRuling ? (
            <button
              type="button"
              className="memoAction"
              onClick={onJumpToRuling}
              aria-label="Jump to the ruling"
            >
              Jump to ruling
            </button>
          ) : null}
          {onDownloadPDF ? (
            <button
              type="button"
              className="memoAction"
              onClick={onDownloadPDF}
              aria-label="Download IC pack as PDF"
            >
              IC pack (PDF)
            </button>
          ) : null}
          {companyName ? (
            <button
              type="button"
              className="memoAction"
              onClick={() => copy(companyName)}
              aria-label={`Copy company name: ${companyName}`}
            >
              {copied ? 'Copied' : 'Copy name'}
            </button>
          ) : null}
          {onClose ? (
            <button type="button" className="memoAction" onClick={onClose}>
              Close
            </button>
          ) : null}
        </div>
      </div>
      <div className="memoMastheadIdentity">
        <div className="memoMastheadSubject">
          <h1 className="memoCoverCompany memoMastheadCompany" id="memo-title">
            {companyName || '—'}
          </h1>
          {descriptor ? <p className="memoMastheadDescriptor">{descriptor}</p> : null}
          {location ? (
            <p className="memoMeta memoMastheadLocation">{renderWithMonoNumbers(location)}</p>
          ) : null}
        </div>
      </div>
      <MemoTags startup={startup} />
    </header>
  );
}
