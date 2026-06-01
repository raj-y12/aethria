import { useEffect, useRef, type ReactNode } from 'react';
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

/**
 * ⌘K dispatch — full-screen takeover styled to match AgentLogoutModal.
 * Three views: input (compose) → progress (live reveal while analyzing) →
 * result overview. Always dismissible: a running lookup continues in the
 * background (result lands in the queue + a ready toast), so the analyst is
 * never trapped waiting.
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
  const running = !!progress && !result;

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

  // Autofocus the input on open (only the compose view renders one).
  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => {
      containerRef.current?.querySelector('input')?.focus();
    }, 30);
    return () => window.clearTimeout(id);
  }, [open]);

  const eyebrow = result ? 'Lookup Complete' : running ? 'Analyzing' : 'Dispatch';
  const title = result
    ? 'Here’s what we found'
    : running
      ? progress!.name || progress!.query
      : 'Look up a company';
  const bottomLabel = result ? 'Close · Esc' : running ? 'Continue in background →' : 'Cancel · Esc';

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
            className="type-display text-center text-[clamp(28px,4vw,52px)] font-medium text-oxford leading-[1.1] m-0 max-w-[15ch]"
          >
            {title}
          </motion.h1>

          {result ? (
            <motion.div
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0px)' }}
              transition={{ duration: 0.45, ease: EASE, delay: 0.16 }}
              className="mt-phi-6 w-full max-w-lg"
            >
              {result}
            </motion.div>
          ) : running ? (
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
                className="w-full max-w-md"
              >
                <AgentDispatch
                  input={input}
                  setInput={setInput}
                  onSubmit={onSubmit}
                  onCancel={onCancel}
                  isBusy={isBusy}
                  message={message}
                  onClearMessage={onClearMessage}
                  lookupPhase={lookupPhase}
                  displayMode="embedded"
                />
              </motion.div>
            </>
          )}

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
