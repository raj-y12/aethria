import { useEffect, useRef, useState, type ReactNode } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

type Metric = {
  label: string;
  note: string;
  kind: 'roman' | 'int' | 'percent' | 'decimal';
  displayRoman?: string;
  endInt?: number;
  endDecimal?: number;
};

const HERO_METRIC: Metric = {
  label: 'PIPELINE DEPTH',
  note: 'Phases under one audit trail',
  kind: 'roman',
  displayRoman: 'IV',
};

const SUPPORT_METRICS: Metric[] = [
  { label: 'REVIEW DIMENSIONS', note: 'Configurable per mandate', kind: 'int', endInt: 6 },
  { label: 'PROVENANCE', note: 'Memo and escalation lineage', kind: 'percent', endInt: 100 },
  { label: 'AVAILABILITY TARGET', note: 'SLA-grade operations', kind: 'decimal', endDecimal: 99.95 },
];

const DARK_DIVIDER = 'rgba(244, 241, 234, 0.14)';

function useCountInt(end: number, run: boolean, duration = 900) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) {
      setV(0);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      const eased = 1 - (1 - t) ** 2;
      setV(Math.round(end * eased));
      if (t < 1) raf = requestAnimationFrame(tick);
      else setV(end);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run, end, duration]);
  return v;
}

function useCountDecimal(end: number, run: boolean, duration = 1000) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!run) {
      setV(0);
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / duration);
      const eased = 1 - (1 - t) ** 2;
      setV(Number((end * eased).toFixed(2)));
      if (t < 1) raf = requestAnimationFrame(tick);
      else setV(end);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [run, end, duration]);
  return v;
}

function RomanReveal({ show, text, size = 'hero' }: { show: boolean; text: string; size?: 'hero' | 'support' }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!show) {
      setVisible(false);
      return;
    }
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, [show]);
  const sizeClass =
    size === 'hero'
      ? 'text-[clamp(3.5rem,14vw,5.5rem)] md:text-[88px]'
      : 'text-[clamp(1.5rem,5vw,2.25rem)] md:text-[36px]';
  return (
    <span
      className={`font-bold leading-none tracking-[-0.04em] text-[var(--color-paper)] transition-opacity duration-500 tabular-nums ${sizeClass}`}
      style={{ fontFamily: '"Space Mono", monospace', opacity: visible ? 1 : 0 }}
    >
      {text}
    </span>
  );
}

function MetricNumber({ metric, run, size = 'support' }: { metric: Metric; run: boolean; size?: 'hero' | 'support' }) {
  const n6 = useCountInt(6, run && metric.kind === 'int');
  const n100 = useCountInt(100, run && metric.kind === 'percent');
  const dec = useCountDecimal(99.95, run && metric.kind === 'decimal');
  const sizeClass =
    size === 'hero'
      ? 'text-[clamp(3.5rem,14vw,5.5rem)] md:text-[88px]'
      : 'text-[clamp(1.5rem,5vw,2.25rem)] md:text-[36px]';

  let numberNode: ReactNode;
  if (metric.kind === 'roman') {
    numberNode = <RomanReveal show={run} text={metric.displayRoman ?? ''} size={size} />;
  } else if (metric.kind === 'int') {
    numberNode = (
      <span
        className={`font-bold leading-none tracking-[-0.03em] text-[var(--color-paper)] tabular-nums ${sizeClass}`}
        style={{ fontFamily: '"Space Mono", monospace' }}
      >
        {n6}
      </span>
    );
  } else if (metric.kind === 'percent') {
    numberNode = (
      <span
        className={`font-bold leading-none tracking-[-0.03em] text-[var(--color-paper)] tabular-nums ${sizeClass}`}
        style={{ fontFamily: '"Space Mono", monospace' }}
      >
        {n100}%
      </span>
    );
  } else {
    numberNode = (
      <span
        className={`font-bold leading-none tracking-[-0.03em] text-[var(--color-paper)] tabular-nums ${sizeClass}`}
        style={{ fontFamily: '"Space Mono", monospace' }}
      >
        {dec.toFixed(2)}%
      </span>
    );
  }

  return numberNode;
}

