import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { tokens } from '../design-system/tokens';

interface SystemBarProps {
  scoutCount?: number;
  /** Override nav link (e.g. { href: '/', label: 'Home' } on Settings page) */
  navLink?: { href: string; label: string };
}

const PROCESS_MESSAGES = [
  'Continuous capital allocation scan',
  'System active — no escalation required',
  'Evaluating inbound intelligence',
] as const;

/**
 * Instrumentation: status, scout count, process signal. Full-width. Restrained.
 */
export default function SystemBar({
  scoutCount = 0,
  navLink,
}: SystemBarProps) {
  const link = navLink ?? { href: '/settings', label: 'Settings' };
  const [status, setStatus] = useState<'Active' | 'Scanning'>('Active');
  const [processIndex, setProcessIndex] = useState(0);

  useEffect(() => {
    const t = setInterval(
      () => setStatus((s) => (s === 'Active' ? 'Scanning' : 'Active')),
      5000
    );
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setProcessIndex((i) => (i + 1) % PROCESS_MESSAGES.length),
      12000
    );
    return () => clearInterval(t);
  }, []);

  return (
    <div className="fixed top-[3.25rem] left-0 right-0 z-50 border-b border-ivory/[0.12] bg-oxford">
      <div className="w-full min-w-0 px-4 xs:px-6 sm:px-8 lg:px-12 py-2 sm:py-2.5 flex flex-wrap items-center justify-between gap-x-4 sm:gap-x-8 gap-y-2">
        <div className="flex items-center gap-3 sm:gap-6 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-sans text-[10px] uppercase tracking-[0.14em] text-ivory/60">
              Status
            </span>
            <span className="font-sans text-[12px] text-ivory">{status}</span>
          </div>
          <span className="w-px h-3.5 bg-ivory/25" aria-hidden />
          <div className="flex items-center gap-2">
            <span className="font-sans text-[10px] uppercase tracking-[0.14em] text-ivory/60">
              Scouts
            </span>
            <span className="font-sans text-[12px] tabular-nums text-ivory">
              {scoutCount}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 sm:gap-6 min-w-0 flex-1 xs:flex-initial justify-end">
          <div className="min-w-0 overflow-hidden max-w-[50vw] sm:max-w-none">
            <AnimatePresence mode="wait">
              <motion.span
                key={processIndex}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: tokens.motion.duration.short, ease: tokens.motion.ease }}
                className="block font-sans text-[11px] text-ivory/70 truncate"
              >
                {PROCESS_MESSAGES[processIndex]}
              </motion.span>
            </AnimatePresence>
          </div>
          <span className="w-px h-3.5 bg-ivory/25 shrink-0" aria-hidden />
          <a
            href={link.href}
            className="font-sans text-[11px] uppercase tracking-[0.12em] text-ivory/70 hover:text-ivory transition-colors duration-300 shrink-0"
          >
            {link.label}
          </a>
        </div>
      </div>
    </div>
  );
}
