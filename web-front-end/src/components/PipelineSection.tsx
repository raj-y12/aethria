import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { ScrollReveal } from './ScrollReveal';
import SectionKicker from './SectionKicker';
import { lazy, Suspense } from 'react';

const IntelligenceMap = lazy(() => import('./IntelligenceMap'));
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
    numeral: '01',
    label: 'Scout',
    body: 'Four lenses watch the market against your thesis. When a name surfaces, its sourcing and context arrive attached.',
  },
  {
    numeral: '02',
    label: 'Review',
    body: 'Three independent reviewers score every company across six dimensions. Conviction and doubt both stay on the record.',
  },
  {
    numeral: '03',
    label: 'Decide',
    body: 'Versioned partner logic resolves the three reviews into one verdict: invest, pass, or monitor.',
  },
  {
    numeral: '04',
    label: 'Portfolio',
    body: 'Accepted companies are tracked for execution, signals, and follow-on. Decisions compound instead of scattering.',
  },
];

type Metric = { value: string; label: string; note: string };

const METRICS: Metric[] = [
  { value: '4', label: 'Scout lenses', note: 'Market · builder · pain-point · contrarian' },
  { value: '3', label: 'Reviewer modes', note: 'Default · skeptical · opportunist' },
  { value: '6', label: 'Review dimensions', note: 'Market → defensibility → thesis fit' },
  { value: '1', label: 'Investment record', note: 'Source · review · decision · follow-up' },
];

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
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="pipeline-heading"
    >
      <div className="page-margin-x py-[clamp(6rem,16vh,12rem)]">
        <ScrollReveal y={20} amount={0.2} className="max-w-[820px]">
          <SectionKicker folio="03" label="The pipeline" className="mb-8" />
          <h2
            id="pipeline-heading"
            className="editorial-display font-normal text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            One company moves through{' '}
            <span className="italic text-[var(--color-accent)]">four stages</span>.
          </h2>
        </ScrollReveal>

        <motion.ol
          className="mt-16 list-none border-t border-solid border-[var(--section-divider)] p-0 md:mt-24"
          variants={listVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.1 }}
        >
          {PHASES.map((p) => (
            <motion.li
              key={p.label}
              variants={itemVariants}
              className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-8 border-b border-solid border-[var(--section-divider)] py-12 sm:gap-x-16 md:grid-cols-[minmax(0,0.36fr)_minmax(0,1fr)] md:py-16"
            >
              <span className="font-mono text-[clamp(1.75rem,3.6vw,3rem)] font-bold leading-none tracking-[-0.02em] text-[var(--text-subtle)] tabular-nums">
                {p.numeral}
              </span>
              <div className="min-w-0">
                <h3 className="editorial-display text-[clamp(1.6rem,3.4vw,2.85rem)] leading-[1] tracking-[-0.01em] text-[var(--color-oxford)]">
                  {p.label}
                </h3>
                <p className="mt-5 max-w-[50ch] font-sans text-[clamp(14px,1.4vw,16px)] leading-[1.7] text-[var(--text-secondary)]">
                  {p.body}
                </p>
              </div>
            </motion.li>
          ))}
        </motion.ol>

        {/* The pipeline as a live network — the system topology, oxford ink on paper */}
        <ScrollReveal className="mt-24 w-full md:mt-32" y={16} amount={0.12}>
          <div className="flex items-baseline justify-between gap-6 border-t border-solid border-[var(--section-divider)] pt-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--label-muted)]">The network</p>
            <p className="hidden font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-subtle)] sm:block">
              Scout → Reviewer → Partner → Portfolio
            </p>
          </div>
          <div className="mt-10 h-[clamp(300px,40vh,440px)] w-full">
            <Suspense fallback={<div className="h-full w-full" aria-hidden />}>
              <IntelligenceMap variant="light" />
            </Suspense>
          </div>
        </ScrollReveal>

        <ScrollReveal className="mt-20 w-full md:mt-24" y={16} delay={0.06} amount={0.12}>
          <p className="mb-10 font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--label-muted)]">
            System composition
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4">
            {METRICS.map((metric, i) => (
              <div
                key={metric.label}
                className={`flex flex-col py-6 md:py-2 ${i % 2 === 1 ? 'pl-6 md:pl-0' : ''} ${i >= 2 ? 'border-t border-solid border-[var(--section-divider)] pt-8 md:border-t-0 md:pt-2' : ''}`}
              >
                <span className="font-mono text-[clamp(2.25rem,5vw,4rem)] font-bold leading-[0.9] tracking-[-0.03em] text-[var(--color-oxford)] tabular-nums">
                  {metric.value}
                </span>
                <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--color-oxford)]">
                  {metric.label}
                </p>
                <p className="mt-2 max-w-[26ch] font-sans text-[13px] leading-[1.55] text-[var(--text-muted)]">
                  {metric.note}
                </p>
              </div>
            ))}
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
