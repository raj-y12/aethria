interface AppFooterProps {
  navLink: { href: string; label: string };
}

const STORAGE_KEY = 'aethria_last_activity';

function handleLogout() {
  localStorage.removeItem(STORAGE_KEY);
  window.location.reload();
}

/**
 * Footer strip: nav link (Settings / Home) and Log out.
 * Same padding as content. Nav = primary; Log out = secondary.
 */
export default function AppFooter({ navLink }: AppFooterProps) {
  return (
    <footer
      className="flex-none flex items-center justify-between h-14 px-6 sm:px-8 lg:px-12 bg-paper"
      role="contentinfo"
      aria-label="Footer"
    >
      <a
        href={navLink.href}
        className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/60 hover:text-oxford transition-colors duration-200 min-h-[44px] flex items-center"
      >
        {navLink.label}
      </a>
      <span className="flex-1 min-w-4" aria-hidden />
      <button
        type="button"
        onClick={handleLogout}
        className="font-mono text-[11px] uppercase tracking-[0.16em] text-oxford/50 hover:text-oxford/80 transition-colors duration-200 min-h-[44px] flex items-center -mr-1"
      >
        Log out
      </button>
    </footer>
  );
}
