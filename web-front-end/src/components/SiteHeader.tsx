import { useEffect, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';

/** Match scroll-margin-top on section[id] and Lenis anchor offset. */
export const SITE_HEADER_SCROLL_OFFSET = 88;

const NAV_LINKS = [
  { label: 'Mandate', href: '#mandate' },
  { label: 'Pipeline', href: '#pipeline' },
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

export interface SiteHeaderProps {
  /** When set, show a back link instead of section nav (secondary pages). */
  backTo?: { href: string; label: string };
}

export default function SiteHeader({ backTo }: SiteHeaderProps) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 32);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={`inst-site-header sticky top-0 z-[100] w-full shrink-0 bg-[rgba(244,241,234,0.92)] backdrop-blur-md ${scrolled ? 'inst-site-header--compact' : ''}`}
      style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}
    >
      <div className="inst-site-header-inner page-margin-x">
        <Link to="/home" aria-label="Aethria — home" className="inst-site-header-wordmark shrink-0">
          Aethria<span className="wordmark-dot">.</span>
        </Link>

        {backTo ? (
          <Link
            to={backTo.href}
            className="inline-flex min-h-[44px] items-center px-1 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--label-muted)] transition-colors duration-200 hover:text-[var(--color-accent)]"
          >
            {backTo.label}
          </Link>
        ) : (
          <nav aria-label="Section navigation" className="inst-site-header-nav">
            {NAV_LINKS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={(e) => scrollToAnchor(e, item.href)}
                className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--label-muted)] transition-colors duration-200 hover:text-[var(--color-accent)]"
              >
                {item.label}
              </a>
            ))}
          </nav>
        )}
      </div>
    </header>
  );
}
