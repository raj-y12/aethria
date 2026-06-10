import { Link, useNavigate } from 'react-router';
import SystemIntelligence from '../components/SystemIntelligence';
import { useFundConfiguration } from '../hooks';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

function HeaderReadout({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-phi-1">
      <span className="font-mono text-[clamp(22px,2vw,30px)] font-semibold leading-none tracking-[-0.03em] tabular-nums text-oxford">
        {value}
      </span>
      <span className="type-meta uppercase tracking-[0.1em] text-oxford/40">{label}</span>
    </div>
  );
}

function pct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '--';
  return `${Math.round(v <= 1 ? v * 100 : v)}%`;
}

/**
 * Fund — the instrument itself. The mandate the system runs on, the record of
 * human judgment, the patterns in its decisions, its calibration, and how it
 * evolves. The old "Intelligence" panel's surfaces live here, organised by
 * what they say about the fund rather than where the data comes from.
 */
export default function FundPage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);
  const runtime = data.fundThesisRuntime;

  const fundName =
    data.settings?.fund_identity?.fund_name?.trim() ||
    (runtime?.active_version_number != null ? `Fund Thesis v${runtime.active_version_number}` : 'Fund');

  const openDeal = (startup: Startup) => navigate(`/v1?open=${startup.id}`);
  const stats = runtime?.alignment_stats;

  return (
    <div className="page-transition-enter min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="mx-auto w-full max-w-[1180px] px-phi-5 pb-phi-8 pt-phi-5">
        <header className="flex flex-wrap items-end justify-between gap-x-phi-7 gap-y-phi-5 border-b border-oxford/[0.075] pb-phi-6">
          <div className="min-w-0">
            <p className="type-label-section text-oxford/45">
              The instrument
              {runtime?.active_version_number != null ? ` · Mandate v${runtime.active_version_number}` : ''}
            </p>
            <h1 className="mt-phi-2 type-title font-medium text-oxford">{fundName}</h1>
            <Link
              to="/v1/settings"
              className="mt-phi-2 inline-block type-meta uppercase tracking-[0.1em] text-oxford/40 transition-colors hover:text-oxford btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30"
            >
              Edit mandate →
            </Link>
          </div>
          <div className="flex flex-wrap items-end gap-x-phi-7 gap-y-phi-4">
            <HeaderReadout label="Mandate match" value={pct(stats?.pct_matching_thesis)} />
            <HeaderReadout label="Mean alignment" value={pct(stats?.avg_alignment_score)} />
            <HeaderReadout
              label="Reviewed"
              value={(stats?.reviewed_with_thesis_count ?? 0).toLocaleString()}
            />
          </div>
        </header>

        <SystemIntelligence
          startups={data.startups}
          onStartupClick={openDeal}
          selectedStartupId={null}
          rejectionAnalytics={data.rejectionAnalytics}
          watchlistAnalytics={data.watchlistAnalytics}
          concentrationAnalytics={data.concentrationAnalytics}
          systemHealth={data.systemHealth}
          metaReports={data.metaReports}
          scoutWeights={data.scoutWeights}
          calibrationState={data.calibrationState}
          metaPromptState={data.metaPromptState}
          metaEvalSet={data.metaEvalSet}
          metaInsights={data.metaInsights}
          fundThesisRuntime={data.fundThesisRuntime}
          fundThesisRuntimeLoading={data.fundThesisRuntimeLoading}
          fundThesisRuntimeError={data.fundThesisRuntimeError}
          fundConfiguration={fundConfiguration}
        />
      </div>
    </div>
  );
}
