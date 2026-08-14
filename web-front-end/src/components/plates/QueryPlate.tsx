import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { DEMO_LOOKUP_QUERY, DEMO_LOOKUP_RESULT, LookupResultSnapshot } from '@aethria/product-chrome';
import Plate from '../Plate';

const CHAR_MIN_MS = 60;
const CHAR_MAX_MS = 90;
const STAGE_DELAY_MS = 820;
const MEMO_DELAY_MS = 520;
const STAGES = ['Scouting', 'Reviewing', 'Deciding'] as const;
type QueryStage = (typeof STAGES)[number];
type QueryStatus = QueryStage | 'pending' | 'complete';

const TYPED_QUERY = DEMO_LOOKUP_QUERY;

function stageState(status: QueryStatus, stage: QueryStage) {
  if (status === 'complete') return 'complete';
  if (status === 'pending') return 'pending';
  const currentIndex = STAGES.indexOf(status);
  const stageIndex = STAGES.indexOf(stage);
  if (stageIndex < currentIndex) return 'complete';
  if (stageIndex === currentIndex) return 'active';
  return 'pending';
}

/** Plate 06 — place a query: the real on-demand lookup, reused from product-chrome. */
export default function QueryPlate() {
  const reduce = useReducedMotion();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const started = useRef(false);
  const timeoutRef = useRef<number | null>(null);

  // Initial state is the settled, fully-rendered look (query typed, memo visible, no caret) —
  // matches SSR output and the reduced-motion experience. Only the effect below (client-only,
  // motion allowed) resets to empty on mount and types it back out once the plate scrolls into view.
  const [typed, setTyped] = useState(TYPED_QUERY);
  const [memoIn, setMemoIn] = useState(true);
  const [caretOn, setCaretOn] = useState(false);
  const [status, setStatus] = useState<QueryStatus>('complete');

  useEffect(() => {
    if (reduce) return;

    // Reset to empty immediately on mount (plate is off-screen — 06 of 08), not when the
    // observer fires, so the visible transition is "scrolls in already empty → types", never
    // a flash of the settled memo blinking out.
    setTyped('');
    setMemoIn(false);
    setCaretOn(true);
    setStatus('pending');

    const runSequence = () => {
      if (started.current) return;
      started.current = true;

      let i = 0;
      const typeChar = () => {
        i += 1;
        setTyped(TYPED_QUERY.slice(0, i));
        if (i < TYPED_QUERY.length) {
          timeoutRef.current = window.setTimeout(typeChar, CHAR_MIN_MS + Math.random() * (CHAR_MAX_MS - CHAR_MIN_MS));
        } else {
          timeoutRef.current = window.setTimeout(() => {
            setCaretOn(false);
            let stageIndex = 0;
            const advanceStage = () => {
              const stage = STAGES[stageIndex];
              if (!stage) {
                setStatus('complete');
                timeoutRef.current = window.setTimeout(() => setMemoIn(true), MEMO_DELAY_MS);
                return;
              }
              setStatus(stage);
              stageIndex += 1;
              timeoutRef.current = window.setTimeout(advanceStage, STAGE_DELAY_MS);
            };
            advanceStage();
          }, MEMO_DELAY_MS);
        }
      };
      timeoutRef.current = window.setTimeout(typeChar, CHAR_MIN_MS + Math.random() * (CHAR_MAX_MS - CHAR_MIN_MS));
    };

    const clearPendingTimeout = () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };

    const root = rootRef.current;
    if (!root || typeof IntersectionObserver === 'undefined') {
      runSequence();
      return clearPendingTimeout;
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
    return () => {
      obs.disconnect();
      clearPendingTimeout();
    };
  }, [reduce]);

  return (
    <Plate
      id="query"
      index="06 — 08"
      title="Place a Query"
      capLeft="On-demand intelligence / lookup"
      capRight="Any name · a sourced record"
      tone="product-evidence"
    >
      <div
        ref={rootRef}
        className="query reveal d2"
        data-query-flow="dispatch-sequence"
        aria-label="Aethria lookup sequence"
      >
        <div className="query-bar">
          <span className="p">›</span>
          <span className="query-text">{typed}</span>
          {caretOn ? <span className="query-caret" /> : null}
          <span className="query-submit" aria-hidden="true">↵</span>
        </div>
        <div className="query-pipeline" aria-live="polite" aria-label="Lookup stages">
          {STAGES.map((stage) => (
            <span className={`query-stage ${stageState(status, stage)}`} key={stage}>
              {stage}
            </span>
          ))}
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
