import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import AgentDispatch from './AgentDispatch';

const EASE = [0.16, 1, 0.3, 1] as const;

export interface LookupProgress {
  query: string;
  name: string | null;
  sector: string | null;
  found: boolean;
  reviewed: boolean;
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
  onClearMessage,
  lookupPhase,
  progress,
  result,
}: DispatchCommandBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Local override: "Look up another" shows the compose view even while a prior
  // lookup is still tracked. Reset whenever the takeover closes.
  const [compose, setCompose] = useState(false);
  useEffect(() => {
    if (!open) setCompose(false);
  }, [open]);

  const hasTracked = !!progress || !!result;
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

  const modal = (
    <AnimatePresence>
      {open && (
        <motion.div
          key="dispatch-takeover"
          ref={containerRef}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: EASE }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center p-phi-6 bg-paper"
          role="dialog"
          aria-modal="true"
          aria-label="Look up a company"
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={view}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0, transform: 'translateY(-8px)' }}
              transition={{ duration: 0.26, ease: EASE }}
              className="flex w-full flex-col items-center"
            >
              <motion.p
                initial={{ opacity: 0, transform: 'translateY(10px)' }}
                animate={{ opacity: 1, transform: 'translateY(0px)' }}
                transition={{ duration: 0.45, ease: EASE, delay: 0.05 }}
                className="type-meta uppercase tracking-[0.16em] text-oxford/40 mb-phi-3"
              >
                {eyebrow}
              </motion.p>

              <motion.h1
                initial={{ opacity: 0, transform: 'translateY(12px)' }}
                animate={{ opacity: 1, transform: 'translateY(0px)' }}
                transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
                className={`type-display text-center text-[clamp(28px,4vw,52px)] font-medium text-oxford leading-[1.1] m-0 ${
                  view === 'result' ? 'max-w-none whitespace-nowrap' : 'max-w-[15ch]'
                }`}
              >
                {title}
              </motion.h1>

              {view === 'result' ? (
                <motion.div
                  initial={{ opacity: 0, transform: 'translateY(10px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)' }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.16 }}
                  className="mt-phi-6 flex w-full max-w-lg flex-col items-center gap-phi-4"
                >
                  {result}
                  <QuietLink onClick={() => setCompose(true)}>+ Look up another</QuietLink>
                </motion.div>
              ) : view === 'progress' ? (
                <motion.div
                  initial={{ opacity: 0, transform: 'translateY(10px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)' }}
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
                  <QuietLink onClick={() => setCompose(true)}>+ Look up another</QuietLink>
                </motion.div>
              ) : (
                <>
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
                    className="type-body text-center text-oxford/50 mt-phi-3 mb-phi-8 max-w-[34ch]"
                  >
                    Search any company — evaluated against your active mandate. The result lands in the queue.
                  </motion.p>

                  <motion.div
                    initial={{ opacity: 0, transform: 'translateY(10px)' }}
                    animate={{ opacity: 1, transform: 'translateY(0px)' }}
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
                        message={message}
                        onClearMessage={onClearMessage}
                        lookupPhase={lookupPhase}
                        displayMode="embedded"
                      />
                    </div>
                    {hasTracked ? (
                      <QuietLink onClick={() => setCompose(false)}>← Back to current lookup</QuietLink>
                    ) : null}
                  </motion.div>
                </>
              )}
            </motion.div>
          </AnimatePresence>

          <motion.button
            initial={{ opacity: 0, transform: 'translateY(10px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
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
