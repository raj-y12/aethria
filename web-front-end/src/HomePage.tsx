import { Link } from 'react-router-dom';
import { useEffect, useState, type ReactNode } from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import GrainOverlay from './components/GrainOverlay';
import MarketTape from './components/MarketTape';
import IntelligenceMap from './components/IntelligenceMap';
import DashboardPreview from './components/DashboardPreview';
import DeskClock from './components/DeskClock';
import HomeStatsSection from './components/HomeStatsSection';
import { ScrollReveal } from './components/ScrollReveal';
import { SCROLL_EASE } from './motionTokens';

export default function HomePage() {
  const reduce = useReducedMotion();

  const subtextVariants: Variants = reduce
    ? {
        hidden: { opacity: 1, y: 0 },
        visible: { opacity: 1, y: 0 },
      }
    : {
        hidden: { opacity: 0, y: 18 },
        visible: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.55, delay: 0.38, ease: SCROLL_EASE },
        },
      };

  const ctaVariants: Variants = reduce
    ? {
        hidden: { opacity: 1 },
        visible: { opacity: 1 },
      }
    : {
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: { duration: 0.45, delay: 0.72, ease: SCROLL_EASE },
        },
      };

  const heroViewport = { once: true as const, amount: 0.35 };

  const pipelineGridVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.09,
        delayChildren: reduce ? 0 : 0.06,
      },
    },
  };

  const pipelineCardVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.48, ease: SCROLL_EASE },
    },
  };

  const closingSectionVariants: Variants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: reduce ? 0 : 0.52,
        ease: SCROLL_EASE,
        staggerChildren: reduce ? 0 : 0.11,
        delayChildren: reduce ? 0 : 0.06,
      },
    },
  };

  const closingChildVariants: Variants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.46, ease: SCROLL_EASE },
    },
  };

  return (
    <div
      className="min-h-[100dvh] flex flex-col relative overflow-x-hidden w-full"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GrainOverlay opacity={0.028} variant="light" />

      <header
        className="inst-site-header sticky top-0 z-[100] w-full shrink-0 border-b border-solid border-[var(--section-divider)] bg-[var(--surface-base)]"
        style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}
      >
        <div className="page-margin-x grid min-h-[52px] grid-cols-[1fr_1fr] items-center gap-2 sm:gap-4 md:grid-cols-[1fr_auto_1fr]">
          <nav aria-label="Site navigation">
            <Link
              data-cursor-expand
              to="/"
              className="font-wordmark inline-flex min-h-[44px] items-center justify-self-start text-[15px] font-normal normal-case leading-none tracking-normal text-[var(--text-primary)] transition-opacity hover:opacity-80 sm:text-[16px]"
            >
              Aethria
            </Link>
          </nav>
          <p className="hidden justify-self-center text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)] md:block">
            Deal flow operating system
          </p>
          <DeskClock className="min-w-0 justify-self-end text-right" />
        </div>
      </header>

      <main className="relative z-10 flex-1 flex flex-col min-w-0 overflow-x-hidden">
        {/* Hero — paper column + Oxford monolith + ticker */}
        <div className="flex shrink-0 min-w-0 flex-col border-b border-solid border-[var(--section-divider)]">
          <div className="flex min-w-0 flex-col md:flex-row md:items-stretch">
            <section
              className="home-hero-left paper-dot-grid page-margin-x order-2 flex w-full shrink-0 flex-col justify-center py-16 md:py-24 md:w-[32%] lg:w-[28%]"
              style={{ backgroundColor: 'var(--color-paper)' }}
            >
              <motion.p
                className="section-numeral mb-6"
                aria-hidden
                initial={reduce ? false : { opacity: 0, y: 10 }}
                whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
                viewport={heroViewport}
                transition={{ duration: reduce ? 0 : 0.45, ease: SCROLL_EASE }}
              >
                I
              </motion.p>
              <motion.p
                className="mb-6 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]"
                initial={reduce ? false : { opacity: 0, y: 8 }}
                whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
                viewport={heroViewport}
                transition={{ duration: reduce ? 0 : 0.45, delay: reduce ? 0 : 0.06, ease: SCROLL_EASE }}
              >
                Early access · 2026
              </motion.p>

              <motion.p
                className="max-w-[36ch] font-sans text-[16px] leading-[1.65] text-[var(--text-secondary)] md:max-w-none"
                variants={subtextVariants}
                initial="hidden"
                whileInView="visible"
                viewport={heroViewport}
              >
                Autonomous discovery, structured review, and partner-ready memos before the committee opens the file. One
                pipeline. Full traceability. Conviction you can defend in the room.
              </motion.p>

              <motion.div
                variants={ctaVariants}
                initial="hidden"
                whileInView="visible"
                viewport={heroViewport}
                className="mt-10"
              >
                <Link
                  to="/request-access"
                  data-cursor-expand
                  className="group font-mono inline-flex w-full min-h-[44px] cursor-pointer items-center justify-center rounded-none bg-[var(--surface-strong)] px-6 py-3 text-[11px] uppercase tracking-[0.14em] text-[var(--text-inverse)] transition-colors duration-[250ms] ease hover:bg-[rgba(0,27,71,0.9)] md:w-fit"
                >
                  <span className="flex items-center justify-center">
                    <span>Request access</span>
                    <span
                      className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                      aria-hidden
                    >
                      {'\u00A0→'}
                    </span>
                  </span>
                </Link>
              </motion.div>
            </section>

          <div
            data-cursor-expand
            className="home-monolith-in order-1 relative flex w-full md:flex-1 min-h-[min(54vh,440px)] md:min-h-[min(74vh,840px)] items-center justify-start overflow-hidden px-6 py-24 sm:px-10 md:px-14 lg:px-16 xl:px-20 shrink-0"
            style={{
              backgroundColor: 'var(--color-oxford)',
            }}
          >
            <div className="home-monolith-ambient" aria-hidden />
            <div className="home-monolith-brass-rule" aria-hidden />
            <motion.h1
              data-cursor="headline"
              className="home-monolith-headline relative z-[1] w-full min-w-0 text-left text-[clamp(2.5rem,5.5vw,4.65rem)] leading-[0.98] max-w-[min(100%,15ch)] md:max-w-[17ch]"
              style={{ color: 'var(--color-paper)' }}
              initial={reduce ? false : { opacity: 0, x: -28 }}
              whileInView={reduce ? undefined : { opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.45 }}
              transition={{ duration: reduce ? 0 : 0.85, delay: reduce ? 0 : 0.2, ease: SCROLL_EASE }}
            >
              <span className="block tracking-[-0.035em]">Judgment</span>
              <span className="block mt-2 md:mt-3 italic font-normal opacity-[0.9] text-[0.88em] tracking-[-0.02em]">
                at institutional standard.
              </span>
            </motion.h1>
            <p
              className="absolute z-[2] right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(1rem,env(safe-area-inset-bottom))] font-mono text-[10px] tracking-[0.18em] uppercase text-[var(--text-inverse-secondary)] md:right-8 md:bottom-7 md:text-[11px]"
              aria-hidden
            >
              Protocol 4.1 · Oxford surface
            </p>
          </div>
          </div>

          <div className="relative z-10 w-full shrink-0">
            <MarketTape />
          </div>
        </div>

        <HomeStatsSection />

        {/* Section III — pipeline */}
        <section
          className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)] pb-8"
          aria-labelledby="pipeline-heading"
          style={{ backgroundColor: 'var(--color-paper)', color: 'var(--color-charcoal)' }}
        >
          <div className="w-full border-b border-solid border-[var(--section-divider)] pt-16 md:pt-24">
            <ScrollReveal className="page-margin-x" y={16} amount={0.2}>
              <p className="section-numeral mb-6" aria-hidden="true">III</p>
              <div className="flex min-w-0 flex-row items-stretch">
                <div className="flex min-w-0 flex-1 flex-col pr-0 md:pr-10">
                  <h2
                    id="pipeline-heading"
                    className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.15] tracking-[-0.02em] text-[#001433] md:text-[36px] md:tracking-normal"
                  >
                    The pipeline
                  </h2>
                  <p className="mt-4 max-w-xl font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.65)]">
                    From signal to position. Four locked phases. No hand-offs lost in email.
                  </p>
                </div>
                <div
                className="hidden w-[clamp(14rem,25vw,16.5rem)] shrink-0 flex-col items-end justify-center bg-[#001433] lg:flex"
                  style={{ paddingRight: 'max(16px, env(safe-area-inset-right))' }}
                >
                  <div className="flex flex-col items-end gap-2 text-right">
                    <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-secondary)]">
                      Phases I — IV
                    </p>
                    <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-muted)]">
                      Single audit trail
                    </p>
                  </div>
                </div>
              </div>
            </ScrollReveal>
          </div>

          <div className="page-margin-x flex flex-col pb-0 pt-6 md:pt-8">
            <motion.div
              className="grid w-full grid-cols-1 gap-0 divide-y divide-solid divide-[var(--section-divider)] lg:grid-cols-4 lg:divide-x lg:divide-y-0 lg:items-start"
              variants={pipelineGridVariants}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.12, margin: '0px 0px -5% 0px' }}
            >
              {[
                {
                  phase: 'I',
                  label: 'SCOUT',
                  body: 'Agents monitor market signals continuously against your fund thesis. When a name surfaces, context and sourcing are already assembled.',
                  signal: 'thesis-gated discovery',
                },
                {
                  phase: 'II',
                  label: 'REVIEW',
                  body: 'Structured evaluation across dimensions you define. Conviction emerges; uncertainty is explicit. On-demand lookup runs at any time.',
                  signal: 'conviction',
                },
                {
                  phase: 'III',
                  label: 'DECIDE',
                  body: 'Clear positions with reasoning attached. Advance, pass, or hold — no ambiguous queue.',
                  signal: 'precision',
                },
                {
                  phase: 'IV',
                  label: 'PORTFOLIO',
                  body: 'Decisions compound. Exposure, concentration, and follow-on judgment stay in view.',
                  signal: 'continuity',
                },
              ].map(({ phase, label, body, signal }) => (
                <motion.div
                  key={label}
                  variants={pipelineCardVariants}
                  className="flex min-w-0 flex-col border-l-0 border-solid border-[var(--section-divider)] px-0 py-8 first:pt-6 last:pb-6 sm:px-1 lg:border-l lg:px-8 lg:py-8 lg:first:pt-8 lg:last:pb-8"
                >
                  <div className="flex flex-row items-baseline justify-between gap-3">
                    <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-muted)]">{phase}</span>
                    <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--label-muted)]">{label}</span>
                  </div>
                  <div className="mt-0 h-px w-full shrink-0 bg-[var(--section-divider)]" aria-hidden />
                  <p className="mt-4 font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.78)]">{body}</p>
                  <p className="mt-6 font-sans text-[14px] italic leading-snug text-[var(--text-muted)] lowercase">
                    {signal}
                  </p>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </section>

        {/* Section IV — intelligence map (paper left, monolith right — mirrors hero rhythm) */}
        <section
          className="flex min-h-0 w-full flex-col items-stretch border-b border-solid border-[var(--section-divider)] lg:flex-row"
          aria-labelledby="graph-section-heading"
        >
          <ScrollReveal
            className="flex w-full shrink-0 flex-col justify-center self-stretch bg-[#f4f1ea] py-12 px-[max(1.25rem,var(--safe-left))] pb-10 pr-[max(1.25rem,var(--safe-right))] pt-12 md:py-14 md:px-8 lg:w-[35%] lg:px-12 lg:py-16"
            style={{ color: 'var(--color-charcoal)' }}
            y={24}
            amount={0.2}
          >
            <div className="w-full max-w-lg">
              <p className="section-numeral mb-6" aria-hidden="true">IV</p>
              <h2
                id="graph-section-heading"
                className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.15] tracking-[-0.02em] text-[#001433] md:text-[36px] md:tracking-normal"
              >
                How intelligence routes
              </h2>
              <p className="mt-4 max-w-lg font-sans text-[15px] font-normal leading-[1.7] text-[rgba(0,27,71,0.65)]">
                Scouts feed the reviewer. Partner logic and portfolio stay coupled. Meta-agent oversight on dashed paths.
              </p>
            </div>
          </ScrollReveal>
          <div className="relative flex w-full min-w-0 shrink-0 flex-col items-stretch bg-[#001433] lg:w-[65%]">
            <ScrollReveal
              className="flex min-h-[min(420px,72vw)] w-full flex-1 flex-col items-center justify-center px-3 pb-2 pt-4 sm:min-h-[460px] sm:px-4 lg:min-h-[500px] lg:px-0 lg:pb-0 lg:pt-0"
              y={16}
              delay={0.08}
              amount={0.15}
            >
              <IntelligenceMap variant="dark" />
            </ScrollReveal>
            <motion.p
              className="shrink-0 py-3 text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-muted)]"
              initial={reduce ? false : { opacity: 0 }}
              whileInView={reduce ? undefined : { opacity: 1 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: reduce ? 0 : 0.45, delay: reduce ? 0 : 0.12, ease: SCROLL_EASE }}
            >
              Scout · Review · Decide · Portfolio
            </motion.p>
          </div>
        </section>

        {/* Section V — live indicators */}
        <motion.section
          className="home-closing home-closing-ledger paper-dot-grid section-divider-top relative w-full overflow-hidden border-b border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
          variants={closingSectionVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.16, margin: '0px 0px -8% 0px' }}
        >
          <div className="page-margin-x relative z-[1] mx-auto w-full max-w-[1200px] py-16 md:py-24">
            <motion.p className="section-numeral mb-8 md:mb-12" aria-hidden variants={closingChildVariants}>
              V
            </motion.p>

            <div className="flex flex-col gap-10 md:gap-14 lg:flex-row lg:items-stretch lg:gap-16 xl:gap-24">
              <motion.div
                className="flex min-h-0 min-w-0 flex-1 flex-col justify-center py-6 md:py-10 lg:max-w-[540px] lg:py-12 lg:pr-6"
                variants={closingChildVariants}
              >
                <h2 className="text-[clamp(1.5rem,4.8vw,1.75rem)] font-normal leading-[1.2] tracking-[-0.02em] text-[#001433] md:text-[28px] md:tracking-normal">
                  <span className="block">Run the pipeline.</span>
                  <span className="mt-2 block">Keep the conviction.</span>
                </h2>
                <p className="mt-7 max-w-[420px] font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.78)]">
                  Aethria discovers, scores, and recommends. You advance, pass, or hold.
                </p>

                <ul
                  className="conviction-cap-lines mt-9 flex list-none flex-col gap-[12px] p-0 m-0"
                  aria-label="Product capabilities"
                >
                  {[
                    'FUND THESIS · MANDATE-GATED PIPELINE',
                    'ON-DEMAND LOOKUP · INSTANT COMPANY ANALYSIS',
                    'INVESTMENT MEMOS · FULL REASONING CHAIN',
                    'ESCALATIONS · HUMAN-IN-LOOP PATHS',
                    'PORTFOLIO SIGNALS · CONCENTRATION ANALYTICS',
                  ].map((line) => (
                    <li key={line} className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-muted)]">
                      {line}
                    </li>
                  ))}
                </ul>

                <Link
                  to="/request-access"
                  data-cursor-expand
                  className="group mt-11 inline-flex min-h-[44px] w-full cursor-pointer items-center justify-center rounded-none bg-[var(--surface-strong)] px-6 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--text-inverse)] transition-colors duration-[250ms] ease hover:bg-[rgba(0,27,71,0.9)] sm:w-fit"
                >
                  <span className="flex items-center justify-center">
                    <span>Request access</span>
                    <span
                      className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                      aria-hidden
                    >
                      {'\u00A0→'}
                    </span>
                  </span>
                </Link>
              </motion.div>
              <motion.div
                className="flex min-h-0 w-full min-w-0 flex-1 flex-col justify-center py-6 md:py-10 lg:py-12"
                variants={closingChildVariants}
              >
                <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
                  Live indicators
                </p>
                <LiveSignalPills />
              </motion.div>
            </div>
          </div>
        </motion.section>

        <DashboardPreview />

        {/* Section VII — Fund Thesis + On-Demand Lookup */}
        <section
          className="flex min-h-0 w-full flex-col items-stretch border-b border-solid border-[var(--section-divider)] lg:flex-row"
          aria-labelledby="thesis-lookup-heading"
        >
          {/* Left panel — Fund Thesis (oxford dark) */}
          <ScrollReveal
            className="flex w-full shrink-0 flex-col justify-center self-stretch bg-[#001433] py-14 px-[max(1.25rem,var(--safe-left))] pr-[max(1.25rem,var(--safe-right))] md:py-16 md:px-8 lg:w-1/2 lg:px-12 lg:py-20"
            y={20}
            amount={0.18}
          >
            <div className="w-full max-w-lg">
              <p className="section-numeral mb-6 text-[rgba(244,241,234,0.22)]" aria-hidden="true">VII</p>
              <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-[rgba(244,241,234,0.38)]">
                Configuration layer
              </p>
              <h2
                id="thesis-lookup-heading"
                className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.12] tracking-[-0.02em] text-[#f4f1ea]"
              >
                Define your mandate.
                <br />
                <span className="italic font-normal opacity-80 text-[0.92em]">The system obeys.</span>
              </h2>
              <p className="mt-5 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[rgba(244,241,234,0.6)]">
                Upload or write your investment thesis. Every scout, reviewer, and partner decision is gated against it — automatically, without re-configuration.
              </p>

              {/* Thesis card mock */}
              <div
                className="mt-8 border border-solid border-[rgba(244,241,234,0.12)] p-4 sm:p-5"
                aria-hidden
              >
                <div className="flex items-center justify-between">
                  <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-[rgba(244,241,234,0.35)]">
                    Active Mandate
                  </p>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="h-1.5 w-1.5 rounded-none bg-[#f4f1ea]"
                      style={{ opacity: 0.55, animation: 'pipeline-dot-pulse 2.4s ease-in-out infinite' }}
                    />
                    <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(244,241,234,0.45)]">
                      Live
                    </span>
                  </span>
                </div>
                <p className="mt-2.5 font-sans text-[15px] font-semibold text-[#f4f1ea]">
                  Deep-Tech Infrastructure
                </p>
                <p className="mt-1 font-sans text-[13px] leading-[1.6] text-[rgba(244,241,234,0.5)]">
                  Series A–B · European markets · B2B focus
                </p>
                <div className="mt-3 h-px bg-[rgba(244,241,234,0.1)]" />
                <p className="mt-3 font-sans text-[13px] italic leading-[1.65] text-[rgba(244,241,234,0.4)]">
                  "Backing infrastructure teams building the plumbing of the next compute cycle — prioritising capital efficiency and defensible wedge."
                </p>
              </div>
            </div>
          </ScrollReveal>

          {/* Right panel — On-Demand Lookup (paper light) */}
          <ScrollReveal
            className="flex w-full shrink-0 flex-col justify-center self-stretch bg-[#f4f1ea] py-14 px-[max(1.25rem,var(--safe-left))] pr-[max(1.25rem,var(--safe-right))] md:py-16 md:px-8 lg:w-1/2 lg:px-12 lg:py-20"
            y={20}
            delay={0.08}
            amount={0.18}
          >
            <div className="w-full max-w-lg">
              <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.12em] text-[rgba(0,27,71,0.38)]">
                Instant intelligence
              </p>
              <h2 className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.12] tracking-[-0.02em] text-[#001433]">
                Interrogate any name.
                <br />
                <span className="italic font-normal opacity-75 text-[0.92em]">Instantly.</span>
              </h2>
              <p className="mt-5 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.65)]">
                On-demand lookup delivers a full investment memo on any company in seconds. No pipeline wait. Benchmarked against your active thesis the moment results arrive.
              </p>

              {/* Lookup interface mock */}
              <div
                className="mt-8 border border-solid border-[var(--section-divider)]"
                aria-hidden
              >
                {/* Query bar */}
                <div className="flex items-center gap-3 border-b border-solid border-[var(--section-divider)] bg-[rgba(0,27,71,0.025)] px-4 py-2.5">
                  <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(0,27,71,0.35)]">
                    LOOKUP
                  </span>
                  <span className="h-3 w-px shrink-0 bg-[var(--section-divider)]" />
                  <span className="font-sans text-[13px] text-[rgba(0,27,71,0.65)]">Meridian Systems</span>
                  <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-[rgba(0,27,71,0.3)]">
                    ↵ run
                  </span>
                </div>

                {/* Result preview */}
                <div className="px-4 py-4">
                  <div className="mb-3 flex items-baseline justify-between gap-3">
                    <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.4)]">
                      Result
                    </p>
                    <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(0,27,71,0.35)]">
                      B2B Infrastructure · Series A
                    </p>
                  </div>
                  <p className="font-sans text-[18px] font-semibold leading-tight text-[#001433]">
                    STRONG.
                  </p>
                  <p className="mt-1.5 font-sans text-[13px] leading-[1.6] text-[rgba(0,27,71,0.58)]">
                    Thesis-aligned · High conviction · Pending unit economics review
                  </p>
                  <div className="mt-3 grid grid-cols-5 gap-x-2">
                    {['MKT', 'EXEC', 'PROD', 'TECH', 'DEF'].map((d, i) => (
                      <div key={d} className="flex flex-col items-center gap-0.5">
                        <span className="font-mono text-[10px] text-[rgba(0,27,71,0.35)]">{d}</span>
                        <span className="font-mono text-[11px] font-bold text-[rgba(0,27,71,0.7)]">
                          {[9, 8, 8, 9, 7][i]}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </section>

        <motion.footer
          className="home-footer paper-dot-grid section-divider-top relative z-20 w-full shrink-0"
          initial={reduce ? false : { opacity: 0, y: 18 }}
          whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: reduce ? 0 : 0.52, ease: SCROLL_EASE }}
        >
          <div className="page-margin-x mx-auto flex w-full max-w-[1200px] flex-col pt-14 pb-10 md:pt-24 md:pb-14">
            <p className="max-w-2xl font-sans text-[15px] font-normal leading-[1.7] text-[rgba(0,27,71,0.65)]">
              Private markets intelligence. Built for the standards of banks, advisors, and funds that cannot afford
              narrative drift.
            </p>

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

type PipelineStatus = 'ACTIVE' | 'PROCESSING' | 'IDLE';

const PIPELINE_STATUS_CYCLE: PipelineStatus[] = ['ACTIVE', 'PROCESSING', 'IDLE'];

const PIPELINE_STATUS_CONFIG: Record<
  PipelineStatus,
  { dot: string; dotAnimation?: string; label: string; valueOpacity: string }
> = {
  ACTIVE: {
    dot: 'bg-[var(--color-oxford)]',
    dotAnimation: 'pipeline-dot-pulse 2s ease-in-out infinite',
    label: 'ACTIVE',
    valueOpacity: 'text-[var(--color-oxford)]',
  },
  PROCESSING: {
    dot: 'bg-[rgba(0,27,71,0.45)]',
    dotAnimation: 'pipeline-dot-pulse 3.5s ease-in-out infinite',
    label: 'PROCESSING',
    valueOpacity: 'text-[rgba(0,27,71,0.55)]',
  },
  IDLE: {
    dot: 'bg-[rgba(0,27,71,0.2)]',
    dotAnimation: undefined,
    label: 'IDLE',
    valueOpacity: 'text-[rgba(0,27,71,0.3)]',
  },
};

function LiveSignalPills() {
  const reduce = useReducedMotion();
  const [dealsCount, setDealsCount] = useState(47);
  const [statusIndex, setStatusIndex] = useState(0);
  const [minutesAgo, setMinutesAgo] = useState(2);

  const pipelineStatus = PIPELINE_STATUS_CYCLE[statusIndex];
  const statusConfig = PIPELINE_STATUS_CONFIG[pipelineStatus];

  const pillListVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.09,
        delayChildren: reduce ? 0 : 0.05,
      },
    },
  };

  const pillItemVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, y: 12 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.42, ease: SCROLL_EASE },
    },
  };

  useEffect(() => {
    const dealsInterval = setInterval(() => {
      setDealsCount((prev) => prev + 1);
    }, 3500 + Math.random() * 2500);
    return () => clearInterval(dealsInterval);
  }, []);

  useEffect(() => {
    const statusInterval = setInterval(() => {
      setStatusIndex((prev) => (prev + 1) % PIPELINE_STATUS_CYCLE.length);
    }, 4000);
    return () => clearInterval(statusInterval);
  }, []);

  useEffect(() => {
    const minutesInterval = setInterval(() => {
      setMinutesAgo((prev) => prev + 1);
    }, 60000);
    return () => clearInterval(minutesInterval);
  }, []);

  return (
    <motion.div
      className="flex w-full max-w-md min-w-0 flex-1 flex-col self-stretch border-t border-[var(--section-divider)]"
      variants={pillListVariants}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.35, margin: '0px 0px -5% 0px' }}
    >
      <motion.div variants={pillItemVariants}>
        <SignalPill label="Deals reviewed this cycle" value={`${dealsCount}`} />
      </motion.div>

      {/* Pipeline status row — visually weighted by state */}
      <motion.div variants={pillItemVariants}>
        <SignalPill
          label="Pipeline status"
          prominent
          value={
            <span className={`inline-flex items-center gap-2 transition-colors duration-500 ${statusConfig.valueOpacity}`}>
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-none ${statusConfig.dot}`}
                style={statusConfig.dotAnimation ? { animation: statusConfig.dotAnimation } : undefined}
              />
              <span>{statusConfig.label}</span>
            </span>
          }
        />
      </motion.div>

      <motion.div variants={pillItemVariants}>
        <SignalPill label="Last memo generated" value={`${minutesAgo} min ago`} />
      </motion.div>
    </motion.div>
  );
}

function SignalPill({
  label,
  value,
  prominent = false,
}: {
  label: string;
  value: ReactNode;
  prominent?: boolean;
}) {
  return (
    <div className="flex min-h-[44px] items-center justify-between gap-3 border-b border-[var(--section-divider)] py-3 sm:gap-4">
      <div
        className={`font-mono text-[10px] uppercase tracking-[0.12em] ${
          prominent ? 'text-[rgba(0,27,71,0.6)]' : 'text-[rgba(0,27,71,0.45)]'
        }`}
      >
        {label}
      </div>
      <div className={prominent ? '' : 'font-sans text-[13px] font-semibold tabular-nums text-[var(--color-oxford)]'}>
        {value}
      </div>
    </div>
  );
}
