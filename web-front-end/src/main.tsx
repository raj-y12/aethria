import { ViteReactSSG } from 'vite-react-ssg';
import type { RouteRecord } from 'vite-react-ssg';
import '@fontsource/instrument-sans/400.css';
import '@fontsource/instrument-sans/500.css';
import '@fontsource/instrument-sans/600.css';
import '@fontsource/playfair-display/400.css';
import '@fontsource/playfair-display/500.css';
import '@fontsource/playfair-display/600.css';
import '@fontsource/space-mono/400.css';
import '@fontsource/space-mono/700.css';
import 'lenis/dist/lenis.css';
import './index.css';
import '@aethria/product-chrome';
import App from './App.tsx';

// Single catch-all: App renders our custom AnimatedRoutes, which does its own
// pathname switching (public pages, private-route glob, redirects). SSG only
// prerenders '/' and '/home' (both render HomePage) via includedRoutes in
// vite.config.ts; every other path is handled client-side as before.
export const routes: RouteRecord[] = [{ path: '*', element: <App /> }];

export const createRoot = ViteReactSSG({ routes });
