import { useEffect, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';

/** Match scroll-margin-top on section[id] and Lenis anchor offset. */
export const SITE_HEADER_SCROLL_OFFSET = 88;

const NAV_LINKS = [
  { label: 'The market', href: '#market' },
  { label: 'Method', href: '#method' },
  { label: 'Product', href: '#product' },
];

function scrollToAnchor(e: MouseEvent<HTMLAnchorElement>, href: string) {
  const el = document.querySelector(href);
  if (!el) return;
  e.preventDefault();
  const lenis = (window as unknown as { __lenis?: { scrollTo: (t: Element, o?: { offset?: number }) => void } }).__lenis;
  if (lenis) lenis.scrollTo(el, { offset: -SITE_HEADER_SCROLL_OFFSET });
  else el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/** Scroll depth (px) past which the compact bar fades in — roughly the masthead's height. */
const MASTHEAD_SCROLL_PAST = 420;

export default function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > MASTHEAD_SCROLL_PAST);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // The masthead below (nameplate + ruled section nav) is the page's real header;
  // this compact bar overlays only once the reader has scrolled past it.
  return (
    <header
      className={`inst-site-header inst-site-header--compact fixed inset-x-0 top-0 z-[100] w-full transition-all duration-300 ${
        scrolled
          ? 'translate-y-0 opacity-100 bg-[var(--color-paper)] border-b border-solid border-[var(--section-divider)]'
          : 'pointer-events-none -translate-y-2 opacity-0'
      }`}
      style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}
      aria-hidden={!scrolled}
    >
      <div className="inst-site-header-inner page-margin-x">
        <Link to="/home" aria-label="Aethria — home" className="inst-site-header-wordmark shrink-0" tabIndex={scrolled ? 0 : -1}>
          Aethria<span className="wordmark-dot">.</span>
        </Link>

        <div className="flex items-center gap-7">
          <nav aria-label="Section navigation" className="inst-site-header-nav">
            {NAV_LINKS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={(e) => scrollToAnchor(e, item.href)}
                tabIndex={scrolled ? 0 : -1}
                className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--label-muted)] transition-colors duration-200 hover:text-[var(--color-accent)]"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <a
            href="#access"
            onClick={(e) => scrollToAnchor(e, '#access')}
            tabIndex={scrolled ? 0 : -1}
            className="hidden min-h-[40px] items-center border border-[var(--section-divider)] px-4 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors duration-300 hover:border-[var(--color-oxford)] hover:bg-[var(--color-oxford)] hover:text-[var(--color-paper)] sm:inline-flex"
          >
            Request access
          </a>
        </div>
      </div>
    </header>
  );
}
