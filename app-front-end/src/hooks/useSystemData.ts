import { useState, useEffect, useRef } from 'react';
import { fetchStartups } from '../api/startups';
import { fetchEscalations } from '../api/escalations';
import { fetchSignals } from '../api/signals';
import { fetchRejectionAnalytics, fetchWatchlistAnalytics, fetchConcentrationAnalytics } from '../api/analytics';
import { fetchMetaReports, fetchScoutWeights, fetchCalibrationState } from '../api/meta';
import { fetchSettings } from '../api/settings';
import type {
  Startup, EscalationItem, SignalItem,
  RejectionAnalytics, WatchlistAnalytics, ConcentrationAnalytics,
  MetaCycleReport, ScoutWeights, CalibrationState,
} from '../types/startup';
import type { Settings } from '../api/settings';

const POLL_STARTUPS = 12_000;
const POLL_ESCALATIONS = 30_000;
const POLL_SIGNALS = 60_000;
const POLL_META = 60_000;
const POLL_ANALYTICS = 300_000;
const POLL_SETTINGS = 60_000;

function usePoll<T>(fetcher: () => Promise<T>, interval: number, initial: T): T {
  const [data, setData] = useState<T>(initial);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    let active = true;
    const run = () => {
      fetcherRef.current().then((d) => { if (active) setData(d); }).catch(() => {});
    };
    run();
    const id = setInterval(run, interval);
    return () => { active = false; clearInterval(id); };
  }, [interval]);

  return data;
}

export interface SystemData {
  startups: Startup[];
  escalations: EscalationItem[];
  signals: SignalItem[];
  metaReports: MetaCycleReport[];
  rejectionAnalytics: RejectionAnalytics;
  watchlistAnalytics: WatchlistAnalytics;
  concentrationAnalytics: ConcentrationAnalytics;
  scoutWeights: ScoutWeights;
  calibrationState: CalibrationState;
  settings: Settings | null;
  pendingEscalationCount: number;
}

export function useSystemData(): SystemData {
  const startups = usePoll(fetchStartups, POLL_STARTUPS, []);
  const escalations = usePoll(fetchEscalations, POLL_ESCALATIONS, []);
  const signals = usePoll(fetchSignals, POLL_SIGNALS, []);
  const metaReports = usePoll(fetchMetaReports, POLL_META, []);
  const rejectionAnalytics = usePoll(fetchRejectionAnalytics, POLL_ANALYTICS, {
    most_common_red_flags: [], rejection_by_sector: {}, avg_scores_at_rejection: {}, most_common_fail_dimensions: [],
  });
  const watchlistAnalytics = usePoll(fetchWatchlistAnalytics, POLL_ANALYTICS, { total: 0, stale: 0, avg_days: 0 });
  const concentrationAnalytics = usePoll(fetchConcentrationAnalytics, POLL_ANALYTICS, {
    by_sector: {}, most_concentrated_sector: '', most_concentrated_theme: '', last_updated: '',
  });
  const scoutWeights = usePoll(fetchScoutWeights, POLL_META, {
    MarketDrivenScout: 0.25, BuilderTechnicalScout: 0.25, PainPointScout: 0.25, ContrarianScout: 0.25,
  });
  const calibrationState = usePoll(fetchCalibrationState, POLL_META, {
    confidence_threshold_override: null, reviewer_weak_threshold_override: null,
    reviewer_strong_threshold_override: null, last_calibrated_at: null, last_calibrated_cycle: 0, calibration_history: [],
  });
  const settings = usePoll<Settings | null>(() => fetchSettings().catch(() => null), POLL_SETTINGS, null);

  const pendingEscalationCount = escalations.filter((e) => !e.human_resolution).length;

  return {
    startups, escalations, signals, metaReports,
    rejectionAnalytics, watchlistAnalytics, concentrationAnalytics,
    scoutWeights, calibrationState, settings, pendingEscalationCount,
  };
}
