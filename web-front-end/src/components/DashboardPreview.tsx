import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

const PAPER = '#f2f0ea';

const DIMENSION_SCORES: { label: string; score: string }[] = [
  { label: 'MARKET', score: '9/10' },
  { label: 'EXECUTION', score: '8/10' },
  { label: 'PRODUCT', score: '8/10' },
  { label: 'TECHNICAL', score: '9/10' },
  { label: 'DEFENSIBILITY', score: '7/10' },
];

export default function DashboardPreview() {
  const reduce = useReducedMotion();

  const rowVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.12,
        delayChildren: reduce ? 0 : 0.05,
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

  const memoCardVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, x: 28 },
    visible: {
      opacity: 1,
      x: 0,
      transition: { duration: reduce ? 0 : 0.65, ease: SCROLL_EASE },
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
        className="w-2 shrink-0 self-stretch origin-top bg-[#002147] sm:w-6 md:w-12"
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
          viewport={{ once: true, amount: 0.16, margin: '0px 0px -10% 0px' }}
        >
          <motion.div className="relative w-full max-w-xl shrink-0 md:w-[40%] md:pt-9" variants={leftColVariants}>
            <p className="section-numeral mb-6 md:absolute md:left-0 md:top-4 md:mb-0">VI</p>
            <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.45)]">
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
                  label: 'INVESTMENT MEMO',
                  body: 'A complete reasoning chain produced autonomously. Thesis alignment, risk surface, and conviction score before a partner reviews the deal.',
                },
                {
                  label: 'ESCALATION QUEUE',
                  body: 'Edge cases surfaced with precision. Disagreement signals and confidence gaps flagged for human judgment, not buried in the pipeline.',
                },
                {
                  label: 'PORTFOLIO SIGNALS',
                  body: 'Concentration risk, sector exposure, and clustering patterns across active positions. Continuously updated.',
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="border-l border-solid border-[var(--section-divider)] pl-3 md:pl-4"
                >
                  <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.78)]">
                    {item.label}
                  </p>
                  <p className="font-sans text-[15px] leading-[1.7] text-[rgba(0,33,71,0.78)]">{item.body}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <div className="flex w-full shrink-0 justify-center md:flex-1 md:justify-end md:pr-[min(4rem,5vw)]">
            <motion.article
              variants={memoCardVariants}
              className="dashboard-memo-card relative w-full max-w-[540px] shrink-0 p-5 sm:p-7 md:w-[540px] md:max-w-[540px] md:p-9"
              style={{
                backgroundColor: PAPER,
                border: '1px solid var(--section-divider)',
                borderRadius: 0,
                boxSizing: 'border-box',
              }}
              aria-label="Investment memo preview"
            >
              <p className="mb-4 font-mono text-[8px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.25)]">
                AETHRIA INTELLIGENCE · AUTONOMOUS OUTPUT
              </p>
              <h3 className="text-xl font-semibold leading-tight tracking-tight text-[var(--color-oxford)] sm:text-2xl">
                Meridian Systems
              </h3>
              <p className="mt-1.5 font-mono text-[11px] tracking-[0.1em] text-[rgba(0,33,71,0.4)]">
                B2B INFRASTRUCTURE · SERIES A
              </p>

              <div className="my-6 h-px bg-[var(--section-divider)]" aria-hidden />

              <p className="mb-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.48)]">
                INVESTMENT JUDGMENT
              </p>
              <p className="font-sans text-[clamp(1.375rem,5vw,2rem)] font-semibold leading-tight tracking-[-0.03em] text-[var(--color-oxford)] md:text-[32px]">
                STRONG.
              </p>
              <p className="mt-[14px] font-sans text-[15px] font-normal leading-[1.6] text-[rgba(0,33,71,0.7)]">
                Clear market timing, credible founding team, and defensible infrastructure play. Conviction is high pending
                final diligence on unit economics.
              </p>

              <div className="my-6 h-px bg-[var(--section-divider)]" aria-hidden />

              <p className="mb-[18px] font-mono text-[11px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.48)]">
                DIMENSION SCORES
              </p>
              <div className="grid w-full grid-cols-5 gap-x-0.5 gap-y-1 sm:gap-x-2 sm:gap-y-2 md:gap-x-3">
                {DIMENSION_SCORES.map((row) => (
                  <div key={`dim-label-${row.label}`} className="flex min-w-0 items-end justify-center text-center">
                    <p className="m-0 hyphens-auto break-normal font-mono text-[7px] leading-[1.15] tracking-[0.04em] text-[rgba(0,33,71,0.4)] sm:text-[10px] sm:tracking-[0.05em]">
                      {row.label}
                    </p>
                  </div>
                ))}
                {DIMENSION_SCORES.map((row) => (
                  <p
                    key={`dim-score-${row.label}`}
                    className="min-w-0 text-center font-mono text-base font-bold leading-tight text-[var(--color-oxford)] sm:text-xl md:text-2xl"
                  >
                    {row.score}
                  </p>
                ))}
              </div>
            </motion.article>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
