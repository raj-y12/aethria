import type { Startup } from '../../types/startup';
import { buildMemoTags } from './memoContentHelpers';

/** Classification-stamp tag row for the memo masthead — quiet bordered chips,
 *  no colour-coding by sector; the word carries the meaning. */
export default function MemoTags({ startup }: { startup: Startup }) {
  const tags = buildMemoTags(startup);
  if (!tags.length) return null;
  return (
    <ul className="memoTags" aria-label="Company classification">
      {tags.map((tag) => (
        <li key={`${tag.kind}-${tag.label}`} className={`memoTag memoTag--${tag.kind}`}>
          {tag.label}
        </li>
      ))}
    </ul>
  );
}
