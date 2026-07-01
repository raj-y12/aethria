import { useState, useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import GrainOverlay from './components/GrainOverlay';
import SiteHeader from './components/SiteHeader';
import DottedMarketMap, { type MapHit } from './components/DottedMarketMap';

const PROCESSING_DURATION_MS = 1200;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_REGEX = /^https?:\/\/.+/;
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const WAITLIST_URL = API_BASE ? `${API_BASE.replace(/\/$/, '')}/api/waitlist` : '/api/waitlist';
const APP_URL = import.meta.env.VITE_APP_URL ?? '';

/** In-thesis companies plotted on the quiet field beside the form. */
const REQ_HITS: MapHit[] = [
  { lon: -122.4, lat: 37.8 },
  { lon: -0.12, lat: 51.5 },
  { lon: 13.4, lat: 52.5 },
];

const EASE_OUT_EXPO = 'cubic-bezier(0.16, 1, 0.3, 1)';
const TRANSITION_PAGE_ENTER = `opacity 0.6s ${EASE_OUT_EXPO}, transform 0.6s ${EASE_OUT_EXPO}`;
const TRANSITION_FORM_OUT = 'opacity 0.22s ease, transform 0.22s ease';
const TRANSITION_SUCCESS_REVEAL = `opacity 0.55s ${EASE_OUT_EXPO}, transform 0.55s ${EASE_OUT_EXPO}`;

const EDITION_DATE = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'long', year: 'numeric' });

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}

