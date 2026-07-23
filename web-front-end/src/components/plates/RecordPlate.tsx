import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { CountUp } from '../../lib/CountUp';
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
  const [active, setActive] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || reduce) {
      setActive(true);
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        setActive(true);
      },
      { threshold: 0.3 },
    );
    obs.observe(root);
    return () => obs.disconnect();
  }, [reduce]);

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
      </div>
      <p className="caption left reveal d3">
        B2B Infrastructure · Series A · London. A specimen record: reviewers score each dimension one to ten against
        your thesis; the partner engine rules invest, pass, or monitor.
      </p>
    </Plate>
  );
}
