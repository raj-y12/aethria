import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import SiteHeader from './components/SiteHeader';
import EditionLoader from './components/EditionLoader';
import MarketSection from './components/MarketSection';
import MethodSection from './components/MethodSection';
import MetaAgentSection from './components/MetaAgentSection';
import DashboardPreview from './components/DashboardPreview';
import ReviewDisagreement from './components/ReviewDisagreement';
import PortfolioSection from './components/PortfolioSection';
import AccessForm from './components/AccessForm';
import { ScrollReveal } from './components/ScrollReveal';
import { SCROLL_EASE } from './motionTokens';

/** Matches the real reviewer scoring dimensions (see backend/models.py SingleReview). */
const RECORD_SCORES = [
  { label: 'Market', to: 9 },
  { label: 'Product', to: 8 },
  { label: 'Technical', to: 9 },
  { label: 'Execution', to: 8 },
  { label: 'Defensibility', to: 7 },
] as const;

/** Counts a single number up on first view; settles instantly under reduced motion. */
function CountUp({ to, active, reduce }: { to: number; active: boolean; reduce: boolean }) {
  const [n, setN] = useState(reduce ? to : 0);
  useEffect(() => {
    if (reduce || !active) return;
    let raf = 0;
    const start = performance.now();
    const dur = 850;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, to, reduce]);
  return <>{n}</>;
}
import {
  DEMO_LOOKUP_QUERY,
  DEMO_LOOKUP_RESULT,
  LookupCommandBar,
  LookupResultSnapshot,
} from '@aethria/product-chrome';

const LINKEDIN_URL = 'https://www.linkedin.com/company/aethria';

/** Matches CtaTextLink's rendered classes (see components/CtaButton.tsx) for plain <a> anchor-scroll CTAs. */
const CTA_TEXT_LINK_CLASS =
  'group inline-flex items-center gap-3.5 border-b border-solid border-[rgba(0,20,51,0.3)] pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-oxford)] transition-[gap] duration-300 ease-out hover:gap-6 hover:border-[var(--color-oxford)]';

