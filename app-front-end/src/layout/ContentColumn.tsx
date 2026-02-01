import { ReactNode } from 'react';

interface ContentColumnProps {
  children: ReactNode;
  /** content: 80% (editorial). reading: 42rem. panel: wide instrument layout (feed, judgements). */
  variant?: 'content' | 'reading' | 'panel';
  className?: string;
}

/**
 * Content constraint. Panel = wide for operational feed; 60% only for editorial.
 */
export default function ContentColumn({
  children,
  variant = 'content',
  className = '',
}: ContentColumnProps) {
  const maxW =
    variant === 'reading'
      ? 'max-w-[42rem]'
      : variant === 'panel'
        ? 'max-w-[96%] lg:max-w-7xl xl:max-w-[90rem]'
        : 'max-w-[80%]';
  return (
    <div className={`w-full min-w-0 ${maxW} mx-auto px-4 xs:px-6 sm:px-8 lg:px-12 ${className}`}>
      {children}
    </div>
  );
}
