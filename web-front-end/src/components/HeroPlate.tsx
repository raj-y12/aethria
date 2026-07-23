import DottedMarketMap from './DottedMarketMap';

/**
 * Full-viewport opening plate (Izanami calm). Classes (.hero/.hero-veil/.hero-center/
 * .hero-kicker/.hero-statement) live in index.css; the faint dot-map "echo" behind the
 * veil is the real DottedMarketMap in echo mode, not the mockup's standalone canvas.
 * Visual source of truth: _design-explore/J-gallery-instruments.html (.hero) — minus
 * the mockup's bouncing down-arrow hint, which the redesign explicitly drops.
 * The <h1> here is the single page-level heading.
 */
export default function HeroPlate() {
  return (
    <section className="hero">
      <div className="hero-echo">
        <DottedMarketMap echo className="h-full w-full" />
      </div>
      <div className="hero-veil" />
      <div className="hero-center">
        <div className="hero-kicker">Private-market intelligence</div>
        <h1 className="hero-statement">Private-market judgment, on the record.</h1>
      </div>
    </section>
  );
}
