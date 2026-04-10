import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import GrainOverlay from './components/GrainOverlay';
import DeskClock from './components/DeskClock';

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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(t);
  }, []);

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
    const t2 = setTimeout(() => setShowSuccess(true), 300);
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
      if (resData.position != null) setPosition(resData.position);
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
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: PAPER }}
    >
      <header
        className="inst-site-header sticky top-0 z-[100] w-full shrink-0 border-b border-solid border-[var(--section-divider)] bg-[#f2f0ea]"
        style={{ paddingTop: 'max(0px, env(safe-area-inset-top))' }}
      >
        <div className="page-margin-x grid min-h-[52px] grid-cols-[1fr_1fr] items-center gap-2 sm:gap-4 md:grid-cols-[1fr_auto_1fr]">
          <Link
            data-cursor-expand
            to="/"
            className="font-wordmark justify-self-start py-2 text-[15px] font-normal normal-case leading-none tracking-normal text-[#002147] transition-opacity hover:opacity-80 sm:text-[16px]"
          >
            Aethria
          </Link>
          <p className="hidden justify-self-center text-center font-mono text-[9px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.35)] md:block">
            Deal flow operating system
          </p>
          <DeskClock className="min-w-0 justify-self-end text-right" />
        </div>
      </header>

      <div className="flex flex-1 flex-col overflow-x-hidden lg:flex-row">
      {/* ── Left: Oxford monolith ─────────────────────────────────────── */}
      <div
        className="relative flex w-full shrink-0 flex-col justify-center overflow-hidden px-8 py-12 sm:px-12 sm:py-16 lg:sticky lg:top-[53px] lg:h-[calc(100dvh-53px)] lg:w-[42%] lg:px-14 lg:py-16"
        style={{ backgroundColor: OXFORD }}
      >
        <GrainOverlay opacity={0.032} variant="dark" />

        {/* Centre: editorial headline */}
        <div
          className="relative z-10 my-12 lg:my-0"
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(20px)',
            transition: 'opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1)',
          }}
        >
          <h1
            className="home-monolith-headline mb-5 text-[clamp(1.5rem,3vw,2rem)] leading-[1.15] text-[#f2f0ea]"
          >
            The deal pipeline,{' '}
            <em style={{ fontStyle: 'italic', color: 'rgba(242,240,234,0.55)' }}>automated.</em>
          </h1>
          <p className="max-w-[34ch] font-sans text-[13px] leading-[1.7] text-[rgba(242,240,234,0.45)]">
            Autonomous discovery, structured review, and partner-ready memos — before the committee opens the file.
          </p>
        </div>

        <p className="relative z-10 mt-8 font-mono text-[9px] uppercase tracking-[0.14em] text-[rgba(242,240,234,0.22)]">
          Early access · 2026
        </p>
      </div>

      {/* ── Right: form panel ─────────────────────────────────────────── */}
      <div
        className="paper-dot-grid relative flex flex-1 flex-col"
        style={{ backgroundColor: PAPER }}
      >
        <GrainOverlay opacity={0.022} variant="light" />

        <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-8 py-12 sm:px-12 sm:py-16 lg:px-16 lg:py-20">
          <div className="w-full max-w-[26rem]">
            {!submitted ? (
              <div
                style={{
                  opacity: formOut ? 0 : mounted ? 1 : 0,
                  transform: formOut ? 'translateY(-8px)' : 'translateY(0)',
                  transition: 'opacity 0.25s ease, transform 0.25s ease',
                }}
              >
                {/* Form header */}
                <div className="mb-10">
                  <p className="mb-3 font-mono text-[9px] uppercase tracking-[0.16em] text-[rgba(0,33,71,0.35)]">
                    Access request
                  </p>
                  <p className="font-sans text-[15px] leading-[1.7] text-[rgba(0,33,71,0.62)]">
                    Join the waitlist. We'll reach out when a spot opens — no spam.
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col gap-7" noValidate>
                  {/* Name + Email */}
                  <div className="grid grid-cols-1 gap-7 sm:grid-cols-2">
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
                  </div>

                  {/* Role + Firm */}
                  <div className="grid grid-cols-1 gap-7 sm:grid-cols-2">
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
                  </div>

                  {/* LinkedIn */}
                  <div className="flex flex-col">
                    <label htmlFor="waitlist-linkedin" className="form-label-aethria">
                      LinkedIn{' '}
                      <span className="font-normal opacity-55">(optional)</span>
                    </label>
                    <div className="form-input-wrapper">
                      <input
                        id="waitlist-linkedin"
                        type="url"
                        value={linkedin}
                        onChange={(e) => setLinkedin(e.target.value)}
                        placeholder="https://linkedin.com/in/..."
                        className="form-input-aethria placeholder:font-mono placeholder:text-[10px] placeholder:opacity-40"
                        autoComplete="off"
                      />
                    </div>
                  </div>

                  {/* Errors */}
                  {validationError && (
                    <p
                      className="font-mono text-[9px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.5)]"
                      role="alert"
                    >
                      Complete name, email, role, and firm
                    </p>
                  )}
                  {error && (
                    <p
                      className="font-sans text-[13px] leading-relaxed text-[rgba(0,33,71,0.72)]"
                      role="alert"
                    >
                      {error}
                    </p>
                  )}

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={loading || processing}
                    className="group mt-1 inline-flex min-h-[46px] w-full cursor-pointer items-center justify-center rounded-none bg-[#002147] px-6 py-3 font-mono text-[11px] uppercase tracking-[0.14em] text-[#f2f0ea] transition-colors duration-[250ms] ease-out hover:bg-[rgba(0,33,71,0.88)] disabled:cursor-not-allowed disabled:opacity-65"
                  >
                    <span className="flex items-center justify-center gap-0">
                      <span>
                        {loading
                          ? `Submitting${'.'.repeat(ellipsisStep)}`
                          : processing
                            ? 'Processing entry'
                            : 'Submit application'}
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
            ) : (
              /* ── Success state ──────────────────────────────────────── */
              <div
                className="flex flex-col items-start"
                style={{
                  opacity: showSuccess ? 1 : 0,
                  transform: showSuccess ? 'translateY(0)' : 'translateY(12px)',
                  transition: 'opacity 0.55s cubic-bezier(0.16,1,0.3,1), transform 0.55s cubic-bezier(0.16,1,0.3,1)',
                }}
              >
                <p className="mb-2 font-mono text-[9px] uppercase tracking-[0.16em] text-[rgba(0,33,71,0.35)]">
                  Entry recorded
                </p>
                <h2
                  className="mb-5 font-display text-[clamp(1.5rem,3vw,1.875rem)] font-normal leading-[1.15] tracking-[-0.02em] text-[#002147]"
                >
                  You're on the list.
                </h2>

                <p className="max-w-[30ch] font-sans text-[13px] leading-[1.75] text-[rgba(0,33,71,0.55)]">
                  {position != null
                    ? `Position #${position}. We'll reach out when a spot opens.`
                    : "We'll reach out when a spot opens."}
                </p>

                <div className="mt-10 flex flex-col items-start gap-4">
                  {APP_URL && (
                    <a
                      href={`${APP_URL.replace(/\/$/, '')}/dashboard`}
                      className="inline-flex min-h-[44px] items-center justify-center border border-[rgba(0,33,71,0.2)] bg-transparent px-6 font-mono text-[10px] uppercase tracking-[0.12em] text-[#002147] transition-colors duration-200 hover:border-[#002147] hover:bg-[#002147] hover:text-[#f2f0ea]"
                    >
                      Proceed to sign in →
                    </a>
                  )}
                  <Link
                    to="/home"
                    className="font-mono text-[9px] uppercase tracking-[0.14em] text-[rgba(0,33,71,0.38)] transition-opacity hover:text-[rgba(0,33,71,0.7)]"
                  >
                    ← Back to home
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Bottom rule */}
        <div
          className="relative z-10 flex shrink-0 items-center justify-between px-8 py-4 sm:px-12 lg:px-16"
          style={{ borderTop: '1px solid var(--section-divider)' }}
        >
          <span className="font-sans text-[12px] text-[rgba(0,33,71,0.38)]">
            © {new Date().getFullYear()} Aethria
          </span>
          <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[rgba(0,33,71,0.25)]">
            Investment intelligence
          </span>
        </div>
      </div>
      </div>
    </div>
  );
}
