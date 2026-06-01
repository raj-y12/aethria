import type { SignalItem } from '../../types/startup';

type Props = {
  startupId: string;
  signals: SignalItem[];
};

export default function MemoPortfolioContext({ startupId, signals }: Props) {
  const related = signals
    .filter((s) => (s.startup_id ?? '') === startupId)
    .sort((a, b) => String(b.detected_at ?? '').localeCompare(String(a.detected_at ?? '')))
    .slice(0, 5);

  if (related.length === 0) return null;

  return (
    <section className="memoPortfolioContext" aria-labelledby="memo-portfolio-context">
      <h2 className="memoPortfolioContextHead" id="memo-portfolio-context">
        Portfolio signals
      </h2>
      <ul className="memoPortfolioContextList">
        {related.map((signal, index) => (
          <li key={signal.id ?? `${signal.signal_type}-${index}`} className="memoPortfolioContextItem">
            <span className="memoPortfolioContextType">{signal.signal_type}</span>
            <span className="memoPortfolioContextText">
              {signal.description || 'Signal detected'}
            </span>
            {signal.detected_at ? (
              <span className="memoPortfolioContextWhen">
                {new Date(signal.detected_at).toLocaleDateString('en-GB')}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
