import Plate from '../Plate';

/**
 * Plate 05 — corrections & revisions, the meta-agent's real self-optimization loop
 * (backend/meta/: reweighter.py, calibrator.py, mutator.py + utils/prompt_version.py).
 * Directional detail is representative under the specimen framing; no invented numbers.
 */
export default function CorrectionsPlate() {
  return (
    <Plate
      id="corrections"
      index="05 — 08"
      title="Corrections & Revisions"
      capLeft="Corrections & Revisions — Plate 05"
      capRight="The masthead, rewriting itself"
    >
      <div className="corrections reveal d2">
        <h4>Meta-Agent — daily pass</h4>
        <p>
          <b>Reweighted</b> — scout weighting shifts with outcomes: market-driven up, pain-point down, against the
          active thesis.
        </p>
        <p>
          <b>Recalibrated</b> — reviewer thresholds adjust so the score that gates invest/pass/monitor tracks real
          conviction, not drift.
        </p>
        <p>
          <b>Mutated</b> — underperforming scout prompts are rewritten, re-hashed, and versioned before the next
          cycle runs.
        </p>
      </div>
      <p className="caption reveal d3">
        The newsroom edits itself. Once a day the meta-agent reads pipeline outcomes and rewrites the instrument that
        produced them — weights, thresholds, prompts — each revision logged and versioned, never silent.
      </p>
    </Plate>
  );
}
