import type { ReactNode } from 'react';
import { buildTrackRecord, calibrationLabel, hasTrackRecord } from '../../lib/trackRecord';
import type { CalibrationState, Startup } from '../../types/startup';

interface MemoTrackRecordProps {
  peerStartups: Startup[];
  calibrationState?: CalibrationState | null;
  calibrationWarning?: string | null;
  renderWithMonoNumbers: (value: unknown) => ReactNode;
}

/**
 * Track-record strip on the memo cover. Reads a single verdict against the
 * fund's actual decision history and the system's calibration state — the
 * institutional question of "should I trust this call?" answered with the
 * book's own numbers rather than a confident-sounding paragraph.
 */
export default function MemoTrackRecord({
  peerStartups,
  calibrationState,
  calibrationWarning,
  renderWithMonoNumbers,
}: MemoTrackRecordProps) {
  const model = buildTrackRecord(peerStartups, calibrationState ?? null, calibrationWarning ?? null);
  if (!hasTrackRecord(model)) return null;

  const bits: string[] = [];
  if (model.decidedCount > 0) {
    bits.push(`${model.investCount}/${model.decidedCount} INVEST calls`);
  }
  if (model.humanRuledCount > 0) {
    bits.push(`${model.humanRuledCount} human-ruled`);
  }
  const cal = calibrationLabel(model);
  if (cal) bits.push(cal);

  if (bits.length === 0) return null;

  return (
    <div className="memoTrackRecord" role="note" aria-label="Fund decision track record">
      <span className="memoTrackRecordLabel">Track record</span>
      <span className="memoTrackRecordLine">{renderWithMonoNumbers(bits.join('   ·   '))}</span>
      {model.calibrationWarning ? (
        <span className="memoTrackRecordWarn">{renderWithMonoNumbers(model.calibrationWarning)}</span>
      ) : null}
    </div>
  );
}
