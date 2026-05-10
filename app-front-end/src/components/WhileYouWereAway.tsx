import { motion } from 'framer-motion';
import GrainOverlay from './GrainOverlay';
import type { ActivitySummary } from '../api/activity';
import { usePrefersReducedMotion } from '../hooks';

interface Props {
  summary: ActivitySummary;
  onDismiss: () => void;
}

const EASE = [0.16, 1, 0.3, 1] as const;

const STATS_CONFIG = (s: ActivitySummary) => [
  { label: 'Discovered', value: s.found, accent: false },
  { label: 'Evaluated', value: s.reviewed, accent: false },
  { label: 'Decided', value: s.decided, accent: false },
  { label: 'Escalated', value: s.escalations, accent: true },
];

export default function WhileYouWereAway({ summary, onDismiss }: Props) {
  const reduceMotion = usePrefersReducedMotion();
  const stats = STATS_CONFIG(summary);

  return (
    <motion.div
      key="while-you-were-away"
      initial={reduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: reduceMotion ? 0 : 0.25, ease: EASE } }}
      transition={{ duration: reduceMotion ? 0 : 0.4, ease: EASE }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'var(--color-paper)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'clamp(24px, 5vw, 56px)',
      }}
    >
      <GrainOverlay opacity={0.028} />
      <div style={{ position: 'relative', zIndex: 10, width: '100%', maxWidth: '40rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {/* Eyebrow */}
        <motion.p
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: reduceMotion ? 0 : 0.2, delay: reduceMotion ? 0 : 0.42, ease: EASE } }}
          transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE, delay: reduceMotion ? 0 : 0.05 }}
          style={{
            fontFamily: "var(--font-mono)",
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
          initial={reduceMotion ? false : { opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: reduceMotion ? 0 : 12, transition: { duration: reduceMotion ? 0 : 0.35, delay: reduceMotion ? 0 : 0.35, ease: EASE } }}
          transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE, delay: reduceMotion ? 0 : 0.1 }}
          style={{
            fontFamily: "var(--font-display)",
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
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: reduceMotion ? 0 : 0.3, delay: reduceMotion ? 0 : 0.28, ease: EASE } }}
          transition={{ duration: reduceMotion ? 0 : 0.5, ease: EASE, delay: reduceMotion ? 0 : 0.18 }}
          style={{
            fontFamily: "var(--font-sans)",
            fontSize: '14px',
            color: 'rgba(var(--color-oxford-rgb), 0.6)',
            marginTop: '12px',
            marginBottom: '55px',
            textAlign: 'center',
          }}
        >
          Agents continued working. Here is what happened.
        </motion.p>

        {/* Stats */}
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
              initial={reduceMotion ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{
                opacity: 0,
                y: reduceMotion ? 0 : 10,
                transition: { duration: reduceMotion ? 0 : 0.3, delay: reduceMotion ? 0 : (stats.length - 1 - i) * 0.06, ease: EASE },
              }}
              transition={{ duration: reduceMotion ? 0 : 0.45, ease: EASE, delay: reduceMotion ? 0 : 0.22 + i * 0.07 }}
              style={{ textAlign: 'center' }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 'clamp(34px, 5vw, 56px)',
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
                  fontFamily: "var(--font-sans)",
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
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: reduceMotion ? 0 : 0.2, delay: 0, ease: EASE } }}
          transition={{ duration: reduceMotion ? 0 : 0.4, ease: EASE, delay: reduceMotion ? 0 : 0.22 + stats.length * 0.07 }}
          onClick={onDismiss}
          className="group btn-aethria-solid"
          style={{ padding: '0 48px' }}
        >
          <span className="flex items-center justify-center">
            <span>Enter Aethria</span>
            <span
              className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
              aria-hidden
            >
              {' →'}
            </span>
          </span>
        </motion.button>
      </div>
    </motion.div>
  );
}
