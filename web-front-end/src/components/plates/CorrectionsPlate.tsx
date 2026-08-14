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
      capLeft="Corrections / versioned learning"
      capRight="Every revision, versioned and logged"
      tone="quiet-transition"
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
          <b>Revised</b> — underperforming scout prompts are revised and versioned before the next cycle runs.
        </p>
      </div>
      <p className="caption reveal d3">
        Once a day the meta-agent reviews pipeline outcomes and calibrates the system that produced them — weights,
        thresholds, prompts — each revision versioned and logged, never silent.
      </p>
    </Plate>
  );
}
