/**
 * AgentLogoutModal
 * Shown when the user tries to log out while agents are running.
 * Three options:
 *   1. Keep running  → proceed with logout (agents continue server-side)
 *   2. Turn off agents → disable all agent stages via API → then logout
 *   3. Cancel → close modal
 */
import { useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';

interface AgentLogoutModalProps {
  open: boolean;
  onCancel: () => void;
  /** Proceed with logout; agents keep running in background */
  onKeepRunning: () => void;
  /** Disable agents via API then logout */
  onTurnOffAndLogout: () => Promise<void>;
}

export default function AgentLogoutModal({
  open,
  onCancel,
  onKeepRunning,
  onTurnOffAndLogout,
}: AgentLogoutModalProps) {
  const [busy, setBusy] = useState(false);

  const handleTurnOff = async () => {
    setBusy(true);
    try {
      await onTurnOffAndLogout();
    } finally {
      setBusy(false);
    }
  };

  const modal = (
    <AnimatePresence>
      {open && (
        <motion.div
          key="agent-logout-takeover"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center p-phi-6 bg-paper-bright"
          role="dialog"
          aria-modal="true"
        >
          {/* Eyebrow */}
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.05 }}
            className="type-meta uppercase tracking-[0.16em] text-oxford/40 mb-phi-3"
          >
            System Notification
          </motion.p>

          {/* Title */}
          <motion.h1
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
            className="type-display text-center text-[clamp(28px,4vw,52px)] font-medium text-oxford leading-[1.1] m-0 max-w-[15ch]"
          >
            Your agents are still running
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.18 }}
            className="type-body text-center text-oxford/50 mt-phi-3 mb-phi-8 max-w-[34ch]"
          >
            The background pipeline will persist in the cloud after you log out. You can turn them off now, or leave them running.
          </motion.p>

          {/* Actions — vertical stack, centered */}
          <div className="flex flex-col items-center gap-phi-4 w-full max-w-xs">
            {/* Primary: Keep Running */}
            <motion.button
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.25 }}
              onClick={onKeepRunning}
              disabled={busy}
              className="w-full px-phi-7 py-[14px] bg-oxford text-paper-bright type-meta uppercase tracking-[0.12em] btn-interaction cursor-pointer transition-opacity hover:opacity-80 disabled:opacity-50"
            >
              Continue running & Log out
            </motion.button>

            {/* Secondary: Turn Off */}
            <motion.button
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.32 }}
              onClick={() => void handleTurnOff()}
              disabled={busy}
              className="w-full text-oxford/50 hover:text-oxford type-meta uppercase tracking-[0.12em] btn-interaction cursor-pointer transition-colors disabled:opacity-50"
            >
              {busy ? 'Turning off agents…' : 'Stop agents then log out'}
            </motion.button>

            {/* Cancel */}
            <motion.button
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1], delay: 0.39 }}
              onClick={onCancel}
              disabled={busy}
              className="mt-phi-4 type-meta uppercase tracking-[0.12em] text-oxford/30 hover:text-oxford/50 btn-interaction cursor-pointer transition-colors disabled:opacity-50 border-b border-oxford/10 pb-0.5"
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
