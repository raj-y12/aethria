import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import GrainOverlay from './components/GrainOverlay';
import CustomCursor from './components/CustomCursor';

const OXFORD = '#002147';
const PAPER = '#F2F0EA';
const PROCESSING_DURATION_MS = 1200;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Use external backend when VITE_API_URL is set (local dev with run.py); otherwise use Vercel serverless /api/waitlist
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const WAITLIST_URL = API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/waitlist` : '/api/waitlist';

const labelClass = 'font-mono text-[10px] uppercase tracking-widest opacity-70';
const inputClass =
  'w-full bg-transparent font-sans text-base md:text-lg font-medium py-2 md:py-2.5 outline-none border-0 border-b border-[rgba(0,33,71,0.15)] focus:border-[#002147] transition-[border-color] duration-[150ms]';

export default function RequestAccessPage() {
  const [submitted, setSubmitted] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitHover, setSubmitHover] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [firm, setFirm] = useState('');
  const [linkedin, setLinkedin] = useState('');

  useEffect(() => {
    if (!processing) return;
    const t = setTimeout(() => {
      setProcessing(false);
      setSubmitted(true);
    }, PROCESSING_DURATION_MS);
    return () => clearTimeout(t);
  }, [processing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmedEmail = email.trim();
    if (!EMAIL_REGEX.test(trimmedEmail)) {
      setError('Please enter a valid email address.');
      return;
    }
    if (!name.trim() || !role.trim() || !firm.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(WAITLIST_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          email: trimmedEmail,
          role: role.trim(),
          firm: firm.trim(),
          linkedin: linkedin.trim() || undefined,
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
      setLoading(false);
      setProcessing(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="min-h-[100dvh] h-[100dvh] overflow-hidden flex flex-col relative"
      style={{ backgroundColor: PAPER }}
    >
      <GrainOverlay opacity={0.02} />
      <CustomCursor />

      {/* Header — compact */}
      <nav className="shrink-0 z-20 flex items-center justify-between px-4 py-3 md:px-6 md:py-4">
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
          className={`${labelClass} transition-opacity duration-300 hover:opacity-100`}
          style={{ color: OXFORD }}
        >
          Home
        </Link>
      </nav>

      {/* Main — centered fixed canvas */}
      <main className="flex-1 flex items-center justify-center overflow-hidden px-4 py-4 md:px-8 md:py-6">
        <div className="w-full max-w-5xl flex flex-col md:flex-row items-center justify-center gap-6 md:gap-12 lg:gap-16">
          {/* Left: metadata pinned left, vertically centered with form */}
          <aside className="hidden md:flex flex-col justify-center md:w-[25%] md:min-w-[25%]">
            <p className={labelClass} style={{ color: OXFORD }}>
              REGISTRY / 2026
            </p>
            <p className={`${labelClass} mt-2`} style={{ color: OXFORD }}>
              EARLY ACCESS
            </p>
          </aside>

          {/* Right: form or success */}
          <div className="w-full md:w-[75%] md:min-w-0 flex flex-col justify-center">
            {!submitted ? (
              <>
                {/* Metadata on mobile — above title */}
                <div className="md:hidden mb-2">
                  <p className={labelClass} style={{ color: OXFORD }}>
                    REGISTRY / 2026 · EARLY ACCESS
                  </p>
                </div>

                <h1
                  className="font-display font-normal text-3xl md:text-4xl leading-tight mb-5 md:mb-7"
                  style={{ color: OXFORD }}
                >
                  Request access
                </h1>

                <div className={processing ? 'opacity-50 transition-opacity duration-300' : undefined}>
                  <form onSubmit={handleSubmit} className="flex flex-col">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 md:gap-x-12 gap-y-5 md:gap-y-6">
                      <div className="flex flex-col">
                        <label htmlFor="waitlist-name" className={`${labelClass} mb-0.5`} style={{ color: OXFORD }}>
                          NAME *
                        </label>
                        <input
                          id="waitlist-name"
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className={inputClass}
                          style={{ color: OXFORD }}
                          required
                        />
                      </div>
                      <div className="flex flex-col">
                        <label htmlFor="waitlist-email" className={`${labelClass} mb-0.5`} style={{ color: OXFORD }}>
                          EMAIL *
                        </label>
                        <input
                          id="waitlist-email"
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          className={inputClass}
                          style={{ color: OXFORD }}
                          required
                        />
                      </div>
                      <div className="flex flex-col">
                        <label htmlFor="waitlist-role" className={`${labelClass} mb-0.5`} style={{ color: OXFORD }}>
                          ROLE *
                        </label>
                        <input
                          id="waitlist-role"
                          type="text"
                          value={role}
                          onChange={(e) => setRole(e.target.value)}
                          className={inputClass}
                          style={{ color: OXFORD }}
                          required
                        />
                      </div>
                      <div className="flex flex-col">
                        <label htmlFor="waitlist-firm" className={`${labelClass} mb-0.5`} style={{ color: OXFORD }}>
                          FIRM *
                        </label>
                        <input
                          id="waitlist-firm"
                          type="text"
                          value={firm}
                          onChange={(e) => setFirm(e.target.value)}
                          className={inputClass}
                          style={{ color: OXFORD }}
                          required
                        />
                      </div>
                      <div className="flex flex-col md:col-span-2">
                        <label htmlFor="waitlist-linkedin" className={`${labelClass} mb-0.5`} style={{ color: OXFORD }}>
                          LINKEDIN <span className="opacity-60 font-normal">(optional)</span>
                        </label>
                        <input
                          id="waitlist-linkedin"
                          type="url"
                          value={linkedin}
                          onChange={(e) => setLinkedin(e.target.value)}
                          placeholder="https://linkedin.com/in/..."
                          className={`${inputClass} placeholder:font-mono placeholder:text-[10px]`}
                          style={{ color: OXFORD }}
                        />
                      </div>
                    </div>

                    {error && (
                      <p
                        className="mt-4 font-sans text-[13px] font-medium"
                        style={{ color: '#b91c1c' }}
                        role="alert"
                      >
                        {error}
                      </p>
                    )}
                    <button
                      type="submit"
                      data-cursor-expand
                      disabled={loading || processing}
                      className="mt-6 md:mt-8 w-full flex items-center justify-center py-3.5 md:py-4 rounded-none font-mono text-[10px] uppercase tracking-widest text-white transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed"
                      style={{ backgroundColor: OXFORD }}
                      onMouseEnter={() => setSubmitHover(true)}
                      onMouseLeave={() => setSubmitHover(false)}
                    >
                      <span className="flex items-center justify-center">
                        <span>
                          {loading ? 'SUBMITTING…' : processing ? 'PROCESSING ENTRY' : 'SUBMIT APPLICATION'}
                        </span>
                        <span
                          className="inline-block overflow-hidden transition-all duration-200 ease-out origin-left flex-shrink-0 whitespace-nowrap"
                          style={{ width: loading || processing || submitHover ? '1.25em' : '0.5em' }}
                        >
                          {'\u00A0—'}
                        </span>
                      </span>
                    </button>
                  </form>
                </div>
              </>
            ) : (
              <div className="flex flex-col text-left">
                <p
                  className="font-display font-normal text-2xl md:text-3xl leading-snug max-w-[20ch] mb-6 md:mb-8"
                  style={{ color: OXFORD }}
                >
                  Application Received. Registry entry pending review.
                </p>
                <Link
                  to="/home"
                  data-cursor-expand
                  className={`${labelClass} hover:opacity-100 transition-opacity inline-block`}
                  style={{ color: OXFORD }}
                >
                  BACK TO HOME
                </Link>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Footer — compact */}
      <footer className="shrink-0 z-20 flex items-center justify-between px-4 pt-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom,0px))] md:px-6 md:pt-3 md:pb-[max(0.75rem,env(safe-area-inset-bottom,0px))]">
        <span
          className="font-sans text-[10px] md:text-[11px] tracking-wide opacity-70 transition-opacity duration-300 hover:opacity-100"
          style={{ color: OXFORD }}
        >
          © Aethria
        </span>
        <span
          className={`${labelClass} transition-opacity duration-300 hover:opacity-100`}
          style={{ color: OXFORD }}
        >
          Investment intelligence
        </span>
      </footer>
    </div>
  );
}
