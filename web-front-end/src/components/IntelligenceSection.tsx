import { useRef } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import IntelligenceMap from './IntelligenceMap';
import { ScrollReveal } from './ScrollReveal';
import { SCROLL_EASE } from '../motionTokens';

type Metric = {
  label: string;
  note: string;
  value: string;
};

const METRICS: Metric[] = [
  { label: 'Scout lenses', note: 'Market, builder, pain-point, contrarian', value: '4' },
  { label: 'Reviewer modes', note: 'Default, skeptical, opportunist', value: '3' },
  { label: 'Review dimensions', note: 'Market, product, technical, execution, defensibility, thesis fit', value: '6' },
  { label: 'Investment record', note: 'Source, review, recommendation, follow-up', value: '1' },
];

const PIPELINE_PHASES = ['Scout', 'Review', 'Decide', 'Track'] as const;

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

  const itemVariants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.42, ease: SCROLL_EASE },
    },
  };

  return (
    <div ref={ref} className="intelligence-metrics-panel">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)]">System composition</p>
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
              <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">{metric.label}</p>
              <p className="mt-1.5 font-sans text-[13px] leading-[1.55] text-[var(--text-muted)]">{metric.note}</p>
            </div>
          </motion.li>
        ))}
      </motion.ol>
    </div>
  );
}

export default function IntelligenceSection() {
  return (
    <section
      id="intelligence"
      className="w-full"
      style={{ backgroundColor: 'var(--surface-base)' }}
      aria-labelledby="intelligence-heading"
    >
      <div className="page-margin-x py-16 md:py-24">
        <ScrollReveal y={20} amount={0.2} className="max-w-[820px]">
          <h2
            id="intelligence-heading"
            className="editorial-display text-[clamp(2rem,5.5vw,3.25rem)] text-[var(--color-oxford)]"
          >
            The thesis becomes the constraint.
          </h2>
          <p className="mt-5 max-w-[58ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
            Four scout lenses, three reviewer modes, and partner logic — all scoped to your active mandate. The full
            intelligence trail stays visible from discovery to decision.
          </p>
        </ScrollReveal>

        <ScrollReveal className="mx-auto mt-12 w-full max-w-[1180px] md:mt-16" y={16} delay={0.06} amount={0.12}>
          <div className="intelligence-proof-grid">
            <div className="flex h-[min(360px,64vw)] min-h-[260px] flex-col lg:h-[430px]">
              <IntelligenceMap variant="light" />
            </div>
            <MetricsPanel metrics={METRICS} />
          </div>
        </ScrollReveal>

        <p className="mt-8 text-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
          {PIPELINE_PHASES.join(' · ')}
        </p>
      </div>
    </section>
  );
}
