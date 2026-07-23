import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { DEMO_LOOKUP_MEMO_SAMPLE, LookupResultSnapshot } from '@aethria/product-chrome';
import { SCROLL_EASE } from '../motionTokens';
import SectionRule from './SectionRule';

const FEATURES = [
  {
    n: '01',
    label: 'Fund thesis',
    body: 'Your investment mandate governs every decision. Scouts, reviewers, and partners operate against defined criteria with visible policy lineage.',
  },
  {
    n: '02',
    label: 'On-demand lookup',
    body: 'Request instant analysis on any company. A full memo surfaces in seconds, drawn from live signals and benchmarked against your active thesis.',
  },
  {
    n: '03',
    label: 'Escalation queue',
    body: 'Edge cases surfaced with precision. Disagreement signals and confidence gaps flagged for human judgment, not buried in the pipeline.',
  },
] as const;

/**
 * The record — a dense-document archetype (SEC-filing feel), deliberately different
 * from the headline-led sections around it. No kicker, no display headline: just a
 * one-line index label, a numbered feature ledger, and the memo as a raw printout.
 */
export default function DashboardPreview() {
  const reduce = useReducedMotion();

  const rowVariants: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: reduce ? 0 : 0.08, delayChildren: reduce ? 0 : 0.04 } },
  };

  const itemVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : 0.5, ease: SCROLL_EASE } },
  };

  const memoVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, x: 24 },
    visible: { opacity: 1, x: 0, transition: { duration: reduce ? 0 : 0.6, delay: reduce ? 0 : 0.1, ease: SCROLL_EASE } },
  };

  return (
    <section
      id="product"
      className="w-full"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="record-heading"
    >
      <SectionRule />
      <motion.div
        className="page-margin-x py-[clamp(2rem,4.5vh,3rem)]"
        variants={rowVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.12, margin: '0px 0px -10% 0px' }}
      >
        <div className="np-head flex items-baseline gap-x-4">
          <span className="np-folio">A6</span>
          <span className="np-label">The Record</span>
        </div>

        <h2 id="record-heading" className="np-hed mt-5 max-w-[18ch] text-[var(--color-oxford)]">
          The system shows its work.
        </h2>

        <div className="mt-12 grid gap-10 md:grid-cols-[0.72fr_1.28fr] md:items-start md:gap-16">
          <div className="flex flex-col">
            {FEATURES.map((item) => (
              <motion.div
                key={item.label}
                variants={itemVariants}
                className="grid grid-cols-[3.4rem_1fr] items-start gap-4 border-t border-solid border-[var(--section-divider)] py-7 first:border-t-0 first:pt-0"
              >
                <p className="np-figure">{item.n}</p>
                <div>
                  <h3 className="editorial-display text-[1.3rem] font-normal leading-[1.15] tracking-[-0.015em] text-[var(--color-oxford)]">
                    {item.label}
                  </h3>
                  <p className="np-serif mt-2 max-w-[38ch] text-[14.5px] leading-[1.65] text-[var(--text-secondary)]">
                    {item.body}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>

          <motion.div variants={memoVariants} className="w-full" aria-label="Investment memo sample output">
            <p className="mb-5 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-subtle)]">
              Investment memo · sample output
            </p>
            <LookupResultSnapshot {...DEMO_LOOKUP_MEMO_SAMPLE} />
          </motion.div>
        </div>
      </motion.div>
    </section>
  );
}
