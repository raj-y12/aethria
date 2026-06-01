import { useEffect, useRef } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import AgentDispatch from './AgentDispatch';
import { usePrefersReducedMotion } from '../hooks';

const EASE = [0.16, 1, 0.3, 1] as const;

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
}

/**
 * ⌘K command bar for on-demand lookup. Dispatch is an action, not a destination —
 * so it lives behind a keystroke and a centered overlay rather than an always-on
 * rail input. Reuses AgentDispatch (embedded) for the input/run/status UI.
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
}: DispatchCommandBarProps) {
  const reduceMotion = usePrefersReducedMotion();
  const cardRef = useRef<HTMLDivElement>(null);

  // Esc closes (unless a lookup is mid-flight, where Esc should be a no-op so the
  // user doesn't accidentally lose the running status).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isBusy) {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, isBusy, onClose]);

  // Autofocus the input when the bar opens.
  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => {
      cardRef.current?.querySelector('input')?.focus();
    }, 20);
    return () => window.clearTimeout(id);
  }, [open]);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[120] flex items-start justify-center px-phi-4 pt-[14vh]"
          initial={reduceMotion ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reduceMotion ? { opacity: 0 } : { opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.16, ease: EASE }}
        >
          <div
            className="absolute inset-0 bg-oxford/35 backdrop-blur-[2px]"
            aria-hidden
            onClick={() => {
              if (!isBusy) onClose();
            }}
          />
          <motion.div
            ref={cardRef}
            role="dialog"
            aria-modal="true"
            aria-label="Look up a company"
            className="relative w-full max-w-[560px] border border-oxford/15 bg-paper px-phi-5 py-phi-4 shadow-[0_24px_60px_-20px_rgba(0,20,51,0.35)]"
            initial={reduceMotion ? false : { opacity: 0, y: -10, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.99 }}
            transition={{ duration: reduceMotion ? 0 : 0.2, ease: EASE }}
          >
            <div className="mb-phi-2 flex items-baseline justify-between">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-oxford/40">
                Look up a company
              </p>
              <kbd className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/30">Esc</kbd>
            </div>
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
            <p className="mt-phi-3 font-mono text-[10px] tracking-[0.04em] text-oxford/30">
              Searches any company — evaluated against your active mandate. Result lands in the queue.
            </p>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
