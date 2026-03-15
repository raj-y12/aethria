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
        className="type-title font-bold text-ivory hover:opacity-90 btn-interaction"
        aria-label="Aethria"
      >
        Aethria
      </Link>
      <button
        type="button"
        onClick={onMenuToggle}
        className="type-label-tab text-ivory/70 hover:text-ivory btn-interaction"
        aria-controls="mobile-menu"
        id="mobile-menu-button"
      >
        Menu
      </button>
    </header>
  );
}
