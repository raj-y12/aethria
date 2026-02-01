import { ReactNode } from 'react';
import Divider from './Divider';

interface SectionProps {
  children: ReactNode;
  /** Vertical padding. Default: py-16 lg:py-24 */
  spacing?: 'none' | 'sm' | 'md' | 'lg';
  /** Optional divider below. Soft line, not a block. */
  dividerBelow?: boolean;
  className?: string;
}

const spacingMap = {
  none: '',
  sm: 'py-10 lg:py-14',
  md: 'py-16 lg:py-24',
  lg: 'py-20 lg:py-32',
};

/**
 * Vertical rhythm block. No box, no fill. Content breathes.
 */
export default function Section({
  children,
  spacing = 'md',
  dividerBelow = false,
  className = '',
}: SectionProps) {
  return (
    <section className={`${spacingMap[spacing]} ${className}`}>
      {children}
      {dividerBelow && <Divider className="mt-16 lg:mt-24" />}
    </section>
  );
}
