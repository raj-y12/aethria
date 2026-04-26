const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

const ADMIN_TOKEN_KEY = 'aethria_admin_token';

export interface AdminAgentConfig {
  scouts_enabled: boolean;
  reviewers_enabled: boolean;
  partners_enabled: boolean;
  agents_status: 'running' | 'stopped' | 'error' | string;
  agents_last_started_at: string | null;
}

export interface AdminUserRow {
  user_id: string;
  email: string | null;
  display_name: string;
  created_at: string | null;
  is_logged_in: boolean;
  active_sessions_count: number;
  last_active_at: string | null;
  agents_enabled: boolean;
  agent_config: AdminAgentConfig;
  loop_alive: boolean;
  startup_stats: {
    total: number;
    partner_decisions: Record<string, number>;
  };
  pipeline_stats: {
    runs_24h: number;
    latest_activity_at: string | null;
    startups_found_24h: number;
    reviewed_24h: number;
    decisions_24h: number;
    escalations_24h: number;
  };
}

export interface AdminOverview {
  generated_at: string;
  totals: {
    users: number;
    active_sessions: number;
    users_with_agents_enabled: number;
    startups: number;
    pipeline_runs_24h: number;
  };
  users: AdminUserRow[];
}

export interface AdminLoginResult {
  token: string;
  token_type: 'bearer' | string;
  expires_in_seconds: number;
}

export function getAdminToken(): string | null {
  if (typeof sessionStorage === 'undefined') return null;
  return sessionStorage.getItem(ADMIN_TOKEN_KEY);
}

export function setAdminToken(token: string): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken(): void {
  if (typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

async function adminFetch(input: string, init?: RequestInit): Promise<Response> {
  const token = getAdminToken();
  const headers = {
    ...(init?.headers ?? {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401) {
    clearAdminToken();
  }
  return response;
}

export async function loginAdmin(secret: string): Promise<AdminLoginResult> {
  const response = await fetch(`${API_BASE}/api/admin/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ secret }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail ?? `Admin login failed: ${response.status}`);
  }
  const result = body as AdminLoginResult;
  setAdminToken(result.token);
  return result;
}

export async function fetchAdminOverview(): Promise<AdminOverview> {
  const response = await adminFetch(`${API_BASE}/api/admin/overview`, {
    headers: { Accept: 'application/json' },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail ?? `Admin overview failed: ${response.status}`);
  }
  return body as AdminOverview;
}

