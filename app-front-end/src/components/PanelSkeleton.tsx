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
  return <div className={`skeleton-shimmer rounded-none ${className}`} />;
}

export function WorkGridSkeleton() {
  return (
    <div className="w-full px-4 sm:px-6 lg:px-10 pt-2 pb-6 lg:pb-8 space-y-3">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="border border-oxford/[0.06] p-4 flex gap-4">
          <SkeletonBlock className="w-12 h-12 shrink-0" />
          <div className="flex-1 min-w-0 space-y-2">
            <SkeletonLine className="w-3/4 max-w-[200px]" />
            <SkeletonLine className="w-1/2 max-w-[120px]" />
          </div>
          <SkeletonBlock className="w-16 h-5 shrink-0" />
        </div>
      ))}
    </div>
  );
}

export function LiveFeedSkeleton() {
  return (
    <div className="p-3 sm:p-4 space-y-2">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div key={i} className="flex gap-3 items-center">
          <SkeletonLine className="w-12 shrink-0" />
          <SkeletonLine className="flex-1 max-w-full" />
        </div>
      ))}
    </div>
  );
}

export function SystemIntelligenceSkeleton() {
  return (
    <div className="p-4 space-y-6">
      <div className="flex gap-2">
        {[1, 2, 3].map((i) => (
          <SkeletonBlock key={i} className="h-8 w-20" />
        ))}
      </div>
      <div className="space-y-3">
        <SkeletonLine className="w-32" />
        <SkeletonLine className="w-full" />
        <SkeletonLine className="w-5/6" />
        <SkeletonBlock className="h-20 w-full mt-4" />
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
