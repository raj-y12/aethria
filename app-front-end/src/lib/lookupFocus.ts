/**
 * Shared handle for the on-demand lookup ("Analyze a company") input.
 *
 * The lookup is Aethria's hero action — any empty state or keyboard shortcut
 * can route the user straight into it without prop-drilling a callback through
 * the whole layout tree. The desktop rail input carries this id.
 */
export const LOOKUP_INPUT_ID = 'aethria-lookup-input';

/** Focus (and scroll to) the primary lookup input if it is mounted. */
export function focusLookupInput(): boolean {
  if (typeof document === 'undefined') return false;
  const el = document.getElementById(LOOKUP_INPUT_ID) as HTMLInputElement | null;
  if (!el) return false;
  el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  el.focus();
  return true;
}

/** True when the event target is a field the user is actively typing into. */
export function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName?.toLowerCase();
  return Boolean(el.isContentEditable || tag === 'input' || tag === 'textarea' || tag === 'select');
}
