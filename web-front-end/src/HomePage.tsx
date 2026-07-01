import { useEffect, useRef, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, useReducedMotion, type Variants } from 'framer-motion';
import GrainOverlay from './components/GrainOverlay';
import SiteHeader from './components/SiteHeader';
import MarketTape from './components/MarketTape';
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
  'group inline-flex items-center gap-3.5 border-b border-solid border-[var(--color-oxford)] pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-oxford)] transition-[gap] duration-300 ease-out hover:gap-6';

/** Smooth-scrolls to an in-page anchor via Lenis when present, matching SiteHeader's nav links. */
function scrollToAnchor(e: MouseEvent<HTMLAnchorElement>, href: string) {
  const el = document.querySelector(href);
  if (!el) return;
  e.preventDefault();
  const lenis = (window as unknown as { __lenis?: { scrollTo: (t: Element, o?: { offset?: number }) => void } }).__lenis;
  if (lenis) lenis.scrollTo(el, { offset: -88 });
  else el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

const FOOTER_COLUMNS: { heading: string; items: string[] }[] = [
  { heading: 'Product', items: ['Fund thesis', 'On-demand lookup', 'Investment memos', 'Portfolio signals'] },
  { heading: 'Pipeline', items: ['Scout', 'Review', 'Decide', 'Portfolio'] },
];

export default function HomePage() {
  const reduce = useReducedMotion();
  const sidebarRef = useRef<HTMLDivElement | null>(null);
  const sidebarInView = useInView(sidebarRef, { once: true, amount: 0.5 });

  // The application form lives at the bottom of this page now (no separate
  // /request-access route); honour old bookmarked/shared #access links.
  useEffect(() => {
    if (window.location.hash !== '#access') return;
    const el = document.getElementById('access');
    if (!el) return;
    const t = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
    return () => clearTimeout(t);
  }, []);

  const subtextVariants: Variants = reduce
    ? { hidden: { opacity: 1, y: 0 }, visible: { opacity: 1, y: 0 } }
    : {
        hidden: { opacity: 0, y: 18 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.55, delay: 0.34, ease: SCROLL_EASE } },
      };

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GrainOverlay opacity={0.028} variant="light" />

      <SiteHeader />

      <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-x-hidden">
        {/* Front page — masthead, lede, and a live record sit above the fold together,
            so a first-time visitor reads what it does before the philosophy of how. */}
        <section
          className="home-hero-section relative w-full overflow-hidden"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x flex items-center justify-between pt-7 font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--text-subtle)]">
            <span>Vol. I · No. 1</span>
            <span className="hidden sm:inline">Fund Intelligence Edition</span>
            <span>By invitation</span>
          </div>

          <motion.div
            className="mt-3 text-center"
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={reduce ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: reduce ? 0 : 0.8, ease: SCROLL_EASE }}
          >
            <p className="font-wordmark text-[clamp(2.1rem,5vw,3.1rem)] font-medium leading-none tracking-[-0.01em] text-[var(--color-oxford)]">
              Aethria<span className="wordmark-dot">.</span>
            </p>
            <p className="mt-2 font-mono text-[9.5px] uppercase tracking-[0.24em] text-[var(--text-subtle)]">
              — Private market judgment, recorded —
            </p>
          </motion.div>

          <div className="mt-5">
            <MarketTape />
          </div>

          <div className="page-margin-x grid grid-cols-1 gap-x-14 gap-y-14 py-[clamp(3rem,7vh,5rem)] lg:grid-cols-[1.85fr_1fr]">
            {/* Lede */}
            <div>
              <motion.p
                className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]"
                initial={reduce ? false : { opacity: 0, y: 8 }}
                animate={reduce ? undefined : { opacity: 1, y: 0 }}
                transition={{ duration: reduce ? 0 : 0.6, delay: reduce ? 0 : 0.15, ease: SCROLL_EASE }}
              >
                Lede — The Thesis Engine
              </motion.p>

              <motion.h1
                className="editorial-display mt-3 max-w-[17ch] font-normal text-[clamp(2.5rem,6vw,5.2rem)] leading-[1.0] tracking-[-0.02em] text-[var(--color-oxford)]"
                initial={reduce ? false : { opacity: 0, y: 20 }}
                animate={reduce ? undefined : { opacity: 1, y: 0 }}
                transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.25, ease: SCROLL_EASE }}
              >
                Private market judgment, made{' '}
                <span className="italic text-[var(--color-accent)]">inspectable</span>.
              </motion.h1>

              <motion.p
                className="mt-6 max-w-[54ch] border-t border-solid border-[var(--section-divider)] pt-5 font-display text-[clamp(1.05rem,1.6vw,1.25rem)] italic leading-[1.55] text-[var(--text-secondary)]"
                variants={subtextVariants}
                initial="hidden"
                animate="visible"
              >
                Continuously discovers companies, reviews them against your fund thesis, records disagreement, and
                produces investment-ready records — every decision traceable to its evidence.
              </motion.p>

              <motion.p
                className="mt-4 font-mono text-[9.5px] uppercase tracking-[0.12em] text-[var(--text-subtle)]"
                initial={reduce ? false : { opacity: 0 }}
                animate={reduce ? undefined : { opacity: 1 }}
                transition={{ duration: reduce ? 0 : 0.6, delay: reduce ? 0 : 0.55 }}
              >
                By the partner engine · updated continuously
              </motion.p>

              <motion.div
                className="mt-6 max-w-[640px] font-sans text-[14px] leading-[1.68] text-[var(--text-secondary)] sm:columns-2 sm:gap-9"
                initial={reduce ? false : { opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: reduce ? 0 : 0.7, ease: SCROLL_EASE }}
              >
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
              </motion.div>

              <a href="#market" onClick={(e) => scrollToAnchor(e, '#market')} className={`${CTA_TEXT_LINK_CLASS} mt-7`}>
                <span>See today's full record</span>
                <span aria-hidden>→</span>
              </a>
            </div>

            {/* Sidebar — today's record, above the fold */}
            <motion.div
              ref={sidebarRef}
              initial={reduce ? false : { opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: reduce ? 0 : 0.8, ease: SCROLL_EASE }}
            >
              <p className="flex items-center gap-2 border-t border-solid border-[var(--section-divider)] pt-4 font-mono text-[9.5px] uppercase tracking-[0.16em] text-[var(--text-subtle)]">
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
              <p className="mt-5 font-display text-[12.5px] italic leading-[1.55] text-[var(--text-secondary)]">
                "Reviewer disagreement surfaced. Mandate fit recorded." — the actual output, not a mockup.
              </p>
            </motion.div>
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
            className="page-margin-x grid items-start gap-10 py-[clamp(2.5rem,6vh,4rem)] md:grid-cols-[0.8fr_1fr] md:gap-16"
            y={20}
            amount={0.18}
          >
            <div className="max-w-md md:sticky md:top-32">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">A2 — Mandate</p>
              <p
                id="mandate-heading"
                className="mt-6 font-sans text-[clamp(1.15rem,2.1vw,1.5rem)] font-light leading-[1.5] text-[var(--color-oxford)]"
              >
                It only looks for what you tell it to. Write the investment thesis once — scouts, reviewers, and
                partner logic treat it as a hard constraint, not a decorative preference.
              </p>
            </div>

            <div className="w-full max-w-[480px] md:justify-self-end">
              <div className="flex items-center justify-between border-t border-solid border-[var(--section-divider)] pt-5">
                <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-subtle)]">
                  Active mandate
                </p>
                <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-accent)]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" aria-hidden /> Live
                </span>
              </div>
              <h3 className="mt-6 editorial-display text-[clamp(1.5rem,2.6vw,2.1rem)] font-normal leading-[1.1] tracking-[-0.01em] text-[var(--color-oxford)]">
                Deep-Tech Infrastructure
              </h3>
              <p className="mt-4 font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
                Backing infrastructure teams building the plumbing of the next compute cycle — capital-efficient, with a
                defensible wedge.
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-subtle)]">
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
          {/* Interaction-first — the command line and record lead; the explanation is a
              caption underneath, not a headline above. Inverts the title→content order
              used by the other sections so the page doesn't read as one repeated template. */}
          <ScrollReveal className="page-margin-x py-[clamp(2.5rem,6vh,4rem)]" y={20} amount={0.16}>
            <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">A9 — On demand</p>

            <div className="mx-auto mt-8 w-full max-w-[760px]" aria-hidden>
              <LookupCommandBar query={DEMO_LOOKUP_QUERY} trailing="run" />
              <div className="mt-10 flex flex-col gap-4 border-t border-solid border-[var(--section-divider)] pt-8 md:flex-row md:gap-10">
                <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-subtle)] md:w-[120px]">
                  ↳ Record
                </p>
                <div className="w-full max-w-[520px]">
                  <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
                </div>
              </div>
            </div>

            <p
              id="lookup-heading"
              className="mx-auto mt-12 max-w-[52ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]"
            >
              <span className="text-[var(--color-oxford)]">Look up any company, get the record.</span> Type any
              company name — on-demand lookup turns it into a sourced investment record in seconds, benchmarked
              against your active thesis the moment results arrive.
            </p>
          </ScrollReveal>
        </section>

        {/* Closing — the last word, set large with air */}
        <section
          className="w-full border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x py-[clamp(3.5rem,8vh,5.5rem)]">
            <ScrollReveal y={22} amount={0.25} className="max-w-[1100px]">
              <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">A10 — Access</p>
              <h2 className="editorial-display mt-3 max-w-[16ch] font-normal text-[clamp(2.85rem,8vw,7rem)] leading-[0.95] tracking-[-0.025em] text-[var(--color-oxford)]">
                For funds that need judgment with{' '}
                <span className="italic text-[var(--color-accent)]">memory</span>.
              </h2>
              <p className="mt-10 max-w-[46ch] font-sans text-[16px] leading-[1.75] text-[var(--text-secondary)]">
                Aethria turns sourcing, review, and partner decisions into one investment record — with the evidence
                trail attached.
              </p>
              <div className="mt-12">
                <a href="#access" onClick={(e) => scrollToAnchor(e, '#access')} className={CTA_TEXT_LINK_CLASS}>
                  <span>Request access</span>
                  <span aria-hidden>→</span>
                </a>
              </div>
              <p className="mt-8 font-mono text-[9.5px] uppercase tracking-[0.2em] text-[var(--text-subtle)]">
                — End of record —
              </p>
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
          <GrainOverlay opacity={0.03} variant="dark" />

          <div id="access" className="page-margin-x relative z-10 mx-auto flex w-full max-w-[1200px] flex-col pt-12 pb-8 md:pt-16 md:pb-10">
            {/* The coupon — the access capture, folded into the footer's header */}
            <div className="grid grid-cols-1 gap-10 border-b border-solid border-[rgba(244,241,234,0.14)] pb-14 md:grid-cols-[0.8fr_1fr] md:gap-16 md:pb-16">
              <div className="max-w-md">
                <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-brand-mark-inverse)]">
                  Notice of subscriber access
                </p>
                <h2 className="mt-4 editorial-display text-[clamp(1.9rem,3.8vw,2.7rem)] font-normal leading-[1.08] tracking-[-0.02em] text-[var(--text-inverse)]">
                  Request access.
                </h2>
                <p className="mt-4 font-sans text-[14px] leading-[1.65] text-[var(--text-inverse-secondary)]">
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
                <p className="mt-4 max-w-[46ch] font-sans text-[14px] leading-[1.7] text-[var(--text-inverse-secondary)]">
                  Private markets intelligence for funds that need the evidence trail, not another beautiful spreadsheet.
                </p>
              </div>
              <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[rgba(244,241,234,0.4)] md:text-right">
                AETHRIA_CORE // OPERATIONAL
                <br />
                Build {new Date().getFullYear()}.{String(new Date().getMonth() + 1).padStart(2, '0')}
              </p>
            </div>

            <nav
              aria-label="Footer navigation"
              className="flex flex-wrap items-center gap-x-3 gap-y-3 pt-8 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--text-inverse-muted)]"
            >
              {FOOTER_COLUMNS.flatMap((col) => col.items)
                .concat(['Request access', 'LinkedIn'])
                .map((item, i, arr) => {
                  const isLast = i === arr.length - 1;
                  const isAccess = item === 'Request access';
                  const isLinkedIn = item === 'LinkedIn';
                  const node = isAccess ? (
                    <a
                      key={item}
                      href="#access"
                      onClick={(e) => scrollToAnchor(e, '#access')}
                      className="transition-colors hover:text-[var(--color-brand-mark-inverse)]"
                    >
                      {item}
                    </a>
                  ) : isLinkedIn ? (
                    <a
                      key={item}
                      href={LINKEDIN_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="transition-colors hover:text-[var(--color-brand-mark-inverse)]"
                    >
                      {item}
                    </a>
                  ) : (
                    <span key={item}>{item}</span>
                  );
                  return (
                    <span key={`${item}-wrap`} className="inline-flex items-center gap-3">
                      {node}
                      {!isLast && <span aria-hidden className="text-[rgba(244,241,234,0.25)]">/</span>}
                    </span>
                  );
                })}
            </nav>

            <div className="mt-10 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-solid border-[rgba(244,241,234,0.14)] pt-6 font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(244,241,234,0.5)]">
              <span>© {new Date().getFullYear()} Aethria</span>
              <span aria-hidden className="text-[rgba(244,241,234,0.25)]">/</span>
              <span>Confidential</span>
              <span aria-hidden className="text-[rgba(244,241,234,0.25)]">/</span>
              <span>For qualified recipients</span>
              <span aria-hidden className="text-[rgba(244,241,234,0.25)]">/</span>
              <span>Investment intelligence</span>
            </div>
          </div>
        </motion.footer>
      </main>
    </div>
  );
}
