import type { ReactNode } from 'react';
import type { EvidenceLedgerModel } from '../../lib/evidenceLedger';
import { prettyFieldName } from '../../lib/evidenceLedger';

type Props = {
  model: EvidenceLedgerModel;
  showConfidence: boolean;
  renderWithMonoNumbers: (value: unknown) => ReactNode;
};

const SOURCE_TYPE_LABEL: Record<string, string> = {
  official: 'Official',
  reputable: 'Reputable',
  web: 'Web',
  unknown: 'Unverified',
};

/**
 * First-class evidence ledger. Evidence is the memo's trust surface, so this
 * leads with a provenance read (sourced vs inferred, primary vs secondary),
 * then claim-level citations, then the gaps. Everything here is grounded in
 * data the pipeline captured — no invented dates or quality scores.
 */
export default function MemoEvidenceLedger({ model, showConfidence, renderWithMonoNumbers }: Props) {
  const { entries, tierCounts, inferredFields, sourcedFieldCount, missingEvidence, contested } = model;

  const summaryBits: string[] = [];
  if (sourcedFieldCount > 0) summaryBits.push(`${sourcedFieldCount} sourced`);
  if (inferredFields.length > 0) summaryBits.push(`${inferredFields.length} inferred`);
  if (tierCounts.official > 0) summaryBits.push(`${tierCounts.official} official`);
  if (tierCounts.reputable > 0) summaryBits.push(`${tierCounts.reputable} reputable`);
  if (tierCounts.web > 0) summaryBits.push(`${tierCounts.web} web`);
  const summaryLine = summaryBits.join('   ·   ');

  return (
    <section className="memoDocSection memoEvidenceSection" aria-labelledby="memo-evidence">
      <h2 className="memoDocSectionHead" id="memo-evidence">Evidence</h2>

      {summaryLine && <p className="memoEvStatLine">{renderWithMonoNumbers(summaryLine)}</p>}

      {contested && (
        <p className="memoEvidenceContested">Reviewers disagree on this case — weigh the evidence directly.</p>
      )}

      {entries.length > 0 && (
        <ul className="memoEvidenceList">
          {entries.map((e, i) => (
            <li key={i} className="memoEvidenceRow">
              <span className={`memoEvidenceTag memoEvidenceTag--${e.sourceType}`}>
                {SOURCE_TYPE_LABEL[e.sourceType] ?? 'Unverified'}
              </span>
              <span className="memoEvidenceBody">
                <span className="memoEvidenceClaim">{renderWithMonoNumbers(e.claim)}</span>
                {e.href ? (
                  <a className="memoLink memoEvidenceCite" href={e.href} target="_blank" rel="noreferrer">
                    {renderWithMonoNumbers(e.label)}
                  </a>
                ) : (
                  <span className="memoEvidenceCite">{renderWithMonoNumbers(e.label)}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {showConfidence && inferredFields.length > 0 && (
        <div className="memoDocSubsection">
          <p className="memoDocSubhead">Inferred, not sourced</p>
          <p className="memoEvidenceInferred">
            {renderWithMonoNumbers(inferredFields.map(prettyFieldName).join(', '))}
          </p>
        </div>
      )}

      {missingEvidence.length > 0 && (
        <div className="memoDocSubsection">
          <p className="memoDocSubhead">Missing evidence</p>
          <ul className="memoList">
            {missingEvidence.map((item, i) => (
              <li key={i} className="memoListItem">
                <span className="memoBullet" aria-hidden>·</span>
                <span>{renderWithMonoNumbers(item)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
