import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { DEMO_LOOKUP_QUERY, DEMO_LOOKUP_RESULT, LookupResultSnapshot } from '@aethria/product-chrome';
import Plate from '../Plate';

const CHAR_MIN_MS = 60;
const CHAR_MAX_MS = 90;
const STAGE_DELAY_MS = 820;
const MEMO_DELAY_MS = 520;
const STEPS = ['Identify', 'Discover', 'Review', 'Decide'] as const;
type QueryStep = (typeof STEPS)[number];
type QueryStatus = QueryStep | 'pending';
type QueryFlow = 'input' | 'analysis' | 'snapshot';

const TYPED_QUERY = DEMO_LOOKUP_QUERY;

function stepState(status: QueryStatus, step: QueryStep) {
  if (status === 'pending') return 'pending';
  const currentIndex = STEPS.indexOf(status);
  const stepIndex = STEPS.indexOf(step);
  if (stepIndex < currentIndex) return 'complete';
  if (stepIndex === currentIndex) return 'active';
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
  const [flow, setFlow] = useState<QueryFlow>('snapshot');
  const [caretOn, setCaretOn] = useState(false);
  const [status, setStatus] = useState<QueryStatus>('pending');

  useEffect(() => {
    if (reduce) return;

    // Reset to empty immediately on mount (plate is off-screen — 06 of 08), not when the
    // observer fires, so the visible transition is "scrolls in already empty → types", never
    // a flash of the settled memo blinking out.
    setTyped('');
    setFlow('input');
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
            setFlow('analysis');
            let stepIndex = 0;
            const advanceStep = () => {
              const step = STEPS[stepIndex];
              if (!step) {
                timeoutRef.current = window.setTimeout(() => setFlow('snapshot'), MEMO_DELAY_MS);
                return;
              }
              setStatus(step);
              stepIndex += 1;
              timeoutRef.current = window.setTimeout(advanceStep, STAGE_DELAY_MS);
            };
            advanceStep();
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
      tone="stock-editorial"
    >
      <div
        ref={rootRef}
        className="query reveal d2"
        data-query-flow="dispatch-sequence"
        data-dispatch-stages="Identify Discover Review Decide"
        aria-label="Aethria lookup sequence"
      >
        {flow === 'input' ? (
          <div className="query-state query-input-state" aria-label="Company lookup input">
            <div className="query-bar active">
              <span className="p">&gt;</span>
              <span className="query-text">{typed}</span>
              {caretOn ? <span className="query-caret" /> : null}
              <span className="query-submit" aria-hidden="true">↵</span>
            </div>
          </div>
        ) : null}
        {flow === 'analysis' ? (
          <div className="query-state query-analysis-state" aria-label="Analysis progress">
            <h3 className="query-company-name">{TYPED_QUERY}</h3>
            <div className="query-progress" aria-live="polite">
              {STEPS.map((step, index) => (
                <div className="query-progress-step" key={step}>
                  {index > 0 ? <span className="query-progress-connector" aria-hidden="true" /> : null}
                  <span className="query-progress-item">
                    <span className={`query-progress-dot ${stepState(status, step)}`} aria-hidden="true" />
                    <span className={`query-progress-label ${stepState(status, step)}`}>{step}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        {flow === 'snapshot' ? (
          <div className="query-state query-snapshot-state memo-reveal in">
            <LookupResultSnapshot
              {...DEMO_LOOKUP_RESULT}
              size="lg"
              className="query-dispatch-snapshot"
            />
          </div>
        ) : null}
      </div>
      <p className="caption reveal d3">
        On-demand lookup turns any company name into a sourced investment record in seconds — benchmarked against
        your active thesis the moment results arrive.
      </p>
    </Plate>
  );
}
