import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ClerkProvider } from '@clerk/react-router';
import '@fontsource/instrument-sans/400.css';
import '@fontsource/instrument-sans/500.css';
import '@fontsource/instrument-sans/600.css';
import '@fontsource/playfair-display/400.css';
import '@fontsource/playfair-display/500.css';
import '@fontsource/playfair-display/600.css';
import '@fontsource/playfair-display/700.css';
import '@fontsource/space-mono/400.css';
import '@fontsource/space-mono/700.css';
import './index.css';
import '@aethria/product-chrome';
import App from './App.tsx';
import ErrorBoundary from './components/ErrorBoundary';
import { clerkAppearance } from './design-system/clerk-appearance';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Operational data should refresh by default. Immutable queries opt into
      // infinity explicitly through getQueryConfig('STATIC').
      staleTime: 90_000,
      gcTime: 30 * 60_000,
      refetchOnWindowFocus: false,
      refetchOnMount: true,
      refetchOnReconnect: true,
      refetchInterval: false,
      retry: 1,
    },
  },
});

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!PUBLISHABLE_KEY) {
  throw new Error('Add your Clerk Publishable Key to the .env file (VITE_CLERK_PUBLISHABLE_KEY)');
}

/** Single route: App handles all paths (sign-in, redirects, dashboard). */
function ClerkProviderWithRouter() {
  return (
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      appearance={clerkAppearance}
      signInUrl="/sign-in"
      signInFallbackRedirectUrl="/v1"
      afterSignOutUrl="/sign-in"
    >
      <Routes>
        <Route path="*" element={<App />} />
      </Routes>
    </ClerkProvider>
  );
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary label="root">
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ClerkProviderWithRouter />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>,
);
