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

  return (
    <motion.div
      key="while-you-were-away"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: '#F2F0EA',
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
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.05 }}
        style={{
          fontFamily: "'Space Mono', ui-monospace, monospace",
          fontSize: '10px',
          letterSpacing: '0.16em',
          textTransform: 'uppercase',
          color: 'rgba(0, 33, 71, 0.4)',
          marginBottom: '16px',
        }}
      >
        System Report
      </motion.p>

      {/* Title */}
      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
        style={{
          fontFamily: "'Cormorant Garamond', Georgia, serif",
          fontSize: 'clamp(36px, 5vw, 64px)',
          fontWeight: 500,
          color: '#002147',
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
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.18 }}
        style={{
          fontFamily: "'Instrument Sans', system-ui, sans-serif",
          fontSize: '14px',
          color: 'rgba(0, 33, 71, 0.5)',
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
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.22 + i * 0.07 }}
            style={{ textAlign: 'center' }}
          >
            <div
              style={{
                fontFamily: "'Space Mono', ui-monospace, monospace",
                fontSize: 'clamp(40px, 6vw, 72px)',
                fontWeight: 700,
                lineHeight: 1,
                color: stat.accent ? '#7D2B3A' : '#002147',
                letterSpacing: '-0.03em',
              }}
            >
              {stat.value.toLocaleString()}
            </div>
            <div
              style={{
                fontFamily: "'Instrument Sans', system-ui, sans-serif",
                fontSize: '13px',
                color: 'rgba(0, 33, 71, 0.5)',
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
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay: 0.22 + stats.length * 0.07 }}
        onClick={onDismiss}
        style={{
          padding: '14px 48px',
          backgroundColor: '#002147',
          color: '#F2F0EA',
          border: 'none',
          fontFamily: "'Space Mono', ui-monospace, monospace",
          fontSize: '11px',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          cursor: 'pointer',
          transition: 'opacity 0.15s',
        }}
        onHoverStart={(e) => ((e.target as HTMLButtonElement).style.opacity = '0.8')}
        onHoverEnd={(e) => ((e.target as HTMLButtonElement).style.opacity = '1')}
      >
        Enter System
      </motion.button>
    </motion.div>
  );
}
