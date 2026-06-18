import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchStartups } from '../api/startups';
import { fetchEscalations } from '../api/escalations';
import { fetchSignals } from '../api/signals';
import {
  fetchRejectionAnalytics,
  fetchWatchlistAnalytics,
  fetchConcentrationAnalytics,
  fetchSystemHealth,
} from '../api/analytics';
import {
  fetchMetaReports,
  fetchMetaPromptState,
  fetchMetaEvalSet,
  fetchScoutWeights,
  fetchCalibrationState,
  fetchMetaInsights,
} from '../api/meta';
import { fetchFundThesisRuntime, type FundThesisRuntime } from '../api/fundThesis';
import { fetchSettings } from '../api/settings';
import { getQueryConfig, type QueryLiveGate } from '../lib/queryIntent';
import { useQueryLiveGate } from './useQueryLiveGate';
import { useStartupsStream } from './useStartupsStream';
import type {
  Startup, EscalationItem, SignalItem,
  RejectionAnalytics, WatchlistAnalytics, ConcentrationAnalytics,
  MetaCycleReport, MetaPromptState, MetaEvalSet, ScoutWeights, CalibrationState,
  SystemHealthSnapshot, MetaInsightsPayload,
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
  metaPromptState: MetaPromptState;
  metaEvalSet: MetaEvalSet;
  systemHealth: SystemHealthSnapshot | null;
  metaInsights: MetaInsightsPayload | null;
  fundThesisRuntime: FundThesisRuntime | null;
  fundThesisRuntimeLoading: boolean;
  fundThesisRuntimeError: string | null;
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
      void queryClient.invalidateQueries({ queryKey: ['analytics', 'system-health'] });
      void queryClient.invalidateQueries({ queryKey: ['meta', 'insights'] });
      void queryClient.invalidateQueries({ queryKey: ['fund-thesis'] });
    }
  }, [systemPanelOpen, isTabVisible, queryClient]);

  // Push-based freshness: an SSE stream nudges us to refetch the moment the
  // pipeline writes new data. Only run it while the tab is visible (bounds open
  // connections; the tab-focus invalidation above covers the return trip).
  const streamConnected = useStartupsStream(isTabVisible);

  // The deal-flow grid is the primary surface users watch update. When the push
  // stream is healthy, polling is just a slow safety net (90s) since updates
  // arrive instantly. If the stream is down (or the tab is hidden), fall back to
  // the brisk activity-aware cadence so the grid still stays fresh — while
  // keeping backend egress conservative when nobody's watching.
  const startupsPollMs = !isTabVisible
    ? false
    : streamConnected
      ? 90_000
      : userActive
        ? 15_000
        : 60_000;
  const startupsQuery = useQuery({
    queryKey: ['startups', 'list'],
    queryFn: fetchStartups,
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 15_000 }),
    refetchInterval: startupsPollMs,
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

  const metaPromptStateQuery = useQuery({
    queryKey: ['meta', 'prompt-state'],
    queryFn: () => fetchMetaPromptState(),
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) =>
      prev ?? { active: {}, active_detail: {}, pending: [] },
  });

  const metaEvalSetQuery = useQuery({
    queryKey: ['meta', 'eval-set'],
    queryFn: fetchMetaEvalSet,
    ...getQueryConfig('STATIC'),
    placeholderData: (prev) => prev ?? { startup_ids: [], count: 0, max: 50 },
  });

  const systemHealthQuery = useQuery({
    queryKey: ['analytics', 'system-health'],
    queryFn: fetchSystemHealth,
    ...getQueryConfig('STATIC'),
  });

  const metaInsightsQuery = useQuery({
    queryKey: ['meta', 'insights'],
    queryFn: fetchMetaInsights,
    ...getQueryConfig('STATIC'),
  });

  const fundThesisRuntimeQuery = useQuery({
    queryKey: ['fund-thesis', 'runtime'],
    queryFn: () => fetchFundThesisRuntime().catch(() => null),
    ...getQueryConfig('SEMI_DYNAMIC', { liveGate, pollIntervalMs: 120_000 }),
    refetchInterval: isTabVisible ? 120_000 : false,
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
    metaPromptState: metaPromptStateQuery.data ?? { active: {}, active_detail: {}, pending: [] },
    metaEvalSet: metaEvalSetQuery.data ?? { startup_ids: [], count: 0, max: 50 },
    systemHealth: systemHealthQuery.data ?? null,
    metaInsights: metaInsightsQuery.data ?? null,
    fundThesisRuntime: fundThesisRuntimeQuery.data ?? null,
    fundThesisRuntimeLoading: fundThesisRuntimeQuery.isPending,
    fundThesisRuntimeError: fundThesisRuntimeQuery.isError ? 'Could not load thesis runtime' : null,
    settings: settingsQuery.data ?? null,
    pendingEscalationCount,
    startupsError: startupsQuery.isError ? 'Could not load startups' : null,
    liveGate,
  };
}
