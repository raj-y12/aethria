/**
 * Full-screen "While you were away" summary shown on return after inactivity.
 */
import { motion } from 'framer-motion';
import type { ActivitySummary } from '../api/activity';

interface Props {
  summary: ActivitySummary;
  onDismiss: () => void;
}

const STATS = (s: ActivitySummary) => [
  { label: 'Startups discovered', value: s.found, accent: false },
  { label: 'Evaluated by reviewers', value: s.reviewed, accent: false },
  { label: 'Decisions rendered', value: s.decided, accent: false },
  { label: 'Escalations flagged', value: s.escalations, accent: true },
];

export default function WhileYouWereAway({ summary, onDismiss }: Props) {
  const stats = STATS(summary);

  const ease = [0.16, 1, 0.3, 1] as const;

  return (
    <motion.div
      key="while-you-were-away"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.25, delay: 0.48, ease } }}
      transition={{ duration: 0.4, ease }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'var(--color-paper)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '34px',
      }}
    >
      {/* Eyebrow */}
      <motion.p
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 10, transition: { duration: 0.35, delay: 0.42, ease } }}
        transition={{ duration: 0.45, ease, delay: 0.05 }}
        style={{
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontSize: '11px',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: 'rgba(var(--color-oxford-rgb), 0.55)',
          marginBottom: '16px',
        }}
      >
        System Report
      </motion.p>

      {/* Title */}
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 12, transition: { duration: 0.35, delay: 0.35, ease } }}
        transition={{ duration: 0.5, ease, delay: 0.1 }}
        style={{
          fontFamily: "'EB Garamond', Georgia, serif",
          fontSize: 'clamp(36px, 5vw, 64px)',
          fontWeight: 500,
          color: 'var(--color-oxford)',
          lineHeight: 1.1,
          margin: 0,
          textAlign: 'center',
        }}
      >
        While you were away
      </motion.h1>

      {/* Subtitle */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.3, delay: 0.28, ease } }}
        transition={{ duration: 0.5, ease, delay: 0.18 }}
        style={{
          fontFamily: "'Geist Sans', system-ui, sans-serif",
          fontSize: '14px',
          color: 'rgba(var(--color-oxford-rgb), 0.6)',
          marginTop: '12px',
          marginBottom: '55px',
          textAlign: 'center',
        }}
      >
        Agents continued working. Here is what happened.
      </motion.p>

      {/* Stats — horizontal row */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-start',
          justifyContent: 'center',
          gap: 'clamp(32px, 6vw, 80px)',
          marginBottom: '64px',
          flexWrap: 'wrap',
        }}
      >
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{
              opacity: 0,
              y: 10,
              transition: { duration: 0.3, delay: (stats.length - 1 - i) * 0.06, ease },
            }}
            transition={{ duration: 0.45, ease, delay: 0.22 + i * 0.07 }}
            style={{ textAlign: 'center' }}
          >
            <div
              style={{
                fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                fontSize: 'clamp(40px, 6vw, 72px)',
                fontWeight: 700,
                lineHeight: 1,
                color: stat.accent ? 'var(--color-accent)' : 'var(--color-oxford)',
                letterSpacing: '-0.03em',
              }}
            >
              {stat.value.toLocaleString()}
            </div>
            <div
              style={{
                fontFamily: "'Geist Sans', system-ui, sans-serif",
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

      {/* CTA */}
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: 0.2, delay: 0, ease } }}
        transition={{ duration: 0.4, ease, delay: 0.22 + stats.length * 0.07 }}
        onClick={onDismiss}
        className="group btn-aethria-solid"
        style={{ padding: '0 48px' }} // Maintaining width for the full-screen CTA
      >
        <span className="flex items-center justify-center">
          <span>Enter System</span>
          <span
            className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
            aria-hidden
          >
            {'\u00A0→'}
          </span>
        </span>
      </motion.button>
    </motion.div>
  );
}
