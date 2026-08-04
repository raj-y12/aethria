import type { MouseEvent } from 'react';

/** Smooth-scrolls to an in-page anchor via Lenis when present, matching SiteHeader's nav links. */
export function scrollToAnchor(e: MouseEvent<HTMLAnchorElement>, href: string): void {
  const el = document.querySelector(href);
  if (!el) return;
  e.preventDefault();
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const lenis = (window as unknown as { __lenis?: { scrollTo: (t: Element, o?: { offset?: number }) => void } }).__lenis;
  if (lenis && !reduceMotion) lenis.scrollTo(el, { offset: -88 });
  else el.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
}
