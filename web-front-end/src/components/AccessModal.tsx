import { useEffect, useRef } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import AccessForm from './AccessForm';

const EASE: [number, number, number, number] = [0.16, 1, 0.3, 1];
const FOCUSABLE = 'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Full-screen request-access panel, opened from the frame nav on routes that
 * carry no access plate of their own. The form is the same one the home
 * gallery closes on — this is a second door to it, not a second form.
 */
export default function AccessModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const reduce = useReducedMotion();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    returnFocusRef.current = document.activeElement as HTMLElement | null;

    // Lenis owns the scroll, so stopping it is what actually locks the page.
    const lenis = (window as unknown as { __lenis?: { stop: () => void; start: () => void } }).__lenis;
    lenis?.stop();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      // Keep tabbing inside the panel while it owns the screen.
      const items = panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!items || items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = prevOverflow;
      lenis?.start();
      returnFocusRef.current?.focus();
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="access-modal-title"
          // Wipe with clip-path, not transform: a transformed ancestor would make
          // the fixed close button resolve against the panel and ride up with it.
          initial={reduce ? { opacity: 0 } : { clipPath: 'inset(100% 0 0 0)' }}
          animate={reduce ? { opacity: 1 } : { clipPath: 'inset(0% 0 0 0)' }}
          exit={reduce ? { opacity: 0 } : { clipPath: 'inset(100% 0 0 0)' }}
          transition={{ duration: reduce ? 0.2 : 0.55, ease: EASE }}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 60,
            backgroundColor: 'var(--color-oxford)',
            overflowY: 'auto',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 'clamp(1.5rem, 5vw, 3rem)',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            aria-label="Close request access"
            style={{
              position: 'fixed',
              top: 'clamp(1.25rem, 3vw, 2rem)',
              right: 'clamp(1.25rem, 3vw, 2rem)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              color: 'var(--stock)',
              opacity: 0.65,
              padding: '0.75rem',
            }}
          >
            Close
          </button>

          <div style={{ width: '100%', maxWidth: '720px' }}>
            <h2
              id="access-modal-title"
              className="hero-statement"
              style={{
                color: 'var(--stock)',
                fontSize: 'clamp(1.8rem, 4vw, 3.2rem)',
                textAlign: 'center',
                marginBottom: '2.5rem',
              }}
            >
              For funds that need judgment with memory.
            </h2>
            <AccessForm />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
