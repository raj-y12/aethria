import { useRef, type ReactNode } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

type Metric = {
  label: string;
  note: string;
  kind: 'roman' | 'int' | 'percent' | 'decimal';
  displayRoman?: string;
  value?: string;
};

const METRICS: Metric[] = [
  { label: 'PIPELINE DEPTH', note: 'Phases under one audit trail', kind: 'roman', displayRoman: 'IV' },
  { label: 'REVIEW DIMENSIONS', note: 'Configurable per mandate', kind: 'int', value: '6' },
  { label: 'PROVENANCE', note: 'Memo and escalation lineage', kind: 'percent', value: '100%' },
  { label: 'AVAILABILITY TARGET', note: 'SLA-grade operations', kind: 'decimal', value: '99.95%' },
];

function MetricNumber({ metric }: { metric: Metric }) {
  const sizeClass = 'text-[clamp(1.75rem,7vw,2.75rem)] font-bold leading-none tracking-[-0.03em] text-[var(--color-oxford)] tabular-nums md:text-[44px]';

  let numberNode: ReactNode;
  if (metric.kind === 'roman') {
    numberNode = (
      <span className={sizeClass} style={{ fontFamily: '"Space Mono", monospace' }}>
        {metric.displayRoman}
      </span>
    );
  } else {
    numberNode = (
      <span className={sizeClass} style={{ fontFamily: '"Space Mono", monospace' }}>
        {metric.value}
      </span>
    );
  }

  return numberNode;
}

export default function HomeStatsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(sectionRef, { once: true, amount: 0.2 });

  const gridVariants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.08,
        delayChildren: reduce ? 0 : 0.04,
      },
    },
  };

  const itemVariants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.48, ease: SCROLL_EASE },
    },
  };

  return (
    <section
      ref={sectionRef}
      className="paper-dot-grid relative w-full border-b border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)', color: 'var(--color-charcoal)' }}
      aria-label="Operating metrics"
    >
      <div className="page-margin-x relative z-[1] py-12 md:py-[80px]">
        <motion.p
          className="section-numeral mb-8 md:mb-10"
          aria-hidden
          initial={reduce ? false : { opacity: 0, y: 10 }}
          animate={inView || reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
          transition={{ duration: reduce ? 0 : 0.45, ease: SCROLL_EASE }}
        >
          II
        </motion.p>

        <motion.div
          className="flex flex-col lg:flex-row lg:items-start"
          variants={gridVariants}
          initial={reduce ? false : 'hidden'}
          animate={inView || reduce ? 'visible' : 'hidden'}
        >
          {METRICS.map((metric, index) => (
            <motion.div
              key={metric.label}
              variants={itemVariants}
              className={`relative min-w-0 flex-1 py-8 pl-0 pr-0 first:pt-0 last:pb-0 sm:pl-1 sm:pr-2 md:px-4 lg:py-0 lg:pl-20 lg:pr-6 ${
                index > 0
                  ? 'border-t border-solid border-[var(--section-divider)] pt-10 lg:border-l lg:border-t-0 lg:pt-0'
                  : ''
              }`}
            >
              <MetricNumber metric={metric} />
              <motion.div className="my-3 h-px w-full bg-[var(--section-divider)]" aria-hidden />
              <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--label-muted)]">{metric.label}</p>
              <p className="mt-2 font-sans text-[14px] leading-[1.6] text-[var(--text-muted)]">{metric.note}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
