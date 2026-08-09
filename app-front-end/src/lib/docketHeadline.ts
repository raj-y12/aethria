import type { QueueView } from '../components/queue/DecisionQueueHeader';

export interface DocketHeadline {
  /** Mono kicker above the frame — names the state, then counts it. */
  eyebrow: string;
  /** True when the view is the one that genuinely needs a person. */
  urgent: boolean;
}

export interface DocketCounts {
  /** Rows the active view is actually showing. */
  shown: number;
  needRuling: number;
}

function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

/**
 * The docket names the view it is showing. Escalations are the only state that
 * claims urgency; every other view is a way of looking, not a demand. Counts come
 * from the rows on screen, so the kicker can never disagree with the list.
 */
export function docketHeadline(view: QueueView, counts: DocketCounts): DocketHeadline {
  const { shown, needRuling } = counts;

  if (view === 'ESCALATED') {
    return shown === 0
      ? { eyebrow: 'Awaiting your ruling · none', urgent: false }
      : {
          eyebrow: `Awaiting your ruling · ${shown} ${plural(shown, 'matter', 'matters')}`,
          urgent: true,
        };
  }

  if (view === 'NEW') {
    return shown === 0
      ? { eyebrow: 'New since you left · none', urgent: false }
      : {
          eyebrow: `New since you left · ${shown} ${plural(shown, 'company', 'companies')}`,
          urgent: false,
        };
  }

  if (view === 'STALE') {
    return shown === 0
      ? { eyebrow: 'Gone quiet · none', urgent: false }
      : { eyebrow: `Gone quiet · ${shown} ${plural(shown, 'matter', 'matters')}`, urgent: false };
  }

  // Open / all: a ruling still outranks the count when one is waiting.
  if (needRuling > 0) {
    return {
      eyebrow: `Awaiting your ruling · ${needRuling} ${plural(needRuling, 'matter', 'matters')}`,
      urgent: true,
    };
  }

  return shown === 0
    ? { eyebrow: 'On the desk · none', urgent: false }
    : { eyebrow: `On the desk · ${shown} ${plural(shown, 'matter', 'matters')}`, urgent: false };
}
