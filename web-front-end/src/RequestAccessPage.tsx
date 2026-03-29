import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import GrainOverlay from './components/GrainOverlay';

const PROCESSING_DURATION_MS = 1200;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const WAITLIST_URL = API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/waitlist` : '/api/waitlist';
const APP_URL = import.meta.env.VITE_APP_URL ?? '';

export default function RequestAccessPage() {
  const [submitted, setSubmitted] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState(false);
  const [submitHover, setSubmitHover] = useState(false);
  const [position, setPosition] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [firm, setFirm] = useState('');
  const [linkedin, setLinkedin] = useState('');
  const [showSuccess, setShowSuccess] = useState(false);
  const [formOut, setFormOut] = useState(false);
  const [ellipsisStep, setEllipsisStep] = useState(0);

  useEffect(() => {
    if (!processing) return;
    const t = setTimeout(() => {
      setProcessing(false);
      setFormOut(true);
    }, PROCESSING_DURATION_MS);
    return () => clearTimeout(t);
  }, [processing]);

  useEffect(() => {
    if (!formOut) return;
    const t1 = setTimeout(() => setSubmitted(true), 200);
    const t2 = setTimeout(() => setShowSuccess(true), 200 + 100);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [formOut]);

  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => {
      setEllipsisStep((prev) => (prev + 1) % 4);
    }, 220);
    return () => clearInterval(interval);
  }, [loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setValidationError(false);
    const trimmedName = name.trim();
    const trimmedEmail = email.trim();
    const trimmedRole = role.trim();
    const trimmedFirm = firm.trim();
    const allFilled = trimmedName && trimmedEmail && trimmedRole && trimmedFirm;
    if (!allFilled) {
      setValidationError(true);
      return;
    }
    if (!EMAIL_REGEX.test(trimmedEmail)) {
      setError('Please enter a valid email address.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(WAITLIST_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: trimmedName,
          email: trimmedEmail,
          role: trimmedRole,
          firm: trimmedFirm,
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
      const resData = await res.json().catch(() => ({}));
      if (resData.position != null) {
        setPosition(resData.position);
      }
      setLoading(false);
      setProcessing(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const nameEmpty = validationError && !name.trim();
  const emailEmpty = validationError && !email.trim();
  const roleEmpty = validationError && !role.trim();
  const firmEmpty = validationError && !firm.trim();

  return (
    <div
      className="min-h-[100dvh] h-[100dvh] overflow-auto overflow-x-hidden flex flex-col relative w-full"
      style={{ backgroundColor: 'var(--color-paper)' }}
    >
      <GrainOverlay opacity={0.02} />

      <header className="site-header-bar flex items-center justify-between page-margin-x pt-[max(1.5rem,env(safe-area-inset-top))] sm:pt-8 pb-4 md:pb-6 shrink-0 z-20">
        <Link
          data-cursor-expand
          to="/"
          className="font-display text-[17px] hover:opacity-80 transition-opacity text-left flex-1 md:flex-none min-h-[44px] flex items-center"
          style={{ color: 'var(--color-oxford)' }}
        >
          Aethria
        </Link>
        <Link
          data-cursor-expand
          to="/home"
          className="font-mono text-[10px] uppercase tracking-[0.1em] opacity-70 inline-flex items-center min-h-[44px] transition-opacity duration-300 hover:opacity-100"
          style={{ color: 'var(--color-oxford)' }}
        >
          Home
        </Link>
      </header>

      <div className="shrink-0 page-margin-x pt-0 pb-1">
        <p className="form-label-aethria mb-0" style={{ color: 'var(--color-oxford)', opacity: 0.5 }}>
          2026 · EARLY ACCESS
        </p>
      </div>

      <main className="request-content-area flex-1 flex items-center justify-center overflow-auto py-8 md:py-12 page-margin-x">
        <div className="w-full max-w-2xl flex flex-col justify-center">
          {!submitted ? (
            <>
              <p
                className="font-mono text-[12px] uppercase tracking-[0.2em] mb-3"
                style={{ color: 'var(--color-oxford)', opacity: 0.75 }}
              >
                REQUEST ACCESS
              </p>
              <p className="font-sans text-[14px] mb-2 leading-relaxed" style={{ color: 'var(--color-oxford)', opacity: 0.6 }}>
                Join the waitlist. We’ll reach out when a spot opens.
              </p>
              <p className="font-sans text-[13px] mb-10" style={{ color: 'var(--color-oxford)', opacity: 0.45 }}>
                We’ll confirm by email. No spam.
              </p>

              <div style={{ opacity: formOut ? 0 : 1, transition: 'opacity 200ms ease' }}>
                <form onSubmit={handleSubmit} className="flex flex-col request-form" noValidate>
                  <div className="grid grid-cols-1 md:grid-cols-2 request-form-grid gap-x-8 md:gap-x-12 gap-y-4 md:gap-y-6">
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-name" className="form-label-aethria">
                        NAME
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-name"
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className={`form-input-aethria ${nameEmpty ? 'form-input-aethria-error' : ''}`}
                        />
                      </div>
                    </div>
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-email" className="form-label-aethria">
                        EMAIL
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-email"
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          className={`form-input-aethria ${emailEmpty ? 'form-input-aethria-error' : ''}`}
                        />
                      </div>
                    </div>
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-role" className="form-label-aethria">
                        ROLE
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-role"
                          type="text"
                          value={role}
                          onChange={(e) => setRole(e.target.value)}
                          className={`form-input-aethria ${roleEmpty ? 'form-input-aethria-error' : ''}`}
                        />
                      </div>
                    </div>
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-firm" className="form-label-aethria">
                        FIRM
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-firm"
                          type="text"
                          value={firm}
                          onChange={(e) => setFirm(e.target.value)}
                          className={`form-input-aethria ${firmEmpty ? 'form-input-aethria-error' : ''}`}
                        />
                      </div>
                    </div>
                    <div className="flex flex-col md:col-span-2">
                      <label htmlFor="waitlist-linkedin" className="form-label-aethria">
                        LINKEDIN <span className="opacity-60 font-normal">(optional)</span>
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-linkedin"
                          type="url"
                          value={linkedin}
                          onChange={(e) => setLinkedin(e.target.value)}
                          placeholder="https://linkedin.com/in/..."
                          className="form-input-aethria placeholder:font-mono placeholder:text-[10px]"
                          autoComplete="off"
                        />
                      </div>
                    </div>
                  </div>

                  {validationError && (
                    <p className="mt-3 font-mono text-[9px] uppercase tracking-[0.1em]" style={{ color: 'var(--color-oxford)', opacity: 0.55 }} role="alert">
                      Complete name, email, role, and firm
                    </p>
                  )}
                  {error && (
                    <p className="mt-4 font-sans text-[13px]" style={{ color: 'var(--color-oxford)', opacity: 0.75 }} role="alert">
                      {error}
                    </p>
                  )}
                  <button
                    type="submit"
                    data-cursor-expand
                    disabled={loading || processing}
                    className="request-submit-btn mt-6 md:mt-8 btn-aethria btn-aethria-solid h-11 disabled:opacity-70 disabled:cursor-not-allowed relative overflow-hidden"
                    onMouseEnter={() => setSubmitHover(true)}
                    onMouseLeave={() => setSubmitHover(false)}
                  >
                    <span
                      className="absolute inset-0"
                      style={{
                        backgroundColor: 'var(--color-paper)',
                        transform: submitHover || loading || processing ? 'translateX(0)' : 'translateX(-100%)',
                        transition: 'transform 300ms ease',
                      }}
                    />
                    <span className="relative flex items-center justify-center">
                      <span>
                        {loading
                          ? `SUBMITTING${'.'.repeat(ellipsisStep)}`
                          : processing
                          ? 'PROCESSING ENTRY'
                          : 'SUBMIT APPLICATION'}
                      </span>
                      <span
                        className="inline-block overflow-hidden transition-all duration-200 ease-out origin-left flex-shrink-0 whitespace-nowrap"
                        style={{ width: loading || processing || submitHover ? '1.25em' : '0.5em' }}
                      >
                        {'\u00A0›'}
                      </span>
                    </span>
                  </button>
                  </form>
                </div>
              </>
            ) : (
            <div
              className="flex flex-col items-center justify-center text-center"
              style={{ opacity: showSuccess ? 1 : 0, transition: 'opacity 300ms ease' }}
            >
              <p
                className="font-display text-[28px]"
                style={{ color: 'var(--color-oxford)', marginBottom: 8 }}
              >
                You&apos;re on the list.
              </p>
              <p
                className="font-sans text-[14px]"
                style={{ color: 'var(--color-oxford)', opacity: 0.65, marginBottom: 16 }}
              >
                {position != null
                  ? `Position #${position}. We'll reach out when a spot opens.`
                  : "We'll reach out when a spot opens."}
              </p>
              <svg
                width="48"
                height="48"
                viewBox="0 0 48 48"
                aria-hidden="true"
                style={{ marginTop: 8 }}
              >
                <circle
                  cx="24"
                  cy="24"
                  r="21"
                  fill="none"
                  stroke="#002147"
                  strokeWidth="1"
                  strokeOpacity="0.18"
                />
                <path
                  d="M15 24.5L21 30.5L33.5 18"
                  fill="none"
                  stroke="#002147"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    strokeDasharray: 40,
                    strokeDashoffset: showSuccess ? 0 : 40,
                    transition: 'stroke-dashoffset 600ms ease',
                  }}
                />
              </svg>
                {APP_URL && (
                  <a
                    href={APP_URL.replace(/\/$/, '') + '/dashboard'}
                    data-cursor-expand
                    className="mt-8 inline-flex items-center justify-center min-h-[44px] px-6 border border-[var(--color-oxford)] text-[var(--color-oxford)] font-mono text-[10px] uppercase tracking-[0.1em] hover:bg-[var(--color-oxford)] hover:text-[var(--color-paper)] transition-colors rounded-none"
                  >
                    Proceed to sign in
                  </a>
                )}
                <Link
                  to="/home"
                  data-cursor-expand
                  className="font-mono text-[10px] uppercase mt-8 inline-flex items-center min-h-[44px] transition-opacity hover:opacity-100"
                  style={{ color: 'var(--color-oxford)', opacity: 0.45 }}
                >
                  ← Back to home
                </Link>
              </div>
            )}
        </div>
      </main>

      <footer
        className="shrink-0 z-20 flex items-center justify-between page-margin-x pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] md:pt-5 md:pb-4 border-t"
        style={{ borderColor: 'rgba(0, 33, 71, 0.06)', color: 'var(--color-oxford)', backgroundColor: 'var(--color-paper)' }}
      >
        <span className="font-sans text-[10px] md:text-[11px] tracking-wide" style={{ color: 'var(--color-oxford)', opacity: 0.65 }}>
          © Aethria
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.15em]" style={{ color: 'var(--color-oxford)', opacity: 0.5 }}>
          INVESTMENT INTELLIGENCE
        </span>
      </footer>
    </div>
  );
}
