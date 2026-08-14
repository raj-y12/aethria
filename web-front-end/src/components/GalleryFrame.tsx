import { useEffect, useState, type MouseEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useReducedMotion } from 'framer-motion';
import { bureauTimes, editionNo } from '../lib/clocks';
import { scrollToAnchor } from '../lib/scrollToAnchor';

/**
 * Fixed marginal furniture (Obys/Izanami-style gallery frame) + film-grain overlay.
 * Visual source of truth: docs/design/explorations/J-gallery-instruments.html (.frame.tl/.tr/.bl/.br, .wordmark, .grain).
 * Classes are already defined in index.css (Task 1) — this just supplies markup + live clock/edition state.
 */
export default function GalleryFrame({
  enter = true,
  active,
  quiet = false,
  onAccess,
}: {
  enter?: boolean;
  active?: 'home' | 'team';
  quiet?: boolean;
  /** When set, Access opens this instead of seeking an access plate on the page. */
  onAccess?: () => void;
}) {
  const reduce = useReducedMotion();
  const navigate = useNavigate();

  // Plain href anchors do not work while Lenis owns the scroll, and the target
  // plate may not exist on this route at all — fall back to the home gallery.
  const goToPlate = (e: MouseEvent<HTMLAnchorElement>, hash: string) => {
    if (document.querySelector(hash)) {
      scrollToAnchor(e, hash);
      return;
    }
    e.preventDefault();
    navigate(`/home${hash}`);
  };

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
    <div className={`frame-system${quiet ? ' frame-quiet' : ''}`}>
      <div className="grain" />

      <div className={frameCx('tl')}>
        <Link to="/home" className="wordmark">
          Aethria<span className="dot">.</span>
        </Link>
      </div>

      <div className={frameCx('tr')}>
        <a href="#market" onClick={(e) => goToPlate(e, '#market')} aria-current={active === 'home' ? 'page' : undefined}>
          Product
        </a>
        <Link to="/team" aria-current={active === 'team' ? 'page' : undefined}>
          Team
        </Link>
        <a
          href="#access"
          onClick={(e) => {
            if (!onAccess) {
              goToPlate(e, '#access');
              return;
            }
            e.preventDefault();
            onAccess();
          }}
        >
          Request access
        </a>
      </div>

      <div className={frameCx('bl')}>
        {(times ?? [{ label: 'Dublin', time: '— : —' }]).map(
          ({ label, time }) => (
            <div key={label}>
              {time} &nbsp; {label}
            </div>
          )
        )}
      </div>

      <div className={frameCx('br')}>Specimen Edition &middot; No. {edition ?? '—'}</div>
    </div>
  );
}
