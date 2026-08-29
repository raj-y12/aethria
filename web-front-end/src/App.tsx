import { useEffect } from 'react';
import Lenis from 'lenis';
import { MotionConfig } from 'framer-motion';
import AnimatedRoutes from './components/AnimatedRoutes';

/**
 * / = gate; /home = home. All other paths → /.
 */
function App() {
  // Global smooth scroll (Lenis), marketing site only. Client-only: never runs
  // during SSG (useEffect is skipped server-side, and `window` is undefined there).
  // Skipped entirely for prefers-reduced-motion — Lenis's physics-based lerp
  // scroll is itself a motion effect, not just a visual animation.
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
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

  return (
    <MotionConfig reducedMotion="user">
      <AnimatedRoutes />
    </MotionConfig>
  );
}

export default App;
