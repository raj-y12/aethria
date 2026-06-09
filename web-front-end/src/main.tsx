import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import Lenis from 'lenis';
import '@fontsource/instrument-sans/400.css';
import '@fontsource/instrument-sans/500.css';
import '@fontsource/instrument-sans/600.css';
import '@fontsource/instrument-sans/700.css';
import '@fontsource/playfair-display/400.css';
import '@fontsource/playfair-display/500.css';
import '@fontsource/playfair-display/600.css';
import '@fontsource/space-mono/400.css';
import '@fontsource/space-mono/700.css';
import 'lenis/dist/lenis.css';
import './index.css';
import '@aethria/product-chrome';
import App from './App.tsx';

// Global smooth scroll (Lenis) for marketing site only
const lenis = new Lenis({
  lerp: 0.08,
  smoothWheel: true,
});

// Expose for in-page nav anchors (header) to drive smooth scroll.
(window as unknown as { __lenis?: Lenis }).__lenis = lenis;

function raf(time: number) {
  lenis.raf(time);
  requestAnimationFrame(raf);
}

requestAnimationFrame(raf);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
