import { useEffect, useState, type ReactNode } from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';

type PipelineStatus = 'ACTIVE' | 'PROCESSING' | 'IDLE';

const PIPELINE_STATUS_CYCLE: PipelineStatus[] = ['ACTIVE', 'PROCESSING', 'IDLE'];

const PIPELINE_STATUS_CONFIG: Record<
  PipelineStatus,
  {
    dot: string;
    dotAnimation?: string;
    label: string;
    valueClass: string;
    rowClass: string;
  }
> = {
  ACTIVE: {
    dot: 'bg-oxford',
    dotAnimation: 'pipeline-dot-pulse 2s ease-in-out infinite',
    label: 'ACTIVE',
    valueClass: 'text-oxford',
    rowClass: 'bg-oxford/[0.04] border-l-2 border-l-oxford',
  },
  PROCESSING: {
    dot: 'bg-oxford/45',
    dotAnimation: 'pipeline-dot-pulse 3.5s ease-in-out infinite',
    label: 'PROCESSING',
    valueClass: 'text-oxford/55',
    rowClass: 'bg-oxford/[0.025] border-l-2 border-l-oxford/35',
  },
  IDLE: {
    dot: 'bg-oxford/20',
    label: 'IDLE',
    valueClass: 'text-oxford/30',
    rowClass: 'border-l-2 border-l-transparent',
  },
};

const listVariants = (reduce: boolean): Variants => ({
  hidden: {},
  visible: {
    transition: {
      staggerChildren: reduce ? 0 : 0.08,
      delayChildren: reduce ? 0 : 0.06,
    },
  },
});

const itemVariants = (reduce: boolean): Variants => ({
  hidden: reduce ? {} : { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: reduce ? 0 : 0.45, ease: SCROLL_EASE },
  },
});

export default function LiveIndicatorsPanel() {
  const reduce = useReducedMotion();
  const [dealsCount, setDealsCount] = useState(47);
  const [statusIndex, setStatusIndex] = useState(0);
  const [minutesAgo, setMinutesAgo] = useState(2);

  const pipelineStatus = PIPELINE_STATUS_CYCLE[statusIndex];
  const status = PIPELINE_STATUS_CONFIG[pipelineStatus];

  useEffect(() => {
    const dealsInterval = setInterval(() => {
      setDealsCount((prev) => prev + 1);
    }, 3500 + Math.random() * 2500);
    return () => clearInterval(dealsInterval);
  }, []);

  useEffect(() => {
    const statusInterval = setInterval(() => {
      setStatusIndex((prev) => (prev + 1) % PIPELINE_STATUS_CYCLE.length);
    }, 4000);
    return () => clearInterval(statusInterval);
  }, []);

  useEffect(() => {
    const minutesInterval = setInterval(() => {
      setMinutesAgo((prev) => prev + 1);
    }, 60000);
    return () => clearInterval(minutesInterval);
  }, []);

  return (
    <motion.article
      className="flex w-full min-w-0 max-w-[520px] flex-col border border-solid border-[var(--section-divider)] bg-[#f4f1ea] lg:max-w-none"
      aria-label="Live system indicators"
      variants={listVariants(!!reduce)}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.3, margin: '0px 0px -5% 0px' }}
    >
      {/* Panel chrome */}
      <header className="flex items-center justify-between gap-3 border-b border-solid border-[var(--section-divider)] bg-oxford/[0.025] px-4 py-3 sm:px-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-oxford/40">
          System telemetry
        </p>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford pc-live-dot"
            style={{ animation: 'pipeline-dot-pulse 2.4s ease-in-out infinite' }}
            aria-hidden
          />
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/50">Live</span>
        </span>
      </header>

      {/* Primary metric */}
      <motion.div variants={itemVariants(!!reduce)} className="border-b border-solid border-[var(--section-divider)] px-4 py-5 sm:px-6 sm:py-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">
          Deals reviewed this cycle
        </p>
        <p
          className="mt-2 font-mono text-[clamp(2.5rem,8vw,3.25rem)] font-bold leading-none tracking-[-0.04em] text-oxford tabular-nums"
          aria-live="polite"
        >
          {dealsCount}
        </p>
      </motion.div>

      {/* Pipeline status — featured strip */}
      <motion.div
        variants={itemVariants(!!reduce)}
        className={`flex min-h-[52px] items-center justify-between gap-4 border-b border-solid border-[var(--section-divider)] px-4 py-3.5 transition-colors duration-500 sm:px-6 ${status.rowClass}`}
      >
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/45">Pipeline status</p>
        <span
          className={`inline-flex items-center gap-2 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-500 ${status.valueClass}`}
        >
          <span
            className={`h-1.5 w-1.5 shrink-0 rounded-none ${status.dot}`}
            style={status.dotAnimation ? { animation: status.dotAnimation } : undefined}
            aria-hidden
          />
          {status.label}
        </span>
      </motion.div>

      {/* Secondary metrics */}
      <motion.div
        variants={itemVariants(!!reduce)}
        className="grid grid-cols-1 divide-y divide-[var(--section-divider)] sm:grid-cols-2 sm:divide-x sm:divide-y-0"
      >
        <MetricCell label="Last memo generated" value={`${minutesAgo} min ago`} />
        <MetricCell
          label="Agents"
          value={
            <span className="inline-flex items-center gap-1.5">
              <span className="text-oxford/70">Scout · Review · Partner</span>
            </span>
          }
          compactValue
        />
      </motion.div>
    </motion.article>
  );
}

function MetricCell({
  label,
  value,
  compactValue = false,
}: {
  label: string;
  value: ReactNode;
  compactValue?: boolean;
}) {
  return (
    <div className="flex min-h-[72px] flex-col justify-center gap-1.5 px-4 py-4 sm:px-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">{label}</p>
      <p
        className={
          compactValue
            ? 'font-mono text-[10px] uppercase leading-snug tracking-[0.06em] text-oxford/55'
            : 'font-sans text-[15px] font-semibold tabular-nums text-oxford'
        }
      >
        {value}
      </p>
    </div>
  );
}
