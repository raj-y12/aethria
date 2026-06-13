/**
 * Canonical date formatting — editorial en-GB, short month, no slashes.
 * "30 May 2026" / "30 May 2026 · 14:12". Use these instead of ad-hoc
 * toLocaleDateString calls so every surface speaks one register.
 * Compact special forms (spine clock, queue "30 MAY") stay local to their
 * components — this module covers the default document register.
 */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const date = d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  const time = d.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' });
  return `${date} · ${time}`;
}
