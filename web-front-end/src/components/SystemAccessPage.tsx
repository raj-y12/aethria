export interface SystemAccessPageProps {
  hero?: string;
  status?: string;
}

const DEFAULTS = {
  hero: 'Aethria',
  status: 'INFRASTRUCTURE IN PREPARATION',
} as const;

export default function SystemAccessPage({
  hero = DEFAULTS.hero,
  status = DEFAULTS.status,
}: SystemAccessPageProps) {
  return (
    <div className="min-h-screen w-full min-w-0 flex items-center justify-center overflow-x-hidden bg-oxford">
      <div className="w-full min-w-0 flex items-center justify-center px-4 py-8 sm:px-8 sm:py-10 lg:px-12 lg:py-12">
        <div className="w-full max-w-2xl min-w-0 flex flex-col items-center justify-center text-center gap-6 sm:gap-8 lg:gap-10">
          {/* Title — responsive clamp, centering; delay/underline unchanged */}
          <h1
            className="font-display font-bold text-ivory tracking-[-0.05em] system-access-hero w-full max-w-full break-words"
            style={{
              fontSize: 'clamp(1.75rem, 6vw + 1rem, 4rem)',
              lineHeight: 1.1,
            }}
          >
            {hero === 'Aethria' ? (
              <>
                <span className="relative inline-block mr-0.5">
                  A
                  <span
                    className="absolute bottom-0 left-0 right-0 h-[0.06em] bg-ivory system-access-hero-underline"
                    aria-hidden
                  />
                </span>
                ethria
              </>
            ) : (
              hero
            )}
          </h1>

          {/* Status indicator — legible at all sizes, wraps if needed */}
          <p className="font-sans text-ivory/80 uppercase system-access-status w-full max-w-full text-[10px] leading-relaxed tracking-[0.2em] sm:text-[11px] sm:tracking-[0.28em] break-words">
            {status}
          </p>

          {/* Loading triangle — spacing from gap above */}
          <div className="system-access-loader flex-shrink-0" aria-hidden>
            <span className="system-access-loader-dot system-access-loader-dot-1" />
            <span className="system-access-loader-dot system-access-loader-dot-2" />
            <span className="system-access-loader-dot system-access-loader-dot-3" />
          </div>
        </div>
      </div>
    </div>
  );
}
