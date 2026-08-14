import { createElement } from 'react';
import { useReducedMotion } from 'framer-motion';
import { useInView } from '../lib/useInView';

export interface PlateProps {
  id?: string;
  /** e.g. "01 — 08" */
  index: string;
  /** plate head title (Playfair) */
  title: string;
  /** vertical caption rail (left) */
  capLeft: string;
  /** vertical caption rail (right) */
  capRight: string;
  children: React.ReactNode;
  /** the plate title renders as this heading element; default 2 */
  headingLevel?: 2 | 3;
  /** visual surface for the chapter; keeps content primitives reusable without flattening the page rhythm */
  tone?: 'stock-editorial' | 'oxford-intelligence' | 'product-evidence' | 'image-led' | 'quiet-transition';
}

/**
 * Bracket-framed plate wrapper with scroll reveal — the primitive every gallery
 * plate (Tasks 8–11) builds on. Classes (.plate/.plate-cap-l/-r/.framed/.plate-head/
 * .plate-title/.plate-num/.reveal) already live in index.css (Task 1).
 * Visual source of truth: docs/design/explorations/J-gallery-instruments.html.
 */
export default function Plate({
  id,
  index,
  title,
  capLeft,
  capRight,
  children,
  headingLevel = 2,
  tone = 'stock-editorial',
}: PlateProps) {
  const reduce = useReducedMotion();
  const [ref, isIn] = useInView<HTMLElement>(reduce, 0.28);

  return (
    <section ref={ref} id={id} className={`plate surface-${tone}${isIn ? ' in' : ''}`}>
      <span className="plate-cap-l">{capLeft}</span>
      <span className="plate-cap-r">{capRight}</span>
      <div className="framed">
        <div className="plate-head">
          {createElement('h' + headingLevel, { className: 'plate-title reveal' }, title)}
          <div className="plate-num reveal d1">{index}</div>
        </div>
        {children}
      </div>
    </section>
  );
}
