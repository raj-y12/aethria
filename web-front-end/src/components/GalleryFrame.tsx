import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useReducedMotion } from 'framer-motion';
import { bureauTimes, editionNo } from '../lib/clocks';

/**
 * Fixed marginal furniture (Obys/Izanami-style gallery frame) + film-grain overlay.
 * Visual source of truth: docs/design/explorations/J-gallery-instruments.html (.frame.tl/.tr/.bl/.br, .wordmark, .grain).
 * Classes are already defined in index.css (Task 1) — this just supplies markup + live clock/edition state.
 */
export default function GalleryFrame({ enter = true }: { enter?: boolean }) {
  const reduce = useReducedMotion();
  const [times, setTimes] = useState<{ label: string; time: string }[] | null>(null);
  // Computed after mount, not during SSG prerender — a day boundary between
  // build and hydration would otherwise make the server- and client-rendered
  // numbers disagree.
  const [edition, setEdition] = useState<number | null>(null);

  useEffect(() => {
    setTimes(bureauTimes());
    setEdition(editionNo());
    if (reduce) return;
    const id = window.setInterval(() => setTimes(bureauTimes()), 1000);
    return () => window.clearInterval(id);
  }, [reduce]);

  const frameCx = (side: string) => (enter ? `frame ${side} frame-in` : `frame ${side}`);

  return (
    <>
      <div className="grain" />

      <div className={frameCx('tl')}>
        <Link to="/home" className="wordmark">
          Aethria<span className="dot">.</span>
        </Link>
      </div>

      <div className={frameCx('tr')}>
        <a href="#market">Index</a>
        <a href="#access">Access</a>
      </div>

      <div className={frameCx('bl')}>
        {(times ?? [{ label: 'London', time: '— : —' }, { label: 'San Francisco', time: '— : —' }]).map(
          ({ label, time }) => (
            <div key={label}>
              {time} &nbsp; {label}
            </div>
          )
        )}
      </div>

      <div className={frameCx('br')}>Specimen Edition &middot; No. {edition ?? '—'}</div>
    </>
  );
}
