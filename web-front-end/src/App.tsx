import { useEffect } from 'react';
import Lenis from 'lenis';
import AnimatedRoutes from './components/AnimatedRoutes';

/**
 * / = gate; /home = home (the application form lives at /home#access).
 * /request-access redirects to /home#access for old links. All other paths → /.
 */
function App() {
  // Global smooth scroll (Lenis), marketing site only. Client-only: never runs
  // during SSG (useEffect is skipped server-side, and `window` is undefined there).
  useEffect(() => {
    const lenis = new Lenis({ lerp: 0.08, smoothWheel: true });
    // Expose for in-page nav anchors (header) to drive smooth scroll.
    (window as unknown as { __lenis?: Lenis }).__lenis = lenis;
    let id = requestAnimationFrame(function raf(time) {
      lenis.raf(time);
      id = requestAnimationFrame(raf);
    });
    return () => {
      cancelAnimationFrame(id);
      lenis.destroy();
      delete (window as unknown as { __lenis?: Lenis }).__lenis;
    };
  }, []);

  return <AnimatedRoutes />;
}

export default App;
