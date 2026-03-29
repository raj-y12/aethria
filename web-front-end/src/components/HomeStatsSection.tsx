import { useEffect, useRef, useState, type ReactNode } from 'react';
import { motion, useInView, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

const PAPER = '#f2f0ea';

type Metric = {
  label: string;
  note: string;
  kind: 'roman' | 'int' | 'percent' | 'decimal';
  displayRoman?: string;
  endInt?: number;
  endDecimal?: number;
};

const METRICS: Metric[] = [
  { label: 'PIPELINE DEPTH', note: 'Phases under one audit trail', kind: 'roman', displayRoman: 'IV' },
  { label: 'REVIEW DIMENSIONS', note: 'Configurable per mandate', kind: 'int', endInt: 6 },
  { label: 'PROVENANCE', note: 'Memo and escalation lineage', kind: 'percent', endInt: 100 },
  { label: 'AVAILABILITY TARGET', note: 'SLA-grade operations', kind: 'decimal', endDecimal: 99.95 },
];

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

function RomanReveal({ show, text }: { show: boolean; text: string }) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!show) {
      setVisible(false);
      return;
    }
    const id = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(id);
  }, [show]);
  return (
    <span
      className="font-display text-[clamp(2.5rem,12vw,4rem)] font-bold leading-none tracking-[-0.03em] text-[#002147] transition-opacity duration-500 tabular-nums md:text-[64px]"
      style={{ opacity: visible ? 1 : 0 }}
    >
      {text}
    </span>
  );
}

function StatColumn({ metric, index, run }: { metric: Metric; index: number; run: boolean }) {
  const reduce = useReducedMotion();
  const n6 = useCountInt(6, run && metric.kind === 'int');
  const n100 = useCountInt(100, run && metric.kind === 'percent');
  const dec = useCountDecimal(99.95, run && metric.kind === 'decimal');

  let numberNode: ReactNode;
  if (metric.kind === 'roman') {
    numberNode = <RomanReveal show={run} text={metric.displayRoman ?? ''} />;
  } else if (metric.kind === 'int') {
    numberNode = (
      <span className="font-display text-[clamp(2.5rem,12vw,4rem)] font-bold leading-none tracking-[-0.03em] text-[#002147] tabular-nums md:text-[64px]">
        {n6}
      </span>
    );
  } else if (metric.kind === 'percent') {
    numberNode = (
      <span className="font-display text-[clamp(2.5rem,12vw,4rem)] font-bold leading-none tracking-[-0.03em] text-[#002147] tabular-nums md:text-[64px]">
        {n100}%
      </span>
    );
  } else {
    numberNode = (
      <span className="font-display text-[clamp(2.5rem,12vw,4rem)] font-bold leading-none tracking-[-0.03em] text-[#002147] tabular-nums md:text-[64px]">
        {dec.toFixed(2)}%
      </span>
    );
  }

  const itemVariants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 22 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.5, ease: SCROLL_EASE },
    },
  };

  return (
    <motion.div
      variants={itemVariants}
      className={`relative min-w-0 flex-1 py-8 pl-0 pr-0 first:pt-0 last:pb-0 sm:pl-1 sm:pr-2 md:px-4 lg:py-0 lg:pl-20 lg:pr-6 ${
        index > 0
          ? 'border-t border-solid border-[var(--section-divider)] pt-10 lg:border-l lg:border-t-0 lg:pt-0'
          : ''
      }`}
    >
      <div>{numberNode}</div>
      <div className="my-3 h-px w-full bg-[var(--section-divider)]" aria-hidden />
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.45)]">{metric.label}</p>
      <p className="mt-2 font-sans text-[13px] leading-[1.6] text-[rgba(0,33,71,0.55)]">{metric.note}</p>
    </motion.div>
  );
}

export default function HomeStatsSection() {
  const sectionRef = useRef<HTMLElement>(null);
  const reduce = useReducedMotion();
  const inView = useInView(sectionRef, { once: true, amount: 0.2 });
  const [runFlags, setRunFlags] = useState([false, false, false, false]);

  const statsHeaderVariants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 14 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.48, ease: SCROLL_EASE },
    },
  };

  const statsGridVariants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.1,
        delayChildren: reduce ? 0 : 0.06,
      },
    },
  };

  useEffect(() => {
    if (!inView) return;
    const timers = METRICS.map((_, i) =>
      window.setTimeout(() => {
        setRunFlags((prev) => {
          const next = [...prev];
          next[i] = true;
          return next;
        });
      }, i * 150),
    );
    return () => timers.forEach(clearTimeout);
  }, [inView]);

  return (
    <section
      ref={sectionRef}
      className="paper-dot-grid relative w-full border-b border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: PAPER, color: 'var(--color-charcoal)' }}
      aria-label="Operating metrics"
    >
      <div className="page-margin-x relative z-[1] py-12 md:py-[80px]">
        <motion.p
          className="section-numeral mb-6"
          variants={statsHeaderVariants}
          initial={reduce ? false : 'hidden'}
          animate={inView || reduce ? 'visible' : 'hidden'}
        >
          II
        </motion.p>
        <motion.div
          className="flex flex-col lg:flex-row lg:items-start"
          variants={statsGridVariants}
          initial={reduce ? false : 'hidden'}
          animate={inView || reduce ? 'visible' : 'hidden'}
        >
          {METRICS.map((m, i) => (
            <StatColumn key={m.label} metric={m} index={i} run={runFlags[i]} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
