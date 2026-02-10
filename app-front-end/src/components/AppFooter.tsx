interface AppFooterProps {
  navLink: { href: string; label: string };
}

function handleLogout() {
  localStorage.removeItem('aethria_last_activity');
  window.location.href = '/';
}

/**
 * Footer strip: nav link (Settings / Home) and Log out. Paper background.
 */
export default function AppFooter({ navLink }: AppFooterProps) {
  return (
    <footer
      className="flex-none flex items-center justify-between h-12 px-6 sm:px-8 lg:px-12 bg-paper"
      role="contentinfo"
      aria-label="Footer"
    >
      <a
        href={navLink.href}
        className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford transition-colors"
      >
        {navLink.label}
      </a>
      <button
        type="button"
        onClick={handleLogout}
        className="font-mono text-[10px] uppercase tracking-[0.22em] text-oxford/60 hover:text-oxford transition-colors"
      >
        Log out
      </button>
    </footer>
  );
}
