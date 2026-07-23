import { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';

// Composes on the oxford field so the pull-up reveals the dark masthead with no
// paper flash between the two — the letterforms are paper ink, the dot verdigris.
const OXFORD = '#001433';
const INK = '#f4f1ea';
const ACCENT = '#7aab9a';
/** How long the particles get to assemble before the sheet is pulled. */
const ASSEMBLE_MS = 2400;

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  tx: number;
  ty: number;
  accent: boolean;
}

/**
 * Full-screen load-in — "composing today's edition". Thousands of loose ink
 * particles fly in and assemble into the wordmark under spring steering, hold,
 * then the whole sheet is pulled up off the stack to reveal the front page.
 * Click skips. Reduced motion skips entirely.
 */
export default function EditionLoader({ onDone }: { onDone: () => void }) {
  const reduce = useReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (reduce) {
      onDone();
      return;
    }
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const cvs = canvasRef.current;
    if (!cvs) return;
    let raf = 0;
    let cancelled = false;
    let exitTimer = 0;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = window.innerWidth;
    const H = window.innerHeight;
    cvs.width = W * dpr;
    cvs.height = H * dpr;
    const ctx = cvs.getContext('2d')!;
    ctx.scale(dpr, dpr);

    // Sample the wordmark glyphs into target points once the display face is loaded.
    document.fonts.ready.then(() => {
      if (cancelled) return;
      const off = document.createElement('canvas');
      off.width = W;
      off.height = H;
      const octx = off.getContext('2d')!;
      const fontSize = Math.min(W * 0.17, 200);
      octx.font = `500 ${fontSize}px "Playfair Display", Georgia, serif`;
      octx.textBaseline = 'middle';
      octx.textAlign = 'center';
      octx.fillStyle = '#000';
      octx.fillText('Aethria.', W / 2, H / 2);
      // Everything right of the last stem is the wordmark dot — it assembles in verdigris.
      const fullW = octx.measureText('Aethria.').width;
      const wordW = octx.measureText('Aethria').width;
      const dotX = W / 2 - fullW / 2 + wordW;

      const data = octx.getImageData(0, 0, W, H).data;
      const targets: { tx: number; ty: number; accent: boolean }[] = [];
      const gap = 3;
      for (let y = 0; y < H; y += gap) {
        for (let x = 0; x < W; x += gap) {
          if (data[(y * W + x) * 4 + 3] > 128) targets.push({ tx: x, ty: y, accent: x > dotX });
        }
      }
      // ponytail: cap the particle count by striding, 60fps beats fidelity
      const stride = Math.max(1, Math.ceil(targets.length / 2600));
      const particles: Particle[] = targets
        .filter((_, i) => i % stride === 0)
        .map((t) => ({
          ...t,
          // scatter from just outside the viewport edges so they visibly fly in
          x: Math.random() * W * 1.4 - W * 0.2,
          y: Math.random() * H * 1.4 - H * 0.2,
          vx: 0,
          vy: 0,
        }));

      const t0 = performance.now();
      const frame = (ts: number) => {
        if (cancelled) return;
        const elapsed = ts - t0;
        ctx.clearRect(0, 0, W, H);
        // ink builds up as the letters form
        ctx.globalAlpha = Math.min(1, 0.35 + elapsed / 900);
        const k = 0.03;
        const damp = 0.85;
        const turbulence = Math.max(0, 1 - elapsed / 1400); // early chaos, late precision
        for (const p of particles) {
          p.vx = (p.vx + (p.tx - p.x) * k + (Math.random() - 0.5) * turbulence * 1.6) * damp;
          p.vy = (p.vy + (p.ty - p.y) * k + (Math.random() - 0.5) * turbulence * 1.6) * damp;
          p.x += p.vx;
          p.y += p.vy;
          ctx.fillStyle = p.accent ? ACCENT : INK;
          ctx.fillRect(p.x, p.y, 1.7, 1.7);
        }
        raf = requestAnimationFrame(frame);
      };
      raf = requestAnimationFrame(frame);
      exitTimer = window.setTimeout(() => setExiting(true), ASSEMBLE_MS);
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.clearTimeout(exitTimer);
      document.body.style.overflow = prevOverflow;
    };
  }, [reduce, onDone]);

  if (reduce) return null;

  return (
    <motion.div
      className="fixed inset-0 z-[200] cursor-pointer"
      style={{ backgroundColor: OXFORD }}
      animate={exiting ? { y: '-100%' } : { y: 0 }}
      transition={{ duration: 0.8, ease: [0.85, 0, 0.15, 1] }}
      onAnimationComplete={() => {
        if (exiting) onDone();
      }}
      onClick={() => setExiting(true)}
      aria-hidden
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <motion.p
        className="absolute inset-x-0 bottom-10 text-center font-mono text-[9.5px] uppercase tracking-[0.24em] text-[var(--text-inverse-muted)]"
        animate={{ opacity: [0.35, 0.8, 0.35] }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      >
        Composing today's edition
      </motion.p>
      {/* the sheet below peeks out as this one is pulled away */}
      <div className="absolute inset-x-0 bottom-0 h-px bg-[rgba(244,241,234,0.16)]" />
    </motion.div>
  );
}
