import { useEffect, useState } from 'react';
import Plate from '../Plate';
import AccessForm from '../AccessForm';

/** Plate 08 — the closing request-access plate, plus the colophon furniture. */
export default function AccessPlate() {
  // Computed after mount, not during SSG prerender — a year boundary between
  // build and hydration would otherwise make the server- and client-rendered
  // values disagree.
  const [year, setYear] = useState<number | null>(null);
  useEffect(() => setYear(new Date().getFullYear()), []);

  return (
    <>
      <Plate id="access" index="08 — 08" title="Request Access" capLeft="Private access / conversation" capRight="Seats open in small batches" tone="quiet-transition">
        <div className="access-intro reveal d2">
          <p className="hero-kicker">Request access</p>
          <h3 className="hero-statement" style={{ fontSize: 'clamp(1.8rem, 4vw, 3.2rem)' }}>
            For funds that need judgment with memory.
          </h3>
        </div>
        <div className="access-form-surface reveal d3">
          <AccessForm />
        </div>
      </Plate>
      <div className="colophon">
        <div style={{ maxWidth: '32ch' }}>
          <span className="wm">
            Aethria<span style={{ color: 'var(--accent)' }}>.</span>
          </span>
          <p>Private-market intelligence for funds that need the evidence trail, not another beautiful spreadsheet.</p>
        </div>
        <div>
          <p>
            Set in Playfair Display,
            <br />
            Instrument Sans &amp; Space Mono.
          </p>
        </div>
        <div>
          <p>
            Dublin, Ireland
            <br />
            Specimen Edition · © {year ?? '—'}
          </p>
        </div>
      </div>
    </>
  );
}
