import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence, type Variants } from 'framer-motion';
import AgentDispatch from './AgentDispatch';
import { useFocusTrap } from '../hooks';

const EASE = [0.16, 1, 0.3, 1] as const;
/** Reverse-stagger anchor for exit — much shorter than enter so dismiss feels snappy. */
const DISPATCH_EXIT_TAIL_DELAY = 0.1;
const DISPATCH_EXIT_DURATION = 0.2;
const DISPATCH_EXIT_STAGGER = 0.025;

type DispatchExitCustom = { enterY: number; duration: number; enterDelay: number };

function dispatchExitCustom(enterY: number, duration: number, enterDelay: number): DispatchExitCustom {
  return { enterY, duration, enterDelay };
}

/** Propagates reverse-staggered exits to direct motion children. */
const DISPATCH_EXIT_ORCHESTRATOR: Variants = {
  exit: {
    transition: {
      staggerChildren: DISPATCH_EXIT_STAGGER,
      staggerDirection: -1,
    },
  },
};

const DISPATCH_EXIT_PIECE: Variants = {
  exit: ({ enterY, enterDelay }: DispatchExitCustom) => ({
    opacity: 0,
    y: enterY === 0 ? 10 : Math.abs(enterY),
    transition: {
      duration: DISPATCH_EXIT_DURATION,
      ease: EASE,
      delay: Math.max(0, DISPATCH_EXIT_TAIL_DELAY - enterDelay * 0.3),
    },
  }),
};

export interface LookupProgress {
  query: string;
  name: string | null;
  sector: string | null;
  found: boolean;
  reviewed: boolean;
}

export interface LookupChip {
  id: string;
  label: string;
  status: 'scouting' | 'reviewing' | 'decided';
  active: boolean;
}

