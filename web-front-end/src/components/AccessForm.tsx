import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';

const PROCESSING_DURATION_MS = 1200;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_REGEX = /^https?:\/\/.+/;
const APP_URL = import.meta.env.VITE_APP_URL ?? '';

const EASE_OUT_EXPO = 'cubic-bezier(0.16, 1, 0.3, 1)';
const TRANSITION_FORM_OUT = 'opacity 0.22s ease, transform 0.22s ease';
const TRANSITION_SUCCESS_REVEAL = `opacity 0.55s ${EASE_OUT_EXPO}, transform 0.55s ${EASE_OUT_EXPO}`;

/**
 * The subscription coupon — full application form (name/email/role/firm/linkedin),
 * folded into the footer instead of living on its own /request-access page. Same
 * validation and submit logic as before; inverse-styled for the dark oxford ground.
 */
export default function AccessForm() {
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
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (prefilledEmail) setEmail(prefilledEmail);
  }, [prefilledEmail]);

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

  useEffect(() => () => abortRef.current?.abort(), []);

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
      const res = await fetch('/api/waitlist', {
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

  if (submitted) {
    return (
      <div style={{ opacity: showSuccess ? 1 : 0, transform: showSuccess ? 'translateY(0)' : 'translateY(12px)', transition: TRANSITION_SUCCESS_REVEAL }}>
        <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-brand-mark-inverse)]">
          Entry recorded
        </p>
        <h3 className="mb-4 editorial-display text-[clamp(1.6rem,3vw,2.1rem)] font-normal leading-[1.1] tracking-[-0.02em] text-[var(--text-inverse)]">
          You're on the list.
        </h3>
        <p className="max-w-[42ch] font-sans text-[15px] leading-[1.65] text-[var(--text-inverse-secondary)]">
          {position != null ? (
            <span className="block font-medium text-[var(--text-inverse)]">Position #{position}</span>
          ) : null}
          <span className="mt-1 block">We'll reach out when a spot opens.</span>
        </p>
        {APP_URL && (
          <a
            href={`${APP_URL.replace(/\/$/, '')}/dashboard`}
            className="group mt-8 inline-flex min-h-[44px] items-center justify-center bg-[var(--color-paper)] px-6 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--color-oxford)] transition-colors duration-200 hover:bg-[var(--text-inverse)]"
          >
            <span>Sign in</span>
            <span className="inline-block w-2 shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-200 group-hover:w-6" aria-hidden>{' →'}</span>
          </a>
        )}
      </div>
    );
  }

  return (
    <div style={{ opacity: formOut ? 0 : 1, transform: formOut ? 'translateY(-8px)' : 'translateY(0)', transition: TRANSITION_FORM_OUT }}>
      <div className="relative border border-dashed border-[rgba(244,241,234,0.3)] p-6 sm:p-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6" noValidate>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <InverseField id="af-name" label="Name" type="text" value={name} onChange={setName} error={ne} autoComplete="name" maxLength={100} />
            <InverseField id="af-email" label="Email" type="email" value={email} onChange={setEmail} error={ee} autoComplete="email" maxLength={320} />
          </div>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <InverseField id="af-role" label="Role" type="text" value={role} onChange={setRole} error={re} autoComplete="organization-title" maxLength={100} />
            <InverseField id="af-firm" label="Firm" type="text" value={firm} onChange={setFirm} error={fe} autoComplete="organization" maxLength={200} />
          </div>
          <InverseField
            id="af-linkedin"
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
            <p id="af-validation-error" role="alert" className="font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--text-inverse)]">
              Complete all required fields
            </p>
          )}
          {error && (
            <p role="alert" className="font-sans text-[14px] font-medium leading-relaxed text-[var(--text-inverse)]">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || processing}
            className="cta-submit group mt-1 inline-flex min-h-9 w-full cursor-pointer items-center justify-center bg-[var(--color-paper)] px-10 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-oxford)] transition-colors duration-200 hover:bg-[var(--text-inverse)] disabled:cursor-not-allowed disabled:opacity-55"
          >
            <span>
              {loading ? `Submitting${'.'.repeat(ellipsisStep)}` : processing ? 'Processing' : 'Submit application'}
            </span>
            <span
              className={`inline-block shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-200 ${loading || processing ? 'w-6' : 'w-2 group-hover:w-6'}`}
              aria-hidden
            >
              {' →'}
            </span>
          </button>
        </form>
      </div>
    </div>
  );
}

function InverseField({
  id, label, optional, type, value, onChange, error, autoComplete, maxLength, placeholder,
}: {
  id: string; label: string; optional?: boolean; type: string;
  value: string; onChange: (v: string) => void; error?: boolean;
  autoComplete?: string; maxLength?: number; placeholder?: string;
}) {
  return (
    <div className="flex flex-col">
      <label htmlFor={id} className="font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-inverse-muted)]">
        {label}
        {optional && <span className="ml-1 font-normal normal-case opacity-60 tracking-normal">(optional)</span>}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`mt-2 w-full border-0 border-b border-solid bg-transparent pb-2.5 font-sans text-[15px] text-[var(--text-inverse)] outline-none transition-colors duration-300 placeholder:font-mono placeholder:text-[11px] placeholder:text-[rgba(244,241,234,0.35)] focus:border-[var(--color-brand-mark-inverse)] ${error ? 'border-[#c98d86]' : 'border-[rgba(244,241,234,0.28)]'}`}
        autoComplete={autoComplete}
        maxLength={maxLength}
        required={!optional}
        aria-required={!optional ? 'true' : undefined}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? 'af-validation-error' : undefined}
      />
    </div>
  );
}
