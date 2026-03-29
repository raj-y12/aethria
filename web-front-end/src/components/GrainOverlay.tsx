/**
 * Fixed viewport overlay with subtle noise texture.
 * Does not capture pointer events.
 * @param opacity - Optional opacity (default 0.025). Use 0.02 for dark backgrounds (e.g. system init).
 */
export default function GrainOverlay({ opacity = 0.025 }: { opacity?: number }) {
  const noiseDataUri =
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E";

  return (
    <div
      className="fixed inset-0 pointer-events-none z-[9999]"
      style={{
        backgroundImage: `url("${noiseDataUri}")`,
        backgroundRepeat: 'repeat',
        opacity,
        mixBlendMode: 'multiply',
        willChange: 'transform',
        transform: 'translateZ(0)',
      }}
      aria-hidden
    />
  );
}
