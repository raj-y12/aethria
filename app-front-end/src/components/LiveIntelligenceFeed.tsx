import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import { tokens } from '../design-system/tokens';
import type { Startup } from '../types/startup';

interface LogEntry {
  id: string;
  iso: string;
  timestamp: string;
  message: string;
  kind: 'scanned' | 'reviewed' | 'decision';
}

interface LiveIntelligenceFeedProps {
  startups: Startup[];
}

/**
 * Judgements log. System issuing judgements — not a feed. Dense, restrained.
 */
export default function LiveIntelligenceFeed({ startups }: LiveIntelligenceFeedProps) {
  const [entries, setEntries] = useState<LogEntry[]>([]);

  useEffect(() => {
    const out: LogEntry[] = [];
    startups.forEach((s) => {
      if (s.timestamps?.discovered_at) {
        const d = s.timestamps.discovered_at;
        out.push({
          id: `${s.id}-scan`,
          iso: d,
          timestamp: new Date(d).toLocaleTimeString('en-GB', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          }),
          message: `${s.scout.name} · ${s.scout.sector || '—'} · ${((s.scout.confidence ?? 0) * 100).toFixed(0)}%`,
          kind: 'scanned',
        });
      }
      if (s.timestamps?.reviewed_at) {
        const d = s.timestamps.reviewed_at;
        out.push({
          id: `${s.id}-review`,
          iso: d,
          timestamp: new Date(d).toLocaleTimeString('en-GB', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          }),
          message: `${s.scout.name} · M${s.review?.market_score ?? '—'}/T${s.review?.technical_score ?? '—'}`,
          kind: 'reviewed',
        });
      }
      if (s.timestamps?.partnered_at && s.partner?.decision) {
        const d = s.timestamps.partnered_at;
        out.push({
          id: `${s.id}-dec`,
          iso: d,
          timestamp: new Date(d).toLocaleTimeString('en-GB', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          }),
          message: `${s.scout.name} · ${s.partner.decision}`,
          kind: 'decision',
        });
      }
    });
    out.sort((a, b) => new Date(b.iso).getTime() - new Date(a.iso).getTime());
    setEntries(out);
  }, [startups]);

  return (
    <div className="h-full overflow-y-auto no-scrollbar">
      <div className="p-3 sm:p-4 space-y-0">
        <AnimatePresence mode="popLayout">
          {entries.map((e, i) => (
            <motion.div
              key={e.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: tokens.motion.duration.short, delay: i * 0.02, ease: tokens.motion.ease }}
              className="flex items-baseline gap-2 sm:gap-3 py-2 sm:py-2.5 border-b border-oxford/[0.06] font-sans text-[11px] sm:text-[12px]"
            >
              <span className="shrink-0 tabular-nums text-charcoal/50">{e.timestamp}</span>
              <span className="text-charcoal min-w-0 truncate">{e.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
