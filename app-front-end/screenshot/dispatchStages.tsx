/**
 * Screenshot-only: renders the real DispatchCommandBar frozen at one stage, so
 * every screen of a lookup can be captured without a backend. Open
 *   /screenshot/index.html?dispatch=<stage>
 * where <stage> is one of DISPATCH_STAGES below.
 */
import { LookupResultSnapshot } from '@aethria/product-chrome';
import DispatchCommandBar, { type DispatchCommandBarProps } from '../src/components/DispatchCommandBar';
import { buildLookupSnapshotProps } from '../src/lib/productChromeMappers';
import { MOCK_SYSTEM_DATA } from './mock';

const startup = MOCK_SYSTEM_DATA.startups[0];
const noop = () => {};

const base: DispatchCommandBarProps = {
  open: true,
  onClose: noop,
  input: '',
  setInput: noop,
  onSubmit: noop,
  onCancel: noop,
  isBusy: false,
  message: null,
  lookupPhase: null,
  onPickCandidate: noop,
  onRefineWebsite: noop,
  onSubmitRerun: noop,
  onRetry: noop,
  onRetryJob: noop,
  onOpenIdentityReview: noop,
  onFocusChip: noop,
};

const resolving = { query: 'calderwell', name: null, sector: null, resolved: false, found: false, reviewed: false };
const analyzing = { query: 'calderwell', name: 'Calderwell Materials', sector: 'Climate materials', resolved: true, found: true, reviewed: false };

const STAGES: Record<string, Partial<DispatchCommandBarProps>> = {
  compose: {},
  typing: { input: 'Calderwell Materials' },
  confirm: {
    isBusy: true,
    progress: resolving,
    candidates: [
      { name: 'Calderwell Materials', website: 'calderwell.co.uk', description: 'Low-carbon cement additives for precast producers.', confidence: 0.82, source_badges: ['Companies House', 'Website'] },
      { name: 'Calderwell Group', website: 'calderwellgroup.com', description: 'Construction services holding company.', confidence: 0.41, source_badges: ['Website'] },
    ],
  },
  website: { isBusy: true, progress: resolving, needsWebsite: true },
  analyzing: { isBusy: true, lookupPhase: 'Reviewing', progress: analyzing, execution: { status: 'running', attempts: 1, maxAttempts: 3 } },
  retry: { isBusy: true, progress: analyzing, execution: { status: 'retry_wait', attempts: 2, maxAttempts: 3, nextAttemptAt: new Date(Date.now() + 90_000).toISOString(), error: 'Reviewer timed out' } },
  blocked: { progress: analyzing, execution: { status: 'blocked', attempts: 1, maxAttempts: 3, blockCode: 'identity_review_required' } },
  failure: { failure: { query: 'calderwel matrials', message: 'No company matched that name. Try the website instead.' } },
  result: {
    progress: { ...analyzing, reviewed: true },
    result: <LookupResultSnapshot {...buildLookupSnapshotProps(startup)} size="lg" onOpenMemo={noop} className="dispatch-result-snapshot w-full" />,
  },
  rerun: { rerun: { name: 'Calderwell Materials', sector: 'Climate materials', previousContext: null } },
  chips: {
    progress: analyzing,
    isBusy: true,
    chips: [
      { id: 'a', label: 'Calderwell Materials', stage: 'Review', status: 'reviewing', active: true },
      { id: 'b', label: 'Rheinlab', stage: 'Discover', status: 'scouting', active: false },
      { id: 'c', label: 'Kilbride Systems', stage: 'Decide', status: 'decided', active: false },
    ],
  },
};

export const DISPATCH_STAGES = Object.keys(STAGES);

export default function DispatchStageHarness({ stage }: { stage: string }) {
  return (
    <div className="relative h-[100dvh] bg-paper">
      <DispatchCommandBar {...base} {...(STAGES[stage] ?? {})} />
    </div>
  );
}
