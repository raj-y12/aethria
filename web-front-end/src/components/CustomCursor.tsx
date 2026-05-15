import { useEffect, useRef, useState } from 'react';

const DESKTOP_CURSOR_MEDIA = '(pointer: fine) and (min-width: 769px)';

const INK = '#001433';
const PAPER = '#F4F1EA';

type CursorMode = 'default' | 'hover' | 'headline';

/** Parse rgb()/rgba() from computed background (not gradients). */
function parseBackgroundColor(css: string): { r: number; g: number; b: number; a: number } | null {
  const m = css.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)/i);
  if (!m) return null;
  const a = m[4] !== undefined ? Number(m[4]) : 1;
  return { r: Number(m[1]), g: Number(m[2]), b: Number(m[3]), a };
}

/** Walk ancestors until we find an opaque-enough background; treat as dark vs light for cursor contrast. */
function shouldInvertCursor(start: Element | null): boolean {
  let el: Element | null = start;
  const stop = document.documentElement;

  while (el && el !== stop) {
    const raw = window.getComputedStyle(el as HTMLElement).backgroundColor;
    const parsed = parseBackgroundColor(raw);
    if (parsed && parsed.a > 0.12) {
      const { r, g, b } = parsed;
      const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      return lum < 0.45;
    }
    el = el.parentElement;
  }
  return false;
}

export default function CustomCursor() {
  const [active, setActive] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const dotRef = useRef<HTMLDivElement | null>(null);
  const ringRef = useRef<HTMLDivElement | null>(null);
  const posRef = useRef({ x: -100, y: -100 });
  const movedRef = useRef(false);
  const modeRef = useRef<CursorMode>('default');
  const invertRef = useRef(false);

  // Enable only on non-touch, desktop-like pointers
  useEffect(() => {
    const isTouch = navigator.maxTouchPoints > 0;
    if (isTouch) {
      setActive(false);
      return;
    }

    const mq = window.matchMedia(DESKTOP_CURSOR_MEDIA);
    const update = () => setActive(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

  // Mouse tracking + hover mode detection + background-based inversion.
  // Use refs + requestAnimationFrame to avoid rerendering on every pointer movement.
  useEffect(() => {
    if (!active) return;

    let rafId = 0;

    const renderCursor = () => {
      const root = rootRef.current;
      const dot = dotRef.current;
      const ring = ringRef.current;
      if (!root || !ring) {
        rafId = requestAnimationFrame(renderCursor);
        return;
      }

      const { x, y } = posRef.current;
      if (movedRef.current) root.style.visibility = 'visible';

      const el = document.elementFromPoint(x, y) as HTMLElement | null;
      invertRef.current = shouldInvertCursor(el);

      const hoverTarget =
        el?.closest('a,button') ||
        el?.closest('[data-cursor-expand]') ||
        (el && (el as HTMLElement).dataset.cursor === 'hover'
          ? el
          : el?.closest('[data-cursor="hover"]') || null);
      const headlineTarget =
        el?.dataset.cursor === 'headline' ? el : el?.closest('[data-cursor="headline"]');

      modeRef.current = headlineTarget ? 'headline' : hoverTarget ? 'hover' : 'default';

      const showDot = modeRef.current === 'default';
      const ringSize = modeRef.current === 'headline' ? 80 : modeRef.current === 'hover' ? 56 : 36;
      const ringOpacity = modeRef.current === 'default' ? 0.35 : 0.6;
      const fg = invertRef.current ? PAPER : INK;

      if (dot) {
        dot.style.display = showDot ? 'block' : 'none';
        dot.style.transform = `translate(${x - 4}px, ${y - 4}px)`;
        dot.style.backgroundColor = fg;
      }

      ring.style.width = `${ringSize}px`;
      ring.style.height = `${ringSize}px`;
      ring.style.borderColor = fg;
      ring.style.opacity = `${ringOpacity}`;
      ring.style.transform = `translate(${x - ringSize / 2}px, ${y - ringSize / 2}px)`;

      rafId = requestAnimationFrame(renderCursor);
    };

    const handleMove = (e: MouseEvent) => {
      posRef.current = { x: e.clientX, y: e.clientY };
      movedRef.current = true;
    };

    document.documentElement.classList.add('has-custom-cursor');
    window.addEventListener('mousemove', handleMove);
    rafId = requestAnimationFrame(renderCursor);

    return () => {
      document.documentElement.classList.remove('has-custom-cursor');
      window.removeEventListener('mousemove', handleMove);
      cancelAnimationFrame(rafId);
    };
  }, [active]);

  if (!active) return null;

  return (
    <div
      ref={rootRef}
      className="fixed pointer-events-none z-[10000]"
      style={{
        left: 0,
        top: 0,
        width: 0,
        height: 0,
        visibility: 'hidden',
      }}
      aria-hidden
    >
      <div
        ref={dotRef}
        className="absolute rounded-none transition-[transform,background-color,border-color] duration-150 ease-out"
        style={{
          width: 8,
          height: 8,
          backgroundColor: INK,
          transform: 'translate(-100px, -100px)',
        }}
      />

      {/* Hollow ring */}
      <div
        ref={ringRef}
        className="absolute rounded-none transition-[transform,border-color,opacity] duration-300 ease-out"
        style={{
          width: 36,
          height: 36,
          border: `1px solid ${INK}`,
          opacity: 0.35,
          transform: 'translate(-100px, -100px)',
        }}
      />
    </div>
  );
}
