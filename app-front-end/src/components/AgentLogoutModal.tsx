/**
 * AgentLogoutModal
 * Shown when the user tries to log out.
 *
 * Agents ON variant (three options):
 *   1. Keep running  → proceed with logout (agents continue server-side)
 *   2. Turn off agents → disable all agent stages via API → then logout
 *   3. Cancel → close modal
 *
 * Agents OFF variant (three options):
 *   1. Log out → proceed with logout
 *   2. Turn on agents → enable agents via API, then logout
 *   3. Cancel → close modal
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useFocusTrap, usePrefersReducedMotion } from '../hooks';
import { tokens } from '../design-system/tokens';

const EASE = tokens.motion.ease;

interface AgentLogoutModalProps {
  open: boolean;
  agentsEnabled: boolean;
  onCancel: () => void;
  /** Proceed with logout; agents keep running in background */
  onKeepRunning: () => void;
  /** Disable agents via API then logout */
  onTurnOffAndLogout: () => Promise<void>;
  /** Enable agents via API, then logout */
  onTurnOnAndLogout: () => Promise<void>;
}

export default function AgentLogoutModal({
  open,
  agentsEnabled,
  onCancel,
  onKeepRunning,
  onTurnOffAndLogout,
  onTurnOnAndLogout,
}: AgentLogoutModalProps) {
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const reduceMotion = usePrefersReducedMotion();
  useFocusTrap(open, containerRef);

  useEffect(() => {
    if (open) {
      restoreFocusRef.current = document.activeElement as HTMLElement | null;
      return;
    }
    restoreFocusRef.current?.focus?.();
  }, [open]);

  const handleTurnOff = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await onTurnOffAndLogout();
    } catch {
      setActionError('Unable to update agent state right now. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const handleTurnOn = async () => {
    setBusy(true);
    setActionError(null);
    try {
      await onTurnOnAndLogout();
    } catch {
      setActionError('Unable to update agent state right now. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!open || busy) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [busy, onCancel, open]);

  const modal = (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={containerRef}
          key="agent-logout-takeover"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduceMotion ? 0 : 0.4, ease: EASE }}
          className="aethria-atmosphere fixed inset-0 z-[9999] flex flex-col items-center justify-center overflow-hidden p-phi-6 bg-paper"
          role="dialog"
          aria-modal="true"
          aria-labelledby="agent-logout-title"
        >
          {/* The same atmosphere as sign-in and Home. */}
          <div className="grain" aria-hidden />
          <div className="grain" aria-hidden />

          {/* Eyebrow */}
          <motion.p
            initial={{ opacity: 0, transform: 'translateY(10px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.45, ease: EASE, delay: 0.05 }}
            className="type-label-section mb-phi-3"
          >
            System Notification
          </motion.p>

          {/* Title */}
          <motion.h1
            id="agent-logout-title"
            initial={{ opacity: 0, transform: 'translateY(12px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.1 }}
            className="type-display text-center text-[clamp(28px,4vw,52px)] font-medium text-oxford leading-[1.1] m-0 max-w-[15ch]"
          >
            {agentsEnabled ? 'Pipeline is live' : 'Pipeline is offline'}
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, ease: EASE, delay: 0.18 }}
            className="type-body text-center text-oxford/65 mt-phi-3 mb-phi-8 max-w-[34ch]"
          >
            {agentsEnabled
              ? 'The pipeline can keep reviewing deals after you log out. Leave it running, or pause it first.'
              : 'The pipeline is paused. You can log out now or restart it before leaving.'}
          </motion.p>

          {/* Actions — vertical stack, centered */}
          <div className="flex flex-col items-center gap-phi-4 w-full max-w-sm">
            {actionError ? (
              <p
                className="type-meta text-center text-oxford/70 border border-oxford/15 px-3 py-2 w-full"
                role="status"
                aria-live="polite"
              >
                {actionError}
              </p>
            ) : null}
            {agentsEnabled ? (
              <>
                {/* Primary: Keep Running */}
                <motion.span
                  initial={{ opacity: 0, transform: 'translateY(10px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)' }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.25 }}
                  className="aethria-cta-frame"
                >
                  <button type="button" onClick={onKeepRunning} disabled={busy} className="aethria-cta type-action">
                    Keep pipeline running
                  </button>
                </motion.span>

                {/* Secondary: Turn Off */}
                <motion.button
                  initial={{ opacity: 0, transform: 'translateY(10px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)' }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.32 }}
                  onClick={() => void handleTurnOff()}
                  disabled={busy}
                  className="type-action w-full min-h-[44px] hover:text-oxford btn-interaction transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {busy ? 'Pausing pipeline...' : 'Pause pipeline and log out'}
                </motion.button>
              </>
            ) : (
              <>
                {/* Primary: Log out */}
                <motion.span
                  initial={{ opacity: 0, transform: 'translateY(10px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)' }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.25 }}
                  className="aethria-cta-frame"
                >
                  <button type="button" onClick={onKeepRunning} disabled={busy} className="aethria-cta type-action">
                    Log out
                  </button>
                </motion.span>

                {/* Secondary: Turn on agents and log out */}
                <motion.button
                  initial={{ opacity: 0, transform: 'translateY(10px)' }}
                  animate={{ opacity: 1, transform: 'translateY(0px)' }}
                  transition={{ duration: 0.45, ease: EASE, delay: 0.32 }}
                  onClick={() => void handleTurnOn()}
                  disabled={busy}
                  className="type-action w-full min-h-[44px] hover:text-oxford btn-interaction transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {busy ? 'Starting pipeline...' : 'Start pipeline and log out'}
                </motion.button>
              </>
            )}

            {/* Cancel */}
            <motion.button
              initial={{ opacity: 0, transform: 'translateY(10px)' }}
              animate={{ opacity: 1, transform: 'translateY(0px)' }}
              transition={{ duration: 0.45, ease: EASE, delay: 0.39 }}
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="type-action mt-phi-2 hover:text-oxford btn-interaction cursor-pointer transition-colors disabled:cursor-not-allowed disabled:opacity-40 border-b border-oxford/10 pb-0.5"
            >
              Cancel
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(modal, document.body);
}
