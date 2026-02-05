import { ReactNode } from 'react';

/**
 * Wraps page content for a subtle enter animation (fade + slight move).
 * Use as the direct wrapper for route elements.
 */
export default function PageTransition({ children }: { children: ReactNode }) {
  return <div className="page-transition-enter">{children}</div>;
}
