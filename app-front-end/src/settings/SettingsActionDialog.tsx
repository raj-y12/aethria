import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';

export type SettingsActionDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  destructive?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

const EASE = [0.16, 1, 0.3, 1] as const;
const ENABLED_FOCUSABLE =
  'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

export default function SettingsActionDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  destructive = false,
  onCancel,
  onConfirm,
}: SettingsActionDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (open) {
      restoreFocusRef.current = document.activeElement as HTMLElement | null;
      return;
    }
    restoreFocusRef.current?.focus?.();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const frame = requestAnimationFrame(() => {
      const firstEnabled = dialogRef.current?.querySelector<HTMLElement>(ENABLED_FOCUSABLE);
      (firstEnabled ?? dialogRef.current)?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [busy, open]);

  useEffect(() => {
    if (!open) return;
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const enabled = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(ENABLED_FOCUSABLE));
      const first = enabled[0];
      const last = enabled[enabled.length - 1];
      const current = document.activeElement as HTMLElement | null;

      if (!first || !last) {
        event.preventDefault();
        dialogRef.current.focus();
      } else if (!current || !dialogRef.current.contains(current)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && current === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && current === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', trapFocus);
    return () => document.removeEventListener('keydown', trapFocus);
  }, [open]);

  useEffect(() => {
    if (!open || busy) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel, open]);

  if (typeof document === 'undefined') return null;

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          key="settings-action-backdrop"
          className="fixed inset-0 z-[9999] flex items-center justify-center bg-oxford/55 p-phi-5"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.24, ease: EASE }}
        >
          <motion.div
            ref={dialogRef}
            role="dialog"
            tabIndex={-1}
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            className="w-full max-w-[30rem] border border-oxford/15 bg-paper shadow-[0_24px_80px_rgba(26,43,72,0.22)]"
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            transition={{ duration: reduceMotion ? 0 : 0.32, ease: EASE }}
          >
            <div className="border-b border-oxford/[0.08] px-phi-5 py-phi-4">
              <p className="type-label-section text-oxford/55">Dispatch confirmation</p>
              <h2 id={titleId} className="mt-phi-2 type-display text-[1.7rem] leading-tight text-oxford">
                {title}
              </h2>
              <p id={descriptionId} className="mt-phi-3 type-body-sm leading-relaxed text-oxford/65">
                {description}
              </p>
            </div>
            <div className="flex flex-col-reverse gap-phi-2 px-phi-5 py-phi-4 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={onCancel}
                disabled={busy}
                className="type-action inline-flex min-h-11 items-center justify-center px-phi-4 !text-xs text-oxford/65 transition-colors hover:text-oxford disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
              >
                {confirmLabel === 'Discard and leave' ? 'Keep editing' : 'Cancel'}
              </button>
              <button
                type="button"
                onClick={onConfirm}
                disabled={busy}
                className={`inline-flex min-h-11 items-center justify-center px-phi-5 type-action !text-xs transition-colors disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30 ${
                  destructive
                    ? 'bg-escalation text-paper hover:bg-escalation/90'
                    : 'bg-oxford text-paper hover:bg-oxford/90'
                }`}
              >
                {busy ? 'Working…' : confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
