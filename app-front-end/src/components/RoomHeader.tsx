import type { ReactNode } from 'react';
import Reveal from './Reveal';

/**
 * How a room opens — the front door's voice carried into the workspaces.
 * Mono eyebrow, then the title in Playfair ending with the brand's verdigris
 * period (the wordmark's punctuation is the product's signature), then the
 * instrument takes over below.
 */
export default function RoomHeader({
  eyebrow,
  title,
  sub,
  readouts,
  className = '',
}: {
  eyebrow: string;
  /** Set without trailing punctuation — the verdigris period is added. */
  title: string;
  sub?: ReactNode;
  /** Right-aligned instrument readouts (mono numerals). */
  readouts?: ReactNode;
  className?: string;
}) {
  return (
    <header className={`flex flex-wrap items-end justify-between gap-x-phi-7 gap-y-phi-5 ${className}`.trim()}>
      <div className="min-w-0">
        <Reveal delay={0.02} y={6}>
          <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/40">{eyebrow}</p>
        </Reveal>
        <Reveal delay={0.08} y={10}>
          <h1 className="type-display mt-phi-3 break-words text-[clamp(28px,3vw,42px)] leading-[1.08] text-oxford">
            {title}
            <span className="wordmark-dot">.</span>
          </h1>
        </Reveal>
        {sub ? (
          <Reveal delay={0.14} y={6}>
            <div className="mt-phi-3">{sub}</div>
          </Reveal>
        ) : null}
      </div>
      {readouts ? (
        <Reveal delay={0.18} y={8} className="min-w-0">
          {readouts}
        </Reveal>
      ) : null}
    </header>
  );
}
