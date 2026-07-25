import { useEffect, useId, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { usePrefersReducedMotion } from '../hooks';

export type SettingsActionDialogProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  /** Short kicker above the title, matching the log-out takeover. */
  eyebrow?: string;
  busy?: boolean;
  /** Accepted for call-site compatibility; the takeover keeps one visual language. */
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
  eyebrow = 'Confirm',
  busy = false,
  onCancel,
  onConfirm,
}: SettingsActionDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();

  const cancelLabel = confirmLabel === 'Discard and leave' ? 'Keep editing' : 'Cancel';

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
          ref={dialogRef}
          key="settings-action-takeover"
          role="dialog"
          tabIndex={-1}
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
          className="paper-dot-grid fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-paper p-phi-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.4, ease: EASE }}
        >
          <motion.p
            initial={reduceMotion ? false : { opacity: 0, transform: 'translateY(10px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.45, ease: EASE, delay: 0.05 }}
            className="type-label-section mb-phi-3"
          >
            {eyebrow}
          </motion.p>
          <motion.h1
            id={titleId}
            initial={reduceMotion ? false : { opacity: 0, transform: 'translateY(12px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
            className="m-0 max-w-[18ch] text-center type-display text-[clamp(28px,4vw,52px)] font-medium leading-[1.1] text-oxford"
          >
            {title}
          </motion.h1>
          <motion.p
            id={descriptionId}
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
            className="mb-phi-8 mt-phi-3 max-w-[42ch] text-center type-body text-oxford/60"
          >
            {description}
          </motion.p>

          {/* DOM order is Cancel then Confirm (safe first focus + focus-trap order);
              flex-col-reverse paints the primary on top, like the log-out modal. */}
          <div className="flex w-full max-w-sm flex-col-reverse items-center gap-phi-4">
            <motion.button
              type="button"
              onClick={onCancel}
              disabled={busy}
              initial={reduceMotion ? false : { opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0px)' }}
              transition={{ duration: 0.45, ease: EASE, delay: 0.32 }}
              className="type-action mt-phi-2 border-b border-oxford/10 pb-0.5 transition-colors hover:text-oxford btn-interaction disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
            >
              {cancelLabel}
            </motion.button>
            <motion.button
              type="button"
              onClick={onConfirm}
              disabled={busy}
              initial={reduceMotion ? false : { opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0px)' }}
              transition={{ duration: 0.45, ease: EASE, delay: 0.25 }}
              className="w-full btn-aethria-solid disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? 'Working…' : confirmLabel}
            </motion.button>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
