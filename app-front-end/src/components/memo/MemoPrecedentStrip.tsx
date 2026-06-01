import type { ReactNode } from 'react';
import { Link } from 'react-router';
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

type Props = {
  candidates: PrecedentCandidate[];
  renderWithMonoNumbers: (value: unknown) => ReactNode;
};

export default function MemoPrecedentStrip({ candidates, renderWithMonoNumbers }: Props) {
  if (candidates.length === 0) return null;

  return (
    <section className="memoPrecedentStrip" aria-labelledby="memo-precedent-strip">
      <h2 className="memoPrecedentStripHead" id="memo-precedent-strip">
        Similar deals you ruled on
      </h2>
      <ul className="memoPrecedentStripList">
        {candidates.map((candidate) => (
          <li key={candidate.startupId} className="memoPrecedentStripItem">
            <Link to={dealPath(candidate.startupId)} className="memoPrecedentStripLink">
              <span className="memoPrecedentStripName">{candidate.name}</span>
              <span className="memoPrecedentStripDecision">{rulingLabel(candidate.decision)}</span>
            </Link>
            {candidate.rationale ? (
              <p className="memoPrecedentStripRationale">
                {renderWithMonoNumbers(candidate.rationale)}
              </p>
            ) : null}
            {candidate.matchReasons.length > 0 ? (
              <p className="memoPrecedentStripMeta">
                Matched on {candidate.matchReasons.join(', ')}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
