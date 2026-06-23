import { Link } from 'react-router-dom';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { CtaTextLink } from './components/CtaButton';
import GrainOverlay from './components/GrainOverlay';
import SiteHeader from './components/SiteHeader';
import RotatingSeal from './components/RotatingSeal';
import SectionKicker from './components/SectionKicker';
import PipelineSection from './components/PipelineSection';
import DashboardPreview from './components/DashboardPreview';
import ReviewDisagreement from './components/ReviewDisagreement';
import NewsletterBand from './components/NewsletterBand';
import { ScrollReveal } from './components/ScrollReveal';
import { SCROLL_EASE } from './motionTokens';
import {
  DEMO_LOOKUP_QUERY,
  DEMO_LOOKUP_RESULT,
  LookupCommandBar,
  LookupResultSnapshot,
  MandateCard,
} from '@aethria/product-chrome';

const LINKEDIN_URL = 'https://www.linkedin.com/company/aethria';

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

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GrainOverlay opacity={0.028} variant="light" />

      <SiteHeader />

      <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-x-hidden">
        {/* Hero — 白 / quiet luxury: the statement sits low, oceans of air above, seal alone in the void */}
        <section
          className="home-hero-section relative flex min-h-[calc(82vh-64px)] w-full flex-col overflow-hidden"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          {/* Seal — alone in the open upper-right, the single mark in the void */}
          <div
            className="pointer-events-none absolute z-0 hidden lg:block"
            style={{ right: 'var(--page-margin-x)', top: 'clamp(5rem, 13vh, 8.5rem)' }}
          >
            <motion.div
              initial={reduce ? false : { opacity: 0, scale: 0.9 }}
              animate={reduce ? undefined : { opacity: 1, scale: 1 }}
              transition={{ duration: 1.2, delay: 0.6, ease: SCROLL_EASE }}
            >
              <RotatingSeal className="h-[150px] w-[150px] xl:h-[184px] xl:w-[184px]" />
            </motion.div>
          </div>

          {/* Lead — vertically centred, comfortable air without a cavernous top gap */}
          <div className="page-margin-x relative z-10 flex w-full flex-1 flex-col justify-center pb-[7vh] pt-10">
            <motion.div
              className="mb-10 flex items-center gap-4"
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={reduce ? undefined : { opacity: 1, y: 0 }}
              transition={{ duration: reduce ? 0 : 0.5, delay: reduce ? 0 : 0.2, ease: SCROLL_EASE }}
            >
              <span className="font-mono text-[11px] tracking-[0.14em] text-[var(--label-muted)]">01</span>
              <span className="h-px w-12 bg-[var(--section-divider)]" />
              <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--label-muted)]">
                The thesis engine
              </span>
            </motion.div>

            <motion.h1
              className="editorial-display max-w-[17ch] font-normal text-[clamp(2.85rem,8.6vw,8rem)] leading-[0.96] tracking-[-0.025em] text-[var(--color-oxford)]"
              initial={reduce ? false : { opacity: 0, y: 26 }}
              animate={reduce ? undefined : { opacity: 1, y: 0 }}
              transition={{ duration: reduce ? 0 : 1, delay: reduce ? 0 : 0.1, ease: SCROLL_EASE }}
            >
              Private market judgment, made{' '}
              <span className="italic text-[var(--color-accent)]">inspectable</span>.
            </motion.h1>

            <motion.div
              className="mt-12 flex flex-col gap-8 md:flex-row md:items-end md:justify-between md:gap-16"
              variants={subtextVariants}
              initial="hidden"
              animate="visible"
            >
              <p className="max-w-[42ch] font-sans text-[clamp(15px,1.4vw,18px)] leading-[1.7] text-[var(--text-secondary)]">
                An autonomous analyst that sources, reviews, and decides on startups for venture funds — and shows its
                work in one record you can open.
              </p>
              <div className="flex items-center gap-7">
                <CtaTextLink to="/request-access">Request access</CtaTextLink>
                <span className="hidden font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-subtle)] sm:inline">
                  By invitation
                </span>
              </div>
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
          <ScrollReveal
            className="page-margin-x grid items-end gap-14 py-[clamp(6rem,16vh,12rem)] md:grid-cols-[1fr_0.74fr] md:gap-20"
            y={20}
            amount={0.18}
          >
            <div className="max-w-xl">
              <SectionKicker folio="02" label="The mandate" className="mb-8" />
              <h2
                id="mandate-heading"
                className="editorial-display font-normal text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
              >
                It only looks for what you{' '}
                <span className="italic text-[var(--color-accent)]">tell it to</span>.
              </h2>
              <p className="mt-8 max-w-[46ch] font-sans text-[16px] leading-[1.75] text-[var(--text-secondary)]">
                Write the investment thesis once. Scouts, reviewers, and partner logic treat the mandate as a hard
                constraint — not a decorative preference. Change the thesis, and the whole system narrows with it.
              </p>
            </div>

            <div className="w-full max-w-[420px] md:justify-self-end">
              <MandateCard
                variant="paper"
                title="Deep-Tech Infrastructure"
                tags={['B2B Infrastructure', 'Series A–B', 'European Markets']}
                excerpt="Backing infrastructure teams building the plumbing of the next compute cycle — capital-efficient, with a defensible wedge."
                live
                className="bg-transparent p-7 sm:p-8"
              />
              <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)]">
                Active mandate
              </p>
            </div>
          </ScrollReveal>
        </section>

        {/* 2 — Pipeline: what actually runs */}
        <PipelineSection />

        {/* 3 — The record it produces */}
        <DashboardPreview />

        {/* 4 — The disagreement preserved inside the record */}
        <ReviewDisagreement />

        {/* 5 — On-demand lookup: drive it yourself */}
        <section
          id="lookup"
          className="w-full border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
          aria-labelledby="lookup-heading"
        >
          <ScrollReveal className="page-margin-x py-[clamp(6rem,16vh,12rem)]" y={20} amount={0.16}>
            <div className="max-w-[900px]">
              <SectionKicker folio="06" label="On demand" className="mb-8" />
              <h2
                id="lookup-heading"
                className="editorial-display font-normal text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
              >
                Look up any company.{' '}
                <span className="italic text-[var(--color-accent)]">Get the record.</span>
              </h2>
              <p className="mt-8 max-w-[52ch] font-sans text-[16px] leading-[1.75] text-[var(--text-secondary)]">
                Type any company name. On-demand lookup turns it into a sourced investment record in seconds — no
                pipeline wait — benchmarked against your active thesis the moment results arrive.
              </p>
            </div>

            {/* Input line → record below: the interaction as a vertical flow */}
            <div className="mx-auto mt-14 w-full max-w-[760px]" aria-hidden>
              <LookupCommandBar query={DEMO_LOOKUP_QUERY} trailing="run" />
              <div className="mt-8 flex flex-col gap-3 md:flex-row md:gap-10">
                <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)] md:w-[120px] md:pt-1.5">
                  ↳ Record
                </p>
                <div className="w-full max-w-[520px]">
                  <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
                </div>
              </div>
            </div>
          </ScrollReveal>
        </section>

        {/* Closing — the last word, set large with air */}
        <section
          className="w-full border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x py-[clamp(8rem,22vh,16rem)]">
            <ScrollReveal y={22} amount={0.25} className="max-w-[1100px]">
              <SectionKicker folio="07" label="Access" className="mb-10" />
              <h2 className="editorial-display max-w-[16ch] font-normal text-[clamp(2.85rem,8vw,7rem)] leading-[0.95] tracking-[-0.025em] text-[var(--color-oxford)]">
                For funds that need judgment with{' '}
                <span className="italic text-[var(--color-accent)]">memory</span>.
              </h2>
              <p className="mt-10 max-w-[46ch] font-sans text-[16px] leading-[1.75] text-[var(--text-secondary)]">
                Aethria turns sourcing, review, and partner decisions into one investment record — with the evidence
                trail attached.
              </p>
              <div className="mt-12">
                <CtaTextLink to="/request-access">Request access</CtaTextLink>
              </div>
            </ScrollReveal>
          </div>
        </section>

        <NewsletterBand />

        <motion.footer
          className="home-footer relative z-20 w-full shrink-0 border-t border-solid border-[var(--section-divider)]"
          style={{ backgroundColor: 'var(--color-paper)' }}
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
                  className="font-wordmark text-[22px] font-medium leading-none text-[var(--color-oxford)] transition-opacity hover:opacity-80"
                >
                  Aethria<span className="wordmark-dot">.</span>
                </Link>
                <p className="mt-4 max-w-[34ch] font-sans text-[14px] leading-[1.7] text-[var(--text-secondary)]">
                  Private markets intelligence for funds that need the evidence trail, not another beautiful spreadsheet.
                </p>
              </div>

              {FOOTER_COLUMNS.map((col) => (
                <div key={col.heading} className="min-w-0">
                  <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
                    {col.heading}
                  </p>
                  <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                    {col.items.map((item) => (
                      <li key={item} className="font-sans text-[14px] leading-[1.5] text-[var(--text-muted)]">
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}

              <div className="min-w-0">
                <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">Access</p>
                <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
                  <li>
                    <Link to="/request-access" className="accent-link">
                      <span>Request access</span>
                      <span aria-hidden>→</span>
                    </Link>
                  </li>
                  <li>
                    <a
                      href={LINKEDIN_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="accent-link"
                    >
                      <span>LinkedIn</span>
                      <span aria-hidden>→</span>
                    </a>
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
                className="home-footer-tag btn-interaction inline-flex min-h-[44px] shrink-0 items-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)] transition-opacity hover:opacity-70"
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