export default function RequestAccessPage() {
  const reduce = usePrefersReducedMotion();
  const [searchParams] = useSearchParams();
  const prefilledEmail = searchParams.get('email')?.trim() ?? '';
  const [submitted, setSubmitted] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState(false);
  const [position, setPosition] = useState<number | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState(prefilledEmail);
  const [role, setRole] = useState('');
  const [firm, setFirm] = useState('');
  const [linkedin, setLinkedin] = useState('');
  const [showSuccess, setShowSuccess] = useState(false);
  const [formOut, setFormOut] = useState(false);
  const [ellipsisStep, setEllipsisStep] = useState(0);
  const [mounted, setMounted] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (prefilledEmail) setEmail(prefilledEmail);
  }, [prefilledEmail]);

  useEffect(() => {
    if (reduce) {
      setMounted(true);
      return;
    }
    // Double-rAF: ensures the browser paints opacity:0 before the transition fires
    let r2: number;
    const r1 = requestAnimationFrame(() => { r2 = requestAnimationFrame(() => setMounted(true)); });
    return () => {
      cancelAnimationFrame(r1);
      cancelAnimationFrame(r2);
      abortRef.current?.abort();
    };
  }, [reduce]);

  useEffect(() => {
    if (!processing) return;
    const t = setTimeout(() => { setProcessing(false); setFormOut(true); }, PROCESSING_DURATION_MS);
    return () => clearTimeout(t);
  }, [processing]);

  useEffect(() => {
    if (!formOut) return;
    const t1 = setTimeout(() => setSubmitted(true), 200);
    const t2 = setTimeout(() => setShowSuccess(true), 300);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [formOut]);

  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => setEllipsisStep((p) => (p + 1) % 4), 220);
    return () => clearInterval(interval);
  }, [loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setValidationError(false);
    const n = name.trim(), em = email.trim(), r = role.trim(), f = firm.trim();
    if (!n || !em || !r || !f) { setValidationError(true); return; }
    if (!EMAIL_REGEX.test(em)) { setError('Please enter a valid email address.'); return; }
    const li = linkedin.trim();
    if (li && !URL_REGEX.test(li)) { setError('LinkedIn URL must start with https://'); return; }
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setLoading(true);
    try {
      const res = await fetch(WAITLIST_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortRef.current.signal,
        body: JSON.stringify({ name: n, email: em, role: r, firm: f, linkedin: li || undefined }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = typeof data.detail === 'string' ? data.detail
          : (data.detail as { message?: string })?.message || `Request failed (${res.status}).`;
        throw new Error(msg);
      }
      const resData = await res.json().catch(() => ({}));
      if (resData.position != null) setPosition(resData.position);
      setLoading(false);
      setProcessing(true);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const ne = validationError && !name.trim();
  const ee = validationError && !email.trim();
  const re = validationError && !role.trim();
  const fe = validationError && !firm.trim();

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col"
      style={{ backgroundColor: 'var(--surface-base)' }}
    >
      <GrainOverlay opacity={0.022} variant="light" />

      <SiteHeader backTo={{ href: '/', label: '← Back to home' }} />

      {/* Mini masthead — same voice as the front page, without repeating the full nameplate */}
      <div className="page-margin-x flex items-center justify-between pt-6 font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--text-subtle)]">
        <span>Notices &amp; Classifieds</span>
        <span className="hidden sm:inline">{EDITION_DATE}</span>
        <span>By invitation</span>
      </div>

      {/* Body */}
      <main className="page-margin-x relative z-10 grid flex-1 grid-cols-1 items-start gap-16 py-12 md:grid-cols-2 md:gap-24 md:py-16">
        <div
          className="w-full max-w-[min(100%,32rem)]"
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? 'translateY(0)' : 'translateY(14px)',
            transition: reduce ? 'none' : TRANSITION_PAGE_ENTER,
          }}
        >
          {!submitted ? (
            <div
              style={{
                opacity: formOut ? 0 : 1,
                transform: formOut ? 'translateY(-8px)' : 'translateY(0)',
                transition: reduce ? 'none' : TRANSITION_FORM_OUT,
              }}
            >
              {/* Header */}
              <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">
                Notice of subscriber access
              </p>
              <h1 className="mb-4 editorial-display text-[clamp(2rem,4.6vw,2.9rem)] font-normal leading-[1.05] tracking-[-0.02em] text-[var(--text-primary)]">
                Request access.
              </h1>
              <p className="mb-8 max-w-[42ch] font-sans text-[15px] leading-[1.65] text-[var(--text-secondary)]">
                Complete the coupon below. Seats open in small batches — we'll write when yours is ready.
              </p>

              {/* Subscription coupon — a real print convention: dashed cut-line, tear notch */}
              <div className="relative border border-dashed border-[var(--section-divider)] p-6 sm:p-8">
                <span
                  aria-hidden
                  className="absolute -top-[9px] left-6 bg-[var(--color-paper)] px-2 font-mono text-[9px] uppercase tracking-[0.14em] text-[var(--text-subtle)]"
                >
                  ✂ Cut along dotted line
                </span>

                <form onSubmit={handleSubmit} className="flex flex-col gap-7" noValidate>
                  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                    <Field id="r-name" label="Name" type="text" value={name} onChange={setName} error={ne} autoComplete="name" maxLength={100} />
                    <Field id="r-email" label="Email" type="email" value={email} onChange={setEmail} error={ee} autoComplete="email" maxLength={320} />
                  </div>
                  <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                    <Field id="r-role" label="Role" type="text" value={role} onChange={setRole} error={re} autoComplete="organization-title" maxLength={100} />
                    <Field id="r-firm" label="Firm" type="text" value={firm} onChange={setFirm} error={fe} autoComplete="organization" maxLength={200} />
                  </div>
                  <Field
                    id="r-linkedin"
                    label="LinkedIn"
                    optional
                    type="url"
                    value={linkedin}
                    onChange={setLinkedin}
                    autoComplete="off"
                    maxLength={2000}
                    placeholder="https://linkedin.com/in/..."
                  />

                  {validationError && (
                    <p
                      id="form-validation-error"
                      role="alert"
                      className="font-mono text-[12px] font-medium uppercase tracking-[0.1em] text-[var(--text-primary)]"
                    >
                      Complete all required fields
                    </p>
                  )}
                  {error && (
                    <p role="alert" className="font-sans text-[15px] font-medium leading-relaxed text-[var(--text-primary)]">
                      {error}
                    </p>
                  )}

                  <button
                    type="submit"
                    disabled={loading || processing}
                    className="group mt-1 inline-flex min-h-[46px] w-full cursor-pointer items-center justify-center bg-[var(--surface-strong)] px-6 py-3 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--text-inverse)] transition-colors duration-200 hover:bg-[var(--surface-strong-hover)] disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    <span>
                      {loading ? `Submitting${'.'.repeat(ellipsisStep)}` : processing ? 'Processing' : 'Submit application'}
                    </span>
                    <span
                      className={`inline-block shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-200 ${loading || processing ? 'w-6' : 'w-2 group-hover:w-6'}`}
                      aria-hidden
                    >
                      {' →'}
                    </span>
                  </button>
                </form>
              </div>
            </div>
          ) : (
            /* Success */
            <div
              style={{
                opacity: showSuccess ? 1 : 0,
                transform: showSuccess ? 'translateY(0)' : 'translateY(12px)',
                transition: reduce ? 'none' : TRANSITION_SUCCESS_REVEAL,
              }}
            >
              <p className="mb-3 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">
                Entry recorded
              </p>
              <h2 className="mb-5 editorial-display text-[clamp(2rem,4.6vw,2.9rem)] font-normal leading-[1.05] tracking-[-0.02em] text-[var(--text-primary)]">
                You're on the list.
              </h2>
              <p className="max-w-[42ch] font-sans text-[16px] leading-[1.65] text-[var(--text-secondary)]">
                {position != null ? (
                  <span className="block font-medium text-[var(--text-primary)]">Position #{position}</span>
                ) : null}
                <span className="mt-1 block">We'll reach out when a spot opens.</span>
              </p>
              <div className="mt-10 flex flex-col items-start gap-4">
                {APP_URL && (
                  <a
                    href={`${APP_URL.replace(/\/$/, '')}/dashboard`}
                    className="group inline-flex min-h-[44px] items-center justify-center bg-[var(--surface-strong)] px-6 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--text-inverse)] transition-colors duration-200 hover:bg-[var(--surface-strong-hover)]"
                  >
                    <span>Sign in</span>
                    <span className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-200 group-hover:w-6" aria-hidden>{' →'}</span>
                  </a>
                )}
                <Link
                  to="/"
                  className="inline-flex min-h-[44px] items-center font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-subtle)] transition-opacity hover:text-[var(--text-secondary)]"
                >
                  ← Back to home
                </Link>
              </div>
            </div>
          )}
        </div>

        <aside className="hidden md:flex md:flex-col md:justify-center">
          <p className="mb-5 flex items-center gap-2 border-t border-solid border-[var(--section-divider)] pt-4 font-mono text-[9.5px] uppercase tracking-[0.16em] text-[var(--text-subtle)]">
            <motion.span
              className="h-[5px] w-[5px] shrink-0 rounded-full bg-[var(--color-accent)]"
              animate={reduce ? undefined : { opacity: [1, 0.3, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            />
            Today's edition · what you're joining
          </p>
          <DottedMarketMap hits={REQ_HITS} className="h-[300px] w-full" />
          <p className="mt-8 max-w-[36ch] font-display text-[19px] italic leading-[1.5] text-[var(--text-secondary)]">
            "Every decision arrives with the evidence already attached."
          </p>
        </aside>
      </main>

      {/* Footer */}
      <footer
        className="relative z-10 flex shrink-0 flex-wrap items-center justify-between gap-3 px-6 py-5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-muted)] sm:px-10"
        style={{ borderTop: '1px solid var(--section-divider)' }}
      >
        <span className="text-[var(--text-subtle)]">© {new Date().getFullYear()} Aethria</span>
        <span>Investment intelligence</span>
      </footer>
    </div>
  );
}

function Field({
  id, label, optional, type, value, onChange, error, autoComplete, maxLength, placeholder,
}: {
  id: string; label: string; optional?: boolean; type: string;
  value: string; onChange: (v: string) => void; error?: boolean;
  autoComplete?: string; maxLength?: number; placeholder?: string;
}) {
  return (
    <div className="flex flex-col">
      <label htmlFor={id} className="form-label-aethria">
        {label}
        {optional && <span className="ml-1 font-normal normal-case opacity-45 tracking-normal">(optional)</span>}
      </label>
      <div className="form-input-wrapper">
        <input
          id={id}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`form-input-aethria${error ? ' form-input-aethria-error' : ''}${placeholder ? ' placeholder:font-mono placeholder:text-[11px] placeholder:opacity-60' : ''}`}
          autoComplete={autoComplete}
          maxLength={maxLength}
          required={!optional}
          aria-required={!optional ? 'true' : undefined}
          aria-invalid={error ? 'true' : undefined}
          aria-describedby={error ? 'form-validation-error' : undefined}
        />
      </div>
    </div>
  );
}
