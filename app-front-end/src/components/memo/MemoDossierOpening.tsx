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
      <div className="memoDossierOpeningGrid">
        <div className="memoDossierLede">
          <p className="memoDossierKicker">Partner recommendation</p>
          <h2 className={`memoDossierVerdict memoDossierVerdict--${recommendationTone}`}>
            {recommendation}
          </h2>
          {standfirst ? <p className="memoDossierStandfirst">{standfirst}</p> : null}
        </div>

        <aside className="memoDossierRecord" aria-label="Decision record">
          <p className="memoDossierKicker">Decision record</p>
          <p className="memoDossierStat">{conviction}</p>
          <p className="memoDossierMetaLine">
            {[`Panel ${reviewerState}`, mandateFit, status].filter(Boolean).join('  ·  ')}
          </p>
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
      </div>

      {focalQuestion ? (
        <blockquote className="memoDossierQuestion memoDossierQuestion--pull">
          <p className="memoDossierQuestionLabel">What decides it</p>
          <p className="memoDossierQuestionText">{focalQuestion}</p>
        </blockquote>
      ) : null}
    </header>
  );
}
