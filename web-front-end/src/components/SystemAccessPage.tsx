import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import GrainOverlay from './GrainOverlay';

export interface SystemAccessPageProps {
  hero?: string;
  status?: string;
}

const DEFAULTS = {
  hero: 'Aethria',
  status: 'REDIRECTING',
} as const;

const NAVIGATE_DELAY_MS = 3200;
const NAVIGATE_DELAY_REDUCED_MS = 400;
const EXIT_DURATION_MS = 800;

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}

export default function SystemAccessPage({
  hero = DEFAULTS.hero,
  status = DEFAULTS.status,
}: SystemAccessPageProps) {
  const reduce = usePrefersReducedMotion();
  const [exiting, setExiting] = useState(false);
  const [statusText, setStatusText] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const delay = reduce ? NAVIGATE_DELAY_REDUCED_MS : NAVIGATE_DELAY_MS;
    const t = setTimeout(() => setExiting(true), delay);
    return () => clearTimeout(t);
  }, [reduce]);

  useEffect(() => {
    if (!exiting) return;
    const t = setTimeout(() => navigate('/home', { replace: true }), EXIT_DURATION_MS + 300);
    return () => clearTimeout(t);
  }, [exiting, navigate]);

  useEffect(() => {
    const full = status;
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setStatusText(full.slice(0, i));
      if (i >= full.length) clearInterval(interval);
    }, 60);
    return () => clearInterval(interval);
  }, [status]);

  const handleTransitionEnd = useCallback(
    (e: React.TransitionEvent) => {
      if (exiting && e.propertyName === 'transform') navigate('/home', { replace: true });
    },
    [exiting, navigate],
  );

  return (
    <div
      className="relative flex h-[100dvh] w-full items-center justify-center overflow-hidden"
      style={{
        backgroundColor: 'var(--color-oxford)',
        transform: exiting ? 'translateY(-100%)' : 'translateY(0)',
        transition: reduce ? 'none' : `transform ${EXIT_DURATION_MS}ms cubic-bezier(0.85, 0, 0.15, 1)`,
      }}
      onTransitionEnd={handleTransitionEnd}
    >
      <GrainOverlay opacity={0.032} variant="dark" />

      <div className="relative z-10 flex flex-col items-center">
        <h1 className={`font-wordmark text-[clamp(2rem,5vw,3rem)] font-medium normal-case leading-none tracking-normal text-[var(--text-inverse)] ${reduce ? '' : 'system-access-hero'}`}>
          {hero === 'Aethria' ? (
            <>
              Aethria<span className="wordmark-dot--inverse">.</span>
            </>
          ) : (
            hero
          )}
        </h1>

        <p className={`mt-5 font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--text-inverse-muted)] ${reduce ? '' : 'system-access-status'}`}>
          {statusText}&nbsp;
        </p>
      </div>
    </div>
  );
}
