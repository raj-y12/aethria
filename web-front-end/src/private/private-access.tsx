/**
 * Private access route: loads the app-front-end in an iframe.
 * The app shows its EnterSystemPage (login) first, then the main app.
 *
 * To remove access, delete this file. The /private-access route will disappear at build time.
 */
const APP_URL =
  typeof import.meta.env.VITE_APP_URL === 'string' && import.meta.env.VITE_APP_URL
    ? import.meta.env.VITE_APP_URL
    : import.meta.env.DEV
      ? 'http://localhost:3000'
      : '';

export default function PrivateAccess() {
  if (!APP_URL) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>
        Private app URL not configured (set VITE_APP_URL).
      </div>
    );
  }

  const appUrl = APP_URL.includes('?') ? `${APP_URL}&forceLogin=1` : `${APP_URL}?forceLogin=1`;

  return (
    <iframe
      title="Aethria App"
      src={appUrl}
      style={{
        position: 'fixed',
        inset: 0,
        width: '100%',
        height: '100%',
        border: 'none',
      }}
    />
  );
}
