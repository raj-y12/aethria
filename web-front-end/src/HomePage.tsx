import { Link } from 'react-router-dom';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { CtaLink } from './components/CtaButton';
import GrainOverlay from './components/GrainOverlay';
import SiteHeader from './components/SiteHeader';
import MarketTape from './components/MarketTape';
import PipelineSection from './components/PipelineSection';
import DashboardPreview from './components/DashboardPreview';
import ReviewDisagreement from './components/ReviewDisagreement';
import NewsletterBand from './components/NewsletterBand';
import { ScrollReveal } from './components/ScrollReveal';
import { SCROLL_EASE } from './motionTokens';
import { DEMO_LOOKUP_RESULT, DEMO_MANDATE_DARK, LookupResultSnapshot, MandateCard } from '@aethria/product-chrome';

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

  const heroViewport = { once: true as const, amount: 0.3 };

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GrainOverlay opacity={0.028} variant="light" />

      <SiteHeader />

      <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-x-hidden">
        {/* Hero — copy only; product UI lives in Inside Aethria */}
        <section
          className="home-hero-section paper-dot-grid relative w-full overflow-hidden"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x w-full max-w-[920px] pt-14 pb-0 md:pt-20">
            <motion.p
              className="accent-eyebrow mb-8 md:mb-10"
              initial={reduce ? false : { opacity: 0, y: 8 }}
              whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
              viewport={heroViewport}
              transition={{ duration: reduce ? 0 : 0.45, ease: SCROLL_EASE }}
            >
              Aethria · Private markets intelligence
            </motion.p>

            <motion.h1
              className="editorial-display max-w-[14ch] text-[clamp(2.75rem,6vw,4.25rem)] leading-[1.02] text-[var(--color-oxford)]"
              initial={reduce ? false : { opacity: 0, y: 26 }}
              whileInView={reduce ? undefined : { opacity: 1, y: 0 }}
              viewport={heroViewport}
              transition={{ duration: reduce ? 0 : 0.85, delay: reduce ? 0 : 0.08, ease: SCROLL_EASE }}
            >
              Private market judgment, made <span className="accent-underline">inspectable</span>.
            </motion.h1>

            <motion.p
              className="mt-8 max-w-[56ch] font-sans text-[clamp(16px,1.6vw,19px)] font-medium leading-[1.55] text-[var(--color-oxford)]"
              variants={subtextVariants}
              initial="hidden"
              whileInView="visible"
              viewport={heroViewport}
            >
              Scout real companies against your fund thesis. Run three independent reviews. Record the partner decision
              — automatically.
            </motion.p>

            <motion.p
              className="mt-5 max-w-[50ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]"
              variants={subtextVariants}
              initial="hidden"
              whileInView="visible"
              viewport={heroViewport}
            >
              Every recommendation ships with source trail, reviewer disagreement, dimension scores, and mandate fit in
              one investment record.
            </motion.p>

            <motion.div
              className="mt-10 shrink-0"
              variants={subtextVariants}
              initial="hidden"
              whileInView="visible"
              viewport={heroViewport}
            >
              <CtaLink to="/request-access" className="w-full px-[72px] sm:w-fit">
                Request access
              </CtaLink>
            </motion.div>
          </div>

          <div className="relative z-10 mt-12 w-full shrink-0 md:mt-16">
            <MarketTape />
          </div>
        </section>

        {/* Journey order: define the mandate → see what runs → see the record + disagreement → look up on demand. */}

        {/* 1 — Mandate: the constraint that drives everything */}
        <section id="mandate" className="w-full bg-[var(--color-oxford)]" aria-labelledby="mandate-heading">
          <ScrollReveal
            className="page-margin-x flex flex-col gap-10 py-16 md:flex-row md:items-center md:gap-16 md:py-24"
            y={20}
            amount={0.18}
          >
            <div className="w-full max-w-xl shrink-0 md:w-[52%]">
              <p className="accent-eyebrow accent-eyebrow--inverse mb-6">Mandate · the constraint</p>
              <h2
                id="mandate-heading"
                className="editorial-display text-[clamp(2rem,5vw,3.25rem)] text-[var(--color-paper)]"
              >
                Define your mandate.
                <br />
                The system narrows.
              </h2>
              <p className="mt-6 max-w-[46ch] font-sans text-[16px] leading-[1.7] text-[rgba(244,235,230,0.66)]">
                Upload or write the investment thesis once. Scouts, reviewers, and partner logic use the mandate as the
                constraint, not a decorative preference.
              </p>
            </div>

            <div className="w-full max-w-md shrink-0 md:flex-1">
              <div aria-hidden>
                <MandateCard {...DEMO_MANDATE_DARK} />
              </div>
              <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(244,241,234,0.38)]">
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
          className="paper-dot-grid w-full"
          style={{ backgroundColor: 'var(--color-paper)' }}
          aria-labelledby="lookup-heading"
        >
          <ScrollReveal
            className="page-margin-x flex flex-col gap-10 py-16 md:flex-row md:items-center md:gap-16 md:py-24"
            y={20}
            amount={0.18}
          >
            <div className="w-full max-w-[460px] shrink-0 md:w-[46%]">
              <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
                Lookup result · sample output
              </p>
              <div aria-hidden>
                <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
              </div>
            </div>

            <div className="w-full max-w-xl shrink-0 md:flex-1">
              <p className="accent-eyebrow mb-6">On-demand record</p>
              <h2
                id="lookup-heading"
                className="editorial-display text-[clamp(2rem,5vw,3.25rem)] text-[var(--color-oxford)]"
              >
                Look up any company.
                <br />
                Get the record.
              </h2>
              <p className="mt-6 max-w-[46ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
                On-demand lookup turns a company name into a sourced investment record — no pipeline wait. Benchmarked
                against your active thesis the moment results arrive.
              </p>
            </div>
          </ScrollReveal>
        </section>

        {/* Closing CTA */}
        <section
          className="paper-dot-grid w-full"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <div className="page-margin-x py-16 md:py-28">
            <ScrollReveal y={22} amount={0.25} className="max-w-[820px]">
              <h2 className="editorial-display max-w-[14ch] text-[clamp(2.4rem,6.5vw,4.5rem)] text-[var(--color-oxford)]">
                For funds that need judgment with memory.
              </h2>
              <p className="mt-6 max-w-[48ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
                Request access to see how Aethria turns sourcing, review, and partner decisions into one investment
                record.
              </p>
              <CtaLink to="/request-access" className="mt-10 w-full px-[72px] sm:w-fit">
                Request access
              </CtaLink>
            </ScrollReveal>
          </div>
        </section>

        <NewsletterBand />

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
