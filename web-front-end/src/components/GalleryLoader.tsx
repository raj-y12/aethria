import { useEffect } from 'react';
import { editionNo } from '../lib/clocks';

/**
 * Full-viewport arrival overlay — plays once per session, client-only (never
 * prerendered; HomePage mounts it conditionally post-hydration). Wordmark +
 * brackets + edition label settle in, hold, then the whole plate lifts and
 * dissolves. Sequence timing lives in CSS (index.css, "GALLERY LOADER"); this
 * component only owns the two dismissal timeouts and session/scroll-lock
 * bookkeeping.
 */
export default function GalleryLoader({ onLift, onDone }: { onLift: () => void; onDone: () => void }) {
  useEffect(() => {
    try {
      sessionStorage.setItem('aethria-intro-seen', '1');
    } catch {
      // ponytail: private-mode Safari throws on storage access — best effort only
    }

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // ponytail: fixed timers matching the CSS sequence exactly (loader-lift's
    // 1600ms delay + 800ms duration in index.css) rather than wiring up
    // animationend listeners for a one-shot, non-interactive overlay.
    // onLift fires the instant the dissolve begins, so the hero starts
    // settling in BEHIND the still-fading overlay (single continuous entrance,
    // not visible → hidden → animate-in).
    const liftTimer = window.setTimeout(onLift, 1600);
    const doneTimer = window.setTimeout(onDone, 2450);

    return () => {
      window.clearTimeout(liftTimer);
      window.clearTimeout(doneTimer);
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  return (
    <div className="gallery-loader">
      <div className="gallery-loader-grain" />
      <div className="gallery-loader-center">
        <div className="gallery-loader-mark">
          <div className="gallery-loader-wordmark">
            Aethria<span className="gallery-loader-dot">.</span>
          </div>
        </div>
        <div className="gallery-loader-label">SPECIMEN EDITION &middot; No. {editionNo()}</div>
      </div>
    </div>
  );
}
