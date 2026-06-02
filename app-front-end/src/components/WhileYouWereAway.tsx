import { motion } from 'framer-motion';
import GrainOverlay from './GrainOverlay';
import AuthInstitutionalFooter from './AuthInstitutionalFooter';
import CountUp from './CountUp';
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
  { label: 'Agent-decided', value: s.agent_decided ?? s.decided, accent: false },
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
            fontSize: 'clamp(28px, 3.5vw, 44px)',
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

        {/* Stats — fixed 4-column row; never wrap (wide counts used to force stack) */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
            alignItems: 'start',
            gap: '8px clamp(12px, 2.5vw, 28px)',
            width: '100%',
            marginBottom: '64px',
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
              style={{ minWidth: 0, textAlign: 'center' }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'clamp(26px, 3.2vw, 40px)',
                  fontWeight: 500,
                  lineHeight: 1,
                  color: stat.accent ? 'var(--color-accent)' : 'var(--color-oxford)',
                  letterSpacing: '-0.02em',
                  fontVariantNumeric: 'tabular-nums',
                }}
              >
                <CountUp to={stat.value} delay={reduceMotion ? 0 : 0.22 + i * 0.07} reduceMotion={reduceMotion} />
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  lineHeight: 1.35,
                  color: 'rgba(var(--color-oxford-rgb), 0.55)',
                  marginTop: '8px',
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  textWrap: 'balance',
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
          whileTap={reduceMotion ? {} : { scale: 0.97 }}
          onClick={onDismiss}
          className="group btn-aethria-solid"
          style={{ padding: '0 72px' }}
        >
          <span className="flex items-center justify-center">
            <span>Enter Aethria</span>
            <span
              className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease group-hover:w-6"
              aria-hidden
            >
              {'\u00a0→'}
            </span>
          </span>
        </motion.button>
      </div>

      <motion.footer
        initial={reduceMotion ? false : { opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, transition: { duration: reduceMotion ? 0 : 0.2, ease: EASE } }}
        transition={{ duration: reduceMotion ? 0 : 1, ease: EASE, delay: reduceMotion ? 0 : 1 }}
        className="fixed bottom-0 left-0 z-[10000] w-full p-phi-6 flex justify-center pointer-events-none"
      >
        <AuthInstitutionalFooter />
      </motion.footer>
    </motion.div>
  );
}
