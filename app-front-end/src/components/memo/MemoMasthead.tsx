import type { Startup } from '../../types/startup';
import MemoTags from './MemoTags';
import { renderWithMonoNumbers } from './memoContentHelpers';
import {
  MEMO_LEAN_LABELS,
  MEMO_STATUS_LABELS,
  memoVerdictVariant,
  type MemoDecisionBrief,
} from '../../lib/memoDecisionBrief';
import { DECISION_BADGE_CLASS, VERDICT_CHIP_CLASS } from '../../design-system/verdictBadgeTokens';

interface MemoMastheadProps {
  startup: Startup;
  /** Canonical decision brief — verdict badge and top reason read from here,
   * never from the legacy `startup.partner.recommendation` field, so the
   * masthead can't assert a decision the evidence doesn't support. */
  brief?: MemoDecisionBrief;
  onAddContext?: () => void;
  onDownloadPDF?: () => void;
  onClose?: () => void;
  /** Share link / co-GP view: hides Add context. */
  readOnly?: boolean;
}

function MemoVerdictBadge({ brief }: { brief: MemoDecisionBrief }) {
  if (brief.status === 'loading' || brief.status === 'unavailable') return null;
  const variant = memoVerdictVariant(brief);
  const label = brief.status === 'blocked' || brief.status === 'recorded'
    ? MEMO_STATUS_LABELS[brief.status]
    : MEMO_LEAN_LABELS[brief.lean];
  const reason = brief.drivers[0];
  return (
    <div className="memoMastheadVerdict">
      <span className={`${VERDICT_CHIP_CLASS} ${DECISION_BADGE_CLASS[variant]}`}>{label}</span>
      {reason ? <p className="memoMastheadVerdictReason">{reason}</p> : null}
    </div>
  );
}

/**
 * The dossier masthead — one owner for the memo's identity and document
 * actions on every viewport. Replaces the old split where desktop actions
 * lived in the Decision Stage's action slot and mobile actions in a separate
 * header row inside the memo body.
 */
export default function MemoMasthead({
  startup,
  brief,
  onAddContext,
  onDownloadPDF,
  onClose,
  readOnly = false,
}: MemoMastheadProps) {
  const companyName = startup.scout.name?.trim() || '';
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
          {brief ? <MemoVerdictBadge brief={brief} /> : null}
        </div>
      </div>
      <MemoTags startup={startup} />
    </header>
  );
}
