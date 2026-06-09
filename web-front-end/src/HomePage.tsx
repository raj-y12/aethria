import { Link } from 'react-router-dom';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import GrainOverlay from './components/GrainOverlay';
import MarketTape from './components/MarketTape';
import IntelligenceMap from './components/IntelligenceMap';
import HomeStatsSection from './components/HomeStatsSection';
import PipelineSection from './components/PipelineSection';
import BeliefSection from './components/BeliefSection';
import FieldNotes from './components/FieldNotes';
import DeskClock from './components/DeskClock';
import { ScrollReveal } from './components/ScrollReveal';
import { SCROLL_EASE } from './motionTokens';
import {
  DEMO_LOOKUP_RESULT,
  DEMO_MANDATE_DARK,
  LookupResultSnapshot,
  MandateCard,
} from '@aethria/product-chrome';

const FOOTER_COLUMNS: { heading: string; items: string[] }[] = [
  { heading: 'Product', items: ['Fund thesis', 'On-demand lookup', 'Investment memos', 'Portfolio signals'] },
  { heading: 'Pipeline', items: ['Scout', 'Review', 'Decide', 'Portfolio'] },
];

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
              to="/home"
              className="font-wordmark inline-flex min-h-[44px] items-center justify-self-start text-[15px] font-medium normal-case leading-none tracking-normal text-[var(--text-primary)] transition-opacity hover:opacity-80 sm:text-[16px]"
            >
              Aethria<span className="wordmark-dot">.</span>
            </Link>
          </nav>
          <p className="hidden justify-self-center text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)] md:block">
            Deal flow operating system
          </p>
          <DeskClock className="min-w-0 justify-self-end text-right" />
        </div>
      </header>

      <main className="relative z-10 flex-1 flex flex-col min-w-0 overflow-x-hidden">
        {/* Section I — Hero: paper column + Oxford monolith + ticker */}
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
                className="accent-eyebrow mb-6"
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
                      {' →'}
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
                  at institutional <span className="accent-underline">standard.</span>
                </span>
              </motion.h1>
              <p
                className="absolute z-[2] right-[max(1.25rem,env(safe-area-inset-right))] bottom-[max(1rem,env(safe-area-inset-bottom))] font-mono text-[11px] tracking-[0.1em] uppercase text-[var(--text-inverse-secondary)] md:right-8 md:bottom-7"
                aria-hidden
              >
                Secure Session · Institutional Access
              </p>
            </div>
          </div>

          <div className="relative z-10 w-full shrink-0">
            <MarketTape />
          </div>
        </div>

        {/* Section II — operating metrics */}
        <HomeStatsSection />

        {/* Section III — the belief */}
        <BeliefSection />

        {/* Section IV — the pipeline */}
        <PipelineSection />

        {/* Section V — intelligence map (paper) */}
        <section
          className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)', color: 'var(--color-charcoal)' }}
          aria-labelledby="graph-section-heading"
        >
          <motion.div className="page-margin-x py-14 md:py-20">
            <ScrollReveal y={20} amount={0.2}>
              <p className="section-numeral mb-6" aria-hidden="true">
                V
              </p>
              <h2
                id="graph-section-heading"
                className="max-w-xl text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.15] tracking-[-0.02em] text-[#001433] md:text-[36px] md:tracking-normal"
              >
                How intelligence routes
              </h2>
              <p className="mt-4 max-w-xl font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.65)]">
                Scouts feed the reviewer. Partner logic and portfolio stay coupled. Meta-agent oversight on dashed paths.
              </p>
            </ScrollReveal>

            <ScrollReveal
              className="mt-10 flex h-[min(380px,68vw)] w-full flex-col sm:h-[420px] md:mt-12 lg:h-[460px]"
              y={16}
              delay={0.06}
              amount={0.12}
            >
              <IntelligenceMap variant="light" />
            </ScrollReveal>

            <p className="mt-6 text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
              Scout · Review · Decide · Portfolio
            </p>
          </motion.div>
        </section>

        {/* Section VI — Field Notes (editorial grid) */}
        <FieldNotes />

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
              <p className="section-numeral mb-6 text-[rgba(244,241,234,0.22)]" aria-hidden="true">
                VII
              </p>
              <p className="accent-eyebrow mb-3">Configuration layer</p>
              <h2
                id="thesis-lookup-heading"
                className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.12] tracking-[-0.02em] text-[#f4f1ea]"
              >
                Define your mandate.
                <br />
                <span className="italic font-normal opacity-80 text-[0.92em]">
                  The system <span className="accent-underline">obeys.</span>
                </span>
              </h2>
              <p className="mt-5 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[rgba(244,241,234,0.6)]">
                Upload or write your investment thesis. Every scout, reviewer, and partner decision is gated against that mandate with visible lineage.
              </p>

              <div className="mt-8" aria-hidden>
                <MandateCard {...DEMO_MANDATE_DARK} />
              </div>
            </div>
          </ScrollReveal>

          {/* Right panel — On-Demand Lookup (paper light) */}
          <ScrollReveal
            className="flex w-full shrink-0 flex-col justify-center self-stretch border-t border-solid border-[var(--section-divider)] bg-[#f4f1ea] py-14 px-[max(1.25rem,var(--safe-left))] pr-[max(1.25rem,var(--safe-right))] md:py-16 md:px-8 lg:w-1/2 lg:border-l lg:border-t-0 lg:px-12 lg:py-20"
            y={20}
            delay={0.08}
            amount={0.18}
          >
            <div className="w-full max-w-lg">
              <p className="accent-eyebrow mb-3">Instant intelligence</p>
              <h2 className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.12] tracking-[-0.02em] text-[#001433]">
                Interrogate any name.
                <br />
                <span className="italic font-normal opacity-75 text-[0.92em]">
                  <span className="accent-underline">Instantly.</span>
                </span>
              </h2>
              <p className="mt-5 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.65)]">
                On-demand lookup delivers a full investment memo on any company in seconds. No pipeline wait. Benchmarked against your active thesis the moment results arrive.
              </p>

              <div className="mt-8" aria-hidden>
                <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
              </div>
            </div>
          </ScrollReveal>
        </section>

        {/* Section VIII — closing CTA (Oxford block, à la Balderton's pre-footer band) */}
        <section
          className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x py-16 md:py-24">
            <ScrollReveal
              y={22}
              amount={0.2}
              className="mx-auto w-full max-w-[1100px] bg-[var(--color-oxford)] px-7 py-14 md:px-16 md:py-20"
            >
              <div className="flex flex-col gap-10 md:flex-row md:items-center md:justify-between">
                <div className="max-w-xl">
                  <p className="section-numeral section-numeral--on-dark mb-5 font-mono" aria-hidden>
                    VIII
                  </p>
                  <h2 className="text-[clamp(2rem,4.5vw,2.75rem)] font-normal leading-[1.1] tracking-[-0.02em] text-[var(--color-paper)]">
                    Run the pipeline.
                    <br />
                    <span className="italic opacity-90">Keep the conviction.</span>
                  </h2>
                  <p className="mt-5 max-w-[44ch] font-sans text-[15px] leading-[1.7] text-[var(--text-inverse-secondary)]">
                    Aethria discovers, scores, and recommends. You advance, pass, or hold — with the reasoning attached.
                  </p>
                </div>

                <Link
                  to="/request-access"
                  data-cursor-expand
                  className="group inline-flex min-h-[44px] w-full shrink-0 cursor-pointer items-center justify-center rounded-none bg-[var(--color-accent)] px-7 py-3.5 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--color-paper)] transition-colors duration-[250ms] ease hover:bg-[var(--color-accent-strong)] sm:w-fit"
                >
                  <span className="flex items-center justify-center">
                    <span>Request access</span>
                    <span
                      className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
                      aria-hidden
                    >
                      {' →'}
                    </span>
                  </span>
                </Link>
              </div>
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
              {/* Brand */}
              <div className="min-w-0">
                <Link
                  to="/home"
                  data-cursor-expand
                  className="font-wordmark text-[20px] font-medium leading-none text-[var(--color-oxford)] transition-opacity hover:opacity-80"
                >
                  Aethria<span className="wordmark-dot">.</span>
                </Link>
                <p className="mt-4 max-w-[34ch] font-sans text-[14px] leading-[1.7] text-[var(--text-secondary)]">
                  Private markets intelligence. Built for the standards of banks, advisors, and funds that cannot afford
                  narrative drift.
                </p>
              </div>

              {/* Capability columns (presentational — feature categories, not routes) */}
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

              {/* Access */}
              <div className="min-w-0">
                <p className="accent-eyebrow accent-eyebrow--bare mb-4">Access</p>
                <ul className="flex list-none flex-col gap-2.5 p-0 m-0">
                  <li>
                    <Link
                      to="/request-access"
                      data-cursor-expand
                      className="accent-link"
                    >
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
