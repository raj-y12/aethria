import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { DEMO_LOOKUP_QUERY, DEMO_LOOKUP_RESULT, LookupCommandBar, LookupResultSnapshot } from '@aethria/product-chrome';
import Plate from '../Plate';

const CHAR_MIN_MS = 60;
const CHAR_MAX_MS = 90;
const MEMO_DELAY_MS = 500;

/** Plate 06 — place a query: the real on-demand lookup, reused from product-chrome. */
export default function QueryPlate() {
  const reduce = useReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const started = useRef(false);

  // Initial state is the settled, fully-rendered look (query typed, memo visible, no caret) —
  // matches SSR output and the reduced-motion experience. Only the effect below (client-only,
  // motion allowed) resets to empty and types it back out once the plate scrolls into view.
  const [typed, setTyped] = useState(DEMO_LOOKUP_QUERY);
  const [memoIn, setMemoIn] = useState(true);
  const [caretOn, setCaretOn] = useState(false);

  useEffect(() => {
    if (reduce) return;

    const runSequence = () => {
      if (started.current) return;
      started.current = true;
      setTyped('');
      setMemoIn(false);
      setCaretOn(true);

      let i = 0;
      const typeChar = () => {
        i += 1;
        setTyped(DEMO_LOOKUP_QUERY.slice(0, i));
        if (i < DEMO_LOOKUP_QUERY.length) {
          window.setTimeout(typeChar, CHAR_MIN_MS + Math.random() * (CHAR_MAX_MS - CHAR_MIN_MS));
        } else {
          window.setTimeout(() => setMemoIn(true), MEMO_DELAY_MS);
        }
      };
      window.setTimeout(typeChar, CHAR_MIN_MS + Math.random() * (CHAR_MAX_MS - CHAR_MIN_MS));
    };

    const root = rootRef.current;
    if (!root || typeof IntersectionObserver === 'undefined') {
      runSequence();
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        runSequence();
      },
      { threshold: 0.3 },
    );
    obs.observe(root);
    return () => obs.disconnect();
  }, [reduce]);

  return (
    <Plate
      id="query"
      index="06 — 08"
      title="Place a Query"
      capLeft="Place a Query — Plate 06"
      capRight="Any name · a sourced record"
    >
      <div ref={rootRef} className="query reveal d2" aria-hidden>
        <div className="query-typing">
          <LookupCommandBar query={typed} trailing="run" />
          {caretOn ? <span className="query-caret" /> : null}
        </div>
        <div className={`memo-reveal${memoIn ? ' in' : ''}`}>
          <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
        </div>
      </div>
      <p className="caption reveal d3">
        On-demand lookup turns any company name into a sourced investment record in seconds — benchmarked against
        your active thesis the moment results arrive.
      </p>
    </Plate>
  );
}
