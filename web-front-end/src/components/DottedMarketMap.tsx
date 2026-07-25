import { useEffect, useRef } from 'react';
import { geoNaturalEarth1, geoPath } from 'd3-geo';
import { feature } from 'topojson-client';
import { useReducedMotion } from 'framer-motion';
// Bundled world geometry — fetched as a static asset (no tsconfig json import needed).
import worldUrl from 'world-atlas/countries-110m.json?url';

export interface MapHit {
  /** longitude, latitude of an in-thesis company */
  lon: number;
  lat: number;
}

interface DottedMarketMapProps {
  hits?: MapHit[];
  /** Faint, supportive echo (e.g. behind the hero) — static dots only, no live layer. */
  echo?: boolean;
  className?: string;
}

const ACCENT = '#3d6b5e';
const ACCENT_RGB = '61,107,94';
const INK_RGB = '0,20,51';

type Pt = [number, number];
interface FieldInfo {
  proj: (p: Pt) => Pt | null;
  W: number;
  H: number;
  landPts: Pt[];
}

/**
 * The market, as a dotted world map. Most companies are faint ink dots ("scanned");
 * the few inside the active thesis glow in the brand verdigris. In live mode a green
 * wave spreads outward from each hit through the surrounding land dots. No text labels.
 */
export default function DottedMarketMap({ hits = [], echo = false, className }: DottedMarketMapProps) {
  const baseRef = useRef<HTMLCanvasElement | null>(null);
  const fxRef = useRef<HTMLCanvasElement | null>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const base = baseRef.current;
    if (!base) return;
    let raf = 0;
    let rafAssembly = 0;
    let cancelled = false;
    let cleanupResize: (() => void) | undefined;
    let cleanupPointer: (() => void) | undefined;
    // Cursor probe — the field reacts to where the reader is looking. Pointer devices only.
    const hoverEnabled =
      typeof window !== 'undefined' && window.matchMedia('(hover: hover)').matches;
    const pointer = { x: -1, y: -1, active: false };

    fetch(worldUrl)
      .then((r) => r.json())
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .then((world: any) => {
        if (cancelled) return;
        const land = feature(world, world.objects.countries);

        /** Sizes the canvas, computes projection + land dot targets; paints them unless `paint` is false. */
        const drawDots = (canvas: HTMLCanvasElement, opacity: number, paint = true): FieldInfo => {
          const dpr = Math.min(window.devicePixelRatio || 1, 2);
          const W = canvas.clientWidth;
          const H = canvas.clientHeight;
          canvas.width = W * dpr;
          canvas.height = H * dpr;
          const ctx = canvas.getContext('2d')!;
          ctx.scale(dpr, dpr);
          ctx.clearRect(0, 0, W, H);
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const proj = geoNaturalEarth1().fitSize([W, H * 1.16], land as any).translate([W / 2, H / 2]);
          const off = document.createElement('canvas');
          off.width = W;
          off.height = H;
          const octx = off.getContext('2d')!;
          octx.fillStyle = '#000';
          octx.beginPath();
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          geoPath(proj as any, octx)(land as any);
          octx.fill();
          const data = octx.getImageData(0, 0, W, H).data;
          const gap = Math.max(5, Math.round(W / 190));
          const landPts: Pt[] = [];
          for (let y = 0; y < H; y += gap) {
            for (let x = 0; x < W; x += gap) {
              if (data[(y * W + x) * 4 + 3] > 130) {
                if (paint) {
                  ctx.beginPath();
                  ctx.arc(x, y, 1, 0, 6.283);
                  ctx.fillStyle = `rgba(${INK_RGB},${opacity})`;
                  ctx.fill();
                }
                landPts.push([x, y]);
              }
            }
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          return { proj: proj as any, W, H, landPts };
        };

        // Live map defers painting — the field assembles on first view; echo and
        // reduced-motion paint at once.
        const paintImmediately = echo || !!reduce;
        let info = drawDots(base, echo ? 0.13 : 0.2, paintImmediately);
        let assembled = false;
        let assembling = false;
        let liveStarted = false;
        const fx = fxRef.current;
        let fxctx: CanvasRenderingContext2D | null = null;
        let targets: (Pt | null)[] = [];
        // Per-hit list of nearby land dots with their distance — the medium the green wave spreads through.
        let spreads: { pts: { p: Pt; d: number }[] }[] = [];
        let maxR = 0;
        // Per-hit spread state — grows a step each time an arc lands, decays slowly.
        let growth: { r: number; goal: number }[] = [];
        let arcs: { s: Pt; t: Pt; c: Pt; hi: number; p: number; sp: number }[] = [];

        const setupFx = () => {
          if (!fx) return;
          const dpr = Math.min(window.devicePixelRatio || 1, 2);
          fx.width = base.width;
          fx.height = base.height;
          fxctx = fx.getContext('2d');
          fxctx?.scale(dpr, dpr);
          targets = hits.map((h) => info.proj([h.lon, h.lat]));
          maxR = Math.max(60, Math.min(info.W, info.H) * 0.17);
          spreads = targets.map((t) => {
            if (!t) return { pts: [] };
            const pts: { p: Pt; d: number }[] = [];
            for (const p of info.landPts) {
              const d = Math.hypot(p[0] - t[0], p[1] - t[1]);
              if (d < maxR) pts.push({ p, d });
            }
            return { pts };
          });
          // Seeded with a base spread so every hit shows a green field immediately;
          // arc landings push it outward from there.
          growth = targets.map(() => ({ r: 0, goal: maxR * 0.35 }));
          arcs = [];
        };

        const drawStaticHits = () => {
          if (!fxctx) return;
          fxctx.clearRect(0, 0, info.W, info.H);
          spreads.forEach((s) => {
            s.pts.forEach(({ p, d }) => {
              fxctx!.beginPath();
              fxctx!.arc(p[0], p[1], 1.1, 0, 6.283);
              fxctx!.fillStyle = `rgba(${ACCENT_RGB},${0.35 * (1 - d / maxR)})`;
              fxctx!.fill();
            });
          });
          targets.forEach((t) => {
            if (!t) return;
            fxctx!.beginPath();
            fxctx!.arc(t[0], t[1], 3.4, 0, 6.283);
            fxctx!.fillStyle = ACCENT;
            fxctx!.fill();
          });
        };

        if (!echo) setupFx();

        const onResize = () => {
          if (assembling && !assembled) assembled = true; // abort mid-flight assembly; targets are stale
          info = drawDots(base, echo ? 0.13 : 0.2, paintImmediately || assembled);
          if (!echo) {
            setupFx();
            if (reduce) drawStaticHits();
            else if (assembled) startLive();
          }
        };
        window.addEventListener('resize', onResize);
        cleanupResize = () => window.removeEventListener('resize', onResize);

        if (echo) return;
        if (reduce) {
          drawStaticHits();
          return;
        }

        // The reader's cursor probes the market: nearby dots warm to verdigris and
        // faint lines reach toward the closest in-thesis names.
        if (hoverEnabled && fx) {
          const onMove = (e: PointerEvent) => {
            const rect = fx.getBoundingClientRect();
            pointer.x = e.clientX - rect.left;
            pointer.y = e.clientY - rect.top;
            pointer.active = true;
          };
          const onLeave = () => {
            pointer.active = false;
          };
          fx.addEventListener('pointermove', onMove);
          fx.addEventListener('pointerleave', onLeave);
          cleanupPointer = () => {
            fx.removeEventListener('pointermove', onMove);
            fx.removeEventListener('pointerleave', onLeave);
          };
        }

        // Scout arcs shoot toward the hits; each landing pushes that hit's green
        // spread one step further out through the dot grid. Untouched, it decays back.
        const GROW_STEP = () => maxR * 0.22; // radius gained per arc landing
        const FRONT = 12; // wavefront thickness (px)

        const spawnArc = () => {
          if (!info.landPts.length || !targets.length) return;
          const hi = (Math.random() * targets.length) | 0;
          const t = targets[hi];
          if (!t) return;
          const s = info.landPts[(Math.random() * info.landPts.length) | 0];
          const mx = (s[0] + t[0]) / 2;
          const my = (s[1] + t[1]) / 2 - Math.hypot(t[0] - s[0], t[1] - s[1]) * 0.28;
          arcs.push({ s, t, c: [mx, my], hi, p: 0, sp: 0.006 + Math.random() * 0.006 });
        };

        let last = 0;
        const frame = (ts: number) => {
          if (cancelled || !fxctx) return;
          const { W, H } = info;
          fxctx.clearRect(0, 0, W, H);
          // arcs
          if (ts - last > 520) {
            last = ts;
            spawnArc();
            if (Math.random() < 0.5) spawnArc();
          }
          arcs = arcs.filter((a) => {
            if (a.p < 1) return true;
            // landed — the spread claims the next ring of dots
            const g = growth[a.hi];
            if (g) g.goal = Math.min(g.goal + GROW_STEP(), maxR);
            return false;
          });
          arcs.forEach((a) => {
            a.p += a.sp;
            const bez = (t: number): Pt => [
              (1 - t) * (1 - t) * a.s[0] + 2 * (1 - t) * t * a.c[0] + t * t * a.t[0],
              (1 - t) * (1 - t) * a.s[1] + 2 * (1 - t) * t * a.c[1] + t * t * a.t[1],
            ];
            fxctx!.beginPath();
            const tail = Math.max(0, a.p - 0.18);
            for (let t = tail; t <= a.p; t += 0.02) {
              const q = bez(t);
              if (t === tail) fxctx!.moveTo(q[0], q[1]);
              else fxctx!.lineTo(q[0], q[1]);
            }
            fxctx!.strokeStyle = `rgba(${ACCENT_RGB},0.55)`;
            fxctx!.lineWidth = 1.1;
            fxctx!.stroke();
            const head = bez(Math.min(a.p, 1));
            fxctx!.beginPath();
            fxctx!.arc(head[0], head[1], 1.8, 0, 6.283);
            fxctx!.fillStyle = ACCENT;
            fxctx!.fill();
          });
          // spreads — ease toward the goal each landing set, decay slowly when unfed
          spreads.forEach((s, i) => {
            const g = growth[i];
            if (!g) return;
            g.goal = Math.max(maxR * 0.35, g.goal - 0.012);
            g.r += (g.goal - g.r) * 0.045;
            if (g.r < 1) return;
            s.pts.forEach(({ p, d }) => {
              if (d > g.r + FRONT * 2) return;
              const stain = d <= g.r ? 0.55 * (1 - d / (maxR * 1.3)) : 0;
              const front = 0.5 * Math.exp(-((d - g.r) * (d - g.r)) / (2 * FRONT * FRONT));
              const a = stain + front;
              if (a < 0.03) return;
              fxctx!.beginPath();
              fxctx!.arc(p[0], p[1], 1.3, 0, 6.283);
              fxctx!.fillStyle = `rgba(${ACCENT_RGB},${a})`;
              fxctx!.fill();
            });
          });
          // in-thesis hits with pulse — a soft glow, an expanding ring, a solid core
          targets.forEach((t) => {
            if (!t) return;
            const glow = fxctx!.createRadialGradient(t[0], t[1], 0, t[0], t[1], 16);
            glow.addColorStop(0, `rgba(${ACCENT_RGB},0.22)`);
            glow.addColorStop(1, `rgba(${ACCENT_RGB},0)`);
            fxctx!.beginPath();
            fxctx!.arc(t[0], t[1], 16, 0, 6.283);
            fxctx!.fillStyle = glow;
            fxctx!.fill();
            const r = 6 + 6 * Math.abs(Math.sin(ts / 700));
            fxctx!.beginPath();
            fxctx!.arc(t[0], t[1], r, 0, 6.283);
            fxctx!.strokeStyle = `rgba(${ACCENT_RGB},${0.45 - (r - 6) / 26})`;
            fxctx!.lineWidth = 1;
            fxctx!.stroke();
            fxctx!.beginPath();
            fxctx!.arc(t[0], t[1], 3.4, 0, 6.283);
            fxctx!.fillStyle = ACCENT;
            fxctx!.fill();
          });

          // cursor probe layer — warms nearby land, reaches to the closest hits
          if (pointer.active) {
            const CR = Math.max(100, Math.min(W, H) * 0.17);
            const CR2 = CR * CR;
            for (const p of info.landPts) {
              const dx = p[0] - pointer.x;
              const dy = p[1] - pointer.y;
              if (dx < -CR || dx > CR || dy < -CR || dy > CR) continue;
              const d2 = dx * dx + dy * dy;
              if (d2 > CR2) continue;
              const a = 0.55 * (1 - Math.sqrt(d2) / CR);
              if (a < 0.03) continue;
              fxctx!.beginPath();
              fxctx!.arc(p[0], p[1], 1.35, 0, 6.283);
              fxctx!.fillStyle = `rgba(${ACCENT_RGB},${a})`;
              fxctx!.fill();
            }
            const reach = Math.max(W, H) * 0.62;
            targets
              .filter((t): t is Pt => !!t)
              .map((t) => ({ t, d: Math.hypot(t[0] - pointer.x, t[1] - pointer.y) }))
              .sort((a, b) => a.d - b.d)
              .slice(0, 3)
              .forEach(({ t, d }) => {
                const a = 0.34 * (1 - d / reach);
                if (a <= 0.01) return;
                fxctx!.beginPath();
                fxctx!.moveTo(pointer.x, pointer.y);
                fxctx!.lineTo(t[0], t[1]);
                fxctx!.strokeStyle = `rgba(${ACCENT_RGB},${a})`;
                fxctx!.lineWidth = 1;
                fxctx!.stroke();
              });
            fxctx!.beginPath();
            fxctx!.arc(pointer.x, pointer.y, 5.5, 0, 6.283);
            fxctx!.strokeStyle = `rgba(${ACCENT_RGB},0.6)`;
            fxctx!.lineWidth = 1;
            fxctx!.stroke();
            fxctx!.beginPath();
            fxctx!.arc(pointer.x, pointer.y, 2, 0, 6.283);
            fxctx!.fillStyle = ACCENT;
            fxctx!.fill();
          }

          raf = requestAnimationFrame(frame);
        };

        const startLive = () => {
          if (liveStarted) return;
          liveStarted = true;
          raf = requestAnimationFrame(frame);
        };

        // The field assembles like the edition loader — land dots fly in under
        // spring steering the first time the map scrolls into view; the arcs and
        // green spreads only start once the continents have settled.
        const runAssembly = () => {
          if (assembling || assembled) return;
          assembling = true;
          const ctx = base.getContext('2d')!;
          const { W, H, landPts } = info;
          const parts = landPts.map(([tx, ty]) => ({
            tx,
            ty,
            x: Math.random() * W * 1.4 - W * 0.2,
            y: Math.random() * H * 1.4 - H * 0.2,
            vx: 0,
            vy: 0,
          }));
          const t0 = performance.now();
          const DUR = 1900;
          const step = (ts: number) => {
            if (cancelled || assembled) return;
            const elapsed = ts - t0;
            ctx.clearRect(0, 0, W, H);
            const turbulence = Math.max(0, 1 - elapsed / 1200);
            ctx.fillStyle = `rgba(${INK_RGB},0.2)`;
            for (const p of parts) {
              p.vx = (p.vx + (p.tx - p.x) * 0.03 + (Math.random() - 0.5) * turbulence * 1.4) * 0.84;
              p.vy = (p.vy + (p.ty - p.y) * 0.03 + (Math.random() - 0.5) * turbulence * 1.4) * 0.84;
              p.x += p.vx;
              p.y += p.vy;
              ctx.fillRect(p.x, p.y, 1.6, 1.6);
            }
            if (elapsed < DUR) {
              rafAssembly = requestAnimationFrame(step);
              return;
            }
            assembled = true;
            info = drawDots(base, 0.2); // settle onto the exact grid
            startLive();
          };
          rafAssembly = requestAnimationFrame(step);
        };

        const io = new IntersectionObserver(
          (entries) => {
            if (!entries[0].isIntersecting) return;
            io.disconnect();
            runAssembly();
          },
          { threshold: 0.2 },
        );
        io.observe(base);
        const removeResize = cleanupResize;
        cleanupResize = () => {
          removeResize?.();
          io.disconnect();
        };
      })
      .catch(() => {
        /* world data failed to load — leave the canvas empty rather than throw */
      });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      cancelAnimationFrame(rafAssembly);
      cleanupResize?.();
      cleanupPointer?.();
    };
  }, [echo, reduce, hits]);

  return (
    <div className={className} style={{ position: 'relative' }} aria-hidden>
      <canvas ref={baseRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      {!echo && <canvas ref={fxRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />}
    </div>
  );
}
