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
const STARTUPS_DELAY = 0;
const ESCALATIONS_DELAY = 1_200;
const SIGNALS_DELAY = 2_400;
const META_REPORTS_DELAY = 3_600;
const ANALYTICS_REJECTION_DELAY = 4_800;
const ANALYTICS_WATCHLIST_DELAY = 6_000;
const ANALYTICS_CONCENTRATION_DELAY = 7_200;
const SCOUT_WEIGHTS_DELAY = 8_400;
const CALIBRATION_DELAY = 9_600;
const SETTINGS_DELAY = 10_800;
const POLL_STARTUPS_FAST = 4_000;
const POLL_META_SLOW = 180_000;
const POLL_ANALYTICS_SLOW = 900_000;

function usePoll<T>(
  fetcher: () => Promise<T>,
  interval: number,
  initial: T,
  initialDelayMs = 0,
  enabled = true,
  /** Increment to run an immediate fetch (e.g. System panel opened). */
  refreshKey = 0
): T {
  const [data, setData] = useState<T>(initial);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const refreshKeyRef = useRef(refreshKey);

  useEffect(() => {
    if (!enabled) return;

    let active = true;
    let inFlight = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const run = () => {
      if (!active || inFlight) return;
      inFlight = true;
      fetcherRef.current()
        .then((d) => {
          if (active) setData(d);
        })
        .catch(() => {})
        .finally(() => {
          inFlight = false;
        });
    };
    if (initialDelayMs > 0) {
      timeoutId = setTimeout(run, initialDelayMs);
    } else {
      run();
    }
    const id = setInterval(run, interval);
    return () => {
      active = false;
      clearInterval(id);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [interval, initialDelayMs, enabled]);

  useEffect(() => {
    if (!enabled) return;
    if (refreshKeyRef.current === refreshKey) return;
    refreshKeyRef.current = refreshKey;
    if (refreshKey === 0) return;

    let cancelled = false;
    fetcherRef.current()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [refreshKey, enabled]);

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

export interface UseSystemDataOptions {
  systemPanelOpen?: boolean;
  lookupActive?: boolean;
}

export function useSystemData(options: UseSystemDataOptions = {}): SystemData {
  const { systemPanelOpen = false, lookupActive = false } = options;
  const [isTabVisible, setIsTabVisible] = useState(() =>
    typeof document === 'undefined' ? true : document.visibilityState === 'visible'
  );
  const [systemIntelRefreshKey, setSystemIntelRefreshKey] = useState(0);
  const prevSystemPanelOpen = useRef(systemPanelOpen);
  const prevTabVisible = useRef(isTabVisible);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const handleVisibility = () => setIsTabVisible(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  useEffect(() => {
    const panelJustOpened = systemPanelOpen && !prevSystemPanelOpen.current;
    const tabJustVisible = isTabVisible && !prevTabVisible.current;
    prevSystemPanelOpen.current = systemPanelOpen;
    prevTabVisible.current = isTabVisible;

    if (!systemPanelOpen || !isTabVisible) return;
    if (panelJustOpened || tabJustVisible) {
      setSystemIntelRefreshKey((k) => k + 1);
    }
  }, [systemPanelOpen, isTabVisible]);

  const startupsPollMs = lookupActive ? POLL_STARTUPS_FAST : POLL_STARTUPS;
  const metaPollMs = systemPanelOpen ? POLL_META : POLL_META_SLOW;
  const analyticsPollMs = systemPanelOpen ? POLL_ANALYTICS : POLL_ANALYTICS_SLOW;

  const startups = usePoll(fetchStartups, startupsPollMs, [], STARTUPS_DELAY, isTabVisible);
  const escalations = usePoll(fetchEscalations, POLL_ESCALATIONS, [], ESCALATIONS_DELAY, isTabVisible);
  const signals = usePoll(fetchSignals, POLL_SIGNALS, [], SIGNALS_DELAY, isTabVisible);
  const metaReports = usePoll(fetchMetaReports, metaPollMs, [], META_REPORTS_DELAY, isTabVisible, systemIntelRefreshKey);
  const rejectionAnalytics = usePoll(fetchRejectionAnalytics, analyticsPollMs, {
    most_common_red_flags: [], rejection_by_sector: {}, avg_scores_at_rejection: {}, most_common_fail_dimensions: [],
  }, ANALYTICS_REJECTION_DELAY, isTabVisible, systemIntelRefreshKey);
  const watchlistAnalytics = usePoll(
    fetchWatchlistAnalytics,
    analyticsPollMs,
    { total: 0, stale: 0, avg_days: 0 },
    ANALYTICS_WATCHLIST_DELAY,
    isTabVisible,
    systemIntelRefreshKey
  );
  const concentrationAnalytics = usePoll(fetchConcentrationAnalytics, analyticsPollMs, {
    by_sector: {}, most_concentrated_sector: '', most_concentrated_theme: '', last_updated: '',
  }, ANALYTICS_CONCENTRATION_DELAY, isTabVisible, systemIntelRefreshKey);
  const scoutWeights = usePoll(fetchScoutWeights, metaPollMs, {
    MarketDrivenScout: 0.25, BuilderTechnicalScout: 0.25, PainPointScout: 0.25, ContrarianScout: 0.25,
  }, SCOUT_WEIGHTS_DELAY, isTabVisible, systemIntelRefreshKey);
  const calibrationState = usePoll(fetchCalibrationState, metaPollMs, {
    confidence_threshold_override: null, reviewer_weak_threshold_override: null,
    reviewer_strong_threshold_override: null, last_calibrated_at: null, last_calibrated_cycle: 0, calibration_history: [],
  }, CALIBRATION_DELAY, isTabVisible, systemIntelRefreshKey);
  const settings = usePoll<Settings | null>(
    () => fetchSettings().catch(() => null),
    POLL_SETTINGS,
    null,
    SETTINGS_DELAY,
    isTabVisible
  );

  const pendingEscalationCount = escalations.filter((e) => !e.human_resolution).length;

  return {
    startups, escalations, signals, metaReports,
    rejectionAnalytics, watchlistAnalytics, concentrationAnalytics,
    scoutWeights, calibrationState, settings, pendingEscalationCount,
  };
}
