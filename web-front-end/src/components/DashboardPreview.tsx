import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

const PAPER = '#f4f1ea';

const DIMENSION_SCORES: { label: string; score: string }[] = [
  { label: 'MARKET', score: '9/10' },
  { label: 'EXECUTION', score: '8/10' },
  { label: 'PRODUCT', score: '8/10' },
  { label: 'TECHNICAL', score: '9/10' },
  { label: 'DEFENSIBILITY', score: '7/10' },
];

const THESIS_CRITERIA = ['B2B Infrastructure', 'Series A–B', 'European Markets'];

export default function DashboardPreview() {
  const reduce = useReducedMotion();

  const rowVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.1,
        delayChildren: reduce ? 0 : 0.04,
      },
    },
  };

  const leftColVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, y: 22 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.52, ease: SCROLL_EASE },
    },
  };

  const thesisCardVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, x: 28 },
    visible: {
      opacity: 1,
      x: 0,
      transition: { duration: reduce ? 0 : 0.52, ease: SCROLL_EASE },
    },
  };

  const memoCardVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, x: 28 },
    visible: {
      opacity: 1,
      x: 0,
      transition: { duration: reduce ? 0 : 0.65, delay: reduce ? 0 : 0.1, ease: SCROLL_EASE },
    },
  };

  const stripVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, scaleY: 0.92 },
    visible: {
      opacity: 1,
      scaleY: 1,
      transition: { duration: reduce ? 0 : 0.45, ease: SCROLL_EASE },
    },
  };

  return (
    <section className="section-divider-top flex w-full overflow-hidden border-b border-solid border-[var(--section-divider)]">
      <motion.div
        className="w-2 shrink-0 self-stretch origin-top bg-[#001433] sm:w-6 md:w-12"
        aria-hidden
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.4 }}
        variants={stripVariants}
      />
      <div className="min-w-0 flex-1 self-stretch" style={{ backgroundColor: PAPER }}>
        <motion.div
          className="page-margin-x flex flex-col gap-10 pt-14 pb-12 sm:gap-12 sm:pt-20 sm:pb-14 md:flex-row md:items-start md:gap-16 md:pt-24 md:pb-16"
          variants={rowVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.12, margin: '0px 0px -10% 0px' }}
        >
          {/* Left column */}
          <motion.div className="relative w-full max-w-xl shrink-0 md:w-[40%] md:pt-9" variants={leftColVariants}>
            <p className="section-numeral mb-6 md:absolute md:left-0 md:top-4 md:mb-0">VI</p>
            <p className="mb-3 font-mono text-[12px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.5)]">
              Inside Aethria
            </p>
            <h2 className="mb-6 text-[clamp(2.15rem,4.2vw,3rem)] leading-[1.08] text-[var(--color-oxford)]">
              The system thinks
              <br />
              before you decide.
            </h2>

            <div className="mt-2 flex flex-col gap-8">
              {[
                {
                  label: 'FUND THESIS',
                  body: 'Your investment mandate governs every decision. Scouts, reviewers, and partners all operate within your defined criteria — automatically, with no configuration drift.',
                },
                {
                  label: 'ON-DEMAND LOOKUP',
                  body: 'Request instant analysis on any company. A full memo surfaces in seconds, drawn from live signals and benchmarked against your active thesis.',
                },
                {
                  label: 'ESCALATION QUEUE',
                  body: 'Edge cases surfaced with precision. Disagreement signals and confidence gaps flagged for human judgment, not buried in the pipeline.',
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="border-l border-solid border-[var(--section-divider)] pl-3 md:pl-4"
                >
                  <p className="mb-1.5 font-mono text-[12px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.82)]">
                    {item.label}
                  </p>
                  <p className="font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.78)]">{item.body}</p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Right column — thesis card + lookup/memo card */}
          <div className="flex w-full shrink-0 justify-center md:flex-1 md:justify-end md:pr-[min(4rem,5vw)]">
            <div className="flex w-full max-w-[540px] shrink-0 flex-col gap-3 md:w-[540px] md:max-w-[540px]">

              {/* Fund thesis card — compact */}
              <motion.article
                variants={thesisCardVariants}
                style={{
                  backgroundColor: PAPER,
                  border: '1px solid var(--section-divider)',
                  borderRadius: 0,
                  boxSizing: 'border-box',
                }}
                className="w-full p-4 sm:p-5"
                aria-label="Fund thesis preview"
              >
                <div className="flex items-center justify-between">
                  <p className="font-mono text-[11px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.4)]">
                    Active Mandate · Fund Thesis
                  </p>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      className="h-1.5 w-1.5 shrink-0 rounded-none bg-[#001433]"
                      style={{ opacity: 0.65, animation: 'pipeline-dot-pulse 2.4s ease-in-out infinite' }}
                      aria-hidden
                    />
                    <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(0,27,71,0.5)]">
                      Live
                    </span>
                  </span>
                </div>
                <p className="mt-2.5 font-sans text-[15px] font-semibold leading-tight tracking-tight text-[var(--color-oxford)]">
                  Deep-Tech Infrastructure
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {THESIS_CRITERIA.map((c) => (
                    <span
                      key={c}
                      className="border border-solid border-[var(--section-divider)] px-2 py-0.5 font-mono text-[10px] tracking-[0.06em] text-[rgba(0,27,71,0.58)]"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              </motion.article>

              {/* Lookup result card — main */}
              <motion.article
                variants={memoCardVariants}
                className="relative w-full p-5 sm:p-7 md:p-9"
                style={{
                  backgroundColor: PAPER,
                  border: '1px solid var(--section-divider)',
                  borderRadius: 0,
                  boxSizing: 'border-box',
                }}
                aria-label="On-demand lookup result preview"
              >
                {/* Lookup query bar */}
                <div
                  className="mb-5 flex items-center gap-3 border border-solid border-[rgba(0,27,71,0.1)] bg-[rgba(0,27,71,0.025)] px-3 py-2"
                >
                  <span className="shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-[rgba(0,27,71,0.35)]">
                    LOOKUP
                  </span>
                  <span
                    className="h-3 w-px shrink-0 bg-[var(--section-divider)]"
                    aria-hidden
                  />
                  <span className="min-w-0 font-sans text-[13px] text-[rgba(0,27,71,0.7)]">
                    Meridian Systems
                  </span>
                  <span className="ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-[rgba(0,27,71,0.35)]">
                    Result
                  </span>
                </div>

                <p className="mb-4 font-mono text-[12px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.4)]">
                  AETHRIA INTELLIGENCE · AUTONOMOUS OUTPUT
                </p>
                <h3 className="text-xl font-semibold leading-tight tracking-tight text-[var(--color-oxford)] sm:text-2xl">
                  Meridian Systems
                </h3>
                <p className="mt-1.5 font-mono text-[13px] tracking-[0.08em] text-[rgba(0,27,71,0.5)]">
                  B2B INFRASTRUCTURE · SERIES A
                </p>

                <div className="my-5 h-px bg-[var(--section-divider)]" aria-hidden />

                <p className="mb-1.5 font-mono text-[12px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.58)]">
                  INVESTMENT JUDGMENT
                </p>
                <p className="font-sans text-[clamp(1.375rem,5vw,2rem)] font-semibold leading-tight tracking-[-0.03em] text-[var(--color-oxford)] md:text-[32px]">
                  STRONG.
                </p>
                <p className="mt-3 font-sans text-[15px] font-normal leading-[1.6] text-[rgba(0,27,71,0.7)]">
                  Clear market timing, credible founding team, and defensible infrastructure play. Conviction is high pending
                  final diligence on unit economics.
                </p>

                <div className="my-5 h-px bg-[var(--section-divider)]" aria-hidden />

                <p className="mb-[14px] font-mono text-[12px] uppercase tracking-[0.11em] text-[rgba(0,27,71,0.58)]">
                  DIMENSION SCORES
                </p>
                <div className="grid w-full grid-cols-5 gap-x-0.5 gap-y-1 sm:gap-x-2 sm:gap-y-2 md:gap-x-3">
                  {DIMENSION_SCORES.map((row) => (
                    <div key={`dim-label-${row.label}`} className="flex min-w-0 items-end justify-center text-center">
                      <p className="m-0 hyphens-auto break-normal font-mono text-[12px] leading-[1.25] tracking-[0.03em] text-[rgba(0,27,71,0.55)]">
                        {row.label}
                      </p>
                    </div>
                  ))}
                  {DIMENSION_SCORES.map((row) => (
                    <p
                      key={`dim-score-${row.label}`}
                      className="min-w-0 text-center font-mono text-base font-bold leading-tight text-[var(--color-oxford)] sm:text-xl md:text-2xl"
                      style={{ fontFamily: '"Space Mono", monospace' }}
                    >
                      {row.score}
                    </p>
                  ))}
                </div>
              </motion.article>

            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
