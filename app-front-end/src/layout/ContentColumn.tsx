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
        ? 'max-w-[1800px]'
        : 'max-w-[80%]';
  return (
    <div className={`w-full min-w-0 ${maxW} mx-auto px-5 sm:px-8 lg:px-10 ${className}`}>
      {children}
    </div>
  );
}
