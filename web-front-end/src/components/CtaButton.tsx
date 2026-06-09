import { Link, type LinkProps } from 'react-router-dom';
import type { ButtonHTMLAttributes, ReactNode } from 'react';

const CTA_BASE =
  'cta-button group inline-flex h-9 cursor-pointer items-center justify-center rounded-none bg-[var(--surface-strong)] font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse)]';

function CtaButtonInner({ children }: { children: ReactNode }) {
  return (
    <span className="flex items-center justify-center">
      <span>{children}</span>
      <span className="cta-button-arrow" aria-hidden>
        {'\u00A0→'}
      </span>
    </span>
  );
}

export function CtaLink({ children, className = '', ...props }: LinkProps & { className?: string }) {
  return (
    <Link className={`${CTA_BASE} ${className}`.trim()} {...props}>
      <CtaButtonInner>{children}</CtaButtonInner>
    </Link>
  );
}

export function CtaSubmit({
  children,
  className = '',
  type = 'submit',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { className?: string }) {
  return (
    <button type={type} className={`${CTA_BASE} ${className}`.trim()} {...props}>
      <CtaButtonInner>{children}</CtaButtonInner>
    </button>
  );
}
