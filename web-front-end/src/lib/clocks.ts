const ZONES = [
  { label: 'London', tz: 'Europe/London' },
  { label: 'San Francisco', tz: 'America/Los_Angeles' },
] as const;

export function bureauTimes(now: Date = new Date()) {
  return ZONES.map(({ label, tz }) => ({
    label,
    time: new Intl.DateTimeFormat('en-GB', {
      timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).format(now),
  }));
}

export function editionNo(now: Date = new Date()) {
  return Math.floor((now.getTime() - Date.UTC(now.getUTCFullYear(), 0, 0)) / 86_400_000);
}
