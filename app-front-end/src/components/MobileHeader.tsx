import { Link } from 'react-router';

/**
 * Canonical mobile top bar: one height, padding, wordmark, and menu trigger.
 * Used by AppFrame and SettingsPage so nav chrome is identical.
 */
interface MobileHeaderProps {
  isOpen: boolean;
  onMenuToggle: () => void;
  /**
   * Matters awaiting a human ruling. The spine carries this on desktop, but the
   * phone is where a partner checks in — without it, the small screen cannot say
   * that anything needs them.
   */
  pendingEscalations?: number;
  onEscalationsClick?: () => void;
}

export default function MobileHeader({
  isOpen,
  onMenuToggle,
  pendingEscalations = 0,
  onEscalationsClick,
}: MobileHeaderProps) {
  return (
    <header
      className="aethria-mobile-header flex items-center justify-between px-phi-4 pt-[max(var(--space-3),env(safe-area-inset-top))] pb-phi-3 border-b border-hairline bg-oxford"
      aria-label="Navigation"
    >
      <Link
        to="/v1"
        className="font-wordmark text-[20px] font-medium leading-[1.4] text-paper hover:opacity-90 btn-interaction"
        aria-label="Aethria"
      >
        Aethria<span className="wordmark-dot wordmark-dot--inverse">.</span>
      </Link>
      <div className="flex items-center gap-phi-2">
        {pendingEscalations > 0 && onEscalationsClick ? (
          <button
            type="button"
            onClick={onEscalationsClick}
            aria-label={`${pendingEscalations} matters need your ruling`}
            className="type-status flex min-h-[44px] items-center gap-phi-1 px-phi-2 text-escalation-bright btn-interaction"
          >
            Need ruling
            <span className="tabular-nums">{pendingEscalations.toLocaleString()}</span>
          </button>
        ) : null}
      <button
        type="button"
        onClick={onMenuToggle}
        className="aethria-mobile-menu-button type-label-tab text-white/70 hover:text-white btn-interaction min-h-[44px] min-w-[44px] flex items-center justify-center"
        aria-controls="mobile-menu"
        aria-expanded={isOpen}
        id="mobile-menu-button"
        aria-label="Menu"
      >
        <span className="aethria-mobile-menu-glyph" aria-hidden="true">
          <span />
          <span />
        </span>
      </button>
      </div>
    </header>
  );
}
