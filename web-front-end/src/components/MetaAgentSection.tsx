import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';
import SectionRule from './SectionRule';

/**
 * The meta-agent — daily self-optimization loop (mutator / reweighter / calibrator).
 * Real facts from backend/meta/: analyses pipeline outcomes, mutates scout prompts,
 * reweights scouts, calibrates reviewer thresholds, runs on a 24h interval.
 */
const PROCESSES = [
  {
    n: '01',
    label: 'Mutate',
    body: 'Underperforming scout prompts are rewritten from pipeline outcomes — every change is hashed to a prompt version, never silent.',
  },
  {
    n: '02',
    label: 'Reweight',
    body: "Scouts that keep surfacing companies worth reviewing earn more of the pipeline's attention. Ones that don't, earn less.",
  },
  {
    n: '03',
    label: 'Calibrate',
    body: 'Reviewer thresholds drift toward the decisions your fund actually makes, not a fixed scoring rubric.',
  },
] as const;

export default function MetaAgentSection() {
  const reduce = useReducedMotion();

  return (
    <section
      id="meta"
      className="w-full"
      style={{ backgroundColor: 'var(--color-oxford)' }}
      aria-labelledby="meta-heading"
    >
      <SectionRule inverse />
      <div className="page-margin-x py-[clamp(3rem,6vh,4.75rem)]">
        <div className="np-head flex flex-wrap items-baseline justify-between gap-x-8 gap-y-4">
          <p className="np-label" style={{ color: 'var(--text-inverse)' }}>
            A5 — The Meta-Agent
          </p>
          <p className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-inverse-muted)]">
            <motion.span
              className="h-[5px] w-[5px] shrink-0 rounded-full bg-[var(--color-brand-mark-inverse)]"
              animate={reduce ? undefined : { opacity: [1, 0.3, 1] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
            />
            Runs every 24 hours
          </p>
        </div>

        <h2
          id="meta-heading"
          className="editorial-display mt-6 max-w-[20ch] font-normal text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.02] tracking-[-0.02em] text-[var(--text-inverse)]"
        >
          The system rewires itself.
        </h2>
        <p className="np-serif mt-5 max-w-[58ch] text-[15.5px] leading-[1.7] text-[var(--text-inverse-secondary)]">
          Once a day, a meta-agent studies what the pipeline actually decided and adjusts three things about how it
          looks and judges — never the thesis itself, and never without a record of the change.
        </p>

        <div className="mt-8 grid grid-cols-1 md:grid-cols-3">
          {PROCESSES.map((p, i) => (
            <motion.div
              key={p.label}
              className={`py-6 md:py-7 md:pr-9 ${i > 0 ? 'border-t border-solid border-[rgba(244,241,234,0.14)] md:border-l md:border-t-0 md:pl-9' : ''}`}
              initial={reduce ? false : { opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: reduce ? 0 : 0.65, ease: SCROLL_EASE, delay: reduce ? 0 : i * 0.08 }}
            >
              <p className="font-mono text-[11px] text-[var(--color-brand-mark-inverse)]">{p.n}</p>
              <h3 className="editorial-display mt-2 text-[1.25rem] font-normal leading-[1.15] tracking-[-0.01em] text-[var(--text-inverse)]">
                {p.label}
              </h3>
              <p className="np-serif mt-3 max-w-[36ch] text-[14.5px] leading-[1.65] text-[var(--text-inverse-secondary)]">
                {p.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
