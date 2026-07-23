import Plate from '../Plate';

/**
 * Plate 03 — the review, two quiet columns. Real reviewer copy from ReviewDisagreement.tsx
 * (the three-persona REVIEWERS array): the two poles run as the .review spread, the
 * Default reviewer's balanced take runs in the caption. No invented arguments.
 */
export default function ReviewPlate() {
  return (
    <Plate
      id="review"
      index="03 — 08"
      title="The Review"
      capLeft="The Review — Plate 03"
      capRight="The disagreement, preserved"
    >
      <div className="review reveal d2">
        <div className="side">
          <div className="h for">
            Opportunist — for <span className="num">8</span>
          </div>
          <div className="lede">First credible team to own this layer of the stack.</div>
          <p>The timing window is open now.</p>
        </div>
        <div className="side">
          <div className="h against">
            Skeptical — against <span className="num">4</span>
          </div>
          <div className="lede">Defensibility leans on a single integration partner.</div>
          <p>Replaceable inside eighteen months.</p>
        </div>
      </div>
      <p className="caption reveal d3">
        Even the balanced base case lands at 7 — real wedge and a credible team, but capital intensity compresses
        the early-stage return profile. Built to disagree: the split stays on the record, never averaged into a
        number that hides the argument.
      </p>
    </Plate>
  );
}
