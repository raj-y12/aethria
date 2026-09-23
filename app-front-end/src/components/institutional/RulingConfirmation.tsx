import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useFocusTrap, usePrefersReducedMotion } from '../../hooks';
import { tokens } from '../../design-system/tokens';
import type { HumanRulingDecision } from '../../api/decisions';

const EASE_OUT = tokens.motion.ease;

const DECISION_LABEL: Record<HumanRulingDecision, string> = {
  advance: 'Advance',
  monitor: 'Monitor',
  pass: 'Pass',
};

export interface RulingConfirmationProps {
  open: boolean;
  /** `confirm` asks before the write; `recorded` acknowledges after it lands. */
  phase: 'confirm' | 'recorded';
  companyName: string | null;
  decision: HumanRulingDecision;
  rationale: string;
  /** What Aethria leaned toward, in plain words — null when it had no lean. */
  systemLean: string | null;
  diverges: boolean;
  /** Human-readable override attribution, when the operator gave one. */
  overrideLabel: string | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  /** Offered after the ruling is recorded, to return to the queue. */
  onDone?: () => void;
}

/**
 * Full-screen confirmation for the one act the product exists for.
 *
 * A ruling is the authoritative, permanent record, so it gets the same weight as
 * publishing a policy version: the call restated against the system's lean, the
 * rationale read back, and an explicit acknowledgement once it lands.
 *
 * ponytail: the paper-plate shell is deliberately duplicated from
 * FundThesisConfirmationModal rather than extracted. Two consumers do not earn a
 * generic dialog abstraction, and the publish flow is the most load-bearing code
 * in Settings — not worth destabilising for shared markup. Extract if a third
 * surface needs it.
 */
export default function RulingConfirmation({
  open,
  phase,
  companyName,
  decision,
  rationale,
  systemLean,
  diverges,
  overrideLabel,
  busy,
  onCancel,
  onConfirm,
  onDone,
}: RulingConfirmationProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const primaryRef = useRef<HTMLButtonElement>(null);
  const reduceMotion = usePrefersReducedMotion();
  useFocusTrap(open, containerRef);

  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => primaryRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [open, phase]);

  useEffect(() => {
    if (!open || busy) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (phase === 'recorded') onDone?.();
      else onCancel();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel, onDone, open, phase]);

  if (typeof document === 'undefined') return null;

  const recorded = phase === 'recorded';
  const subject = companyName ?? 'this company';
  const step = (delay: number) => ({
    initial: { opacity: 0, transform: 'translateY(10px)' },
    animate: { opacity: 1, transform: 'translateY(0)' },
    transition: {
      duration: reduceMotion ? 0 : 0.5,
      ease: EASE_OUT,
      delay: reduceMotion ? 0 : delay,
    },
  });

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          ref={containerRef}
          key="ruling-confirmation"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.32, ease: EASE_OUT }}
          className="fixed inset-0 z-[9999] min-h-0 overflow-y-auto overscroll-contain bg-paper text-oxford"
          role="dialog"
          aria-modal="true"
          aria-labelledby="ruling-confirmation-title"
          aria-describedby="ruling-confirmation-description"
        >
          <div className="relative z-10 flex min-h-full w-full flex-col items-center justify-center px-phi-6 py-phi-7">
            <motion.p {...step(0.08)} className="type-label-section mb-phi-3 text-center">
              {recorded ? 'Recorded' : 'Your ruling'}
            </motion.p>
            <motion.h1
              id="ruling-confirmation-title"
              {...step(0.14)}
              className="font-sans m-0 max-w-[18ch] text-center text-[clamp(28px,4vw,52px)] font-semibold leading-[1.05] tracking-[-0.04em] text-oxford"
            >
              {recorded
                ? `${DECISION_LABEL[decision]} on ${subject}.`
                : `${DECISION_LABEL[decision]} on ${subject}?`}
            </motion.h1>
            <motion.p
              id="ruling-confirmation-description"
              {...step(0.22)}
              className="type-body mt-phi-3 max-w-[52ch] text-center text-oxford/65"
            >
              {recorded
                ? 'This is now the fund’s authoritative record for this company. It carries your rationale, the policy version it was made under, and the time you made it.'
                : 'A ruling is the fund’s authoritative record. It cannot be edited once committed — a later ruling supersedes it, and both stay on the record.'}
            </motion.p>

            <motion.dl
              {...step(0.32)}
              className="mt-phi-7 w-full min-w-0 max-w-2xl bg-paper"
            >
              <div className="grid grid-cols-1 gap-y-phi-2 border-b border-oxford/[0.06] px-phi-5 py-phi-4 md:grid-cols-[minmax(9rem,26%)_minmax(0,1fr)] md:gap-x-phi-5 md:gap-y-0">
                <dt className="type-label-section text-oxford/65">Your call</dt>
                <dd className="type-body-emphasis m-0">{DECISION_LABEL[decision]}</dd>
              </div>
              {systemLean ? (
                <div className="grid grid-cols-1 gap-y-phi-2 border-b border-oxford/[0.06] px-phi-5 py-phi-4 md:grid-cols-[minmax(9rem,26%)_minmax(0,1fr)] md:gap-x-phi-5 md:gap-y-0">
                  <dt className="type-label-section text-oxford/65">Aethria leaned</dt>
                  <dd className="m-0">
                    <span className="type-body">{systemLean}</span>
                    <span
                      className={`type-status ml-phi-3 ${diverges ? 'text-escalation' : 'text-oxford/65'}`}
                    >
                      {diverges ? 'You diverge' : 'You agree'}
                    </span>
                  </dd>
                </div>
              ) : null}
              {diverges && overrideLabel ? (
                <div className="grid grid-cols-1 gap-y-phi-2 border-b border-oxford/[0.06] px-phi-5 py-phi-4 md:grid-cols-[minmax(9rem,26%)_minmax(0,1fr)] md:gap-x-phi-5 md:gap-y-0">
                  <dt className="type-label-section text-oxford/65">Why it differs</dt>
                  <dd className="type-body m-0">{overrideLabel}</dd>
                </div>
              ) : null}
              <div className="grid grid-cols-1 gap-y-phi-2 px-phi-5 py-phi-4 md:grid-cols-[minmax(9rem,26%)_minmax(0,1fr)] md:gap-x-phi-5 md:gap-y-0">
                <dt className="type-label-section text-oxford/65">Your rationale</dt>
                <dd className="type-body-sm m-0 whitespace-pre-wrap break-words leading-relaxed [overflow-wrap:anywhere]">
                  {rationale}
                </dd>
              </div>
            </motion.dl>

            <motion.div
              {...step(0.42)}
              className="mt-phi-7 flex w-full max-w-sm flex-col items-center gap-phi-4"
            >
              {recorded ? (
                <button
                  ref={primaryRef}
                  type="button"
                  onClick={() => (onDone ? onDone() : onCancel())}
                  className="w-full btn-aethria-solid"
                >
                  {onDone ? 'Back to the docket' : 'Done'}
                </button>
              ) : (
                <>
                  <button
                    ref={primaryRef}
                    type="button"
                    onClick={onConfirm}
                    disabled={busy}
                    className="w-full btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {busy ? 'Recording ruling…' : 'Commit this ruling'}
                  </button>
                  <button
                    type="button"
                    onClick={onCancel}
                    disabled={busy}
                    className="type-action inline-flex min-h-11 items-center justify-center px-phi-3 text-oxford/65 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
                  >
                    <span className="border-b border-oxford/10 pb-0.5 transition-colors hover:border-oxford/40">
                      Keep editing
                    </span>
                  </button>
                </>
              )}
            </motion.div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
