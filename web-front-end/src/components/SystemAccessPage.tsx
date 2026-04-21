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
const EXIT_DURATION_MS = 800;

export default function SystemAccessPage({
  hero = DEFAULTS.hero,
  status = DEFAULTS.status,
}: SystemAccessPageProps) {
  const [exiting, setExiting] = useState(false);
  const [statusText, setStatusText] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => setExiting(true), NAVIGATE_DELAY_MS);
    return () => clearTimeout(t);
  }, []);

  // Fallback: navigate even if CSS transitions are disabled or never fire.
  useEffect(() => {
    if (!exiting) return;
    const fallback = setTimeout(
      () => navigate('/home', { replace: true }),
      EXIT_DURATION_MS + 300,
    );
    return () => clearTimeout(fallback);
  }, [exiting, navigate]);

  useEffect(() => {
    const full = status;
    let index = 0;
    const interval = setInterval(() => {
      index += 1;
      setStatusText(full.slice(0, index));
      if (index >= full.length) {
        clearInterval(interval);
      }
    }, 60);
    return () => clearInterval(interval);
  }, [status]);

  const handleTransitionEnd = useCallback(
    (e: React.TransitionEvent) => {
      if (exiting && e.propertyName === 'transform') {
        navigate('/home', { replace: true });
      }
    },
    [exiting, navigate]
  );

  return (
    <div
      className="relative flex h-[100dvh] min-h-[100dvh] w-full min-w-0 items-center justify-center overflow-hidden"
      style={{
        backgroundColor: 'var(--color-oxford)',
        transform: exiting ? 'translateY(-100%)' : 'translateY(0)',
        transition: `transform ${EXIT_DURATION_MS}ms cubic-bezier(0.85, 0, 0.15, 1)`,
      }}
      onTransitionEnd={handleTransitionEnd}
    >
      <div
        className="pointer-events-none absolute inset-0 z-[1]"
        aria-hidden
        style={{
          background:
            'radial-gradient(ellipse 88% 55% at 15% 20%, rgba(252, 252, 252, 0.06), transparent 55%), radial-gradient(ellipse 70% 45% at 85% 15%, rgba(242, 240, 234, 0.05), transparent 50%), radial-gradient(circle at 50% 110%, rgba(0, 0, 0, 0.35), transparent 45%)',
          mixBlendMode: 'soft-light',
        }}
      />
      <GrainOverlay opacity={0.028} variant="dark" />
      <div
        className="relative z-10 flex w-full min-w-0 flex-col items-center justify-center px-[max(1.25rem,env(safe-area-inset-left))] py-[max(2rem,env(safe-area-inset-top))] pb-[max(2rem,env(safe-area-inset-bottom))] pr-[max(1.25rem,env(safe-area-inset-right))] sm:px-10 sm:py-12"
      >
        <div className="flex max-w-[min(100%,20rem)] flex-col items-center sm:max-w-none">
          <h1
            className="font-wordmark text-center text-[clamp(1.875rem,5.5vw,3.25rem)] font-normal normal-case leading-[1.08] tracking-normal text-[#f2f0ea] system-access-hero"
          >
            {hero === 'Aethria' ? (
              <>
                <span className="relative inline-block">
                  A
                  <span
                    className="system-access-hero-underline absolute bottom-0 left-0 block h-[0.08em] min-h-[2px] w-full bg-[rgba(252,252,252,0.85)]"
                    aria-hidden
                  />
                </span>
                ethria
              </>
            ) : (
              hero
            )}
          </h1>
        </div>
        <p
          className="system-access-status mt-8 w-full max-w-full break-words text-center font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(242,240,234,0.72)]"
        >
          {statusText}
        </p>
        <div
          className="mt-10 h-px w-[min(10rem,55vw)] overflow-hidden bg-[rgba(242,240,234,0.12)]"
          aria-hidden
        >
          <div
            className="h-full w-full origin-left bg-[rgba(252,252,252,0.92)]"
            style={{
              animation: 'system-access-progress 2.5s ease forwards',
            }}
          />
        </div>
      </div>
    </div>
  );
}
