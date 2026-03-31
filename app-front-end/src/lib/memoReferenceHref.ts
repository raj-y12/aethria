/** First http(s) URL in a reference line (e.g. "Title — https://x.com/y"). */
export function memoReferenceHref(raw: string): string | null {
  const m = String(raw ?? '').match(/https?:\/\/[^\s\]\)"'<>]+/i);
  if (!m) return null;
  return m[0].replace(/[),.;]+$/, '');
}

export function memoReferenceLabel(raw: string): string {
  return String(raw ?? '').trim();
}
