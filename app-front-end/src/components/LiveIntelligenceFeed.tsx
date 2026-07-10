import { motion, AnimatePresence } from 'framer-motion';
import { useEffect, useState } from 'react';
import { tokens } from '../design-system/tokens';
import { transitionOrReduced } from '../design-system/motion';
import { usePrefersReducedMotion } from '../hooks';
import type { Startup, SignalItem, MetaCycleReport } from '../types/startup';
import { formatReviewOverallStructuredScore } from '../lib/reviewScoring';
import SignalEventRow from './SignalEventRow';
import EmptyState from './EmptyState';
import { UI_JUDGEMENTS_SUBTITLE } from '../design-system/ui-text';

/** One stamp per entry — date + time, no seconds, no second timestamp line. */
function feedStamp(iso: string): string {
  const d = new Date(iso);
  const day = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
  const time = d.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' });
  return `${day} · ${time}`;
}

interface LogEntry {
  id: string;
  iso: string;
  timestamp: string;
  message: string;
  kind: 'scanned' | 'reviewed' | 'decision' | 'meta_cycle' | 'signal_detected' | 'escalation_resolved';
  decision?: string; // INVEST | PASS | MONITOR — for kind 'decision'
}

function logProvenanceLabel(kind: LogEntry['kind']): string {
  switch (kind) {
    case 'scanned':
      return 'Scout queue';
    case 'reviewed':
      return 'Reviewer synthesis';
    case 'decision':
      return 'Partner verdict';
    case 'meta_cycle':
      return 'Meta-Agent cycle';
    case 'signal_detected':
      return 'Portfolio signal';
    case 'escalation_resolved':
      return 'Human resolution';
    default:
      return 'System';
  }
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
  const reduceMotion = usePrefersReducedMotion();
  const [entries, setEntries] = useState<LogEntry[]>([]);

  useEffect(() => {
    const out: LogEntry[] = [];
    startups.forEach((s) => {
      if (s.timestamps?.discovered_at) {
        const d = s.timestamps.discovered_at;
        out.push({
          id: `${s.id}-scan`,
          iso: d,
          timestamp: feedStamp(d),
          message: `${s.scout.name} · ${s.scout.sector || '—'} · ${((s.scout.confidence ?? 0) * 100).toFixed(0)}%`,
          kind: 'scanned',
        });
      }
      if (s.timestamps?.reviewed_at) {
        const d = s.timestamps.reviewed_at;
        const overall = formatReviewOverallStructuredScore(s.review);
        out.push({
          id: `${s.id}-review`,
          iso: d,
          timestamp: feedStamp(d),
          message: `${s.scout.name} · Score ${overall}/10`,
          kind: 'reviewed',
        });
      }
      if (s.timestamps?.partnered_at && s.partner?.recommendation) {
        const d = s.timestamps.partnered_at;
        out.push({
          id: `${s.id}-dec`,
          iso: d,
          timestamp: feedStamp(d),
          message: s.scout.name,
          kind: 'decision',
          decision: s.partner.recommendation,
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
          timestamp: feedStamp(d),
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
          timestamp: feedStamp(r.ran_at),
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
          timestamp: feedStamp(d),
          message: `Resolved · ${s.scout.name} · ${s.human_resolution.decision}`,
          kind: 'escalation_resolved',
        });
      }
    });

    out.sort((a, b) => new Date(b.iso).getTime() - new Date(a.iso).getTime());
    setEntries(out);
  }, [startups, signals, metaReports]);

  if (entries.length === 0) {
    return (
      <div className="h-full overflow-y-auto flex flex-col">
        <EmptyState
          label="Judgements"
          body={`${UI_JUDGEMENTS_SUBTITLE} Stream fills as the pipeline runs.`}
        />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="space-y-0 px-phi-4 py-phi-5 sm:px-phi-5 bg-surface-canvas">
        <AnimatePresence mode="popLayout">
          {entries.map((e, i) => (
            <motion.div
              key={e.id}
              initial={reduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={transitionOrReduced(reduceMotion, {
                duration: tokens.motion.duration.short,
                delay: reduceMotion ? 0 : i * 0.025,
                ease: tokens.motion.ease,
              })}
              className={i > 0 ? 'border-t border-oxford/[0.05]' : ''}
            >
              <SignalEventRow
                layout="stacked"
                timestamp={e.timestamp}
                label={logProvenanceLabel(e.kind)}
                body={
                  e.kind === 'decision' && e.decision ? (
                    <>
                      {e.message}
                      {/* Verdict inline with its subject — never floated to the panel edge. */}
                      <span className="type-status text-oxford/80">
                        {' '}· {e.decision}
                      </span>
                    </>
                  ) : (
                    e.message
                  )
                }
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
