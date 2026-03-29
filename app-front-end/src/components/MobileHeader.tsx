import { Link } from 'react-router';

/**
 * Canonical mobile top bar: one height, padding, wordmark, and menu trigger.
 * Used by MainLayout and SettingsPage so nav chrome is identical.
 */
interface MobileHeaderProps {
  onMenuToggle: () => void;
}

export default function MobileHeader({ onMenuToggle }: MobileHeaderProps) {
  return (
    <header
      className="flex items-center justify-between px-4 pt-[max(1.25rem,env(safe-area-inset-top))] pb-3 border-b border-oxford/[0.06] bg-oxford"
      aria-label="Navigation"
    >
      <Link
        to="/v1"
        className="font-display text-[24px] font-normal leading-[1.4] text-white hover:opacity-90 btn-interaction"
        aria-label="Aethria"
      >
        Aethria
      </Link>
      <button
        type="button"
        onClick={onMenuToggle}
        className="type-label-tab text-white/70 hover:text-white btn-interaction"
        aria-controls="mobile-menu"
        id="mobile-menu-button"
      >
        Menu
      </button>
    </header>
  );
}
