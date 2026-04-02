import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchStartups } from '../api/startups';
import { fetchEscalations } from '../api/escalations';
import { fetchSignals } from '../api/signals';
import { fetchRejectionAnalytics, fetchWatchlistAnalytics, fetchConcentrationAnalytics } from '../api/analytics';
import { fetchMetaReports, fetchScoutWeights, fetchCalibrationState } from '../api/meta';
import { fetchSettings } from '../api/settings';
import { getQueryConfig, type QueryLiveGate } from '../lib/queryIntent';
import { useQueryLiveGate } from './useQueryLiveGate';
import type {
  Startup, EscalationItem, SignalItem,
  RejectionAnalytics, WatchlistAnalytics, ConcentrationAnalytics,
  MetaCycleReport, ScoutWeights, CalibrationState,
} from '../types/startup';
import type { Settings } from '../api/settings';

const emptyRejection: RejectionAnalytics = {
  most_common_red_flags: [],
  rejection_by_sector: {},
  avg_scores_at_rejection: {},
  most_common_fail_dimensions: [],
};

const defaultCalibration: CalibrationState = {
  confidence_threshold_override: null,
  reviewer_weak_threshold_override: null,
  reviewer_strong_threshold_override: null,
  last_calibrated_at: null,
  last_calibrated_cycle: 0,
  calibration_history: [],
};

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
  startupsError: string | null;
  /** Shared tab + idle gate for child components (e.g. agents status). */
  liveGate: QueryLiveGate;
}

export interface UseSystemDataOptions {
  systemPanelOpen?: boolean;
}

export function useSystemData(options: UseSystemDataOptions = {}): SystemData {
  const { systemPanelOpen = false } = options;
  const queryClient = useQueryClient();
  const { tabVisible: isTabVisible, userActive } = useQueryLiveGate();
  const liveGate: QueryLiveGate = { tabVisible: isTabVisible, userActive };

  const prevSystemPanelOpen = useRef(systemPanelOpen);
  const prevTabVisible = useRef(isTabVisible);

  useEffect(() => {
    const panelJustOpened = systemPanelOpen && !prevSystemPanelOpen.current;
    const tabJustVisible = isTabVisible && !prevTabVisible.current;
    prevSystemPanelOpen.current = systemPanelOpen;
    prevTabVisible.current = isTabVisible;

    if (tabJustVisible) {
      void queryClient.invalidateQueries({ queryKey: ['startups', 'list'] });
    }

    if (!systemPanelOpen || !isTabVisible) return;
    if (panelJustOpened || tabJustVisible) {
      void queryClient.invalidateQueries({ queryKey: ['meta'] });
      void queryClient.invalidateQueries({ queryKey: ['analytics'] });
    }
  }, [systemPanelOpen, isTabVisible, queryClient]);

  const startupsQuery = useQuery({
    queryKey: ['startups', 'list'],
    queryFn: fetchStartups,
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 60_000 }),
    placeholderData: (prev) => prev ?? [],
  });

  const escalationsQuery = useQuery({
    queryKey: ['escalations'],
    queryFn: fetchEscalations,
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 120_000 }),
    placeholderData: (prev) => prev ?? [],
  });

  const signalsQuery = useQuery({
    queryKey: ['signals'],
    queryFn: fetchSignals,
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 120_000 }),
    placeholderData: (prev) => prev ?? [],
  });

  const metaReportsQuery = useQuery({
    queryKey: ['meta', 'reports'],
    queryFn: fetchMetaReports,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) => prev ?? [],
  });

  const rejectionAnalyticsQuery = useQuery({
    queryKey: ['analytics', 'rejections'],
    queryFn: fetchRejectionAnalytics,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) => prev ?? emptyRejection,
  });

  const watchlistAnalyticsQuery = useQuery({
    queryKey: ['analytics', 'watchlist'],
    queryFn: fetchWatchlistAnalytics,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) => prev ?? { total: 0, stale: 0, avg_days: 0 },
  });

  const concentrationAnalyticsQuery = useQuery({
    queryKey: ['analytics', 'concentration'],
    queryFn: fetchConcentrationAnalytics,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) =>
      prev ?? {
        by_sector: {},
        most_concentrated_sector: '',
        most_concentrated_theme: '',
        last_updated: '',
      },
  });

  const scoutWeightsQuery = useQuery({
    queryKey: ['meta', 'weights'],
    queryFn: fetchScoutWeights,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) =>
      prev ?? {
        MarketDrivenScout: 0.25,
        BuilderTechnicalScout: 0.25,
        PainPointScout: 0.25,
        ContrarianScout: 0.25,
      },
  });

  const calibrationQuery = useQuery({
    queryKey: ['meta', 'calibration'],
    queryFn: fetchCalibrationState,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) => prev ?? defaultCalibration,
  });

  const settingsQuery = useQuery({
    queryKey: ['settings'],
    queryFn: () => fetchSettings().catch(() => null),
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) => prev ?? null,
  });

  const startups = startupsQuery.data ?? [];
  const escalations = escalationsQuery.data ?? [];

  const pendingEscalationCount = escalations.filter((e) => !e.human_resolution).length;

  return {
    startups,
    escalations,
    signals: signalsQuery.data ?? [],
    metaReports: metaReportsQuery.data ?? [],
    rejectionAnalytics: rejectionAnalyticsQuery.data ?? emptyRejection,
    watchlistAnalytics: watchlistAnalyticsQuery.data ?? { total: 0, stale: 0, avg_days: 0 },
    concentrationAnalytics: concentrationAnalyticsQuery.data ?? {
      by_sector: {},
      most_concentrated_sector: '',
      most_concentrated_theme: '',
      last_updated: '',
    },
    scoutWeights: scoutWeightsQuery.data ?? {
      MarketDrivenScout: 0.25,
      BuilderTechnicalScout: 0.25,
      PainPointScout: 0.25,
      ContrarianScout: 0.25,
    },
    calibrationState: calibrationQuery.data ?? defaultCalibration,
    settings: settingsQuery.data ?? null,
    pendingEscalationCount,
    startupsError: startupsQuery.isError ? 'Could not load startups' : null,
    liveGate,
  };
}
