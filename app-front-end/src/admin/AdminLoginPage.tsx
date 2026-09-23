import { useState, type FormEvent } from 'react';
import { loginAdmin } from '../api/admin';

interface AdminLoginPageProps {
  onAuthenticated: () => void;
}

export default function AdminLoginPage({ onAuthenticated }: AdminLoginPageProps) {
  const [secret, setSecret] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await loginAdmin(secret);
      setSecret('');
      onAuthenticated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Admin login failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-[100dvh] bg-paper text-oxford flex items-center justify-center px-6">
      <section className="aethria-admin-login w-full max-w-[460px] px-8 py-10">
        <p className="type-label-section">Aethria Admin</p>
        <h1 className="mt-4 font-sans text-[40px] font-semibold leading-none tracking-[-0.04em] text-oxford">Master Access</h1>
        <p className="mt-5 type-body text-oxford/65">
          Enter the backend admin secret to view global user, session, and agent telemetry.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
          <label className="flex flex-col gap-2">
            <span className="type-label-section">Admin Secret</span>
            <input
              type="password"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              className="bg-transparent border-0 border-b border-oxford/15 rounded-none outline-none focus:border-oxford/45 transition-colors duration-300 type-body text-oxford py-3 placeholder:text-oxford/65"
              placeholder="Enter master secret"
              autoComplete="current-password"
              autoFocus
            />
          </label>

          {error && (
            <div className="border-l-2 border-accent/50 px-4 py-3 type-meta text-accent">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!secret.trim() || submitting}
            className="type-action mt-2 w-fit border-0 border-b border-oxford/25 bg-transparent px-0 py-3 text-oxford transition-colors hover:border-oxford disabled:cursor-not-allowed disabled:opacity-35"
          >
            {submitting ? 'Verifying' : 'Enter Dashboard'}
          </button>
        </form>
      </section>
    </main>
  );
}
