import { Link } from 'react-router-dom';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { CtaTextLink } from './components/CtaButton';
import GrainOverlay from './components/GrainOverlay';
import SiteHeader from './components/SiteHeader';
import SectionKicker from './components/SectionKicker';
import MarketSection from './components/MarketSection';
import MethodSection from './components/MethodSection';
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
        {/* Hero — 白 / quiet luxury: the statement sits low, oceans of air above */}
        <section
          className="home-hero-section relative flex min-h-[calc(82vh-64px)] w-full flex-col overflow-hidden"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          {/* Provenance — a quiet institutional mark in the void, no motion */}
          <div
            className="pointer-events-none absolute z-0 hidden text-right lg:block"
            style={{ right: 'var(--page-margin-x)', top: 'clamp(5rem, 13vh, 8.5rem)' }}
          >
            <motion.p
              className="font-mono text-[10px] uppercase leading-[1.9] tracking-[0.16em] text-[var(--text-subtle)]"
              initial={reduce ? false : { opacity: 0 }}
              animate={reduce ? undefined : { opacity: 1 }}
              transition={{ duration: 1.2, delay: 0.6, ease: SCROLL_EASE }}
            >
              AETHRIA_CORE // OPERATIONAL
              <br />
              Fund intelligence · v2
            </motion.p>
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

            <div className="w-full max-w-[440px] md:justify-self-end">
              <div className="border border-solid border-[var(--section-divider)] bg-[var(--color-paper-deep)] p-8 sm:p-10">
                <div className="flex items-center justify-between">
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)]">
                    Active mandate
                  </p>
                  <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--color-accent)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" aria-hidden /> Live
                  </span>
                </div>
                <h3 className="mt-7 editorial-display text-[clamp(1.5rem,2.6vw,2.1rem)] font-normal leading-[1.1] tracking-[-0.01em] text-[var(--color-oxford)]">
                  Deep-Tech Infrastructure
                </h3>
                <p className="mt-4 font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
                  Backing infrastructure teams building the plumbing of the next compute cycle — capital-efficient, with a
                  defensible wedge.
                </p>
                <div className="mt-8 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-solid border-[var(--section-divider)] pt-6 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
                  <span>B2B Infrastructure</span>
                  <span className="text-[var(--text-subtle)]">/</span>
                  <span>Series A–B</span>
                  <span className="text-[var(--text-subtle)]">/</span>
                  <span>European Markets</span>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </section>

        {/* 2 — The market: the whole field scanned, the few that fit */}
        <MarketSection />

        {/* 3 — Method: how the judgment is formed */}
        <MethodSection />

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
            <div className="mx-auto mt-16 w-full max-w-[760px] md:mt-20" aria-hidden>
              <LookupCommandBar query={DEMO_LOOKUP_QUERY} trailing="run" />
              <div className="mt-10 flex flex-col gap-4 md:flex-row md:gap-10">
                <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)] md:w-[120px] md:pt-2">
                  ↳ Record
                </p>
                <div className="w-full max-w-[520px] border border-solid border-[var(--section-divider)] bg-[var(--color-paper-deep)] p-4 sm:p-6">
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
          {/* Colophon — one flattened strip, no columns. The wordmark and the one-line
              descriptor read like a book's closing imprint; the nav collapses into a single
              slash-separated run of micro-links beneath it. */}
          <div className="page-margin-x mx-auto flex w-full max-w-[1200px] flex-col pt-16 pb-10 md:pt-24 md:pb-14">
            <div className="flex flex-col gap-6 border-b border-solid border-[var(--section-divider)] pb-10 md:flex-row md:items-end md:justify-between md:gap-12">
              <div className="min-w-0">
                <Link
                  to="/home"
                  className="font-wordmark text-[22px] font-medium leading-none text-[var(--color-oxford)] transition-opacity hover:opacity-80"
                >
                  Aethria<span className="wordmark-dot">.</span>
                </Link>
                <p className="mt-4 max-w-[46ch] font-sans text-[14px] leading-[1.7] text-[var(--text-secondary)]">
                  Private markets intelligence for funds that need the evidence trail, not another beautiful spreadsheet.
                </p>
              </div>
              <p className="shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-subtle)] md:text-right">
                AETHRIA_CORE // OPERATIONAL
                <br />
                Build {new Date().getFullYear()}.{String(new Date().getMonth() + 1).padStart(2, '0')}
              </p>
            </div>

            <nav
              aria-label="Footer navigation"
              className="flex flex-wrap items-center gap-x-3 gap-y-3 pt-8 font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--label-muted)]"
            >
              {FOOTER_COLUMNS.flatMap((col) => col.items)
                .concat(['Request access', 'LinkedIn'])
                .map((item, i, arr) => {
                  const isLast = i === arr.length - 1;
                  const isAccess = item === 'Request access';
                  const isLinkedIn = item === 'LinkedIn';
                  const node = isAccess ? (
                    <Link key={item} to="/request-access" className="transition-colors hover:text-[var(--color-accent)]">
                      {item}
                    </Link>
                  ) : isLinkedIn ? (
                    <a
                      key={item}
                      href={LINKEDIN_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="transition-colors hover:text-[var(--color-accent)]"
                    >
                      {item}
                    </a>
                  ) : (
                    <span key={item}>{item}</span>
                  );
                  return (
                    <span key={`${item}-wrap`} className="inline-flex items-center gap-3">
                      {node}
                      {!isLast && <span aria-hidden className="text-[var(--text-subtle)]">/</span>}
                    </span>
                  );
                })}
            </nav>

            <div className="mt-10 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-solid border-[var(--section-divider)] pt-6 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-muted)]">
              <span>© {new Date().getFullYear()} Aethria</span>
              <span aria-hidden className="text-[var(--text-subtle)]">/</span>
              <span>Confidential</span>
              <span aria-hidden className="text-[var(--text-subtle)]">/</span>
              <span>For qualified recipients</span>
              <span aria-hidden className="text-[var(--text-subtle)]">/</span>
              <span>Investment intelligence</span>
            </div>
          </div>
        </motion.footer>
      </main>
    </div>
  );
}
