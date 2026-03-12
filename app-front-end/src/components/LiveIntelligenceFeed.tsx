import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import { tokens } from '../design-system/tokens';
import type { Startup, SignalItem, MetaCycleReport } from '../types/startup';

interface LogEntry {
  id: string;
  iso: string;
  timestamp: string;
  message: string;
  kind: 'scanned' | 'reviewed' | 'decision' | 'meta_cycle' | 'signal_detected' | 'escalation_resolved';
}

interface LiveIntelligenceFeedProps {
  startups: Startup[];
  signals?: SignalItem[];
  metaReports?: MetaCycleReport[];
}

/**
 * Judgements log. System issuing judgements — not a feed. Dense, restrained.
 */
export default function LiveIntelligenceFeed({ startups, signals, metaReports }: LiveIntelligenceFeedProps) {
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

    // Signal events
    (signals ?? []).forEach((sig) => {
      if (sig.detected_at) {
        const d = sig.detected_at;
        out.push({
          id: `sig-${sig.id ?? sig.detected_at}`,
          iso: d,
          timestamp: new Date(d).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          message: `Signal · ${sig.description?.slice(0, 60) ?? sig.signal_type}`,
          kind: 'signal_detected',
        });
      }
    });

    // Meta-agent cycle events
    (metaReports ?? []).forEach((r) => {
      if (r.ran_at) {
        const mutCount = r.mutations_applied?.length ?? 0;
        const targets = r.mutations_applied?.map((m) => m.agent_target).join(', ') ?? '';
        out.push({
          id: `meta-${r.cycle_number}`,
          iso: r.ran_at,
          timestamp: new Date(r.ran_at).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          message: mutCount > 0
            ? `Meta-Agent · Cycle ${r.cycle_number} · ${mutCount} mutations (${targets})`
            : `Meta-Agent · Cycle ${r.cycle_number} · System stable`,
          kind: 'meta_cycle',
        });
      }
    });

    // Resolved escalations
    startups.forEach((s) => {
      if (s.human_resolution?.resolved_at) {
        const d = s.human_resolution.resolved_at;
        out.push({
          id: `${s.id}-resolved`,
          iso: d,
          timestamp: new Date(d).toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
          message: `Resolved · ${s.scout.name} · ${s.human_resolution.decision}`,
          kind: 'escalation_resolved',
        });
      }
    });

    out.sort((a, b) => new Date(b.iso).getTime() - new Date(a.iso).getTime());
    setEntries(out);
  }, [startups, signals, metaReports]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-3 sm:p-4 space-y-0">
        <AnimatePresence mode="popLayout">
          {entries.map((e, i) => (
            <motion.div
              key={e.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: tokens.motion.duration.short, delay: i * 0.02, ease: tokens.motion.ease }}
              className="flex items-baseline gap-2 sm:gap-3 py-2 sm:py-2.5 border-b font-mono text-[10px] sm:text-[11px]"
            >
              <span className="shrink-0 tabular-nums text-oxford/60 uppercase tracking-[0.22em]">{e.timestamp}</span>
              <span className="text-oxford/80 min-w-0 truncate">{e.message}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