export default function HomeStatsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(sectionRef, { once: true, amount: 0.2 });
  const [heroRun, setHeroRun] = useState(false);
  const [supportRun, setSupportRun] = useState(false);

  const headerVariants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 14 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.48, ease: SCROLL_EASE },
    },
  };

  const bodyVariants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.52, delay: reduce ? 0 : 0.08, ease: SCROLL_EASE },
    },
  };

  useEffect(() => {
    if (!inView) return;
    const heroTimer = window.setTimeout(() => setHeroRun(true), 80);
    const supportTimer = window.setTimeout(() => setSupportRun(true), 280);
    return () => {
      clearTimeout(heroTimer);
      clearTimeout(supportTimer);
    };
  }, [inView]);

  return (
    <section
      ref={sectionRef}
      className="relative w-full border-b border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-oxford)', color: 'var(--color-paper)' }}
      aria-label="Operating metrics"
    >
      <div className="page-margin-x relative z-[1] py-14 md:py-20">
        <motion.div variants={headerVariants} initial={reduce ? false : 'hidden'} animate={inView || reduce ? 'visible' : 'hidden'}>
          <p className="section-numeral section-numeral--on-dark mb-6" aria-hidden>
            II
          </p>
          <h2 className="max-w-[22ch] text-[clamp(1.5rem,4vw,2rem)] font-normal leading-[1.2] tracking-[-0.02em] text-[var(--text-inverse)]">
            Built for institutional throughput
          </h2>
          <p className="mt-3 max-w-xl font-sans text-[15px] leading-[1.65] text-[var(--text-inverse-secondary)]">
            Four locked phases, full lineage, and SLA-grade availability — not vanity metrics on a landing page.
          </p>
        </motion.div>

        <motion.div
          className="mt-12 flex flex-col gap-10 lg:mt-16 lg:flex-row lg:items-end lg:justify-between lg:gap-16"
          variants={bodyVariants}
          initial={reduce ? false : 'hidden'}
          animate={inView || reduce ? 'visible' : 'hidden'}
        >
          <motion.div className="min-w-0 shrink-0 lg:max-w-[42%]">
            <MetricNumber metric={HERO_METRIC} run={heroRun} size="hero" />
            <motion.div
              className="mt-6 h-px w-full max-w-[12rem]"
              aria-hidden
              initial={reduce ? false : { scaleX: 0 }}
              animate={inView || reduce ? { scaleX: 1 } : { scaleX: 0 }}
              transition={{ duration: reduce ? 0 : 0.55, delay: reduce ? 0 : 0.2, ease: SCROLL_EASE }}
              style={{ backgroundColor: DARK_DIVIDER, transformOrigin: 'left' }}
            />
            <p className="mt-5 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-muted)]">
              {HERO_METRIC.label}
            </p>
            <p className="mt-2 font-sans text-[14px] leading-[1.6] text-[var(--text-inverse-secondary)]">{HERO_METRIC.note}</p>
          </motion.div>

          <div
            className="grid min-w-0 flex-1 grid-cols-1 gap-0 sm:grid-cols-3 sm:gap-0"
            style={{ borderColor: DARK_DIVIDER }}
          >
            {SUPPORT_METRICS.map((metric, index) => (
              <motion.div
                key={metric.label}
                className={`min-w-0 py-6 sm:px-6 sm:py-4 ${
                  index > 0 ? 'border-t sm:border-l sm:border-t-0' : ''
                }`}
                style={{ borderColor: DARK_DIVIDER }}
                initial={reduce ? false : { opacity: 0, y: 16 }}
                animate={inView || reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
                transition={{
                  duration: reduce ? 0 : 0.45,
                  delay: reduce ? 0 : 0.15 + index * 0.08,
                  ease: SCROLL_EASE,
                }}
              >
                <MetricNumber metric={metric} run={supportRun} size="support" />
                <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-inverse-muted)]">
                  {metric.label}
                </p>
                <p className="mt-1.5 font-sans text-[13px] leading-[1.55] text-[var(--text-inverse-secondary)]">{metric.note}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
