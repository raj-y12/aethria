import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import IdentityReviewQueue from './IdentityReviewQueue';
import { transitionOrReduced } from '../../design-system/motion';
import { usePrefersReducedMotion } from '../../hooks';
import { useFocusTrap } from '../../hooks/useFocusTrap';

export default function IdentityReviewCenter() {
  const reduceMotion = usePrefersReducedMotion();
  const [open, setOpen] = useState(false);
  const [linkedJobId, setLinkedJobId] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  useFocusTrap(open, panelRef);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  useEffect(() => {
    const openReview = (event: Event) => {
      const detail = (event as CustomEvent<{ jobId?: string | null }>).detail;
      setLinkedJobId(detail?.jobId ?? null);
      setOpen(true);
    };
    window.addEventListener('aethria:open-identity-review', openReview);
    return () => window.removeEventListener('aethria:open-identity-review', openReview);
  }, []);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="identity-review-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[80] flex justify-end bg-oxford/20 backdrop-blur-[2px]"
          role="dialog"
          aria-modal="true"
          aria-label="Identity review center"
        >
          <motion.div
            initial={{ x: 32 }}
            animate={{ x: 0 }}
            exit={{ x: 32 }}
            transition={transitionOrReduced(reduceMotion, { duration: 0.18 })}
            className="h-full w-full max-w-2xl overflow-y-auto bg-paper"
            ref={panelRef}
          >
            <IdentityReviewQueue onClose={() => setOpen(false)} linkedJobId={linkedJobId} />
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
