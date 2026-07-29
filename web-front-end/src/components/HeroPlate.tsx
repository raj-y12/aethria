import DottedMarketMap from './DottedMarketMap';
import { scrollToAnchor } from '../lib/scrollToAnchor';

/**
 * Full-viewport opening plate (Izanami calm). Classes (.hero/.hero-veil/.hero-center/
 * .hero-kicker/.hero-statement) live in index.css; the faint dot-map "echo" behind the
 * veil is the real DottedMarketMap in echo mode, not the mockup's standalone canvas.
 * Visual source of truth: docs/design/explorations/J-gallery-instruments.html (.hero) — minus
 * the mockup's bouncing down-arrow hint, which the redesign explicitly drops.
 * The <h1> here is the single page-level heading.
 *
 * Ink-settle load-in: resting state (no .hero-in) is fully visible — required for
 * prerendered/no-JS output. `.hero-in`, layered in via the `enter` prop, adds the
 * entrance animation; CSS (not JS) is what skips it under reduced motion.
 */
export default function HeroPlate({ enter = true }: { enter?: boolean }) {
  return (
    <section className={enter ? 'hero hero-in' : 'hero'}>
      <div className="hero-echo">
        <DottedMarketMap echo className="h-full w-full" />
      </div>
      <div className="hero-veil" />
      <div className="hero-center">
        <div className="hero-kicker">Private-market intelligence</div>
        <h1 className="hero-statement">Private-market judgment, on the record.</h1>
        <p className="hero-standfirst">
          Aethria sources private companies, evaluates each opportunity against your fund mandate, and preserves
          every decision as institutional memory.
        </p>
        <div className="hero-ctas">
          <a href="#access" className="cta-primary" onClick={(e) => scrollToAnchor(e, '#access')}>
            Request access
          </a>
          <a href="#market" className="cta-secondary" onClick={(e) => scrollToAnchor(e, '#market')}>
            View the system
          </a>
        </div>
      </div>
    </section>
  );
}
