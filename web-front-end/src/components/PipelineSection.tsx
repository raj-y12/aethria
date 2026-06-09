import { useRef } from 'react';
import { motion, useInView, useReducedMotion, type Variants } from 'framer-motion';
import IntelligenceMap from './IntelligenceMap';
import { ScrollReveal } from './ScrollReveal';
import { SCROLL_EASE } from '../motionTokens';

/**
 * Lean pipeline overview — the end-to-end "what actually runs" frame in the journey order
 * (Hero → Mandate → Pipeline → …). Replaces the old full-height phased section; also folds in
 * the system-composition metrics that used to live in IntelligenceSection so the standalone
 * network-map section can retire.
 */

type Phase = {
  numeral: string;
  label: string;
  body: string;
};

const PHASES: Phase[] = [
  {
    numeral: 'I',
    label: 'Scout',
    body: 'Four lenses watch the market against your thesis. When a name surfaces, sourcing and context arrive with it.',
  },
  {
    numeral: 'II',
    label: 'Review',
    body: 'Three independent reviewers score every company across six dimensions. Conviction and doubt both stay explicit.',
  },
  {
    numeral: 'III',
    label: 'Decide',
    body: 'Versioned partner logic resolves the reviews into one recorded verdict — invest, pass, or monitor.',
  },
  {
    numeral: 'IV',
    label: 'Portfolio',
    body: 'Accepted companies are tracked for execution, signals, and follow-on judgment. Decisions compound.',
  },
];

type Metric = { value: string; label: string; note: string };

const METRICS: Metric[] = [
  { value: '4', label: 'Scout lenses', note: 'Market · builder · pain-point · contrarian' },
  { value: '3', label: 'Reviewer modes', note: 'Default · skeptical · opportunist' },
  { value: '6', label: 'Review dimensions', note: 'Market → defensibility → thesis fit' },
  { value: '1', label: 'Investment record', note: 'Source · review · decision · follow-up' },
];

function MetricNumber({ value }: { value: string }) {
  return (
    <span
      className="text-[clamp(1.75rem,5vw,2.5rem)] font-bold leading-none tracking-[-0.03em] text-[var(--color-oxford)] tabular-nums"
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {value}
    </span>
  );
}

function MetricsPanel({ metrics }: { metrics: Metric[] }) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.2 });

  const itemVariants: Variants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 },
    visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : 0.42, ease: SCROLL_EASE } },
  };

  return (
    <div ref={ref} className="intelligence-metrics-panel">
      <p className="accent-eyebrow mb-1">System composition</p>
      <motion.ol
        className="mt-5 flex flex-col"
        initial={false}
        animate={inView || reduce ? 'visible' : undefined}
        variants={{
          hidden: {},
          visible: { transition: { staggerChildren: reduce ? 0 : 0.07, delayChildren: reduce ? 0 : 0.05 } },
        }}
      >
        {metrics.map((metric) => (
          <motion.li key={metric.label} variants={itemVariants} className="intelligence-metric-row">
            <MetricNumber value={metric.value} />
            <div className="min-w-0">
              <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
                {metric.label}
              </p>
              <p className="mt-1.5 font-sans text-[13px] leading-[1.55] text-[var(--text-muted)]">{metric.note}</p>
            </div>
          </motion.li>
        ))}
      </motion.ol>
    </div>
  );
}

export default function PipelineSection() {
  const reduce = useReducedMotion();

  const listVariants: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: reduce ? 0 : 0.08, delayChildren: reduce ? 0 : 0.04 } },
  };

  const itemVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, y: 16 },
    visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : 0.5, ease: SCROLL_EASE } },
  };

  return (
    <section
      id="pipeline"
      className="paper-dot-grid w-full"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="pipeline-heading"
    >
      <div className="page-margin-x py-16 md:py-24">
        <ScrollReveal y={20} amount={0.2} className="max-w-[760px]">
          <p className="accent-eyebrow mb-6">Pipeline · signal to position</p>
          <h2
            id="pipeline-heading"
            className="editorial-display text-[clamp(2rem,5.5vw,3.25rem)] text-[var(--color-oxford)]"
          >
            From signal to <span className="accent-underline">recorded position</span>.
          </h2>
          <p className="mt-6 max-w-[54ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
            Four locked phases, one audit trail. Every hand-off stays inside the record — nothing lost to email or a
            forgotten spreadsheet tab.
          </p>
        </ScrollReveal>

        <motion.ol
          className="pipeline-phase-grid mt-12 grid list-none grid-cols-1 overflow-hidden p-0 sm:grid-cols-2 md:mt-16 lg:grid-cols-4"
          variants={listVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.15 }}
        >
          {PHASES.map((p) => (
            <motion.li
              key={p.label}
              variants={itemVariants}
              className="flex min-w-0 flex-col bg-[var(--color-paper)] p-7 md:p-8"
            >
              <span className="font-mono text-[13px] font-bold leading-none tracking-[0.1em] text-[var(--color-accent)]">
                {p.numeral}
              </span>
              <p className="mt-4 font-mono text-[12px] uppercase tracking-[0.14em] text-[var(--color-oxford)]">
                {p.label}
              </p>
              <p className="mt-3 font-sans text-[14px] leading-[1.65] text-[var(--text-secondary)]">{p.body}</p>
            </motion.li>
          ))}
        </motion.ol>

        <ScrollReveal className="mt-12 w-full md:mt-16" y={16} delay={0.06} amount={0.12}>
          <div className="intelligence-proof-grid">
            <div className="flex h-[min(360px,64vw)] min-h-[260px] flex-col lg:h-[430px]">
              <IntelligenceMap variant="light" />
            </div>
            <MetricsPanel metrics={METRICS} />
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
