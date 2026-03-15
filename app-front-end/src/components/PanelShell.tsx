import type { ReactNode } from 'react';

export const PANEL_HEADER_CLASS =
  'flex-none flex items-center justify-between px-6 py-4 border-b border-oxford/[0.06]';
export const PANEL_TITLE_CLASS = 'type-label-tab text-oxford/60';
export const PANEL_TAB_BAR_CLASS = 'flex-none flex gap-0 border-b border-oxford/[0.06] px-4';
export const PANEL_TAB_BUTTON_CLASS =
  'py-3 px-3 type-label-tab border-b-2 -mb-px focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset btn-interaction';
export const PANEL_TAB_ACTIVE_CLASS = 'text-oxford border-oxford';
export const PANEL_TAB_INACTIVE_CLASS =
  'text-oxford/60 border-transparent hover:text-oxford';
export const PANEL_CONTENT_CLASS =
  'flex-1 min-h-0 overflow-y-auto p-4 sm:p-6';

export interface PanelTab {
  id: string;
  label: string;
}

interface PanelShellProps {
  title: string;
  actions?: ReactNode;
  tabs?: PanelTab[];
  activeTab?: string;
  onTabChange?: (id: string) => void;
  children: ReactNode;
  /** Use when content handles its own scroll (e.g. memo with fixed height). */
  contentOverflowHidden?: boolean;
  /** Override content padding (e.g. memo px-6 sm:px-8 py-6). */
  contentClassName?: string;
  className?: string;
}

/**
 * Shared panel shell: header strip, optional tab bar, content area.
 * Same header height, border, label style, tab style, and content padding everywhere.
 */
export default function PanelShell({
  title,
  actions,
  tabs,
  activeTab,
  onTabChange,
  children,
  contentOverflowHidden,
  contentClassName,
  className = '',
}: PanelShellProps) {
  const contentCls = contentClassName ?? PANEL_CONTENT_CLASS;
  const overflow = contentOverflowHidden ? 'overflow-hidden' : 'overflow-y-auto';

  return (
    <div className={`flex h-full flex-col min-h-0 ${className}`}>
      <header className={PANEL_HEADER_CLASS}>
        <span className={PANEL_TITLE_CLASS}>{title}</span>
        {actions != null && <div className="flex items-center gap-2">{actions}</div>}
      </header>

      {tabs != null && tabs.length > 0 && (
        <nav className={PANEL_TAB_BAR_CLASS} aria-label="Tabs">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onTabChange?.(tab.id)}
                className={`${PANEL_TAB_BUTTON_CLASS} ${
                  isActive ? PANEL_TAB_ACTIVE_CLASS : PANEL_TAB_INACTIVE_CLASS
                }`}
                aria-selected={isActive}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
      )}

      <div className={`flex-1 min-h-0 ${overflow} ${contentCls}`}>
        {children}
      </div>
    </div>
  );
}
