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

/**
 * Understated editorial CTA — a mono label on a single hairline that widens its
 * arrow gap on hover. The quiet, high-end counterpart to the solid CtaLink.
 */
export function CtaTextLink({ children, className = '', ...props }: LinkProps & { className?: string }) {
  return (
    <Link
      className={`group inline-flex items-center gap-3.5 border-b border-solid border-[var(--color-oxford)] pb-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-oxford)] transition-[gap] duration-300 ease-out hover:gap-6 ${className}`.trim()}
      {...props}
    >
      <span>{children}</span>
      <span aria-hidden>→</span>
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
