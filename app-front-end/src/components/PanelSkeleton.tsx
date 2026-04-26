/**
 * Panel-level skeleton loaders. Shimmer placeholder blocks constrained to each panel's layout.
 * Used when app chrome is present and only the panel data is loading (not the global loader).
 */

type Variant = 'workgrid' | 'feed' | 'system';

interface PanelSkeletonProps {
  variant: Variant;
}

function SkeletonLine({ className = '' }: { className?: string }) {
  return <div className={`h-3 skeleton-shimmer rounded-none ${className}`} />;
}

function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`skeleton-shimmer ${className}`} />;
}

export function WorkGridSkeleton() {
  return (
    <div className="w-full space-y-4 px-0 pt-3 pb-8 lg:pb-9">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="flex gap-5 border border-hairline bg-paper p-5">
          <SkeletonBlock className="w-12 h-12 shrink-0 rounded-full" />
          <div className="flex-1 min-w-0 space-y-3">
            <SkeletonLine className="w-3/4 max-w-[200px]" />
            <SkeletonLine className="w-1/2 max-w-[120px]" />
          </div>
          <SkeletonBlock className="w-16 h-5 shrink-0 rounded-none" />
        </div>
      ))}
    </div>
  );
}

export function LiveFeedSkeleton() {
  return (
    <div className="space-y-3 p-5 sm:p-6">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="flex gap-4 items-center">
          <SkeletonLine className="w-12 shrink-0" />
          <SkeletonLine className="flex-1 max-w-full" />
        </div>
      ))}
    </div>
  );
}

export function SystemIntelligenceSkeleton() {
  return (
    <div className="space-y-7 p-5 sm:p-6">
      <div className="flex gap-3">
        {[1, 2, 3].map((i) => (
          <SkeletonBlock key={i} className="h-8 w-20 rounded-none" />
        ))}
      </div>
      <div className="space-y-4">
        <SkeletonLine className="w-32" />
        <SkeletonLine className="w-full" />
        <SkeletonLine className="w-5/6" />
        <SkeletonBlock className="h-20 w-full mt-4 rounded-none" />
      </div>
    </div>
  );
}

export default function PanelSkeleton({ variant }: PanelSkeletonProps) {
  if (variant === 'workgrid') return <WorkGridSkeleton />;
  if (variant === 'feed') return <LiveFeedSkeleton />;
  if (variant === 'system') return <SystemIntelligenceSkeleton />;
  return null;
}
