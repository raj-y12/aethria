import {
  applyDecisionThresholds,
  commitScoreInput,
  getDecisionThresholdBoundaries,
  validateDecisionThresholds,
} from './decisionThresholds';
import {
  DEFAULT_VERDICT_BADGES,
  badgeTextColorForBackground,
  createDefaultFundConfiguration,
  isStartupStaleByConfig,
} from './fundConfiguration';
import type { Startup } from '../types/startup';

const config = createDefaultFundConfiguration({
  fund_config: {
    scoreBands: [
      { id: 'review', min: 60, max: 74, label: 'Review', tone: 'review' },
      { id: 'escalate', min: 75, max: 89, label: 'Escalate', tone: 'positive' },
    ],
  },
} as never);

const expectedBadgeIds = ['INVEST', 'MONITOR', 'PASS', 'STRONG', 'MEDIUM', 'WEAK'];
const expectedBandLabels = ['Pass', 'Monitor', 'Invest'];

if (DEFAULT_VERDICT_BADGES.map((badge) => badge.id).join('|') !== expectedBadgeIds.join('|')) {
  throw new Error('Default verdict badges must match current emitted verdicts.');
}

if (config.verdictBadges.map((badge) => badge.id).join('|') !== expectedBadgeIds.join('|')) {
  throw new Error('Legacy score bands must not replace verdict badge defaults.');
}

if (config.scoreBands.map((band) => band.label).join('|') !== expectedBandLabels.join('|')) {
  throw new Error('Default score bands must reflect current partner verdict bands.');
}

if (badgeTextColorForBackground('#ffffff') !== '#1a2b48') {
  throw new Error('Light badge backgrounds should use dark text.');
}

if (badgeTextColorForBackground('#1a2b48') !== '#fffdf7') {
  throw new Error('Dark badge backgrounds should use light text.');
}

const now = new Date('2026-05-25T12:00:00.000Z').getTime();
const staleStartup = {
  id: 'stale',
  scout: { id: 'stale', name: 'StaleCo', confidence: 0.7 },
  timestamps: {
    // Latest activity is minutes old (would NOT be stale on its own); unresolved_at
    // is older than the default staleAfterHours (48h). now is 2026-05-25T12:00Z, so
    // unresolved_at below is ~54h earlier — stale iff unresolved_at is consulted.
    discovered_at: '2026-05-25T11:00:00.000Z',
    reviewed_at: '2026-05-25T11:15:00.000Z',
    partnered_at: '2026-05-25T11:30:00.000Z',
    unresolved_at: '2026-05-23T06:00:00.000Z',
  },
} as Startup;

if (!isStartupStaleByConfig(staleStartup, config, now)) {
  throw new Error('Stale logic must use unresolved_at before latest activity timestamps.');
}

const resolvedStartup = {
  ...staleStartup,
  human_resolution: {
    decision: 'MAYBE',
    resolved_at: '2026-05-24T07:00:00.000Z',
  },
} as Startup;

if (isStartupStaleByConfig(resolvedStartup, config, now)) {
  throw new Error('Human-resolved startups must never be stale.');
}

const synced = applyDecisionThresholds(config, { passMonitorBoundary: 62, monitorInvestBoundary: 82 });
const bounds = getDecisionThresholdBoundaries(synced);
if (bounds.passMonitorBoundary !== 62 || bounds.monitorInvestBoundary !== 82) {
  throw new Error('Decision thresholds must persist boundary edits.');
}
const passBand = synced.scoreBands.find((band) => band.id === 'pass');
const monitorBand = synced.scoreBands.find((band) => band.id === 'monitor');
const investBand = synced.scoreBands.find((band) => band.id === 'invest');
if (!passBand || passBand.max !== 61 || !monitorBand || monitorBand.min !== 62 || monitorBand.max !== 81) {
  throw new Error('Decision thresholds must sync score bands with boundaries.');
}
if (!investBand || investBand.min !== 82) {
  throw new Error('Decision thresholds must sync invest band minimum.');
}
if (synced.thresholds.partnerReview !== 62 || synced.thresholds.escalation !== 82) {
  throw new Error('Decision thresholds must sync Partner thresholds.');
}
if (!validateDecisionThresholds(synced).valid) {
  throw new Error('Synced thresholds must pass validation.');
}
if (commitScoreInput('65', 2, 99, 60) !== 65) {
  throw new Error('commitScoreInput must parse valid scores.');
}
if (commitScoreInput('', 2, 99, 60) !== 60) {
  throw new Error('commitScoreInput must keep fallback on empty input.');
}
