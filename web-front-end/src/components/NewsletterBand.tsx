import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { CtaSubmit } from './CtaButton';

export default function NewsletterBand() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = email.trim();
    if (trimmed) {
      navigate(`/request-access?email=${encodeURIComponent(trimmed)}`);
    } else {
      navigate('/request-access');
    }
  };

  return (
    <section
      className="w-full border-t border-solid border-[var(--section-divider)] bg-[var(--color-paper)]"
      aria-labelledby="newsletter-heading"
    >
      <div className="page-margin-x py-16 md:py-20">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-8 md:flex-row md:items-end md:justify-between md:gap-12">
          <div className="max-w-md">
            <h2
              id="newsletter-heading"
              className="font-display text-[clamp(1.5rem,3vw,2rem)] font-medium leading-[1.15] tracking-[-0.02em] text-[var(--color-oxford)]"
            >
              Private updates from the build.
            </h2>
            <p className="mt-3 font-sans text-[14px] leading-[1.65] text-[var(--text-secondary)]">
              Occasional notes on investment intelligence, product progress, and access.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex w-full max-w-md flex-col gap-4 sm:flex-row sm:items-end">
            <label className="input-underline-field min-w-0 flex-1">
              <span className="sr-only">Email address</span>
              <input
                type="email"
                name="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@firm.com"
                autoComplete="email"
                className="input-underline"
              />
            </label>
            <CtaSubmit className="shrink-0 px-8">Request access</CtaSubmit>
          </form>
        </div>
      </div>
    </section>
  );
}
