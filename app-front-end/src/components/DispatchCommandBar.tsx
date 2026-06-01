import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import AgentDispatch from './AgentDispatch';

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
 * ⌘K dispatch — full-screen takeover styled to match AgentLogoutModal
 * (eyebrow → display title → subtitle → centered input). Dispatch is an action,
 * not a destination, so it lives behind a keystroke. Reuses AgentDispatch for
 * the input/run/status UI.
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
  const containerRef = useRef<HTMLDivElement>(null);

  // Esc closes (no-op while a lookup is mid-flight so running status isn't lost).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isBusy) {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, isBusy, onClose]);

  // Autofocus the input on open.
  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => {
      containerRef.current?.querySelector('input')?.focus();
    }, 30);
    return () => window.clearTimeout(id);
  }, [open]);

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
            Company Lookup
          </motion.p>

          <motion.h1
            initial={{ opacity: 0, transform: 'translateY(12px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
            className="type-display text-center text-[clamp(28px,4vw,52px)] font-medium text-oxford leading-[1.1] m-0 max-w-[15ch]"
          >
            Look up a company
          </motion.h1>

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

          <motion.button
            initial={{ opacity: 0, transform: 'translateY(10px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.45, ease: EASE, delay: 0.32 }}
            type="button"
            onClick={onClose}
            disabled={isBusy}
            className="mt-phi-7 min-h-[44px] type-meta uppercase tracking-[0.12em] text-oxford/30 hover:text-oxford/50 btn-interaction cursor-pointer transition-colors disabled:opacity-50 border-b border-oxford/10 pb-0.5"
          >
            Cancel · Esc
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(modal, document.body);
}
