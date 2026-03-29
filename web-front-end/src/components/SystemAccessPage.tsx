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
      className="min-h-[100dvh] h-[100dvh] w-full min-w-0 flex items-center justify-center overflow-hidden bg-oxford relative"
      style={{
        transform: exiting ? 'translateY(-100%)' : 'translateY(0)',
        transition: `transform ${EXIT_DURATION_MS}ms cubic-bezier(0.85, 0, 0.15, 1)`,
      }}
      onTransitionEnd={handleTransitionEnd}
    >
      <div
        className="absolute inset-0 pointer-events-none z-[1]"
        aria-hidden
        style={{
          background:
            'radial-gradient(ellipse 85% 60% at 50% 38%, rgba(184, 151, 106, 0.11), transparent 58%), radial-gradient(circle at 50% 125%, rgba(0, 0, 0, 0.42), transparent 48%)',
          mixBlendMode: 'soft-light',
        }}
      />
      <GrainOverlay opacity={0.022} />
      <div
        className="w-full min-w-0 flex flex-col items-center justify-center relative z-10 pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))] pt-[max(2rem,env(safe-area-inset-top))] pb-[max(2rem,env(safe-area-inset-bottom))] sm:px-8 sm:py-10 lg:px-12 lg:py-12"
      >
        {/* Logo: bold, tighter letter-spacing; underline only under "A", left-to-right */}
        <div className="flex flex-col items-center max-w-[80vw] sm:max-w-full">
          <h1
            className="font-display text-ivory text-center break-words tracking-[-0.05em] system-access-hero"
            style={{
              fontSize: 'clamp(1.75rem, 6vw + 1rem, 4rem)',
              lineHeight: 1.1,
            }}
          >
            {hero === 'Aethria' ? (
              <>
                <span className="relative inline-block">
                  A
                  <span
                    className="system-access-hero-underline absolute left-0 bottom-0 block w-full h-[0.06em] min-h-[2px] bg-ivory"
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
          className="font-mono text-[10px] uppercase text-ivory text-center w-full max-w-full break-words system-access-status"
          style={{
            letterSpacing: '0.3em',
            marginTop: '24px',
          }}
          >
          {statusText}
        </p>
        <p
          className="font-mono text-[9px] uppercase tracking-[0.2em] text-ivory/60 text-center mt-2"
          style={{
            letterSpacing: '0.2em',
            opacity: statusText === status ? 1 : 0,
            transition: 'opacity 0.3s ease 0.3s',
          }}
        >
          Investment Intelligence
        </p>
        <div
          style={{
            width: '160px',
            height: '1px',
            backgroundColor: 'rgba(242, 240, 234, 0.2)',
            marginTop: 24,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: '100%',
              height: '100%',
              backgroundColor: 'rgba(242, 240, 234, 0.9)',
              transformOrigin: 'left',
              animation: 'system-access-progress 2.5s ease forwards',
            }}
          />
        </div>
      </div>
    </div>
  );
}
