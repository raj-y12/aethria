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
 * the few inside the active thesis glow in the brand verdigris. In live mode a scan band
 * sweeps and scout→decision arcs travel toward the in-thesis hits. No text labels.
 */
export default function DottedMarketMap({ hits = [], echo = false, className }: DottedMarketMapProps) {
  const baseRef = useRef<HTMLCanvasElement | null>(null);
  const fxRef = useRef<HTMLCanvasElement | null>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const base = baseRef.current;
    if (!base) return;
    let raf = 0;
    let cancelled = false;
    let cleanupResize: (() => void) | undefined;

    fetch(worldUrl)
      .then((r) => r.json())
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .then((world: any) => {
        if (cancelled) return;
        const land = feature(world, world.objects.countries);

        const drawDots = (canvas: HTMLCanvasElement, opacity: number): FieldInfo => {
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
                ctx.beginPath();
                ctx.arc(x, y, 1, 0, 6.283);
                ctx.fillStyle = `rgba(${INK_RGB},${opacity})`;
                ctx.fill();
                landPts.push([x, y]);
              }
            }
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          return { proj: proj as any, W, H, landPts };
        };

        let info = drawDots(base, echo ? 0.13 : 0.2);
        const fx = fxRef.current;
        let fxctx: CanvasRenderingContext2D | null = null;
        let targets: (Pt | null)[] = [];
        let arcs: { s: Pt; t: Pt; c: Pt; p: number; sp: number }[] = [];

        const setupFx = () => {
          if (!fx) return;
          const dpr = Math.min(window.devicePixelRatio || 1, 2);
          fx.width = base.width;
          fx.height = base.height;
          fxctx = fx.getContext('2d');
          fxctx?.scale(dpr, dpr);
          targets = hits.map((h) => info.proj([h.lon, h.lat]));
          arcs = [];
        };

        const drawStaticHits = () => {
          if (!fxctx) return;
          fxctx.clearRect(0, 0, info.W, info.H);
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
          info = drawDots(base, echo ? 0.13 : 0.2);
          if (!echo) {
            setupFx();
            if (reduce) drawStaticHits();
          }
        };
        window.addEventListener('resize', onResize);
        cleanupResize = () => window.removeEventListener('resize', onResize);

        if (echo) return;
        if (reduce) {
          drawStaticHits();
          return;
        }

        const spawnArc = () => {
          if (!info.landPts.length || !targets.length) return;
          const s = info.landPts[(Math.random() * info.landPts.length) | 0];
          const t = targets[(Math.random() * targets.length) | 0];
          if (!t) return;
          const mx = (s[0] + t[0]) / 2;
          const my = (s[1] + t[1]) / 2 - Math.hypot(t[0] - s[0], t[1] - s[1]) * 0.28;
          arcs.push({ s, t, c: [mx, my], p: 0, sp: 0.006 + Math.random() * 0.006 });
        };

        let last = 0;
        const frame = (ts: number) => {
          if (cancelled || !fxctx) return;
          const { W, H } = info;
          fxctx.clearRect(0, 0, W, H);
          // scan band
          const sx = ((ts / 3400) % 1) * W;
          const g = fxctx.createLinearGradient(sx - 70, 0, sx + 70, 0);
          g.addColorStop(0, `rgba(${ACCENT_RGB},0)`);
          g.addColorStop(0.5, `rgba(${ACCENT_RGB},0.07)`);
          g.addColorStop(1, `rgba(${ACCENT_RGB},0)`);
          fxctx.fillStyle = g;
          fxctx.fillRect(sx - 70, 0, 140, H);
          // arcs
          if (ts - last > 520) {
            last = ts;
            spawnArc();
            if (Math.random() < 0.5) spawnArc();
          }
          arcs = arcs.filter((a) => a.p < 1);
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
              t === tail ? fxctx!.moveTo(q[0], q[1]) : fxctx!.lineTo(q[0], q[1]);
            }
            fxctx!.strokeStyle = `rgba(${ACCENT_RGB},0.55)`;
            fxctx!.lineWidth = 1.1;
            fxctx!.stroke();
            const head = bez(a.p);
            fxctx!.beginPath();
            fxctx!.arc(head[0], head[1], 1.8, 0, 6.283);
            fxctx!.fillStyle = ACCENT;
            fxctx!.fill();
          });
          // in-thesis hits with pulse
          targets.forEach((t) => {
            if (!t) return;
            const r = 6 + 6 * Math.abs(Math.sin(ts / 700));
            fxctx!.beginPath();
            fxctx!.arc(t[0], t[1], r, 0, 6.283);
            fxctx!.strokeStyle = `rgba(${ACCENT_RGB},${0.4 - (r - 6) / 30})`;
            fxctx!.lineWidth = 1;
            fxctx!.stroke();
            fxctx!.beginPath();
            fxctx!.arc(t[0], t[1], 3.2, 0, 6.283);
            fxctx!.fillStyle = ACCENT;
            fxctx!.fill();
          });
          raf = requestAnimationFrame(frame);
        };
        raf = requestAnimationFrame(frame);
      })
      .catch(() => {
        /* world data failed to load — leave the canvas empty rather than throw */
      });

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      cleanupResize?.();
    };
  }, [echo, reduce, hits]);

  return (
    <div className={className} style={{ position: 'relative' }} aria-hidden>
      <canvas ref={baseRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      {!echo && <canvas ref={fxRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />}
    </div>
  );
}
