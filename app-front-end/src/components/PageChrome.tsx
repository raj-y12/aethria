import { type ReactNode } from 'react';
import { Link, useLocation } from 'react-router';
import GrainOverlay from './GrainOverlay';
import { railEditorial } from '../design-system/railEditorial';

export interface PageChromeProps {
  title: string;
  kicker?: string;
  children: ReactNode;
}

const NAV: Array<{ href: string; label: string }> = [
  { href: '/v1', label: 'Workspace' },
  { href: '/v1/portfolio', label: 'Portfolio' },
  { href: '/v1/intelligence', label: 'Intelligence' },
  { href: '/v1/settings', label: 'Settings' },
];

/**
 * Full-page chrome for the addressable routes (Portfolio, Intelligence).
 * These were buried behind a right-panel toggle; promoting them to real pages
 * gives the system's most differentiated output room to breathe and a URL.
 */
export default function PageChrome({ title, kicker, children }: PageChromeProps) {
  const { pathname } = useLocation();

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-paper">
      <GrainOverlay opacity={0.028} />
      <header className="flex flex-none items-center gap-phi-5 border-b border-oxford/[0.08] px-phi-5 py-phi-3">
        <p className={railEditorial.wordmark}>
          Aethria<span className="wordmark-dot">.</span>
        </p>
        <nav aria-label="Primary" className="flex items-center gap-phi-4">
          {NAV.map((item) => {
            const active =
              item.href === '/v1'
                ? pathname === '/v1' || pathname.startsWith('/v1/deal')
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                to={item.href}
                aria-current={active ? 'page' : undefined}
                className={`type-label-tab min-h-[36px] inline-flex items-center px-1 transition-colors btn-interaction ${
                  active ? 'text-oxford' : 'text-oxford/45 hover:text-oxford/80'
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto w-full max-w-[1180px] px-phi-5 py-phi-5">
          <div className="mb-phi-4">
            {kicker ? <p className={railEditorial.label}>{kicker}</p> : null}
            <h1 className="type-title font-semibold text-oxford">{title}</h1>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
