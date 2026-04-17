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
        /* Backdrop */
        <motion.div
          key="agent-logout-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-0 z-[200] flex items-center justify-center bg-oxford/60 backdrop-blur-[2px]"
          onClick={onCancel}
          aria-hidden="true"
        >
          {/* Panel — stop propagation so clicks inside don't close */}
          <motion.div
            key="agent-logout-panel"
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.99 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="relative w-full max-w-sm mx-4 bg-paper border border-hairline"
            role="dialog"
            aria-modal="true"
            aria-labelledby="agent-logout-title"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header stripe */}
            <div className="border-b border-hairline px-phi-5 py-phi-3 flex items-center justify-between">
              <p
                id="agent-logout-title"
                className="type-label-section text-oxford/80 uppercase tracking-[0.12em]"
              >
                Agents are still running
              </p>
              <button
                type="button"
                onClick={onCancel}
                className="type-meta uppercase tracking-[0.12em] text-oxford/40 hover:text-oxford btn-interaction focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35"
                aria-label="Cancel and close"
              >
                ✕
              </button>
            </div>

            {/* Body */}
            <div className="px-phi-5 py-phi-5 flex flex-col gap-phi-4">
              {/* Live indicator */}
              <div className="flex items-center gap-phi-2">
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-none bg-oxford/70"
                  style={{ animation: 'aethria-pulse 2.4s cubic-bezier(0.16,1,0.3,1) infinite' }}
                  aria-hidden
                />
                <p className="type-meta uppercase tracking-[0.12em] text-oxford/50">
                  Pipeline active
                </p>
              </div>

              <p className="type-body-sm leading-phi text-oxford/60 max-w-[34ch]">
                Your agents will continue running in the background after you log out. You can turn
                them off now, or leave them running and log out.
              </p>

              {/* Action buttons */}
              <div className="flex flex-col gap-phi-2 pt-phi-2 border-t border-hairline">
                {/* Primary: Keep running */}
                <button
                  id="agent-logout-keep"
                  type="button"
                  onClick={onKeepRunning}
                  disabled={busy}
                  className="w-full min-h-[40px] flex items-center justify-between px-phi-4 py-phi-2 bg-oxford text-paper type-meta uppercase tracking-[0.12em] btn-interaction hover:bg-oxford/90 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-offset-2 focus-visible:ring-offset-paper transition-colors"
                >
                  <span>Keep running</span>
                  <span className="text-paper/50 text-[10px]">Agents stay on</span>
                </button>

                {/* Secondary: Turn off + logout */}
                <button
                  id="agent-logout-turnoff"
                  type="button"
                  onClick={() => void handleTurnOff()}
                  disabled={busy}
                  className="w-full min-h-[40px] flex items-center justify-between px-phi-4 py-phi-2 border border-oxford/30 text-oxford type-meta uppercase tracking-[0.12em] btn-interaction hover:border-oxford/60 hover:bg-oxford/[0.03] disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 focus-visible:ring-offset-2 focus-visible:ring-offset-paper transition-colors"
                >
                  <span>{busy ? 'Turning off…' : 'Turn off agents'}</span>
                  <span className="text-oxford/40 text-[10px]">Then log out</span>
                </button>

                {/* Tertiary: Cancel */}
                <button
                  id="agent-logout-cancel"
                  type="button"
                  onClick={onCancel}
                  disabled={busy}
                  className="w-full min-h-[36px] flex items-center justify-center px-phi-4 py-phi-2 text-oxford/40 type-meta uppercase tracking-[0.12em] btn-interaction hover:text-oxford/70 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );

  if (typeof document === 'undefined') return null;
  return createPortal(modal, document.body);
}
