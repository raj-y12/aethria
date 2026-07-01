import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { DEMO_LOOKUP_MEMO_SAMPLE, LookupResultSnapshot } from '@aethria/product-chrome';
import SectionKicker from './SectionKicker';
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

  return (
    <section
      id="product"
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="inside-aethria-heading"
    >
      <motion.div
        className="page-margin-x py-[clamp(6rem,16vh,12rem)]"
        variants={rowVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.12, margin: '0px 0px -10% 0px' }}
      >
        <motion.div className="max-w-[820px]" variants={leftColVariants}>
          <SectionKicker folio="04" label="The record" className="mb-8" />
          <h2
            id="inside-aethria-heading"
            className="editorial-display font-normal text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            The system shows its <span className="italic text-[var(--color-accent)]">work</span>.
          </h2>
          <p className="mt-8 max-w-[52ch] font-sans text-[16px] leading-[1.75] text-[var(--text-secondary)]">
            Every recommendation becomes one investment record — source trail, reviewer disagreement, dimension scores,
            and mandate fit kept together and open to inspection.
          </p>
        </motion.div>

        <div className="mt-16 grid gap-12 md:mt-24 md:grid-cols-[0.82fr_1.18fr] md:items-start md:gap-20">
          <motion.div className="flex flex-col gap-10" variants={leftColVariants}>
            {FEATURES.map((item) => (
              <div key={item.label}>
                <p className="mb-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--color-oxford)]">
                  {item.label}
                </p>
                <p className="max-w-[40ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
                  {item.body}
                </p>
              </div>
            ))}
          </motion.div>

          <motion.div variants={memoCardVariants} className="w-full" aria-label="Investment memo sample output">
            <p className="mb-5 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)]">
              Investment memo · sample output
            </p>
            <div className="border border-solid border-[var(--section-divider)] bg-[var(--color-paper-deep)] p-4 sm:p-6">
              <LookupResultSnapshot {...DEMO_LOOKUP_MEMO_SAMPLE} />
            </div>
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}
