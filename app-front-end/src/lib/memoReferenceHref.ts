/** First http(s) URL in a reference line (e.g. "Title — https://x.com/y"). */
export function memoReferenceHref(raw: string): string | null {
  const m = String(raw ?? '').match(/https?:\/\/[^\s\]\)"'<>]+/i);
  if (!m) return null;
  return m[0].replace(/[),.;]+$/, '');
}

export function memoReferenceLabel(raw: string): string {
  return String(raw ?? '').trim();
}

/**
 * Regression (audit HIGH-H11): fields like companyResolution.website,
 * linkedin_url, and founder social links are scraped/LLM-retrieved data --
 * as attacker-controlled as any other retrieved text per the backend's own
 * threat model -- but were used directly as `href` with no scheme check. A
 * `javascript:...` value would render as a clickable link that executes in
 * the app's origin. Only http(s) URLs are ever safe to use as href.
 */
export function safeHref(raw: string | null | undefined): string | undefined {
  const value = String(raw ?? '').trim();
  if (!/^https?:\/\//i.test(value)) return undefined;
  return value;
}
