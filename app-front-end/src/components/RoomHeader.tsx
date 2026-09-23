import type { ReactNode } from 'react';
import Reveal from './Reveal';

/**
 * How a room opens — a compact operating header carried into the workspaces.
 * The eyebrow and readouts stay in their instrument registers while the title
 * follows the product sans hierarchy.
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
    <header className={`aethria-room-header flex flex-wrap items-end justify-between gap-x-phi-7 gap-y-phi-5 ${className}`.trim()}>
      <div className="aethria-room-header__copy min-w-0">
        <Reveal delay={0.02} y={6}>
          <p className="aethria-room-header__eyebrow type-label-section type-label-section--eyebrow">{eyebrow}</p>
        </Reveal>
        <Reveal delay={0.08} y={10}>
          <h1 className="aethria-room-header__title type-display mt-phi-3 break-words text-[clamp(28px,3vw,42px)] leading-[1.08] text-oxford">
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
        <Reveal delay={0.18} y={8} className="aethria-room-header__readouts min-w-0">
          {readouts}
        </Reveal>
      ) : null}
    </header>
  );
}
