import { motion, useReducedMotion, type Variants } from 'framer-motion';
import {
  DEMO_LOOKUP_MEMO_SAMPLE,
  DEMO_MANDATE_PAPER,
  LookupResultSnapshot,
  MandateCard,
} from '@aethria/product-chrome';
import { SCROLL_EASE } from '../motionTokens';

const PAPER = '#f4f1ea';

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
    <section className="flex w-full overflow-hidden">
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

              <motion.div variants={thesisCardVariants} className="w-full" aria-label="Fund thesis preview">
                <MandateCard {...DEMO_MANDATE_PAPER} />
              </motion.div>

              <motion.div variants={memoCardVariants} className="w-full" aria-label="On-demand lookup result preview">
                <LookupResultSnapshot {...DEMO_LOOKUP_MEMO_SAMPLE} />
              </motion.div>

            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
