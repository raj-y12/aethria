import type { ReactNode } from 'react';

import type {
  MemoDecisionBrief as MemoDecisionBriefModel,
  MemoProvenance,
  MemoSource,
} from '../../lib/memoDecisionBrief';

const STATUS_LABELS: Record<MemoDecisionBriefModel['status'], string> = {
  loading: 'Decision data loading',
  ready_for_ruling: 'Ready for ruling',
  blocked: 'Blocked by evidence',
  recorded: 'Ruling recorded',
  unavailable: 'Decision data unavailable',
};

const LEAN_LABELS: Record<MemoDecisionBriefModel['lean'], string> = {
  advance: 'Advance',
  monitor: 'Monitor',
  pass: 'Pass',
  none: 'No system lean',
};

const MANDATE_LABELS: Record<MemoDecisionBriefModel['mandate'], string> = {
  conflicted: 'Conflict',
  unknown: 'Unknown',
};

const COVERAGE_LABELS: Record<MemoDecisionBriefModel['coverage'], string> = {
  sufficient: 'Sufficient',
  missing: 'Missing',
  contradictory: 'Contradictory',
  unknown: 'Unknown',
};

const AGREEMENT_LABELS: Record<MemoDecisionBriefModel['agreement'], string> = {
  consistent: 'Consistent',
  contested: 'Contested',
  unknown: 'Unknown',
};

const PROVENANCE_LABELS: Record<MemoProvenance, string> = {
  verified: 'Verified',
  reported: 'Reported',
  'model-derived': 'Model-derived',
  'rule-derived': 'Rule-derived',
  missing: 'Source missing',
};

function SourceLinks({ sources }: { sources: MemoSource[] }) {
  if (sources.length === 0) {
    return <span className="memoDecisionSourceMissing">Source missing</span>;
  }
  return (
    <span className="memoDecisionSources" aria-label="Sources">
      {sources.map((source) => source.href ? (
        <a
          key={source.artifactId}
          href={source.href}
          target="_blank"
          rel="noreferrer"
        >
          {source.title}
        </a>
      ) : <span key={source.artifactId}>{source.title}</span>)}
    </span>
  );
}

export default function MemoDecisionBrief({
  brief,
  stateMessage,
  priorRecommendation,
  children,
}: {
  brief: MemoDecisionBriefModel;
  stateMessage?: string;
  priorRecommendation?: 'INVEST' | 'PASS' | 'MONITOR' | null;
  children?: ReactNode;
}) {
  const pending = brief.status === 'loading' || brief.status === 'unavailable';
  if (pending) {
    return (
      <section
        className={`memoDecisionNotice memoDecisionNotice--${brief.status}`}
        aria-label="Decision status"
      >
        <p className="memoDecisionStatus" role="status">{STATUS_LABELS[brief.status]}</p>
        {stateMessage ? <p className="memoDecisionStateMessage">{stateMessage}</p> : null}
        {brief.status === 'unavailable' && priorRecommendation ? (
          <div className="memoDecisionPriorRecord" aria-label="Prior workflow recommendation">
            <span>Prior workflow recommendation</span>
            <strong>{priorRecommendation.charAt(0) + priorRecommendation.slice(1).toLowerCase()}</strong>
            <em>Reference only</em>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section
      className={`memoDocSection memoRulingControls memoDecisionWorkspace memoDecisionBrief memoDecisionBrief--${brief.status}`}
      aria-labelledby="memo-decision-brief-title"
    >
      <div className="memoDecisionBriefHead">
        <div>
          <p className="memoDecisionEyebrow">Decision workspace</p>
          <h2 className="memoDocSectionHead" id="memo-decision-brief-title">Decision brief</h2>
        </div>
        <p className="memoDecisionStatus" role="status">{STATUS_LABELS[brief.status]}</p>
      </div>

      {stateMessage ? <p className="memoDecisionStateMessage">{stateMessage}</p> : null}

      <div className="memoDecisionStateGrid">
        <div className="memoDecisionLean">
          <p>System lean</p>
          <strong>{LEAN_LABELS[brief.lean]}</strong>
          <span>{PROVENANCE_LABELS[brief.leanProvenance]}</span>
        </div>
        <dl className="memoDecisionChecks">
          <div><dt>Mandate</dt><dd>{MANDATE_LABELS[brief.mandate]}</dd></div>
          <div><dt>Evidence</dt><dd>{COVERAGE_LABELS[brief.coverage]}</dd></div>
          <div><dt>Reviewer state</dt><dd>{AGREEMENT_LABELS[brief.agreement]}</dd></div>
        </dl>
      </div>

      <div className="memoDecisionBriefGrid">
        <section className="memoDecisionDrivers" aria-labelledby="memo-decision-drivers">
          <h3 id="memo-decision-drivers">Decision drivers</h3>
          {brief.drivers.length > 0 ? (
            <ol>{brief.drivers.map((driver) => (
              <li key={driver}>
                <span className="memoDecisionDriverText">{driver}</span>
                <span className="memoDecisionMaterialProvenance">Rule-derived</span>
              </li>
            ))}</ol>
          ) : <p className="memoDecisionMuted">No decision drivers were recorded.</p>}
        </section>

        <section className="memoDecisionRiskSurface" aria-labelledby="memo-decision-risks">
          <h3 id="memo-decision-risks">Risks and evidence gaps</h3>
          {brief.risks.length > 0 ? (
            <ul>
              {brief.risks.map((risk) => (
                <li key={risk.key}>
                  <div className="memoDecisionRiskMeta">
                    <span>{risk.kind === 'risk' ? 'Risk' : 'Gap'}</span>
                    <span>{risk.severity}</span>
                    <span>Rule-derived</span>
                  </div>
                  <p>{risk.text}</p>
                  <span className="memoDecisionSourceMissing">Source missing</span>
                </li>
              ))}
            </ul>
          ) : <p className="memoDecisionMuted">No material company risk or evidence gap was recorded.</p>}
        </section>
      </div>

      {(brief.claims.length > 0 || brief.derivations.length > 0) ? (
        <section className="memoDecisionProvenance" aria-labelledby="memo-decision-provenance">
          <h3 id="memo-decision-provenance">Claim provenance</h3>
          <ul>
            {brief.claims.map((claim) => (
              <li key={`${claim.claimId}-${claim.relationship}`}>
                <p>{claim.claim}</p>
                <span className="memoDecisionProvenanceMeta">
                  <span>{claim.criterion.replace(/_/g, ' ')}</span>
                  <span>{claim.relationship === 'supports' ? 'Supports' : 'Contradicts'}</span>
                  {claim.provenance !== 'missing' ? (
                    <span>{PROVENANCE_LABELS[claim.provenance]}</span>
                  ) : null}
                </span>
                <SourceLinks sources={claim.sources} />
              </li>
            ))}
            {brief.derivations.map((derivation) => (
              <li key={derivation.criterion}>
                <p>{derivation.criterion.replace(/_/g, ' ')}</p>
                <span className="memoDecisionProvenanceMeta">Rule-derived</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {children}
    </section>
  );
}
