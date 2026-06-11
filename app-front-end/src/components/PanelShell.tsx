import type { ReactNode } from 'react';
import { productInteraction, productPanel, productText } from '../design-system/productSystem';

export const PANEL_HEADER_CLASS = `${productPanel.header} justify-between`;
export const PANEL_TITLE_CLASS = productText.mutedLabel;
export const PANEL_TAB_BAR_CLASS =
  'flex-none flex gap-phi-1 px-phi-4 sm:px-phi-5 py-phi-2 bg-surface-canvas';
export const PANEL_TAB_BUTTON_CLASS =
  `py-phi-3 px-phi-3 type-label-tab btn-interaction rounded-none ${productInteraction.quiet}`;
export const PANEL_TAB_ACTIVE_CLASS = productInteraction.selected;
export const PANEL_TAB_INACTIVE_CLASS =
  'text-oxford/[0.42] hover:text-oxford/75 hover:bg-registerTint';
export const PANEL_CONTENT_CLASS =
  'flex-1 min-h-0 overflow-y-auto p-phi-6';

export interface PanelTab {
  id: string;
  label: string;
}

interface PanelShellProps {
  title: string;
  actions?: ReactNode;
  /** Optional complete header body; when provided, replaces the default title/actions row. */
  headerContent?: ReactNode;
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
  /** Optional header edge rule — default none (surface stepping replaces stacked hairlines). */
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
 * Header defaults to canvas/paper surface (matches WorkGrid toolbar); override via headerClassName / headerBorderClass.
 */
export default function PanelShell({
  title,
  actions,
  headerContent,
  tabs,
  activeTab,
  onTabChange,
  children,
  contentOverflowHidden,
  contentClassName,
  className = '',
  headerPaddingClass = '',
  headerBorderClass = '',
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
        className={`${productPanel.header} min-w-0 ${headerPaddingClass} ${headerBorderClass} ${headerJustifyClass} ${headerClassName}`.trim()}
      >
        {headerContent ?? (
          <>
            {showTitle ? <p className={`min-w-0 truncate ${titleCls}`}>{title}</p> : null}
            {actions != null && <div className="ml-auto flex shrink-0 items-start gap-phi-2">{actions}</div>}
          </>
        )}
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
