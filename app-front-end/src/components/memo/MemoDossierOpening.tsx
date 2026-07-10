interface MemoDossierOpeningProps {
  recommendation: string;
  recommendationTone: string;
  standfirst?: string | null;
  conviction: string;
  reviewerState: string;
  mandateFit?: string | null;
  status?: string | null;
  focalQuestion?: string | null;
  blocker?: string | null;
  nextMove?: string | null;
}

function DecisionMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="memoDossierMetric">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

export default function MemoDossierOpening({
  recommendation,
  recommendationTone,
  standfirst,
  conviction,
  reviewerState,
  mandateFit,
  status,
  focalQuestion,
  blocker,
  nextMove,
}: MemoDossierOpeningProps) {
  return (
    <header className="memoDossierOpening">
      <div className="memoDossierLede">
        <p className="memoDossierKicker">Partner recommendation</p>
        <h2 className={`memoDossierVerdict memoDossierVerdict--${recommendationTone}`}>
          {recommendation}
        </h2>
        {standfirst ? <p className="memoDossierStandfirst">{standfirst}</p> : null}
        {focalQuestion ? (
          <div className="memoDossierQuestion">
            <p className="memoDossierQuestionLabel">What decides it</p>
            <p className="memoDossierQuestionText">{focalQuestion}</p>
          </div>
        ) : null}
      </div>

      <aside className="memoDossierRecord" aria-label="Decision record">
        <p className="memoDossierKicker">Decision record</p>
        <dl className="memoDossierMetrics">
          <DecisionMetric label="Conviction" value={conviction} />
          <DecisionMetric label="Review panel" value={reviewerState} />
          {mandateFit ? <DecisionMetric label="Mandate fit" value={mandateFit} /> : null}
          {status ? <DecisionMetric label="Status" value={status} /> : null}
        </dl>
        {blocker ? (
          <div className="memoDossierCallout">
            <p className="memoDossierCalloutLabel">Blocker</p>
            <p>{blocker}</p>
          </div>
        ) : null}
        {nextMove ? (
          <div className="memoDossierCallout memoDossierCallout--action">
            <p className="memoDossierCalloutLabel">Required next move</p>
            <p>{nextMove}</p>
          </div>
        ) : null}
      </aside>
    </header>
  );
}