interface DispatchCommandBarProps {
  open: boolean;
  onClose: () => void;
  input: string;
  setInput: (v: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  isBusy: boolean;
  message: string | null;
  onClearMessage?: () => void;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
  /** In-flight lookup, drives progressive reveal. Null until a lookup is queued. */
  progress?: LookupProgress | null;
  /** Result overview (LookupResultSnapshot) shown once the lookup has a decision. */
  result?: ReactNode;
  /** Tracked lookups (active + backgrounded) shown as a focusable chip stack. */
  chips?: LookupChip[];
  onFocusChip?: (id: string) => void;
}

type StepState = 'done' | 'active' | 'pending';

function ProgressSteps({ progress }: { progress: LookupProgress }) {
  const steps: { label: string; state: StepState }[] = [
    { label: 'Discover', state: progress.found ? 'done' : 'active' },
    { label: 'Review', state: progress.reviewed ? 'done' : progress.found ? 'active' : 'pending' },
    { label: 'Decide', state: progress.reviewed ? 'active' : 'pending' },
  ];
  return (
    <div className="flex items-center justify-center gap-phi-2" aria-label="Analysis progress">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center gap-phi-2">
          {i > 0 ? <span className="h-px w-6 bg-oxford/15" aria-hidden /> : null}
          <span className="inline-flex items-center gap-phi-2">
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-none ${
                step.state === 'done'
                  ? 'bg-oxford'
                  : step.state === 'active'
                    ? 'bg-oxford signal-dot-breathe'
                    : 'bg-oxford/20'
              }`}
              aria-hidden
            />
            <span
              className={`font-mono text-[11px] uppercase tracking-[0.12em] ${
                step.state === 'done'
                  ? 'text-oxford/70'
                  : step.state === 'active'
                    ? 'text-oxford'
                    : 'text-oxford/30'
              }`}
            >
              {step.label}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function QuietLink({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-mono text-[11px] uppercase tracking-[0.12em] text-oxford/35 transition-colors hover:text-oxford/60 btn-interaction"
    >
      {children}
    </button>
  );
}

/**
 * ⌘K dispatch — full-screen takeover styled to match AgentLogoutModal.
 * Single tracked lookup, always resumable: reopening returns to its live state
 * (progress or result). "Look up another" backgrounds the current one (it keeps
 * running server-side and lands in the queue) and resets the compose view.
 */
export default function DispatchCommandBar({
  open,
  onClose,
  input,
  setInput,
  onSubmit,
  onCancel,
  isBusy,
  message,
  progress,
  result,
  chips = [],
  onFocusChip,
}: DispatchCommandBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // aria-modal dialog → keep Tab focus inside the takeover (matches the memo modal
  // and judgements panel). The compose view's own autofocus effect runs after and
  // moves focus to the input.
  useFocusTrap(open, containerRef);
  // Local override: "Look up another" shows the compose view even while a prior
  // lookup is still tracked. Reset whenever the takeover closes.
  const [compose, setCompose] = useState(false);
  useEffect(() => {
    if (!open) setCompose(false);
  }, [open]);

  const view: 'result' | 'progress' | 'compose' = compose
    ? 'compose'
    : result
      ? 'result'
      : progress
        ? 'progress'
        : 'compose';

  // Esc always closes — a running lookup keeps going in the background.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Autofocus the input whenever the compose view is showing.
  useEffect(() => {
    if (!open || view !== 'compose') return;
    const id = window.setTimeout(() => {
      containerRef.current?.querySelector('input')?.focus();
    }, 30);
    return () => window.clearTimeout(id);
  }, [open, view]);

  const handleSubmit = () => {
    onSubmit();
    setCompose(false); // surface the new lookup's progress
  };

  const eyebrow = view === 'result' ? 'Dispatch Complete' : view === 'progress' ? 'Analyzing' : 'Dispatch';
  const title =
    view === 'result'
      ? 'Here’s what we found'
      : view === 'progress'
        ? progress!.name || progress!.query
        : 'Look up a company';
  const bottomLabel =
    view === 'result' ? 'Close · Esc' : view === 'progress' ? 'Continue in background →' : 'Cancel · Esc';
  // Show the stack when there's more than one, or in compose (so you keep context
  // of the lookup you're stepping away from).
  const showChips = chips.length >= 2 || (view === 'compose' && chips.length >= 1);

  const modal = (
    <AnimatePresence>
      {open && (
        <motion.div
          key="dispatch-takeover"
          ref={containerRef}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit="exit"
          variants={{
            exit: {
              opacity: 0,
              transition: {
                duration: 0.18,
                ease: EASE,
                delay: 0.14,
                staggerChildren: DISPATCH_EXIT_STAGGER,
                staggerDirection: -1,
                when: 'afterChildren',
              },
            },
          }}
          transition={{ duration: 0.4, ease: EASE }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center p-phi-6 bg-paper"
          role="dialog"
          aria-modal="true"
          aria-label="Look up a company"
        >
          {showChips ? (
            <motion.div
              variants={DISPATCH_EXIT_PIECE}
              custom={dispatchExitCustom(-6, 0.3, 0)}
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, ease: EASE }}
              className="mb-phi-7 flex flex-wrap items-center justify-center gap-phi-2"
              aria-label="Tracked lookups"
            >
              {chips.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => {
                    onFocusChip?.(c.id);
                    setCompose(false);
                  }}
                  aria-pressed={c.active}
                  className={`inline-flex items-center gap-phi-2 border px-phi-3 py-phi-1 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors btn-interaction ${
                    c.active
                      ? 'border-oxford/30 bg-oxford/[0.06] text-oxford'
                      : 'border-oxford/12 text-oxford/45 hover:border-oxford/25 hover:text-oxford/70'
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-none ${
                      c.status === 'decided'
                        ? 'bg-oxford'
                        : c.status === 'reviewing'
                          ? 'bg-oxford signal-dot-breathe'
                          : 'bg-oxford/30 signal-dot-breathe'
                    }`}
                    aria-hidden
                  />
                  <span className="max-w-[14ch] truncate">{c.label}</span>
                  {c.status === 'decided' ? <span className="text-oxford/40" aria-hidden>✓</span> : null}
                </button>
              ))}
            </motion.div>
          ) : null}

          <motion.div
            key={view}
            variants={DISPATCH_EXIT_ORCHESTRATOR}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit="exit"
            transition={{ duration: 0.26, ease: EASE }}
            className="flex w-full flex-col items-center"
          >
              <motion.p
                variants={DISPATCH_EXIT_PIECE}
                custom={dispatchExitCustom(10, 0.45, 0.05)}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, ease: EASE, delay: 0.05 }}
                className="type-meta uppercase tracking-[0.16em] text-oxford/40 mb-phi-3"
              >
                {eyebrow}
              </motion.p>

              <motion.h1
                variants={DISPATCH_EXIT_PIECE}
                custom={dispatchExitCustom(12, 0.5, 0.1)}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
                className={`type-display text-center text-[clamp(28px,4vw,52px)] font-medium text-oxford leading-[1.1] m-0 ${
                  view === 'result' ? 'max-w-none whitespace-nowrap' : 'max-w-[15ch]'
                }`}
              >
                {title}
              </motion.h1>

              {view === 'result' ? (
                <motion.div
                  variants={DISPATCH_EXIT_PIECE}
                  custom={dispatchExitCustom(10, 0.45, 0.16)}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.16 }}
                  className="mt-phi-6 flex w-full max-w-xl flex-col items-center gap-phi-4"
                >
                  {result}
                  <QuietLink onClick={() => setCompose(true)}>+ Look up another</QuietLink>
                </motion.div>
              ) : view === 'progress' ? (
                <motion.div
                  variants={DISPATCH_EXIT_PIECE}
                  custom={dispatchExitCustom(10, 0.45, 0.16)}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.16 }}
                  className="mt-phi-3 flex flex-col items-center gap-phi-5"
                >
                  {progress!.sector ? (
                    <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-oxford/40">
                      {progress!.sector}
                    </p>
                  ) : null}
                  <ProgressSteps progress={progress!} />
                  {message ? (
                    <p className="type-body text-center text-oxford/45 max-w-[40ch]" aria-live="polite">
                      {message}
                    </p>
                  ) : null}
                  <div className="flex items-center justify-center gap-phi-4">
                    <QuietLink onClick={() => setCompose(true)}>+ Look up another</QuietLink>
                    {onCancel ? <QuietLink onClick={onCancel}>Cancel lookup</QuietLink> : null}
                  </div>
                </motion.div>
              ) : (
                <>
                  <motion.p
                    variants={DISPATCH_EXIT_PIECE}
                    custom={dispatchExitCustom(0, 0.5, 0.18)}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
                    className="type-body text-center text-oxford/50 mt-phi-3 mb-phi-8 max-w-[34ch]"
                  >
                    Search any company — evaluated against your active mandate. The result lands in the queue.
                  </motion.p>

                  <motion.div
                    variants={DISPATCH_EXIT_PIECE}
                    custom={dispatchExitCustom(10, 0.45, 0.25)}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.45, ease: EASE, delay: 0.25 }}
                    className="flex w-full max-w-md flex-col items-center gap-phi-4"
                  >
                    <div className="w-full">
                      <AgentDispatch
                        input={input}
                        setInput={setInput}
                        onSubmit={handleSubmit}
                        onCancel={onCancel}
                        isBusy={isBusy}
                        message={null}
                        lookupPhase={null}
                        displayMode="embedded"
                      />
                    </div>
                  </motion.div>
                </>
              )}
          </motion.div>

          <motion.button
            variants={DISPATCH_EXIT_PIECE}
            custom={dispatchExitCustom(10, 0.45, 0.32)}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: EASE, delay: 0.32 }}
            type="button"
            onClick={onClose}
            className="mt-phi-7 type-meta uppercase tracking-[0.12em] text-oxford/30 hover:text-oxford/50 btn-interaction cursor-pointer transition-colors border-b border-oxford/10 pb-0.5"
          >
            {bottomLabel}
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(modal, document.body);
}
