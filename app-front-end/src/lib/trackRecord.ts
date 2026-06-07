/**
 * Track record — the fund's own decision history, surfaced at the point of
 * decision so a verdict is read against the system's calibrated behaviour, not
 * in a vacuum. Everything here is computed from data the pipeline already
 * persists (per-deal partner recommendations, human rulings, calibration
 * state). No fabricated hit-rates: we report what the book actually contains.
 */
import type { CalibrationState, Startup } from '../types/startup';
import { isDealHumanResolved } from './dealState';

export interface TrackRecordModel {
  /** Deals with a partner recommendation on the book. */
  decidedCount: number;
  investCount: number;
  monitorCount: number;
  passCount: number;
  /** Deals a human has ruled on (the strongest trust signal we have). */
  humanRuledCount: number;
  /** ISO timestamp of the last meta calibration, if any. */
  calibratedAt: string | null;
  /** Number of completed calibration cycles. */
  calibrationCycle: number;
  /** A live calibration warning worth showing next to a verdict. */
  calibrationWarning: string | null;
}

function recommendationOf(s: Startup): string | null {
  const rec = s.partner?.recommendation;
  return typeof rec === 'string' && rec ? rec.toUpperCase() : null;
}

export function buildTrackRecord(
  peerStartups: Startup[],
  calibration: CalibrationState | null,
  calibrationWarning: string | null = null,
): TrackRecordModel {
  let decidedCount = 0;
  let investCount = 0;
  let monitorCount = 0;
  let passCount = 0;
  let humanRuledCount = 0;

  for (const s of peerStartups) {
    const rec = recommendationOf(s);
    if (rec) {
      decidedCount += 1;
      if (rec === 'INVEST') investCount += 1;
      else if (rec === 'MONITOR') monitorCount += 1;
      else if (rec === 'PASS') passCount += 1;
    }
    if (isDealHumanResolved(s)) humanRuledCount += 1;
  }

  return {
    decidedCount,
    investCount,
    monitorCount,
    passCount,
    humanRuledCount,
    calibratedAt: calibration?.last_calibrated_at ?? null,
    calibrationCycle: calibration?.last_calibrated_cycle ?? 0,
    calibrationWarning,
  };
}

/** Compact "calibrated 12 Mar" style label; null when never calibrated. */
export function calibrationLabel(model: TrackRecordModel): string | null {
  if (!model.calibratedAt) {
    return model.calibrationCycle > 0 ? `calibrated · cycle ${model.calibrationCycle}` : null;
  }
  const d = new Date(model.calibratedAt);
  if (Number.isNaN(d.getTime())) return null;
  const when = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  return `calibrated ${when}`;
}

/** True when there is anything worth rendering. */
export function hasTrackRecord(model: TrackRecordModel): boolean {
  return model.decidedCount > 0 || model.humanRuledCount > 0 || model.calibratedAt != null;
}
