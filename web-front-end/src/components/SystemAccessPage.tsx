import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import GrainOverlay from './GrainOverlay';

export interface SystemAccessPageProps {
  hero?: string;
  status?: string;
}

const DEFAULTS = {
  hero: 'Aethria',
  status: 'INFRASTRUCTURE IN PREPARATION',
} as const;

const NAVIGATE_DELAY_MS = 3200;
const EXIT_DURATION_MS = 800;

export default function SystemAccessPage({
  hero = DEFAULTS.hero,
  status = DEFAULTS.status,
}: SystemAccessPageProps) {
  const [exiting, setExiting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => setExiting(true), NAVIGATE_DELAY_MS);
    return () => clearTimeout(t);
  }, []);

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
      <GrainOverlay opacity={0.02} />
      <div className="w-full min-w-0 flex flex-col items-center justify-center px-4 py-8 sm:px-8 sm:py-10 lg:px-12 lg:py-12 relative z-10">
        {/* Logo: bold, tighter letter-spacing; underline only under "A", left-to-right */}
        <div className="flex flex-col items-center max-w-[80vw] sm:max-w-full">
          <h1
            className="font-display font-bold text-ivory text-center break-words tracking-[-0.05em]"
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
                    className="system-init-underline system-init-underline-a absolute left-0 bottom-0 block w-full h-[0.06em] min-h-[2px] bg-ivory"
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
        {/* Status: 10px Monospace, all-caps, 0.3em letter-spacing, exactly 24px below logo */}
        <p
          className="font-mono text-[10px] uppercase text-ivory text-center w-full max-w-full break-words system-init-status"
          style={{
            letterSpacing: '0.3em',
            marginTop: '24px',
          }}
        >
          {status}
        </p>
      </div>
    </div>
  );
}
