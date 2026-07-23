import { useEffect } from 'react';
import { editionNo } from '../lib/clocks';

/**
 * Full-viewport arrival overlay — plays once per session, client-only (never
 * prerendered; HomePage mounts it conditionally post-hydration). Wordmark +
 * brackets + edition label settle in, hold, then the whole plate lifts and
 * dissolves. Sequence timing lives in CSS (index.css, "GALLERY LOADER"); this
 * component only owns the single dismissal timeout and session/scroll-lock
 * bookkeeping.
 */
export default function GalleryLoader({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    try {
      sessionStorage.setItem('aethria-intro-seen', '1');
    } catch {
      // ponytail: private-mode Safari throws on storage access — best effort only
    }

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // ponytail: fixed 1550ms matches the CSS sequence's total duration exactly
    // (see loader-lift's 1100ms delay + 450ms duration in index.css) rather than
    // wiring up animationend listeners for a one-shot, non-interactive overlay.
    const timer = window.setTimeout(onDone, 1550);

    return () => {
      window.clearTimeout(timer);
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
