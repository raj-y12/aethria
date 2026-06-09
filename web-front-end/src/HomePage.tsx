import type { MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import GrainOverlay from './components/GrainOverlay';
import MarketTape from './components/MarketTape';
import IntelligenceMap from './components/IntelligenceMap';
import HomeStatsSection from './components/HomeStatsSection';
import PipelineSection from './components/PipelineSection';
import BeliefSection from './components/BeliefSection';
import FieldNotes from './components/FieldNotes';
import { ScrollReveal } from './components/ScrollReveal';
import { SCROLL_EASE } from './motionTokens';

const NAV_LINKS = [
  { label: 'Pipeline', href: '#pipeline' },
  { label: 'Intelligence', href: '#intelligence' },
  { label: 'Method', href: '#method' },
];

function scrollToAnchor(e: MouseEvent<HTMLAnchorElement>, href: string) {
  const el = document.querySelector(href);
  if (!el) return;
  e.preventDefault();
  const lenis = (window as unknown as { __lenis?: { scrollTo: (t: Element, o?: { offset?: number }) => void } }).__lenis;
  if (lenis) lenis.scrollTo(el, { offset: -72 });
  else el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
import {
  DEMO_LOOKUP_RESULT,
  DEMO_MANDATE_DARK,
  LookupResultSnapshot,
  MandateCard,
} from '@aethria/product-chrome';

const HERO_STAGES = [
  { n: 'I', label: 'Scout', note: 'Signals, sourced' },
  { n: 'II', label: 'Review', note: 'Scored to thesis' },
  { n: 'III', label: 'Decide', note: 'Positions, reasoned' },
  { n: 'IV', label: 'Portfolio', note: 'Conviction, tracked' },
];

const FOOTER_COLUMNS: { heading: string; items: string[] }[] = [
  { heading: 'Product', items: ['Fund thesis', 'On-demand lookup', 'Investment memos', 'Portfolio signals'] },
  { heading: 'Pipeline', items: ['Scout', 'Review', 'Decide', 'Portfolio'] },
];

export default function HomePage() {
  const reduce = useReducedMotion();

  const subtextVariants: Variants = reduce
    ? { hidden: { opacity: 1, y: 0 }, visible: { opacity: 1, y: 0 } }
    : {
        hidden: { opacity: 0, y: 18 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.55, delay: 0.34, ease: SCROLL_EASE } },
      };

  const ctaVariants: Variants = reduce
    ? { hidden: { opacity: 1 }, visible: { opacity: 1 } }
    : {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { duration: 0.45, delay: 0.6, ease: SCROLL_EASE } },
      };

  const stripVariants: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: reduce ? 0 : 0.07, delayChildren: reduce ? 0 : 0.2 } },
  };
  const tileVariants: Variants = {
    hidden: reduce ? { opacity: 1 } : { opacity: 0, y: 14 },
    visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : 0.5, ease: SCROLL_EASE } },
  };

  const heroViewport = { once: true as const, amount: 0.3 };

  return (
    <div
      className="min-h-[100dvh] flex flex-col relative overflow-x-hidden w-full"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GrainOverlay opacity={0.028} variant="light" />

      <header
        className="inst-site-header sticky top-0 z-[100] w-full shrink-0 border-b border-solid border-[var(--section-divider)] bg-[rgba(244,241,234,0.85)] backdrop-blur-md"
        style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}
      >
        <div className="page-margin-x flex min-h-[64px] items-center justify-between gap-6">
          <Link
            data-cursor-expand
            to="/home"
            aria-label="Aethria — home"
            className="font-wordmark inline-flex min-h-[44px] shrink-0 items-center text-[20px] font-medium normal-case leading-none tracking-normal text-[var(--text-primary)] transition-opacity hover:opacity-80 sm:text-[21px]"
          >
            Aethria<span className="wordmark-dot">.</span>
          </Link>

          <nav aria-label="Section navigation" className="hidden items-center gap-9 md:flex">
            {NAV_LINKS.map((item) => (
              <a
                key={item.href}
                href={item.href}
                onClick={(e) => scrollToAnchor(e, item.href)}
                data-cursor-expand
                className="font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--label-muted)] transition-colors duration-200 hover:text-[var(--color-oxford)]"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      <main className="relative z-10 flex-1 flex flex-col min-w-0 overflow-x-hidden">
        {/* ───────────── Section I — Hero ───────────── */}
        <section
          className="paper-dot-grid relative w-full overflow-hidden border-b border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x mx-auto w-full max-w-[1440px] pt-16 pb-12 md:pt-24 md:pb-16">
            <motion.p
              className="accent-eyebrow mb-8 md:mb-12"
              initial={reduce ? false : { opacity: 0, y: 8 }}
              whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
              viewport={heroViewport}
              transition={{ duration: reduce ? 0 : 0.45, ease: SCROLL_EASE }}
            >
              Aethria · Deal flow operating system
            </motion.p>

            <motion.h1
              data-cursor="headline"
              className="editorial-display max-w-[15ch] text-[clamp(2.85rem,9.2vw,7.75rem)] text-[var(--color-oxford)]"
              initial={reduce ? false : { opacity: 0, y: 26 }}
              whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
              viewport={heroViewport}
              transition={{ duration: reduce ? 0 : 0.85, delay: reduce ? 0 : 0.08, ease: SCROLL_EASE }}
            >
              Judgment at <span className="accent-underline">institutional</span> standard.
            </motion.h1>

            <div className="mt-10 flex flex-col gap-8 md:mt-14 md:flex-row md:items-end md:justify-between">
              <motion.p
                className="max-w-[50ch] font-sans text-[clamp(15px,1.5vw,18px)] leading-[1.7] text-[var(--text-secondary)]"
                variants={subtextVariants}
                initial="hidden"
                whileInView="visible"
                viewport={heroViewport}
              >
                Autonomous discovery, structured review, and partner-ready memos before the committee opens the file.
                One pipeline. Full traceability. Conviction you can defend in the room.
              </motion.p>

              <motion.div
                variants={ctaVariants}
                initial="hidden"
                whileInView="visible"
                viewport={heroViewport}
                className="shrink-0"
              >
                <Link
                  to="/request-access"
                  data-cursor-expand
                  className="group inline-flex h-9 w-full items-center justify-center rounded-none bg-[var(--surface-strong)] px-[72px] font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse)] transition-colors duration-[250ms] ease hover:bg-[rgba(0,20,51,0.9)] sm:w-fit"
                >
                  <span>Request access</span>
                  <span
                    className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                    aria-hidden
                  >
                    {' →'}
                  </span>
                </Link>
              </motion.div>
            </div>
          </div>

          {/* Full-bleed stage strip — Balderton's headshot-row beat, in Oxford */}
          <motion.div
            className="grid grid-cols-2 gap-px border-t border-solid border-[var(--section-divider)] bg-[rgba(244,235,230,0.14)] md:grid-cols-4"
            variants={stripVariants}
            initial={reduce ? false : 'hidden'}
            whileInView="visible"
            viewport={{ once: true, amount: 0.2 }}
          >
            {HERO_STAGES.map((s) => (
              <motion.div
                key={s.label}
                variants={tileVariants}
                className="relative flex min-h-[124px] flex-col justify-between bg-[var(--color-oxford)] p-6 md:min-h-[156px] md:p-7"
              >
                <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-inverse-muted)]">{s.n}</span>
                <div>
                  <p className="font-display text-[21px] leading-none text-[var(--color-paper)] md:text-[25px]">
                    {s.label}
                  </p>
                  <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-inverse-muted)]">
                    {s.note}
                  </p>
                </div>
              </motion.div>
            ))}
          </motion.div>

          <div className="relative z-10 w-full shrink-0 border-t border-solid border-[var(--section-divider)]">
            <MarketTape />
          </div>
        </section>

        {/* Section II — operating metrics */}
        <HomeStatsSection />

        {/* Section III — the belief */}
        <BeliefSection />

        {/* Section IV — the pipeline */}
        <PipelineSection />

        {/* ───────────── Section V — intelligence map ───────────── */}
        <section
          id="intelligence"
          className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
          aria-labelledby="graph-section-heading"
        >
          <div className="page-margin-x py-16 md:py-24">
            <ScrollReveal y={20} amount={0.2} className="mx-auto max-w-[760px] text-center">
              <p className="section-numeral mb-6" aria-hidden="true">
                V
              </p>
              <h2
                id="graph-section-heading"
                className="editorial-display text-[clamp(2rem,5.5vw,3.25rem)] text-[var(--color-oxford)]"
              >
                How intelligence routes
              </h2>
              <p className="mx-auto mt-5 max-w-[54ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
                Scouts feed the reviewer. Partner logic and portfolio stay coupled. Meta-agent oversight on the dashed
                paths.
              </p>
            </ScrollReveal>

            <ScrollReveal
              className="mx-auto mt-12 flex h-[min(380px,68vw)] w-full max-w-[1100px] flex-col sm:h-[420px] md:mt-16 lg:h-[460px]"
              y={16}
              delay={0.06}
              amount={0.12}
            >
              <IntelligenceMap variant="light" />
            </ScrollReveal>

            <p className="mt-8 text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
              Scout · Review · Decide · Portfolio
            </p>
          </div>
        </section>

        {/* Section VI — Field Notes (editorial grid) */}
        <FieldNotes />

        {/* ───────────── Section VII — Fund Thesis + On-Demand Lookup ───────────── */}
        <section
          className="flex min-h-0 w-full flex-col items-stretch border-b border-solid border-[var(--section-divider)] lg:flex-row"
          aria-labelledby="thesis-lookup-heading"
        >
          <ScrollReveal
            className="flex w-full shrink-0 flex-col justify-center self-stretch bg-[var(--color-oxford)] py-14 px-[max(1.25rem,var(--safe-left))] pr-[max(1.25rem,var(--safe-right))] md:py-16 md:px-8 lg:w-1/2 lg:px-14 lg:py-24"
            y={20}
            amount={0.18}
          >
            <div className="w-full max-w-lg">
              <p className="section-numeral mb-6 text-[rgba(244,235,230,0.22)]" aria-hidden="true">
                VII
              </p>
              <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.14em] text-[rgba(244,241,234,0.42)]">
                Configuration layer
              </p>
              <h2
                id="thesis-lookup-heading"
                className="editorial-display text-[clamp(2rem,5vw,3rem)] text-[var(--color-paper)]"
              >
                Define your mandate.
                <br />
                <span className="italic font-normal opacity-80">The system obeys.</span>
              </h2>
              <p className="mt-6 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[rgba(244,235,230,0.62)]">
                Upload or write your investment thesis. Every scout, reviewer, and partner decision is gated against that
                mandate with visible lineage.
              </p>

              <div className="mt-9" aria-hidden>
                <MandateCard {...DEMO_MANDATE_DARK} />
              </div>
            </div>
          </ScrollReveal>

          <ScrollReveal
            className="paper-dot-grid flex w-full shrink-0 flex-col justify-center self-stretch border-t border-solid border-[var(--section-divider)] py-14 px-[max(1.25rem,var(--safe-left))] pr-[max(1.25rem,var(--safe-right))] md:py-16 md:px-8 lg:w-1/2 lg:border-l lg:border-t-0 lg:px-14 lg:py-24"
            y={20}
            delay={0.08}
            amount={0.18}
          >
            <div className="w-full max-w-lg">
              <p className="accent-eyebrow mb-4">Instant intelligence</p>
              <h2 className="editorial-display text-[clamp(2rem,5vw,3rem)] text-[var(--color-oxford)]">
                Interrogate any name.
                <br />
                <span className="italic font-normal opacity-70">Instantly.</span>
              </h2>
              <p className="mt-6 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[rgba(0,20,51,0.66)]">
                On-demand lookup delivers a full investment memo on any company in seconds. No pipeline wait. Benchmarked
                against your active thesis the moment results arrive.
              </p>

              <div className="mt-9" aria-hidden>
                <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
              </div>
            </div>
          </ScrollReveal>
        </section>

        {/* ───────────── Section VIII — closing CTA ───────────── */}
        <section
          className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x py-16 md:py-28">
            <ScrollReveal y={22} amount={0.25} className="mx-auto max-w-[820px] text-center">
              <p className="section-numeral mb-6" aria-hidden>
                VIII
              </p>
              <h2 className="editorial-display text-[clamp(2.4rem,6.5vw,4.5rem)] text-[var(--color-oxford)]">
                Run the pipeline.
                <br />
                Keep the <span className="italic">conviction.</span>
              </h2>
              <p className="mx-auto mt-6 max-w-[48ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
                Aethria discovers, scores, and recommends. You advance, pass, or hold — with the reasoning attached.
              </p>
              <Link
                to="/request-access"
                data-cursor-expand
                className="group mx-auto mt-10 inline-flex h-9 w-full items-center justify-center rounded-none bg-[var(--surface-strong)] px-[72px] font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse)] transition-colors duration-[250ms] ease hover:bg-[rgba(0,20,51,0.9)] sm:w-fit"
              >
                <span>Request access</span>
                <span
                  className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                  aria-hidden
                >
                  {' →'}
                </span>
              </Link>
            </ScrollReveal>
          </div>
        </section>

        <motion.footer
          className="home-footer paper-dot-grid relative z-20 w-full shrink-0"
          initial={reduce ? false : { opacity: 0, y: 18 }}
          whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: reduce ? 0 : 0.52, ease: SCROLL_EASE }}
        >
          <div className="page-margin-x mx-auto flex w-full max-w-[1200px] flex-col pt-16 pb-10 md:pt-24 md:pb-14">
            <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 md:grid-cols-[1.6fr_1fr_1fr_1fr] md:gap-12">
              <div className="min-w-0">
                <Link
                  to="/home"
                  data-cursor-expand
                  className="font-wordmark text-[22px] font-medium leading-none text-[var(--color-oxford)] transition-opacity hover:opacity-80"
                >
                  Aethria<span className="wordmark-dot">.</span>
                </Link>
                <p className="mt-4 max-w-[34ch] font-sans text-[14px] leading-[1.7] text-[var(--text-secondary)]">
                  Private markets intelligence. Built for the standards of banks, advisors, and funds that cannot afford
                  narrative drift.
                </p>
              </div>

              {FOOTER_COLUMNS.map((col) => (
                <div key={col.heading} className="min-w-0">
                  <p className="accent-eyebrow accent-eyebrow--bare mb-4">{col.heading}</p>
                  <ul className="flex list-none flex-col gap-2.5 p-0 m-0">
                    {col.items.map((item) => (
                      <li key={item} className="font-sans text-[14px] leading-[1.5] text-[var(--text-muted)]">
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}

              <div className="min-w-0">
                <p className="accent-eyebrow accent-eyebrow--bare mb-4">Access</p>
                <ul className="flex list-none flex-col gap-2.5 p-0 m-0">
                  <li>
                    <Link to="/request-access" data-cursor-expand className="accent-link">
                      <span>Request access</span>
                      <span aria-hidden>→</span>
                    </Link>
                  </li>
                  <li className="font-sans text-[14px] leading-[1.5] text-[var(--text-muted)]">
                    Confidential · qualified recipients
                  </li>
                </ul>
              </div>
            </div>

            <div className="my-12 h-px w-full shrink-0 bg-[var(--section-divider)]" aria-hidden />

            <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between lg:gap-12">
              <div className="flex flex-col gap-4 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)] md:flex-row md:flex-wrap md:items-center md:gap-x-10 md:gap-y-3">
                <span className="text-[var(--label-muted)]">© {new Date().getFullYear()} Aethria</span>
                <span className="break-words">Confidential · For qualified recipients</span>
                <span>Investment intelligence</span>
              </div>
              <Link
                to="/request-access"
                data-cursor-expand
                className="home-footer-tag inline-flex min-h-[44px] shrink-0 items-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)] transition-opacity hover:opacity-70"
              >
                Request access
              </Link>
            </div>
          </div>
        </motion.footer>
      </main>
    </div>
  );
}
