import { useEffect, useState } from 'react';

const DESKTOP_CURSOR_MEDIA = '(pointer: fine) and (min-width: 769px)';

const INK = '#002147';
const PAPER = '#F2F0EA';

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
  const [pos, setPos] = useState({ x: -100, y: -100 });
  const [mode, setMode] = useState<CursorMode>('default');
  const [invert, setInvert] = useState(false);
  const [hasMoved, setHasMoved] = useState(false);

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

  // Mouse tracking + hover mode detection + background-based inversion
  useEffect(() => {
    if (!active) return;

    const handleMove = (e: MouseEvent) => {
      setPos({ x: e.clientX, y: e.clientY });
      setHasMoved(true);

      const el = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null;
      setInvert(shouldInvertCursor(el));

      const hoverTarget =
        el?.closest('a,button') ||
        el?.closest('[data-cursor-expand]') ||
        (el && (el as HTMLElement).dataset.cursor === 'hover'
          ? el
          : el?.closest('[data-cursor="hover"]') || null);
      const headlineTarget =
        el?.dataset.cursor === 'headline' ? el : el?.closest('[data-cursor="headline"]');

      if (headlineTarget) {
        setMode('headline');
      } else if (hoverTarget) {
        setMode('hover');
      } else {
        setMode('default');
      }
    };

    document.documentElement.classList.add('has-custom-cursor');
    window.addEventListener('mousemove', handleMove);

    return () => {
      document.documentElement.classList.remove('has-custom-cursor');
      window.removeEventListener('mousemove', handleMove);
    };
  }, [active]);

  if (!active) return null;

  const showDot = mode === 'default';
  const ringSize = mode === 'headline' ? 80 : mode === 'hover' ? 56 : 36;
  const ringOpacity = mode === 'default' ? 0.35 : 0.6;
  const fg = invert ? PAPER : INK;

  return (
    <div
      className="fixed pointer-events-none z-[10000]"
      style={{
        left: 0,
        top: 0,
        width: 0,
        height: 0,
        visibility: hasMoved ? 'visible' : 'hidden',
      }}
      aria-hidden
    >
      {/* Small filled dot */}
      {showDot && (
        <div
          className="absolute rounded-full transition-[transform,background-color,border-color] duration-150 ease-out"
          style={{
            width: 8,
            height: 8,
            backgroundColor: fg,
            transform: `translate(${pos.x - 4}px, ${pos.y - 4}px)`,
          }}
        />
      )}

      {/* Hollow ring */}
      <div
        className="absolute rounded-full transition-[transform,border-color,opacity] duration-300 ease-out"
        style={{
          width: ringSize,
          height: ringSize,
          border: `1px solid ${fg}`,
          opacity: ringOpacity,
          transform: `translate(${pos.x - ringSize / 2}px, ${pos.y - ringSize / 2}px)`,
        }}
      />
    </div>
  );
}
