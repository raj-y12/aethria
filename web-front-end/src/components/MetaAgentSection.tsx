import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

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
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="meta-heading"
    >
      <div className="page-margin-x py-[clamp(6rem,16vh,12rem)]">
        <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">
            A5 — The Meta-Agent
          </p>
          <p className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-subtle)]">
            <motion.span
              className="h-[5px] w-[5px] shrink-0 rounded-full bg-[var(--color-accent)]"
              animate={reduce ? undefined : { opacity: [1, 0.3, 1] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
            />
            Runs every 24 hours
          </p>
        </div>

        <h2
          id="meta-heading"
          className="editorial-display mt-6 max-w-[20ch] font-normal text-[clamp(2rem,4.6vw,3.4rem)] leading-[1.02] tracking-[-0.02em] text-[var(--color-oxford)]"
        >
          The system <span className="italic text-[var(--color-accent)]">rewires itself</span>.
        </h2>
        <p className="mt-5 max-w-[58ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
          Once a day, a meta-agent studies what the pipeline actually decided and adjusts three things about how it
          looks and judges — never the thesis itself, and never without a record of the change.
        </p>

        <div className="mt-16 grid grid-cols-1 border-t border-solid border-[var(--section-divider)] md:grid-cols-3">
          {PROCESSES.map((p, i) => (
            <motion.div
              key={p.label}
              className={`py-9 md:py-11 md:pr-9 ${i > 0 ? 'border-t border-solid border-[var(--section-divider)] md:border-l md:border-t-0 md:pl-9' : ''}`}
              initial={reduce ? false : { opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: reduce ? 0 : 0.65, ease: SCROLL_EASE, delay: reduce ? 0 : i * 0.08 }}
            >
              <p className="font-mono text-[11px] text-[var(--color-accent)]">{p.n}</p>
              <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--color-oxford)]">
                {p.label}
              </p>
              <p className="mt-3 max-w-[36ch] font-sans text-[14px] leading-[1.65] text-[var(--text-secondary)]">
                {p.body}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
