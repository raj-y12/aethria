import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import GrainOverlay from './components/GrainOverlay';

const PROCESSING_DURATION_MS = 1200;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const WAITLIST_URL = API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/waitlist` : '/api/waitlist';
const APP_URL = import.meta.env.VITE_APP_URL ?? '';

const OXFORD = '#002147';
const PAPER = '#f2f0ea';

export default function RequestAccessPage() {
  const [submitted, setSubmitted] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState(false);
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
      className="paper-dot-grid relative flex min-h-[100dvh] flex-col overflow-x-hidden"
      style={{ backgroundColor: PAPER, color: 'var(--color-charcoal)' }}
    >
      <GrainOverlay opacity={0.028} variant="light" />

      <header
        className="inst-site-header sticky top-0 z-[50] w-full shrink-0 border-b border-solid border-[var(--section-divider)] bg-[#f2f0ea]"
        style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}
      >
        <div className="page-margin-x flex min-h-[52px] items-center justify-between gap-3 sm:gap-4">
          <Link
            data-cursor-expand
            to="/"
            className="font-wordmark flex min-h-[44px] flex-1 items-center py-2 text-left text-[15px] font-normal normal-case leading-none tracking-normal text-[#002147] transition-opacity hover:opacity-80 sm:flex-none sm:text-[16px]"
          >
            Aethria
          </Link>
          <Link
            data-cursor-expand
            to="/home"
            className="inline-flex min-h-[44px] items-center font-mono text-[9px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.45)] transition-opacity duration-300 hover:text-[#002147]"
          >
            Home
          </Link>
        </div>
      </header>

      <main className="request-content-area page-margin-x flex flex-1 flex-col items-center overflow-auto py-10 md:py-14">
        <div className="flex w-full max-w-2xl flex-col justify-center">
          {!submitted ? (
            <>
              <div className="mb-10 border-l border-solid border-[var(--section-divider)] pl-4 md:mb-12 md:pl-5">
                <p className="section-numeral mb-5">VII</p>
                <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.45)]">
                  Early access · 2026
                </p>
                <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.78)]">
                  Request access
                </p>
                <p className="max-w-xl font-sans text-[15px] leading-[1.7] text-[rgba(0,33,71,0.75)]">
                  Join the waitlist. We&apos;ll reach out when a spot opens.
                </p>
                <p className="mt-2 max-w-xl font-sans text-[15px] leading-[1.7] text-[rgba(0,33,71,0.55)]">
                  We&apos;ll confirm by email. No spam.
                </p>
              </div>

              <div className="transition-opacity duration-200 ease-out" style={{ opacity: formOut ? 0 : 1 }}>
                <form onSubmit={handleSubmit} className="request-form flex flex-col" noValidate>
                  <div className="request-form-grid grid grid-cols-1 gap-y-5 gap-x-8 md:grid-cols-2 md:gap-x-12 md:gap-y-6">
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-name" className="form-label-aethria">
                        Name
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-name"
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          className={`form-input-aethria ${nameEmpty ? 'form-input-aethria-error' : ''}`}
                          autoComplete="name"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-email" className="form-label-aethria">
                        Email
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-email"
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          className={`form-input-aethria ${emailEmpty ? 'form-input-aethria-error' : ''}`}
                          autoComplete="email"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-role" className="form-label-aethria">
                        Role
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-role"
                          type="text"
                          value={role}
                          onChange={(e) => setRole(e.target.value)}
                          className={`form-input-aethria ${roleEmpty ? 'form-input-aethria-error' : ''}`}
                          autoComplete="organization-title"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col">
                      <label htmlFor="waitlist-firm" className="form-label-aethria">
                        Firm
                      </label>
                      <div className="form-input-wrapper">
                        <input
                          id="waitlist-firm"
                          type="text"
                          value={firm}
                          onChange={(e) => setFirm(e.target.value)}
                          className={`form-input-aethria ${firmEmpty ? 'form-input-aethria-error' : ''}`}
                          autoComplete="organization"
                        />
                      </div>
                    </div>
                    <div className="flex flex-col md:col-span-2">
                      <label htmlFor="waitlist-linkedin" className="form-label-aethria">
                        LinkedIn <span className="font-normal opacity-60">(optional)</span>
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
                    <p
                      className="mt-4 font-mono text-[9px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.55)]"
                      role="alert"
                    >
                      Complete name, email, role, and firm
                    </p>
                  )}
                  {error && (
                    <p className="mt-4 font-sans text-[14px] leading-relaxed text-[rgba(0,33,71,0.78)]" role="alert">
                      {error}
                    </p>
                  )}
                  <button
                    type="submit"
                    data-cursor-expand
                    disabled={loading || processing}
                    className="request-submit-btn group mt-8 inline-flex min-h-[44px] w-full cursor-pointer items-center justify-center rounded-none bg-[#002147] px-6 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[#f2f0ea] transition-colors duration-[250ms] ease-out hover:bg-[rgba(0,33,71,0.9)] disabled:cursor-not-allowed disabled:opacity-70 md:mt-10 md:w-fit"
                  >
                    <span className="flex items-center justify-center">
                      <span>
                        {loading
                          ? `SUBMITTING${'.'.repeat(ellipsisStep)}`
                          : processing
                            ? 'PROCESSING ENTRY'
                            : 'SUBMIT APPLICATION'}
                      </span>
                      <span
                        className={`inline-block shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-[250ms] ease-out ${
                          loading || processing ? 'w-6' : 'w-2 group-hover:w-6'
                        }`}
                        aria-hidden
                      >
                        {'\u00A0→'}
                      </span>
                    </span>
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div
              className="mx-auto flex w-full max-w-md flex-col items-center text-center"
              style={{ opacity: showSuccess ? 1 : 0, transition: 'opacity 300ms ease' }}
            >
              <p className="section-numeral mb-6 w-full">VII</p>
              <h1 className="font-display text-[clamp(1.625rem,4.5vw,1.875rem)] font-normal leading-[1.2] tracking-[-0.02em] text-[#002147]">
                You&apos;re on the list.
              </h1>
              <p className="mt-4 max-w-md font-sans text-[15px] leading-[1.7] text-[rgba(0,33,71,0.72)]">
                {position != null
                  ? `Position #${position}. We'll reach out when a spot opens.`
                  : "We'll reach out when a spot opens."}
              </p>
              <svg
                width="48"
                height="48"
                viewBox="0 0 48 48"
                className="mt-6"
                aria-hidden
              >
                <circle
                  cx="24"
                  cy="24"
                  r="21"
                  fill="none"
                  stroke={OXFORD}
                  strokeWidth="1"
                  strokeOpacity="0.15"
                />
                <path
                  d="M15 24.5L21 30.5L33.5 18"
                  fill="none"
                  stroke={OXFORD}
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
                  href={`${APP_URL.replace(/\/$/, '')}/dashboard`}
                  data-cursor-expand
                  className="mt-10 inline-flex min-h-[44px] items-center justify-center border border-solid border-[var(--section-divider)] bg-transparent px-6 font-mono text-[10px] uppercase tracking-[0.12em] text-[#002147] transition-colors duration-200 hover:border-[#002147] hover:bg-[#002147] hover:text-[#f2f0ea]"
                >
                  Proceed to sign in
                </a>
              )}
              <Link
                to="/home"
                data-cursor-expand
                className="mt-8 inline-flex min-h-[44px] items-center font-mono text-[10px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.45)] transition-opacity hover:opacity-100"
              >
                ← Back to home
              </Link>
            </div>
          )}
        </div>
      </main>

      <footer
        className="section-divider-top mt-auto flex shrink-0 flex-col items-start gap-3 border-t border-solid border-[var(--section-divider)] bg-[#f2f0ea] page-margin-x pt-5 pb-[max(1rem,env(safe-area-inset-bottom))] sm:flex-row sm:items-center sm:justify-between sm:gap-0 md:pb-5"
        style={{ color: OXFORD }}
      >
        <span className="font-sans text-[13px] leading-relaxed text-[rgba(0,33,71,0.55)]">
          © {new Date().getFullYear()} Aethria
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.4)]">
          Investment intelligence
        </span>
      </footer>
    </div>
  );
}
