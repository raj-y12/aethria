import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  clearAdminToken,
  fetchAdminOverview,
  getAdminToken,
  type AdminOverview,
  type AdminUserRow,
} from '../api/admin';
import LoadingAnimation from '../components/LoadingAnimation';
import AdminLoginPage from './AdminLoginPage';

type UserFilter = 'all' | 'online' | 'agents';

function formatDate(value: string | null): string {
  if (!value) return 'Never';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function decisionSummary(row: AdminUserRow): string {
  const entries = Object.entries(row.startup_stats.partner_decisions);
  if (entries.length === 0) return 'No decisions';
  return entries.map(([label, count]) => `${label} ${count}`).join(' / ');
}

function matchesQuery(row: AdminUserRow, query: string): boolean {
  const haystack = [
    row.user_id,
    row.email ?? '',
    row.display_name,
    row.agent_config.agents_status,
  ].join(' ').toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function StatCard({ label, value, hint }: { label: string; value: number | string; hint: string }) {
  return (
    <div className="border border-oxford/[0.08] bg-paper/70 p-5">
      <p className="type-meta uppercase tracking-[0.14em] text-oxford/35">{label}</p>
      <p className="mt-3 font-display text-[34px] leading-none text-oxford">{value}</p>
      <p className="mt-2 type-meta text-oxford/40">{hint}</p>
    </div>
  );
}

function StatusPill({ active, label }: { active: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center border px-2 py-1 type-meta uppercase tracking-[0.12em] ${
        active
          ? 'border-oxford/20 bg-oxford text-paper'
          : 'border-oxford/[0.08] bg-transparent text-oxford/35'
      }`}
    >
      {label}
    </span>
  );
}

export default function AdminDashboardPage() {
  const [authenticated, setAuthenticated] = useState(() => Boolean(getAdminToken()));
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<UserFilter>('all');

  const loadOverview = useCallback(async () => {
    if (!getAdminToken()) {
      setAuthenticated(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setOverview(await fetchAdminOverview());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load admin overview');
      if (!getAdminToken()) {
        setAuthenticated(false);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authenticated) return undefined;
    void loadOverview();
    const interval = window.setInterval(() => void loadOverview(), 30000);
    return () => window.clearInterval(interval);
  }, [authenticated, loadOverview]);

  const users = useMemo(() => {
    const rows = overview?.users ?? [];
    return rows.filter((row) => {
      if (filter === 'online' && !row.is_logged_in) return false;
      if (filter === 'agents' && !row.agents_enabled) return false;
      return matchesQuery(row, query);
    });
  }, [filter, overview, query]);

  if (!authenticated) {
    return <AdminLoginPage onAuthenticated={() => setAuthenticated(true)} />;
  }

  return (
    <main className="min-h-[100dvh] bg-paper text-oxford px-5 py-6 lg:px-12 lg:py-10">
      <header className="flex flex-col gap-6 border-b border-oxford/[0.08] pb-8 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="type-meta uppercase tracking-[0.18em] text-oxford/35">Aethria Admin</p>
          <h1 className="mt-3 font-display text-[44px] leading-none text-oxford lg:text-[58px]">
            Master Log
          </h1>
          <p className="mt-4 max-w-[720px] type-body text-oxford/55">
            Global session, agent, startup, and pipeline visibility across every known user.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={() => void loadOverview()}
            className="type-meta uppercase tracking-[0.14em] text-oxford/50 hover:text-oxford transition-colors"
          >
            Refresh
          </button>
          <button
            type="button"
            onClick={() => {
              clearAdminToken();
              setOverview(null);
              setAuthenticated(false);
            }}
            className="type-meta uppercase tracking-[0.14em] text-oxford/50 hover:text-oxford transition-colors"
          >
            Exit Admin
          </button>
        </div>
      </header>

      {loading && !overview ? (
        <LoadingAnimation fullScreen={false} />
      ) : (
        <section className="mt-8 flex flex-col gap-8">
          {overview && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <StatCard label="Users" value={overview.totals.users} hint="Known Clerk or DB users" />
              <StatCard label="Online" value={overview.totals.active_sessions} hint="Active Clerk sessions" />
              <StatCard label="Agents On" value={overview.totals.users_with_agents_enabled} hint="Any stage enabled" />
              <StatCard label="Startups" value={overview.totals.startups} hint="All tenant rows" />
              <StatCard label="Runs 24h" value={overview.totals.pipeline_runs_24h} hint="Pipeline cycles" />
            </div>
          )}

          <div className="flex flex-col gap-4 border border-oxford/[0.08] p-4 lg:flex-row lg:items-center lg:justify-between">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search users, email, status"
              className="min-w-0 flex-1 bg-transparent border-0 border-b border-oxford/10 rounded-none outline-none focus:border-oxford/40 transition-colors type-body text-oxford py-2 placeholder:text-oxford/25"
            />
            <div className="flex flex-wrap gap-2">
              {(['all', 'online', 'agents'] as UserFilter[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setFilter(option)}
                  className={`border px-3 py-2 type-meta uppercase tracking-[0.12em] transition-colors ${
                    filter === option
                      ? 'border-oxford bg-oxford text-paper'
                      : 'border-oxford/[0.08] text-oxford/45 hover:text-oxford'
                  }`}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="border border-accent/30 bg-accent/[0.03] px-4 py-3 type-meta text-accent">
              {error}
            </div>
          )}

          <div className="overflow-x-auto border border-oxford/[0.08]">
            <table className="min-w-[1080px] w-full border-collapse">
              <thead className="bg-oxford/[0.03]">
                <tr className="type-meta uppercase tracking-[0.14em] text-oxford/35">
                  <th className="px-4 py-3 text-left font-normal">User</th>
                  <th className="px-4 py-3 text-left font-normal">Session</th>
                  <th className="px-4 py-3 text-left font-normal">Agents</th>
                  <th className="px-4 py-3 text-left font-normal">Startups</th>
                  <th className="px-4 py-3 text-left font-normal">Pipeline</th>
                </tr>
              </thead>
              <tbody>
                {users.map((row) => (
                  <tr key={row.user_id} className="border-t border-oxford/[0.06] align-top">
                    <td className="px-4 py-4">
                      <p className="type-body-sm text-oxford">{row.display_name}</p>
                      <p className="mt-1 type-meta text-oxford/45">{row.email ?? row.user_id}</p>
                    </td>
                    <td className="px-4 py-4">
                      <StatusPill active={row.is_logged_in} label={row.is_logged_in ? 'Online' : 'Offline'} />
                      <p className="mt-2 type-meta text-oxford/45">
                        {row.active_sessions_count} active / last {formatDate(row.last_active_at)}
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-2">
                        <StatusPill active={row.agent_config.scouts_enabled} label="Scout" />
                        <StatusPill active={row.agent_config.reviewers_enabled} label="Review" />
                        <StatusPill active={row.agent_config.partners_enabled} label="Partner" />
                      </div>
                      <p className="mt-2 type-meta text-oxford/45">
                        {row.agent_config.agents_status} / loop {row.loop_alive ? 'alive' : 'idle'}
                      </p>
                    </td>
                    <td className="px-4 py-4">
                      <p className="type-body-sm text-oxford">{row.startup_stats.total} total</p>
                      <p className="mt-1 type-meta text-oxford/45">{decisionSummary(row)}</p>
                    </td>
                    <td className="px-4 py-4">
                      <p className="type-body-sm text-oxford">{row.pipeline_stats.runs_24h} runs in 24h</p>
                      <p className="mt-1 type-meta text-oxford/45">
                        Latest {formatDate(row.pipeline_stats.latest_activity_at)}
                      </p>
                      <p className="mt-1 type-meta text-oxford/45">
                        {row.pipeline_stats.startups_found_24h} found / {row.pipeline_stats.decisions_24h} decisions
                      </p>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center type-body text-oxford/45">
                      No users match this view.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {overview && (
            <p className="type-meta text-oxford/35">
              Generated {formatDate(overview.generated_at)}. Clerk session data is cached briefly by the backend.
            </p>
          )}
        </section>
      )}
    </main>
  );
}

