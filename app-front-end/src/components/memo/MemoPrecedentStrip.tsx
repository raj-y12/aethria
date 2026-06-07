import { useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import { DECISION_BADGE_CLASS, VERDICT_CHIP_CLASS } from '../../design-system/verdictBadgeTokens';
import type { PrecedentCandidate } from '../../lib/institutionalConviction';
import type { RulingDecision } from '../../types/startup';

const APP_ROOT = '/v1';

function dealPath(startupId: string): string {
  return `${APP_ROOT}?deal=${encodeURIComponent(startupId)}`;
}

function rulingLabel(decision: RulingDecision): string {
  if (decision === 'YES') return 'Invest';
  if (decision === 'NO') return 'Pass';
  return 'Monitor';
}

function rulingVariant(decision: RulingDecision): 'invest' | 'pass' | 'monitor' {
  if (decision === 'YES') return 'invest';
  if (decision === 'NO') return 'pass';
  return 'monitor';
}

function formatPrecedentDate(iso: string): string | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function collapseSummary(candidates: PrecedentCandidate[]): string {
  const first = candidates[0];
  if (!first) return '';
  const head = `${rulingLabel(first.decision)} · ${first.name}`;
  if (candidates.length === 1) return head;
  return `${candidates.length} deals · ${head}`;
}

const MATCH_LABELS: Record<string, string> = {
  sector: 'Sector',
  stage: 'Stage',
  recommendation: 'Same recommendation',
};

const PRECEDENT_VERDICT_CLASS: Record<'invest' | 'pass' | 'monitor', string> = {
  invest: DECISION_BADGE_CLASS.INVEST,
  pass: DECISION_BADGE_CLASS.PASS,
  monitor: DECISION_BADGE_CLASS.MONITOR,
};

type Props = {
  candidates: PrecedentCandidate[];
  renderWithMonoNumbers: (value: unknown) => ReactNode;
  /** Collapsed by default to keep the cover compact. */
  initialOpen?: boolean;
};

export default function MemoPrecedentStrip({
  candidates,
  renderWithMonoNumbers,
  initialOpen = false,
}: Props) {
  const [open, setOpen] = useState(initialOpen);

  if (candidates.length === 0) return null;

  const summary = collapseSummary(candidates);

  return (
    <section className="memoPrecedent" aria-labelledby="memo-precedent-strip">
      <button
        type="button"
        className="memoPrecedentToggle"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="memo-precedent-body"
      >
        <span className="memoPrecedentKicker" id="memo-precedent-strip">
          Prior rulings
        </span>
        <span className="memoPrecedentSummary">{summary}</span>
        <span className="memoPrecedentPlus" aria-hidden>
          {open ? '−' : '+'}
        </span>
      </button>

      <div id="memo-precedent-body" className={open ? 'memoPrecedentBody' : 'hidden'}>
        <p className="memoPrecedentLead">
          {candidates.length === 1
            ? 'One deal you already decided that resembles this case.'
            : `${candidates.length} deals you already decided that resemble this case.`}
        </p>

        <ul className="memoPrecedentList">
          {candidates.map((candidate) => {
            const when = formatPrecedentDate(candidate.timestamp);
            const variant = rulingVariant(candidate.decision);
            return (
              <li key={candidate.startupId} className="memoPrecedentCard">
                <Link to={dealPath(candidate.startupId)} className="memoPrecedentCardLink">
                  <div className="memoPrecedentCardTop">
                    <span className={`${VERDICT_CHIP_CLASS} ${PRECEDENT_VERDICT_CLASS[variant]}`}>
                      {rulingLabel(candidate.decision)}
                    </span>
                    <span className="memoPrecedentName">{candidate.name}</span>
                    {when ? (
                      <time className="memoPrecedentWhen" dateTime={candidate.timestamp}>
                        {when}
                      </time>
                    ) : (
                      <span className="memoPrecedentWhen" aria-hidden />
                    )}
                  </div>

                  {candidate.rationale ? (
                    <p className="memoPrecedentRationale">
                      {renderWithMonoNumbers(candidate.rationale)}
                    </p>
                  ) : null}

                  {candidate.matchReasons.length > 0 ? (
                    <ul className="memoPrecedentTags" aria-label="Why this deal matched">
                      {candidate.matchReasons.map((reason) => (
                        <li key={reason} className="memoPrecedentTag">
                          {MATCH_LABELS[reason] ?? reason}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  <span className="memoPrecedentOpen" aria-hidden>
                    Open deal →
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
