import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';
import SectionRule from './SectionRule';

/**
 * The portfolio layer — what happens after INVEST, set as a newspaper briefs column.
 * Real facts from backend/portfolio/: tracks accepted companies across execution,
 * signals, feedback, and health checks.
 */
const BRIEFS = [
  {
    n: '01',
    label: 'Execution',
    body: 'Delivery is tracked against the plan that was on the record the day the decision was made.',
  },
  {
    n: '02',
    label: 'Signals',
    body: 'Hiring, funding, and product signals are collected continuously, not at board-meeting intervals.',
  },
  {
    n: '03',
    label: 'Feedback',
    body: 'Outcomes flow back into scout weighting and reviewer calibration — the pipeline learns from its own book.',
  },
  {
    n: '04',
    label: 'Health checks',
    body: 'Periodic checks flag drift from the original thesis before it becomes a surprise.',
  },
] as const;

export default function PortfolioSection() {
  const reduce = useReducedMotion();

  return (
    <section
      id="portfolio"
      className="w-full"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="portfolio-heading"
    >
      <SectionRule />
      <div className="page-margin-x py-[clamp(2rem,4.5vh,3rem)]">
        <p className="np-head np-label">A8 — The Portfolio</p>

        <motion.div
          initial={reduce ? false : { opacity: 0, y: 18 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: reduce ? 0 : 0.7, ease: SCROLL_EASE }}
        >
          <h2
            id="portfolio-heading"
            className="editorial-display mt-6 max-w-[22ch] font-normal text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.02] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            The record doesn't end at invest.
          </h2>
        </motion.div>

        {/* Briefs — four short ruled columns, the paper's "in brief" strip */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-4">
          {BRIEFS.map((b, i) => (
            <motion.div
              key={b.label}
              className={`py-5 md:py-1 md:pr-7 ${i > 0 ? 'border-t border-solid border-[var(--section-divider)] md:border-l md:border-t-0 md:pl-7' : ''}`}
              initial={reduce ? false : { opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: reduce ? 0 : 0.55, ease: SCROLL_EASE, delay: reduce ? 0 : i * 0.06 }}
            >
              <p className="font-mono text-[11px] text-[var(--color-accent)]">{b.n}</p>
              <h3 className="editorial-display mt-2 text-[1.2rem] font-normal leading-[1.15] tracking-[-0.01em] text-[var(--color-oxford)]">
                {b.label}
              </h3>
              <p className="np-serif mt-2.5 text-[14.5px] leading-[1.65] text-[var(--text-secondary)]">{b.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
