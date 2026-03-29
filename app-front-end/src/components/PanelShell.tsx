import type { ReactNode } from 'react';

export const PANEL_HEADER_CLASS =
  'flex-none flex items-center justify-between px-4 py-3 sm:px-5 sm:py-3 border-b border-oxford/[0.06]';
export const PANEL_TITLE_CLASS = 'type-label-tab text-oxford/60';
export const PANEL_TAB_BAR_CLASS = 'flex-none flex gap-0 border-b border-oxford/[0.06] px-3 sm:px-4';
export const PANEL_TAB_BUTTON_CLASS =
  'py-2.5 px-3 type-label-tab border-b border-transparent -mb-px focus:outline-none focus-visible:ring-2 focus-visible:ring-oxford/40 focus-visible:ring-inset btn-interaction';
export const PANEL_TAB_ACTIVE_CLASS = 'text-oxford border-oxford';
export const PANEL_TAB_INACTIVE_CLASS =
  'text-oxford/60 border-transparent hover:text-oxford hover:border-oxford/20';
export const PANEL_CONTENT_CLASS =
  'flex-1 min-h-0 overflow-y-auto p-4 sm:p-5';

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
  /** Default py-4. */
  headerPaddingClass?: string;
  /** Default border-b border-oxford/[0.06]. Pass "" to remove bottom border. */
  headerBorderClass?: string;
  /** Default justify-between. */
  headerJustifyClass?: string;
  /** When false, header shows actions only (e.g. memo chrome). */
  showTitle?: boolean;
  /** Overrides PANEL_TITLE_CLASS for the title span. */
  titleClassName?: string;
  /** Extra classes on the header element. */
  headerClassName?: string;
  /** When tabs are used, override tab nav / button classes (defaults match System-style strip). */
  tabNavClassName?: string;
  tabButtonClassName?: string;
  tabActiveClassName?: string;
  tabInactiveClassName?: string;
}

/**
 * Shared panel shell: header strip, optional tab bar, content area.
 * Default header uses py-4 and bottom border; override per panel via header* / showTitle props.
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
  headerPaddingClass = 'py-3',
  headerBorderClass = 'border-b border-oxford/[0.06]',
  headerJustifyClass = 'justify-between',
  showTitle = true,
  titleClassName,
  headerClassName = '',
  tabNavClassName,
  tabButtonClassName = PANEL_TAB_BUTTON_CLASS,
  tabActiveClassName = PANEL_TAB_ACTIVE_CLASS,
  tabInactiveClassName = PANEL_TAB_INACTIVE_CLASS,
}: PanelShellProps) {
  const contentCls = contentClassName ?? PANEL_CONTENT_CLASS;
  const overflow = contentOverflowHidden ? 'overflow-hidden' : 'overflow-y-auto';
  const titleCls = titleClassName ?? PANEL_TITLE_CLASS;

  return (
    <div className={`flex h-full flex-col min-h-0 ${className}`}>
      <header
        className={`flex-none flex items-center px-4 sm:px-5 ${headerPaddingClass} ${headerBorderClass} ${headerJustifyClass} ${headerClassName}`.trim()}
      >
        {showTitle ? <span className={titleCls}>{title}</span> : null}
        {actions != null && <div className="flex items-center gap-2">{actions}</div>}
      </header>

      {tabs != null && tabs.length > 0 && (
        <nav className={tabNavClassName ?? PANEL_TAB_BAR_CLASS} aria-label="Tabs">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onTabChange?.(tab.id)}
                className={`${tabButtonClassName} ${
                  isActive ? tabActiveClassName : tabInactiveClassName
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
