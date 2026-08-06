import { useReducedMotion } from 'framer-motion';
import { CountUp } from '../../lib/CountUp';
import { useInView } from '../../lib/useInView';
import Plate from '../Plate';

/** Matches the real reviewer scoring dimensions (see backend/models.py SingleReview). */
const DIMS = [
  { label: 'Market', to: 9 },
  { label: 'Product', to: 8 },
  { label: 'Technical', to: 9 },
  { label: 'Execution', to: 8 },
  { label: 'Defensibility', to: 7 },
] as const;

/** Plate 02 — the record, as a typographic plate: one specimen verdict, five reviewer dimensions. */
export default function RecordPlate() {
  const reduce = useReducedMotion();
  const [rootRef, active] = useInView<HTMLDivElement>(reduce, 0.3);

  return (
    <Plate id="record" index="02 — 08" title="The Record" capLeft="The Record — Plate 02" capRight="One verdict · five dimensions">
      <div ref={rootRef} className="record">
        <div className="record-top reveal d2">
          <div className="record-name">Meridian Compute</div>
          <div className="record-verdict">Invest</div>
        </div>
        <div className="dims reveal d3">
          {DIMS.map((dim) => (
            <div className="dim" key={dim.label}>
              <div className="n">
                <CountUp to={dim.to} active={active} reduce={!!reduce} />
              </div>
              <div className="k">{dim.label}</div>
            </div>
          ))}
        </div>
        <div className="record-reasoning reveal d3">
          <div>
            <h5>Why it fits the mandate</h5>
            <p>First credible team to own this layer of the stack. The timing window is open now.</p>
          </div>
          <div>
            <h5>What could break the thesis</h5>
            <p>Defensibility leans on a single integration partner. Replaceable inside eighteen months.</p>
          </div>
        </div>
      </div>
      <p className="caption left reveal d3">
        B2B Infrastructure · Series A · London. A specimen record: reviewers score each dimension one to ten against
        your thesis; the partner engine rules invest, pass, or monitor.
      </p>
    </Plate>
  );
}