/** Smooth-scrolls to an in-page anchor via Lenis when present, matching SiteHeader's nav links. */
function scrollToAnchor(e: MouseEvent<HTMLAnchorElement>, href: string) {
  const el = document.querySelector(href);
  if (!el) return;
  e.preventDefault();
  const lenis = (window as unknown as { __lenis?: { scrollTo: (t: Element, o?: { offset?: number }) => void } }).__lenis;
  if (lenis) lenis.scrollTo(el, { offset: -88 });
  else el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

export default function HomePage() {
  const reduce = useReducedMotion();
  const sidebarRef = useRef<HTMLDivElement | null>(null);
  const sidebarInView = useInView(sidebarRef, { once: true, amount: 0.5 });
  const [introDone, setIntroDone] = useState(false);

  // The application form lives at the bottom of this page now (no separate
  // /request-access route); honour old bookmarked/shared #access links.
  useEffect(() => {
    if (window.location.hash !== '#access') return;
    const el = document.getElementById('access');
    if (!el) return;
    const t = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      {!introDone && <EditionLoader onDone={() => setIntroDone(true)} />}

      <SiteHeader />

      <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-x-hidden">
        {/* Front page — masthead, lede, and a live record sit above the fold together,
            so a first-time visitor reads what it does before the philosophy of how. */}
        <section
          className="home-hero-section relative w-full overflow-hidden"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x pt-7 text-center font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--text-subtle)]">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </div>

          <div className="mt-3 text-center">
            <p className="font-wordmark text-[clamp(2.1rem,5vw,3.1rem)] font-medium leading-none tracking-[-0.01em] text-[var(--color-oxford)]">
              Aethria<span className="wordmark-dot">.</span>
            </p>
          </div>

          {/* Section-nav strip — the paper's real navigation, ruled under the nameplate
              (the sticky compact bar only overlays once this scrolls away). */}
          <nav aria-label="Section navigation" className="page-margin-x mt-5">
            <div className="np-masthead-nav flex flex-wrap items-center justify-center gap-x-8 gap-y-1 py-2.5">
              {[
                { label: 'The market', href: '#market' },
                { label: 'Method', href: '#method' },
                { label: 'Product', href: '#product' },
                { label: 'Request access', href: '#access' },
              ].map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={(e) => scrollToAnchor(e, item.href)}
                  className="inline-flex min-h-[36px] items-center font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--color-oxford)] transition-colors duration-200 hover:text-[var(--color-accent)]"
                >
                  {item.label}
                </a>
              ))}
            </div>
          </nav>

          <div className="page-margin-x grid grid-cols-1 gap-x-14 gap-y-14 py-[clamp(2.25rem,5vh,3.5rem)] lg:grid-cols-[1.85fr_1fr]">
            {/* Lede */}
            <div>
              <p className="np-head np-label">Lede — The Thesis Engine</p>

              <h1 className="editorial-display mt-3 max-w-[17ch] font-normal text-[clamp(2.5rem,6vw,5.2rem)] leading-[1.0] tracking-[-0.02em] text-[var(--color-oxford)]">
                Private market judgment, made{' '}
                <span className="italic text-[var(--color-accent)]">inspectable</span>.
              </h1>

              <p className="mt-6 max-w-[54ch] font-display text-[clamp(1.05rem,1.6vw,1.25rem)] italic leading-[1.55] text-[var(--text-secondary)]">
                Continuously discovers companies, reviews them against your fund thesis, records disagreement, and
                produces investment-ready records — every decision traceable to its evidence.
              </p>

              <div className="np-serif np-cols mt-6 max-w-[640px] text-[15px] leading-[1.68] text-[var(--text-secondary)] sm:columns-2 sm:gap-9">
                <p className="mb-3">
                  <span className="editorial-display float-left mr-1 text-[3rem] font-medium leading-[0.76] text-[var(--color-oxford)]">
                    F
                  </span>
                  our independent scouts search the live web for real companies — market-driven, technical,
                  pain-point, and contrarian — never a static list. Each candidate is scored by three reviewer modes
                  built to disagree.
                </p>
                <p>
                  Where a rule-based partner engine finds consensus, it rules automatically. Where reviewers split,
                  the disagreement is preserved on the record rather than averaged away.
                </p>
              </div>

              <a href="#market" onClick={(e) => scrollToAnchor(e, '#market')} className={`${CTA_TEXT_LINK_CLASS} mt-7`}>
                <span>See today's full record</span>
                <span aria-hidden>→</span>
              </a>
            </div>

            {/* Sidebar — today's record, above the fold, split off by a column rule */}
            <div ref={sidebarRef} className="lg:border-l lg:border-solid lg:border-[var(--section-divider)] lg:pl-10">
              <p className="flex items-center gap-2 font-mono text-[9.5px] uppercase tracking-[0.16em] text-[var(--text-subtle)]">
                <motion.span
                  className="h-[5px] w-[5px] shrink-0 rounded-full bg-[var(--color-accent)]"
                  animate={reduce ? undefined : { opacity: [1, 0.3, 1] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                />
                Today's record · live
              </p>
              <p className="mt-5 editorial-display text-[1.4rem] font-medium leading-[1.15] text-[var(--color-oxford)]">
                European Infrastructure Co.
              </p>
              <p className="mt-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-[var(--text-subtle)]">
                B2B Infrastructure · Series A · London
              </p>
              <span className="mt-4 inline-block border border-solid border-[var(--color-accent)] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-accent)]">
                Invest
              </span>
              <div className="mt-5 flex gap-6 font-mono text-[10.5px]">
                {RECORD_SCORES.map((s) => (
                  <div key={s.label}>
                    <p className="text-[15px] text-[var(--color-oxford)]">
                      <CountUp to={s.to} active={sidebarInView} reduce={!!reduce} />
                    </p>
                    <p className="mt-0.5 text-[8.5px] uppercase tracking-[0.05em] text-[var(--text-subtle)]">
                      {s.label}
                    </p>
                  </div>
                ))}
              </div>

              {/* Inside this edition — front-page index into the sections below */}
              <nav aria-label="Inside this edition" className="mt-9">
                <p className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-[var(--text-subtle)]">Inside</p>
                <ul className="mt-2">
                  {[
                    { folio: 'A3', label: 'The market', href: '#market' },
                    { folio: 'A4', label: 'Method', href: '#method' },
                    { folio: 'A6', label: 'The record', href: '#product' },
                    { folio: 'A7', label: 'The review', href: '#disagreement' },
                    { folio: 'A9', label: 'On-demand lookup', href: '#lookup' },
                  ].map((item) => (
                    <li key={item.href} className="border-t border-solid border-[var(--section-divider)] first:border-t-0">
                      <a
                        href={item.href}
                        onClick={(e) => scrollToAnchor(e, item.href)}
                        className="group flex min-h-[38px] items-center justify-between gap-4 py-1.5"
                      >
                        <span className="font-display text-[14px] leading-tight text-[var(--color-oxford)] transition-colors group-hover:text-[var(--color-accent)]">
                          {item.label}
                        </span>
                        <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[var(--text-subtle)]">
                          {item.folio}
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              </nav>
            </div>
          </div>
        </section>

        {/* Journey order: define the mandate → see what runs → see the record + disagreement → look up on demand. */}

        {/* 1 — Mandate: the constraint that drives everything */}
        <section
          id="mandate"
          className="w-full border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
          aria-labelledby="mandate-heading"
        >
          {/* Reversed hierarchy — the panel is the artifact this section is about, so it
              gets the larger column; the statement runs small and plain beside it, not as
              a display headline. Breaks from the kicker→title→paragraph shape used elsewhere. */}
          <ScrollReveal
            className="page-margin-x grid items-start gap-10 py-[clamp(2rem,4.5vh,3rem)] md:grid-cols-[0.8fr_1fr] md:gap-16"
            y={20}
            amount={0.18}
          >
            <div className="max-w-md md:sticky md:top-32">
              <p className="np-head np-label">A2 — Mandate</p>
              <p
                id="mandate-heading"
                className="np-serif mt-6 text-[clamp(1.15rem,2.1vw,1.45rem)] leading-[1.5] text-[var(--color-oxford)]"
              >
                It only looks for what you tell it to. Write the investment thesis once — scouts, reviewers, and
                partner logic treat it as a hard constraint, not a decorative preference.
              </p>
            </div>

            {/* The mandate set as a boxed public notice — the one ruled box on the page
                besides the coupon, because a notice IS a box in a paper. */}
            <div className="w-full max-w-[480px] border border-solid border-[var(--section-divider)] p-6 sm:p-7 md:justify-self-end">
              <div className="flex items-center justify-between border-b border-solid border-[var(--section-divider)] pb-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--color-oxford)]">
                  Notice · Active mandate
                </p>
                <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-accent)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" aria-hidden /> Live
                </span>
              </div>
              <h3 className="mt-5 editorial-display text-[clamp(1.5rem,2.6vw,2.1rem)] font-normal leading-[1.1] tracking-[-0.01em] text-[var(--color-oxford)]">
                Deep-Tech Infrastructure
              </h3>
              <p className="np-serif mt-4 text-[15.5px] leading-[1.7] text-[var(--text-secondary)]">
                Backing infrastructure teams building the plumbing of the next compute cycle — capital-efficient, with a
                defensible wedge.
              </p>
              <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-subtle)]">
                <span>B2B Infrastructure</span>
                <span className="text-[var(--text-subtle)]">/</span>
                <span>Series A–B</span>
                <span className="text-[var(--text-subtle)]">/</span>
                <span>European Markets</span>
              </div>
            </div>
          </ScrollReveal>
        </section>

        {/* A3 — The market: the whole field scanned, the few that fit */}
        <MarketSection />

        {/* A4 — Method: how the judgment is formed */}
        <MethodSection />

        {/* A5 — The meta-agent: the system rewires itself */}
        <MetaAgentSection />

        {/* A6 — The record it produces */}
        <DashboardPreview />

        {/* A7 — The disagreement preserved inside the record */}
        <ReviewDisagreement />

        {/* A8 — The portfolio: what happens after invest */}
        <PortfolioSection />

        {/* A9 — On-demand lookup: drive it yourself */}
        <section
          id="lookup"
          className="w-full border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
          aria-labelledby="lookup-heading"
        >
          {/* The command line and record are the artifact; the explanation runs as a caption. */}
          <ScrollReveal className="page-margin-x py-[clamp(2rem,4.5vh,3rem)]" y={20} amount={0.16}>
            <p className="np-head np-label">A9 — On demand</p>

            <h2
              id="lookup-heading"
              className="editorial-display mt-6 max-w-[24ch] font-normal text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.02] tracking-[-0.02em] text-[var(--color-oxford)]"
            >
              Look up any company, get the <span className="italic text-[var(--color-accent)]">record</span>.
            </h2>

            <div className="mx-auto mt-8 w-full max-w-[760px]" aria-hidden>
              <LookupCommandBar query={DEMO_LOOKUP_QUERY} trailing="run" />
              <div className="mt-10 flex flex-col gap-4 md:flex-row md:gap-10">
                <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-subtle)] md:w-[120px]">
                  ↳ Record
                </p>
                <div className="w-full max-w-[520px]">
                  <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
                </div>
              </div>
            </div>

            <p className="np-serif mx-auto mt-10 max-w-[62ch] text-[13.5px] italic leading-[1.6] text-[var(--text-tertiary)]">
              Type any company name — on-demand lookup turns it into a sourced investment record in seconds,
              benchmarked against your active thesis the moment results arrive.
            </p>
          </ScrollReveal>
        </section>

        {/* Closing — the last word, set large with air */}
        <section
          className="w-full border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x py-[clamp(3rem,6vh,4.5rem)]">
            <ScrollReveal y={22} amount={0.25} className="max-w-[1100px]">
              <p className="np-head np-label">A10 — Access</p>
              <h2 className="editorial-display mt-3 max-w-[16ch] font-normal text-[clamp(2.85rem,8vw,7rem)] leading-[0.95] tracking-[-0.025em] text-[var(--color-oxford)]">
                For funds that need judgment with{' '}
                <span className="italic text-[var(--color-accent)]">memory</span>.
              </h2>
              <p className="np-serif mt-10 max-w-[46ch] text-[16.5px] leading-[1.75] text-[var(--text-secondary)]">
                Aethria turns sourcing, review, and partner decisions into one investment record — with the evidence
                trail attached.
              </p>
              <div className="mt-12">
                <a href="#access" onClick={(e) => scrollToAnchor(e, '#access')} className={CTA_TEXT_LINK_CLASS}>
                  <span>Request access</span>
                  <span aria-hidden>→</span>
                </a>
              </div>
            </ScrollReveal>
          </div>
        </section>

        {/* Footer — a real bg-colour break (oxford), the one dark moment on the page.
            The "request access" capture is its lead-in, not a separate section above it. */}
        <motion.footer
          className="home-footer relative z-20 w-full shrink-0 overflow-hidden bg-[var(--color-oxford)]"
          initial={reduce ? false : { opacity: 0, y: 18 }}
          whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.15 }}
          transition={{ duration: reduce ? 0 : 0.52, ease: SCROLL_EASE }}
        >
          <div id="access" className="page-margin-x relative z-10 mx-auto flex w-full max-w-[1200px] flex-col pt-12 pb-8 md:pt-16 md:pb-10">
            {/* The coupon — the access capture, folded into the footer's header */}
            <div className="grid grid-cols-1 gap-10 border-b border-solid border-[rgba(244,241,234,0.14)] pb-14 md:grid-cols-[0.8fr_1fr] md:gap-16 md:pb-16">
              <div className="max-w-md">
                <h2 className="editorial-display text-[clamp(1.9rem,3.8vw,2.7rem)] font-normal leading-[1.08] tracking-[-0.02em] text-[var(--text-inverse)]">
                  Request access.
                </h2>
                <p className="np-serif mt-4 text-[14.5px] leading-[1.65] text-[var(--text-inverse-secondary)]">
                  Complete the coupon. Seats open in small batches — we'll write when yours is ready. Occasional
                  notes on investment intelligence and product progress along the way.
                </p>
              </div>

              <AccessForm />
            </div>

            {/* Colophon — one flattened strip, no columns */}
            <div className="flex flex-col gap-6 pt-12 md:flex-row md:items-end md:justify-between md:gap-12">
              <div className="min-w-0">
                <Link
                  to="/home"
                  className="font-wordmark text-[22px] font-medium leading-none text-[var(--text-inverse)] transition-opacity hover:opacity-80"
                >
                  Aethria<span className="wordmark-dot" style={{ color: 'var(--color-brand-mark-inverse)' }}>.</span>
                </Link>
                <p className="np-serif mt-4 max-w-[46ch] text-[14.5px] leading-[1.7] text-[var(--text-inverse-secondary)]">
                  Private markets intelligence for funds that need the evidence trail, not another beautiful spreadsheet.
                </p>
              </div>
              <nav
                aria-label="Footer navigation"
                className="flex shrink-0 flex-wrap items-center gap-x-6 gap-y-3 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--text-inverse-muted)]"
              >
                <a
                  href="#access"
                  onClick={(e) => scrollToAnchor(e, '#access')}
                  className="transition-colors hover:text-[var(--color-brand-mark-inverse)]"
                >
                  Request access
                </a>
                <a
                  href={LINKEDIN_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-colors hover:text-[var(--color-brand-mark-inverse)]"
                >
                  LinkedIn
                </a>
              </nav>
            </div>

            <div className="mt-10 border-t border-solid border-[rgba(244,241,234,0.14)] pt-6 font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(244,241,234,0.5)]">
              <span>© {new Date().getFullYear()} Aethria</span>
            </div>
          </div>
        </motion.footer>
      </main>
    </div>
  );
}
