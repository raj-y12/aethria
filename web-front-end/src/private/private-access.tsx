/**
 * Private access route: loads the app-front-end in an iframe.
 * The app shows its EnterSystemPage (login) first, then the main app.
 *
 * To remove access, delete this file. The /private-access route will disappear at build time.
 *
 * Production (e.g. Vercel): set env var VITE_APP_URL to the deployed app URL
 * (e.g. https://app.yourdomain.com). Build-time only; redeploy after changing.
 */
function getAppUrl(): string {
  const env = import.meta.env.VITE_APP_URL;
  if (typeof env === 'string' && env.trim()) return env.trim();
  if (import.meta.env.DEV) return 'http://localhost:3000';
  return '';
}

const APP_URL = getAppUrl();

export default function PrivateAccess() {
  if (!APP_URL) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#666', maxWidth: '28rem', margin: '0 auto' }}>
        <p>Private app URL not configured.</p>
        <p style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>
          On Vercel: set <strong>VITE_APP_URL</strong> to your app’s URL (e.g. <code>https://app.yourdomain.com</code>), then redeploy.
        </p>
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
