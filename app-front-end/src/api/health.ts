const API_BASE =
  typeof window !== 'undefined'
    ? (import.meta.env.VITE_API_URL ?? '')
    : 'http://localhost:8000';

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return false;
    const data = await res.json();
    return data?.status === 'ok';
  } catch {
    return false;
  }
}
