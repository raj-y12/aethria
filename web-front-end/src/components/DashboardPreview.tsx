import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { DEMO_LOOKUP_MEMO_SAMPLE, LookupResultSnapshot } from '@aethria/product-chrome';
import { SCROLL_EASE } from '../motionTokens';

const FEATURES = [
  {
    label: 'Fund thesis',
    body: 'Your investment mandate governs every decision. Scouts, reviewers, and partners operate against defined criteria with visible policy lineage.',
  },
  {
    label: 'On-demand lookup',
    body: 'Request instant analysis on any company. A full memo surfaces in seconds, drawn from live signals and benchmarked against your active thesis.',
  },
  {
    label: 'Escalation queue',
    body: 'Edge cases surfaced with precision. Disagreement signals and confidence gaps flagged for human judgment, not buried in the pipeline.',
  },
] as const;

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
    <section
      id="product"
      className="inside-aethria-section flex w-full overflow-hidden"
      aria-labelledby="inside-aethria-heading"
    >
      <motion.div
        className="inside-aethria-strip w-2 shrink-0 self-stretch origin-top bg-[var(--color-oxford)] sm:w-6 md:w-12"
        aria-hidden
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.4 }}
        variants={stripVariants}
      />
      <div className="paper-dot-grid min-w-0 flex-1 self-stretch" style={{ backgroundColor: 'var(--color-paper)' }}>
        <motion.div
          className="page-margin-x flex flex-col gap-10 pt-14 pb-12 sm:gap-12 sm:pt-20 sm:pb-14 md:flex-row md:items-start md:gap-16 md:pt-24 md:pb-16"
          variants={rowVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.12, margin: '0px 0px -10% 0px' }}
        >
          <motion.div className="relative w-full max-w-xl shrink-0 md:w-[40%]" variants={leftColVariants}>
            <p className="accent-eyebrow">Inside Aethria</p>
            <h2
              id="inside-aethria-heading"
              className="editorial-display mt-4 text-[clamp(2.15rem,4.2vw,3rem)] text-[var(--color-oxford)]"
            >
              The system thinks
              <br />
              before you decide.
            </h2>

            <div className="mt-10 flex flex-col gap-8">
              {FEATURES.map((item) => (
                <div key={item.label} className="inside-aethria-feature border-l border-solid border-[var(--section-divider)] pl-4">
                  <p className="mb-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--color-oxford)]">
                    {item.label}
                  </p>
                  <p className="font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">{item.body}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <div className="flex w-full shrink-0 justify-center md:flex-1 md:justify-end md:pr-[min(4rem,5vw)]">
            <motion.div
              variants={memoCardVariants}
              className="flex w-full max-w-[540px] shrink-0 flex-col md:w-[540px] md:max-w-[540px]"
              aria-label="Investment memo sample output"
            >
              <p className="mb-4 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
                Investment memo · sample output
              </p>
              <LookupResultSnapshot {...DEMO_LOOKUP_MEMO_SAMPLE} />
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
