import { useId } from 'react';
import {
  MEMO_LEAN_LABELS,
  type MemoDecisionBrief,
} from '../../lib/memoDecisionBrief';

function recommendationHeading(brief: MemoDecisionBrief): string {
  if (brief.status === 'loading' || brief.status === 'unavailable') return 'Partner’s view';
  return brief.leanProvenance === 'partner-judgment' ? 'Partner’s view' : 'Recommendation';
}

function recommendationLabel(brief: MemoDecisionBrief): string {
  if (brief.status === 'loading' || brief.status === 'unavailable' || brief.lean === 'none') {
    return 'Recommendation unavailable';
  }
  return MEMO_LEAN_LABELS[brief.lean];
}

export default function MemoDecisionLead({
  brief,
  stateMessage,
}: {
  brief: MemoDecisionBrief;
  stateMessage?: string;
}) {
  const headingId = `memo-recommendation-${useId().replace(/:/g, '')}`;
  const explanation = brief.status === 'loading'
    ? 'Loading the decision rationale.'
    : brief.status === 'unavailable'
      ? 'Decision rationale unavailable.'
      : brief.drivers[0] ?? 'No decision rationale was recorded.';

  return (
    <section className="memoDecisionLead" aria-labelledby={headingId}>
      <div className="memoDecisionLeadHeading">
        <p className="memoDecisionEyebrow">{recommendationHeading(brief)}</p>
        <h2 className="memoDecisionLeadVerdict" id={headingId}>{recommendationLabel(brief)}</h2>
      </div>
      <div className="memoDecisionLeadReasoning">
        <p className="memoDecisionLeadTitle">{explanation}</p>
        {brief.drivers.length > 1 && brief.status !== 'loading' && brief.status !== 'unavailable' ? (
          <ul className="memoDecisionLeadReasons">
            {brief.drivers.slice(1).map((driver) => <li key={driver}>{driver}</li>)}
          </ul>
        ) : null}
      </div>
      {brief.mandate === 'conflicted' ? <p className="memoDecisionLeadCause memoDecisionLeadAlert">This opportunity falls outside the fund mandate.</p> : null}
      {brief.ruling ? <p className="memoDecisionLeadRecorded">Human ruling recorded: {brief.ruling.decision}</p> : null}
      {stateMessage ? <p className="memoDecisionLeadCause">{stateMessage}</p> : null}
    </section>
  );
}
