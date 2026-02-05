import { useState } from 'react';
import { Link } from 'react-router-dom';
import GrainOverlay from './components/GrainOverlay';
import CustomCursor from './components/CustomCursor';

const OXFORD = '#002147';
const PAPER = '#F2F0EA';
// Use external backend when VITE_API_URL is set (local dev with run.py); otherwise use Vercel serverless /api/waitlist
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const WAITLIST_URL = API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/waitlist` : '/api/waitlist';

export default function RequestAccessPage() {
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitHover, setSubmitHover] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [firm, setFirm] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !role.trim() || !firm.trim()) return;
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(WAITLIST_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          role: role.trim(),
          firm: firm.trim(),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg =
          typeof data.detail === 'string'
            ? data.detail
            : (data.detail as { message?: string })?.message ||
              `Request failed (${res.status}). Please try again.`;
        throw new Error(msg);
      }
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden relative"
      style={{ backgroundColor: PAPER }}
    >
      <GrainOverlay />
      <CustomCursor />
      {/* Header */}
      <nav className="sticky top-0 z-20 flex items-center justify-between px-6 sm:px-8 lg:px-12 pt-6 sm:pt-8 pb-4 bg-[#F2F0EA]/95 backdrop-blur-sm">
        <Link
          data-cursor-expand
          to="/"
          className="font-display font-normal text-[17px] hover:opacity-80 transition-opacity"
          style={{ color: OXFORD }}
        >
          Aethria
        </Link>
        <Link
          data-cursor-expand
          to="/home"
          className="font-mono text-[10px] uppercase tracking-widest opacity-60 transition-opacity duration-300 hover:opacity-100"
          style={{ color: OXFORD }}
        >
          Home
        </Link>
      </nav>

      {/* Main: 2-column (25% / 75%) on desktop; stacked on mobile (metadata above title on small screens) */}
      <main className="flex-1 flex flex-col lg:flex-row px-6 sm:px-8 lg:px-12 py-10 sm:py-14 lg:py-16 lg:pt-14 gap-10 lg:gap-16 max-w-5xl lg:max-w-none mx-auto w-full">
        {/* Left column: metadata — on mobile stacks above "Request access" title */}
        <aside className="order-1 lg:order-none lg:w-[25%] lg:min-w-[25%] flex flex-col justify-center pt-4 lg:pt-0">
          <p className="font-mono text-[10px] uppercase tracking-widest" style={{ color: OXFORD }}>
            REGISTRY / 2026
          </p>
          <p className="font-mono text-[10px] uppercase tracking-widest mt-3" style={{ color: OXFORD }}>
            EARLY ACCESS
          </p>
        </aside>

        {/* Right column: title + form — title aligned to same vertical rhythm as home headline */}
        <div className="order-2 lg:order-none lg:w-[75%] lg:min-w-0 flex flex-col">
          {!submitted ? (
            <>
              <h1 className="font-display font-normal text-4xl leading-tight mb-8 sm:mb-10" style={{ color: OXFORD }}>
                Request access
              </h1>

              <form onSubmit={handleSubmit} className="flex flex-col">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 sm:gap-x-12 gap-y-8 sm:gap-y-10">
                  <div className="flex flex-col">
                    <label htmlFor="waitlist-name" className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: OXFORD }}>
                      NAME
                    </label>
                    <input
                      id="waitlist-name"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder=""
                      className="w-full bg-transparent font-sans text-lg font-medium py-3 outline-none border-0 border-b border-[rgba(0,33,71,0.1)] focus:border-[#002147] transition-[border-color] duration-[150ms]"
                      style={{ color: OXFORD }}
                      required
                    />
                  </div>
                  <div className="flex flex-col">
                    <label htmlFor="waitlist-email" className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: OXFORD }}>
                      EMAIL
                    </label>
                    <input
                      id="waitlist-email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder=""
                      className="w-full bg-transparent font-sans text-lg font-medium py-3 outline-none border-0 border-b border-[rgba(0,33,71,0.1)] focus:border-[#002147] transition-[border-color] duration-[150ms]"
                      style={{ color: OXFORD }}
                      required
                    />
                  </div>
                  <div className="flex flex-col">
                    <label htmlFor="waitlist-role" className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: OXFORD }}>
                      ROLE
                    </label>
                    <input
                      id="waitlist-role"
                      type="text"
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      placeholder=""
                      className="w-full bg-transparent font-sans text-lg font-medium py-3 outline-none border-0 border-b border-[rgba(0,33,71,0.1)] focus:border-[#002147] transition-[border-color] duration-[150ms]"
                      style={{ color: OXFORD }}
                      required
                    />
                  </div>
                  <div className="flex flex-col">
                    <label htmlFor="waitlist-firm" className="font-mono text-[10px] uppercase tracking-widest mb-1" style={{ color: OXFORD }}>
                      FIRM
                    </label>
                    <input
                      id="waitlist-firm"
                      type="text"
                      value={firm}
                      onChange={(e) => setFirm(e.target.value)}
                      placeholder=""
                      className="w-full bg-transparent font-sans text-lg font-medium py-3 outline-none border-0 border-b border-[rgba(0,33,71,0.1)] focus:border-[#002147] transition-[border-color] duration-[150ms]"
                      style={{ color: OXFORD }}
                      required
                    />
                  </div>
                </div>

                {error && (
                  <p
                    className="mt-6 font-sans text-[13px] font-medium"
                    style={{ color: '#b91c1c' }}
                    role="alert"
                  >
                    {error}
                  </p>
                )}
                <button
                  type="submit"
                  data-cursor-expand
                  disabled={loading}
                  className="mt-10 sm:mt-12 w-full flex items-center justify-center py-4 sm:py-5 rounded-none font-mono text-[10px] uppercase tracking-widest text-white transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed"
                  style={{ backgroundColor: OXFORD }}
                  onMouseEnter={() => setSubmitHover(true)}
                  onMouseLeave={() => setSubmitHover(false)}
                >
                  <span className="flex items-center justify-center">
                    <span>{loading ? 'SUBMITTING…' : 'SUBMIT APPLICATION'}</span>
                    <span
                      className="inline-block overflow-hidden transition-all duration-200 ease-out origin-left flex-shrink-0 whitespace-nowrap"
                      style={{ width: submitHover ? '1.25em' : '0.5em' }}
                    >
                      {'\u00A0—'}
                    </span>
                  </span>
                </button>
              </form>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center text-center py-16 sm:py-24">
              <p
                className="font-display font-normal text-3xl leading-snug max-w-[20ch] mb-8"
                style={{ color: OXFORD }}
              >
                Application Received. Registry entry pending review.
              </p>
              <Link
                to="/home"
                data-cursor-expand
                className="font-mono text-[10px] uppercase tracking-widest hover:opacity-80 transition-opacity inline-block"
                style={{ color: OXFORD }}
              >
                Back to home
              </Link>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="group sticky bottom-0 z-20 flex items-center justify-between px-6 sm:px-8 lg:px-12 py-4 bg-[#F2F0EA]/95 backdrop-blur-sm">
        <span className="font-sans text-[11px] tracking-wide opacity-60 transition-opacity duration-300 group-hover:opacity-100" style={{ color: OXFORD }}>
          © Aethria
        </span>
        <span className="font-mono text-[10px] uppercase tracking-widest opacity-60 transition-opacity duration-300 group-hover:opacity-100" style={{ color: OXFORD }}>
          Investment intelligence
        </span>
      </footer>
    </div>
  );
}
