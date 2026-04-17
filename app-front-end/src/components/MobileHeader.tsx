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
      className="flex items-center justify-between px-3 pt-[max(0.625rem,env(safe-area-inset-top))] pb-2 border-b border-hairline bg-oxford"
      aria-label="Navigation"
    >
      <Link
        to="/v1"
        className="font-wordmark text-[20px] font-normal leading-[1.4] text-white hover:opacity-90 btn-interaction"
        aria-label="Aethria"
      >
        Aethria
      </Link>
      <button
        type="button"
        onClick={onMenuToggle}
        className="type-label-tab text-white/70 hover:text-white btn-interaction min-h-[44px] min-w-[44px] flex items-center justify-center"
        aria-controls="mobile-menu"
        id="mobile-menu-button"
      >
        Menu
      </button>
    </header>
  );
}
