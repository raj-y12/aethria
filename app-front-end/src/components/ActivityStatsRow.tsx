import { motion } from 'framer-motion';
import type { ActivitySummary } from '../api/activity';
import CountUp from './CountUp';

const EASE = [0.16, 1, 0.3, 1] as const;

export interface ActivityStatItem {
  label: string;
  value: number;
  accent: boolean;
}

export function activityStatsFromSummary(s: ActivitySummary): ActivityStatItem[] {
  return [
    { label: 'Discovered', value: s.found, accent: false },
    { label: 'Evaluated', value: s.reviewed, accent: false },
    { label: 'Agent-decided', value: s.agent_decided ?? s.decided, accent: false },
    { label: 'Escalated', value: s.escalations, accent: true },
  ];
}

/** Large mono stat numerals — matches Decision Stage conviction weight. */
export default function ActivityStatsRow({
  stats,
  reduceMotion,
  baseDelay = 0.22,
}: {
  stats: ActivityStatItem[];
  reduceMotion: boolean;
  baseDelay?: number;
}) {
  return (
    <div
      className="flex flex-row flex-wrap items-start justify-center"
      style={{ gap: 'clamp(48px, 8vw, 120px)' }}
    >
      {stats.map((stat, i) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: EASE, delay: baseDelay + i * 0.07 }}
          style={{ textAlign: 'center' }}
        >
          <div
            className="font-mono font-bold tabular-nums text-oxford"
            style={{
              fontSize: 'clamp(52px, 10vw, 96px)',
              lineHeight: 0.85,
              letterSpacing: '-0.05em',
              color: stat.accent ? 'var(--color-accent)' : 'var(--color-oxford)',
              minWidth: `${stat.value.toLocaleString().length}ch`,
            }}
          >
            <CountUp to={stat.value} delay={baseDelay + i * 0.07} reduceMotion={reduceMotion} />
          </div>
          <div
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '13px',
              color: 'rgba(var(--color-oxford-rgb), 0.6)',
              marginTop: '6px',
              letterSpacing: '0.01em',
            }}
          >
            {stat.label}
          </div>
        </motion.div>
      ))}
    </div>
  );
}
