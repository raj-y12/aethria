import type { ReactNode } from 'react';

import {
  MEMO_STATUS_LABELS as STATUS_LABELS,
  type MemoDecisionBrief as MemoDecisionBriefModel,
  type MemoProvenance,
  type MemoSource,
} from '../../lib/memoDecisionBrief';
import { safeHref } from '../../lib/memoReferenceHref';

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
          href={safeHref(source.href)}
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
  children,
}: {
  brief: MemoDecisionBriefModel;
  stateMessage?: string;
  children?: ReactNode;
}) {
  const pending = brief.status === 'loading' || brief.status === 'unavailable';
  return (
    <section
      className={`memoDocSection memoRulingControls memoDecisionWorkspace memoDecisionBrief memoDecisionBrief--${brief.status}`}
      aria-labelledby="memo-decision-brief-title"
    >
      <div className="memoDecisionBriefHead">
        <div>
          <p className="memoDecisionEyebrow">Before you rule</p>
          <h2 className="memoDocSectionHead" id="memo-decision-brief-title">Evidence coverage</h2>
        </div>
        <p className="memoDecisionStatus" role="status">{STATUS_LABELS[brief.status]}</p>
      </div>

      {stateMessage ? <p className="memoDecisionStateMessage">{stateMessage}</p> : null}

      {!pending ? (
        <>
          <div className="memoDecisionBriefGrid">
            <section className="memoDecisionRiskSurface" aria-labelledby="memo-decision-risks">
              <h3 id="memo-decision-risks">Risks and evidence gaps</h3>
              {brief.risks.length > 0 ? (
                <ul>
                  {brief.risks.map((risk) => (
                    <li key={risk.key}>
                      <div className="memoDecisionRiskMeta">
                        <span>{risk.kind === 'risk' ? 'Risk' : 'Gap'}</span>
                        <span>{risk.severity}</span>
                        <span>{brief.leanProvenance === 'partner-judgment' ? 'Review and evidence checks' : 'Rule-derived'}</span>
                      </div>
                      <p>{risk.text}</p>
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
                    {claim.claim.length > 400 ? (
                      <details>
                        <summary>Read source excerpt</summary>
                        <p>{claim.claim}</p>
                      </details>
                    ) : <p>{claim.claim}</p>}
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
        </>
      ) : null}

      {children}
    </section>
  );
}
