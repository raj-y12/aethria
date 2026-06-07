import { useNavigate } from 'react-router';
import PageChrome from '../components/PageChrome';
import SystemIntelligence from '../components/SystemIntelligence';
import { useFundConfiguration } from '../hooks';
import type { SystemData } from '../hooks/useSystemData';
import type { Startup } from '../types/startup';

/**
 * Intelligence — the meta layer (signals, analytics, calibration, thesis runtime)
 * promoted out of the cramped right-panel toggle into a first-class, addressable
 * page. This is Aethria's most differentiated surface; it deserves a real home.
 */
export default function IntelligencePage({ data }: { data: SystemData }) {
  const navigate = useNavigate();
  const { configuration: fundConfiguration } = useFundConfiguration(data.settings);

  const openDeal = (startup: Startup) => navigate(`/v1/deal/${startup.id}`);

  return (
    <PageChrome title="System Intelligence" kicker="Meta layer">
      <SystemIntelligence
        startups={data.startups}
        onStartupClick={openDeal}
        selectedStartupId={null}
        signals={data.signals}
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
    </PageChrome>
  );
}
