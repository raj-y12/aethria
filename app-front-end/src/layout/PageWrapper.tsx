import { ReactNode } from 'react';

interface PageWrapperProps {
  children: ReactNode;
  /** Background: ivory (default) or mist. Flows; no harsh blocks. */
  variant?: 'ivory' | 'mist';
  className?: string;
}

/**
 * Full-width page shell. Institutional, restrained.
 * Header, footer, hero, backgrounds stay full width; use ContentColumn for main content.
 */
export default function PageWrapper({
  children,
  variant = 'ivory',
  className = '',
}: PageWrapperProps) {
  const bg = variant === 'mist' ? 'bg-mist' : 'bg-ivory';
  return (
    <div className={`min-h-screen w-full flex flex-col ${bg} text-charcoal antialiased ${className}`}>
      {children}
    </div>
  );
}
