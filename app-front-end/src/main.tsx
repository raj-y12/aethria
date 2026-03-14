import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router';
import { ClerkProvider } from '@clerk/react-router';
import './index.css';
import App from './App.tsx';
import { clerkAppearance } from './design-system/clerk-appearance';

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  throw new Error('Add your Clerk Publishable Key to the .env file (VITE_CLERK_PUBLISHABLE_KEY)');
}

/** Single route: App handles all paths (sign-in, redirects, dashboard). */
function ClerkProviderWithRouter() {
  const navigate = useNavigate();
  return (
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      appearance={clerkAppearance}
      signInUrl="/sign-in"
      signInFallbackRedirectUrl="/v1"
      afterSignOutUrl="/sign-in"
      routerReplace={(to) => {
        navigate(to, { replace: true });
      }}
      routerPush={(to) => {
        navigate(to);
      }}
    >
      <Routes>
        <Route path="*" element={<App />} />
      </Routes>
    </ClerkProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ClerkProviderWithRouter />
    </BrowserRouter>
  </React.StrictMode>,
);
