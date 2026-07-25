import { jsxs, jsx, Fragment } from "react/jsx-runtime";
import { ViteReactSSG } from "vite-react-ssg";
import { useState, useEffect, useRef, createElement, lazy, Suspense } from "react";
import Lenis from "lenis";
import { Link, useSearchParams, useLocation, useNavigate } from "react-router-dom";
import { useReducedMotion, AnimatePresence, motion } from "framer-motion";
import { geoNaturalEarth1, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import gsap from "gsap";
function cx$1(...parts) {
  return parts.filter(Boolean).join(" ");
}
function trailingLabel(trailing) {
  if (trailing === "result") return "Result";
  if (trailing === "close") return "Close";
  return "↵ run";
}
function LookupCommandBar({
  label = "LOOKUP",
  query,
  trailing = "run",
  className
}) {
  const showQuery = Boolean(query?.trim());
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: cx$1(
        "flex items-center gap-3 border border-solid border-oxford/10 bg-oxford/[0.025] px-3 py-2 sm:px-4 sm:py-2.5",
        className
      ),
      children: [
        /* @__PURE__ */ jsx("span", { className: "shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/35", children: label }),
        showQuery ? /* @__PURE__ */ jsxs(Fragment, { children: [
          /* @__PURE__ */ jsx("span", { className: "h-3 w-px shrink-0 bg-oxford/10", "aria-hidden": true }),
          /* @__PURE__ */ jsx("span", { className: "min-w-0 truncate font-sans text-[13px] text-oxford/65", children: query })
        ] }) : null,
        trailing ? /* @__PURE__ */ jsx("span", { className: "ml-auto shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/30", children: trailingLabel(trailing) }) : null
      ]
    }
  );
}
function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}
function formatScore(score) {
  if (score == null || !Number.isFinite(score)) return "—";
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}
function LookupResultSnapshot({
  companyName,
  queryLabel,
  metaLine,
  verdict,
  verdictColor,
  verdictTextColor,
  summary,
  dimensions,
  thesisLine,
  resolutionLine,
  onOpenMemo,
  openMemoLabel = "Open full memo",
  variant = "snapshot",
  compact = false,
  size = "default",
  intelligenceKicker = "Aethria intelligence · autonomous output",
  judgmentLabel = "Investment judgment",
  dimensionsLabel = "Dimension scores",
  className
}) {
  const isMemo = variant === "memo";
  const lg = !isMemo && size === "lg";
  const pad = compact ? "p-3" : isMemo ? "p-5 sm:p-7 md:p-9" : lg ? "p-6 sm:p-7" : "px-4 py-4 sm:p-5";
  const verdictSize = compact ? "font-sans text-[18px] font-semibold leading-tight text-oxford" : isMemo ? "font-sans text-[clamp(1.375rem,5vw,2rem)] font-semibold leading-tight tracking-[-0.03em] text-oxford md:text-[32px]" : "font-sans text-[18px] font-semibold leading-tight text-oxford";
  const showCompanyName = true;
  return /* @__PURE__ */ jsxs(
    "article",
    {
      className: cx("border border-solid border-oxford/10 bg-paper", className),
      "aria-label": isMemo ? `Investment memo preview for ${companyName}` : queryLabel ? `Lookup result for ${companyName}` : `Intelligence snapshot for ${companyName}`,
      children: [
        isMemo ? /* @__PURE__ */ jsx(
          LookupCommandBar,
          {
            label: "MEMO",
            trailing: "close",
            className: "border-0 bg-paper"
          }
        ) : null,
        /* @__PURE__ */ jsxs("div", { className: pad, children: [
          isMemo ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx("p", { className: "mb-4 font-mono text-[12px] uppercase tracking-[0.11em] text-oxford/40", children: intelligenceKicker }),
            /* @__PURE__ */ jsx("h3", { className: "pc-font-display text-xl font-medium leading-tight tracking-[-0.02em] text-oxford sm:text-2xl", children: companyName }),
            metaLine ? /* @__PURE__ */ jsx("p", { className: "mt-1.5 font-mono text-[13px] tracking-[0.08em] text-oxford/50", children: metaLine }) : null,
            /* @__PURE__ */ jsx("div", { className: "my-5 h-px bg-oxford/10", "aria-hidden": true }),
            /* @__PURE__ */ jsx("p", { className: "mb-1.5 font-mono text-[12px] uppercase tracking-[0.11em] text-oxford/58", children: judgmentLabel })
          ] }) : /* @__PURE__ */ jsxs("div", { className: "mb-3 flex items-baseline justify-between gap-3", children: [
            /* @__PURE__ */ jsx("p", { className: "font-mono text-[10px] uppercase tracking-[0.11em] text-oxford/40", children: "Result" }),
            metaLine ? /* @__PURE__ */ jsx("p", { className: "text-right font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/35", children: metaLine }) : null
          ] }),
          !isMemo && showCompanyName && companyName ? /* @__PURE__ */ jsx(
            "h3",
            {
              className: cx(
                "pc-font-display font-medium leading-tight tracking-[-0.02em] text-oxford",
                compact ? "text-base" : lg ? "text-3xl sm:text-4xl" : "text-xl sm:text-2xl"
              ),
              children: companyName
            }
          ) : null,
          verdictColor ? /* @__PURE__ */ jsx(
            "span",
            {
              className: cx(
                // Filled chip — matches the app-front-end decision chip
                // (VERDICT_CHIP_CLASS/DecisionBadge): configured colour is the
                // fill, with a computed contrasting ink for readability.
                "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none font-mono font-semibold uppercase leading-none min-w-[4.25rem] px-2 py-1 text-[9px] tracking-[0.1em]",
                companyName ? "mt-2" : ""
              ),
              style: { backgroundColor: verdictColor, color: verdictTextColor ?? void 0 },
              children: verdict.replace(/\.$/, "")
            }
          ) : /* @__PURE__ */ jsx("p", { className: cx(isMemo ? "" : companyName ? "mt-2" : "", verdictSize), children: verdict }),
          /* @__PURE__ */ jsx(
            "p",
            {
              className: cx(
                // The takeover card carries the summary as a serif standfirst —
                // it is the finding, not a caption.
                lg ? "pc-font-display mt-3 text-[clamp(1rem,1.8vw,1.125rem)] leading-[1.4] tracking-[-0.012em] text-oxford/80" : "font-sans leading-[1.6] text-oxford/58",
                isMemo ? "mt-3 text-[15px] font-normal" : !lg ? "mt-1.5" : "",
                !isMemo && !lg && (compact ? "text-[13px]" : "text-[15px]")
              ),
              children: summary
            }
          ),
          thesisLine ? /* @__PURE__ */ jsx("p", { className: "mt-2 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/35", children: thesisLine }) : null,
          resolutionLine ? /* @__PURE__ */ jsx("p", { className: "mt-2 border border-solid border-oxford/12 bg-oxford/[0.04] px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-oxford/55", children: resolutionLine }) : null,
          dimensions.length > 0 ? /* @__PURE__ */ jsxs(Fragment, { children: [
            /* @__PURE__ */ jsx("div", { className: cx("bg-oxford/10", isMemo ? "my-5 h-px" : "my-3 h-px sm:my-4"), "aria-hidden": true }),
            isMemo ? /* @__PURE__ */ jsxs(Fragment, { children: [
              /* @__PURE__ */ jsx("p", { className: "mb-[14px] font-mono text-[12px] uppercase tracking-[0.11em] text-oxford/58", children: dimensionsLabel }),
              /* @__PURE__ */ jsxs("div", { className: "grid w-full grid-cols-5 gap-x-0.5 gap-y-1 sm:gap-x-2 sm:gap-y-2 md:gap-x-3", children: [
                dimensions.map((d) => /* @__PURE__ */ jsx("div", { className: "flex min-w-0 items-end justify-center text-center", children: /* @__PURE__ */ jsx("p", { className: "m-0 font-mono text-[11px] leading-[1.25] tracking-[0.03em] text-oxford/55 sm:text-[12px]", children: d.labelShort ?? d.label }) }, `label-${d.key}`)),
                dimensions.map((d) => /* @__PURE__ */ jsx(
                  "p",
                  {
                    className: "min-w-0 text-center font-mono text-base font-bold leading-tight text-oxford sm:text-xl md:text-2xl",
                    children: formatScore(d.score)
                  },
                  `score-${d.key}`
                ))
              ] })
            ] }) : /* @__PURE__ */ jsx("div", { className: "grid grid-cols-5 gap-x-1 sm:gap-x-2", children: dimensions.map((d) => /* @__PURE__ */ jsxs("div", { className: "flex min-w-0 flex-col items-center gap-0.5 text-center", children: [
              /* @__PURE__ */ jsx("span", { className: "font-mono text-[10px] text-oxford/35", children: d.label }),
              /* @__PURE__ */ jsx(
                "span",
                {
                  className: cx(
                    "font-mono font-bold text-oxford/70",
                    lg ? "text-base sm:text-lg" : "text-[11px] sm:text-sm"
                  ),
                  children: formatScore(d.score)
                }
              )
            ] }, d.key)) })
          ] }) : null,
          onOpenMemo ? /* @__PURE__ */ jsx(
            "button",
            {
              type: "button",
              onClick: onOpenMemo,
              className: "mt-4 w-full border border-solid border-oxford/12 bg-oxford px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-paper transition-opacity hover:opacity-90",
              children: openMemoLabel
            }
          ) : null
        ] })
      ]
    }
  );
}
const DEMO_LOOKUP_QUERY = "European infrastructure co.";
const DEMO_LOOKUP_RESULT = {
  companyName: "European infrastructure co.",
  queryLabel: DEMO_LOOKUP_QUERY,
  metaLine: "B2B Infrastructure · Series A · London",
  verdict: "INVEST",
  verdictColor: "#c3d3c9",
  verdictTextColor: "#0a1629",
  summary: "Source trail retained · Reviewer disagreement surfaced · Mandate fit recorded",
  thesisLine: "Investment record prepared for review",
  dimensions: [
    { key: "market", label: "MKT", score: 9 },
    { key: "execution", label: "EXEC", score: 8 },
    { key: "product", label: "PROD", score: 8 },
    { key: "technical", label: "TECH", score: 9 },
    { key: "defensibility", label: "DEF", score: 7 }
  ]
};
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/lib/clocks.ts");
const ZONES = [
  { label: "London", tz: "Europe/London" },
  { label: "San Francisco", tz: "America/Los_Angeles" }
];
function bureauTimes(now = /* @__PURE__ */ new Date()) {
  return ZONES.map(({ label, tz }) => ({
    label,
    time: new Intl.DateTimeFormat("en-GB", {
      timeZone: tz,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false
    }).format(now)
  }));
}
function editionNo(now = /* @__PURE__ */ new Date()) {
  return Math.floor((now.getTime() - Date.UTC(now.getUTCFullYear(), 0, 0)) / 864e5);
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/GalleryFrame.tsx");
function GalleryFrame({ enter = true }) {
  const reduce = useReducedMotion();
  const [times, setTimes] = useState(null);
  const [edition] = useState(editionNo());
  useEffect(() => {
    setTimes(bureauTimes());
    if (reduce) return;
    const id = window.setInterval(() => setTimes(bureauTimes()), 1e3);
    return () => window.clearInterval(id);
  }, [reduce]);
  const frameCx = (side) => enter ? `frame ${side} frame-in` : `frame ${side}`;
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsx("div", { className: "grain" }),
    /* @__PURE__ */ jsx("div", { className: frameCx("tl"), children: /* @__PURE__ */ jsxs(Link, { to: "/home", className: "wordmark", children: [
      "Aethria",
      /* @__PURE__ */ jsx("span", { className: "dot", children: "." })
    ] }) }),
    /* @__PURE__ */ jsxs("div", { className: frameCx("tr"), children: [
      /* @__PURE__ */ jsx("a", { href: "#market", children: "Index" }),
      /* @__PURE__ */ jsx("a", { href: "#access", children: "Access" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: frameCx("bl"), children: (times ?? [{ label: "London", time: "— : —" }, { label: "San Francisco", time: "— : —" }]).map(
      ({ label, time }) => /* @__PURE__ */ jsxs("div", { children: [
        time,
        "   ",
        label
      ] }, label)
    ) }),
    /* @__PURE__ */ jsxs("div", { className: frameCx("br"), children: [
      "Specimen Edition · No. ",
      edition
    ] })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/GalleryLoader.tsx");
function GalleryLoader({ onLift, onDone }) {
  useEffect(() => {
    try {
      sessionStorage.setItem("aethria-intro-seen", "1");
    } catch {
    }
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const liftTimer = window.setTimeout(onLift, 1600);
    const doneTimer = window.setTimeout(onDone, 2450);
    return () => {
      window.clearTimeout(liftTimer);
      window.clearTimeout(doneTimer);
      document.body.style.overflow = prevOverflow;
    };
  }, []);
  return /* @__PURE__ */ jsxs("div", { className: "gallery-loader", children: [
    /* @__PURE__ */ jsx("div", { className: "gallery-loader-grain" }),
    /* @__PURE__ */ jsxs("div", { className: "gallery-loader-center", children: [
      /* @__PURE__ */ jsx("div", { className: "gallery-loader-mark", children: /* @__PURE__ */ jsxs("div", { className: "gallery-loader-wordmark", children: [
        "Aethria",
        /* @__PURE__ */ jsx("span", { className: "gallery-loader-dot", children: "." })
      ] }) }),
      /* @__PURE__ */ jsxs("div", { className: "gallery-loader-label", children: [
        "SPECIMEN EDITION · No. ",
        editionNo()
      ] })
    ] })
  ] });
}
const worldUrl = "/assets/countries-110m-B3KlhDC_.json";
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/DottedMarketMap.tsx");
const ACCENT = "#3d6b5e";
const ACCENT_RGB = "61,107,94";
const INK_RGB = "0,20,51";
function DottedMarketMap({ hits = [], echo = false, className }) {
  const baseRef = useRef(null);
  const fxRef = useRef(null);
  const reduce = useReducedMotion();
  useEffect(() => {
    const base = baseRef.current;
    if (!base) return;
    let raf = 0;
    let rafAssembly = 0;
    let cancelled = false;
    let cleanupResize;
    let cleanupPointer;
    const hoverEnabled = typeof window !== "undefined" && window.matchMedia("(hover: hover)").matches;
    const pointer = { x: -1, y: -1, active: false };
    fetch(worldUrl).then((r) => r.json()).then((world) => {
      if (cancelled) return;
      const land = feature(world, world.objects.countries);
      const drawDots = (canvas, opacity, paint = true) => {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const W = canvas.clientWidth;
        const H = canvas.clientHeight;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        const ctx = canvas.getContext("2d");
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, W, H);
        const proj = geoNaturalEarth1().fitSize([W, H * 1.16], land).translate([W / 2, H / 2]);
        const off = document.createElement("canvas");
        off.width = W;
        off.height = H;
        const octx = off.getContext("2d");
        octx.fillStyle = "#000";
        octx.beginPath();
        geoPath(proj, octx)(land);
        octx.fill();
        const data = octx.getImageData(0, 0, W, H).data;
        const gap = Math.max(5, Math.round(W / 190));
        const landPts = [];
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
        return { proj, W, H, landPts };
      };
      const paintImmediately = echo || !!reduce;
      let info = drawDots(base, echo ? 0.13 : 0.2, paintImmediately);
      let assembled = false;
      let assembling = false;
      let liveStarted = false;
      const fx = fxRef.current;
      let fxctx = null;
      let targets = [];
      let spreads = [];
      let maxR = 0;
      let growth = [];
      let arcs = [];
      const setupFx = () => {
        if (!fx) return;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        fx.width = base.width;
        fx.height = base.height;
        fxctx = fx.getContext("2d");
        fxctx?.scale(dpr, dpr);
        targets = hits.map((h) => info.proj([h.lon, h.lat]));
        maxR = Math.max(60, Math.min(info.W, info.H) * 0.17);
        spreads = targets.map((t) => {
          if (!t) return { pts: [] };
          const pts = [];
          for (const p of info.landPts) {
            const d = Math.hypot(p[0] - t[0], p[1] - t[1]);
            if (d < maxR) pts.push({ p, d });
          }
          return { pts };
        });
        growth = targets.map(() => ({ r: 0, goal: maxR * 0.35 }));
        arcs = [];
      };
      const drawStaticHits = () => {
        if (!fxctx) return;
        fxctx.clearRect(0, 0, info.W, info.H);
        spreads.forEach((s) => {
          s.pts.forEach(({ p, d }) => {
            fxctx.beginPath();
            fxctx.arc(p[0], p[1], 1.1, 0, 6.283);
            fxctx.fillStyle = `rgba(${ACCENT_RGB},${0.35 * (1 - d / maxR)})`;
            fxctx.fill();
          });
        });
        targets.forEach((t) => {
          if (!t) return;
          fxctx.beginPath();
          fxctx.arc(t[0], t[1], 3.4, 0, 6.283);
          fxctx.fillStyle = ACCENT;
          fxctx.fill();
        });
      };
      if (!echo) setupFx();
      const onResize = () => {
        if (assembling && !assembled) assembled = true;
        info = drawDots(base, echo ? 0.13 : 0.2, paintImmediately || assembled);
        if (!echo) {
          setupFx();
          if (reduce) drawStaticHits();
          else if (assembled) startLive();
        }
      };
      window.addEventListener("resize", onResize);
      cleanupResize = () => window.removeEventListener("resize", onResize);
      if (echo) return;
      if (reduce) {
        drawStaticHits();
        return;
      }
      if (hoverEnabled && fx) {
        const onMove = (e) => {
          const rect = fx.getBoundingClientRect();
          pointer.x = e.clientX - rect.left;
          pointer.y = e.clientY - rect.top;
          pointer.active = true;
        };
        const onLeave = () => {
          pointer.active = false;
        };
        fx.addEventListener("pointermove", onMove);
        fx.addEventListener("pointerleave", onLeave);
        cleanupPointer = () => {
          fx.removeEventListener("pointermove", onMove);
          fx.removeEventListener("pointerleave", onLeave);
        };
      }
      const GROW_STEP = () => maxR * 0.22;
      const FRONT = 12;
      const spawnArc = () => {
        if (!info.landPts.length || !targets.length) return;
        const hi = Math.random() * targets.length | 0;
        const t = targets[hi];
        if (!t) return;
        const s = info.landPts[Math.random() * info.landPts.length | 0];
        const mx = (s[0] + t[0]) / 2;
        const my = (s[1] + t[1]) / 2 - Math.hypot(t[0] - s[0], t[1] - s[1]) * 0.28;
        arcs.push({ s, t, c: [mx, my], hi, p: 0, sp: 6e-3 + Math.random() * 6e-3 });
      };
      let last = 0;
      const frame = (ts) => {
        if (cancelled || !fxctx) return;
        const { W, H } = info;
        fxctx.clearRect(0, 0, W, H);
        if (ts - last > 520) {
          last = ts;
          spawnArc();
          if (Math.random() < 0.5) spawnArc();
        }
        arcs = arcs.filter((a) => {
          if (a.p < 1) return true;
          const g = growth[a.hi];
          if (g) g.goal = Math.min(g.goal + GROW_STEP(), maxR);
          return false;
        });
        arcs.forEach((a) => {
          a.p += a.sp;
          const bez = (t) => [
            (1 - t) * (1 - t) * a.s[0] + 2 * (1 - t) * t * a.c[0] + t * t * a.t[0],
            (1 - t) * (1 - t) * a.s[1] + 2 * (1 - t) * t * a.c[1] + t * t * a.t[1]
          ];
          fxctx.beginPath();
          const tail = Math.max(0, a.p - 0.18);
          for (let t = tail; t <= a.p; t += 0.02) {
            const q = bez(t);
            if (t === tail) fxctx.moveTo(q[0], q[1]);
            else fxctx.lineTo(q[0], q[1]);
          }
          fxctx.strokeStyle = `rgba(${ACCENT_RGB},0.55)`;
          fxctx.lineWidth = 1.1;
          fxctx.stroke();
          const head = bez(Math.min(a.p, 1));
          fxctx.beginPath();
          fxctx.arc(head[0], head[1], 1.8, 0, 6.283);
          fxctx.fillStyle = ACCENT;
          fxctx.fill();
        });
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
            fxctx.beginPath();
            fxctx.arc(p[0], p[1], 1.3, 0, 6.283);
            fxctx.fillStyle = `rgba(${ACCENT_RGB},${a})`;
            fxctx.fill();
          });
        });
        targets.forEach((t) => {
          if (!t) return;
          const glow = fxctx.createRadialGradient(t[0], t[1], 0, t[0], t[1], 16);
          glow.addColorStop(0, `rgba(${ACCENT_RGB},0.22)`);
          glow.addColorStop(1, `rgba(${ACCENT_RGB},0)`);
          fxctx.beginPath();
          fxctx.arc(t[0], t[1], 16, 0, 6.283);
          fxctx.fillStyle = glow;
          fxctx.fill();
          const r = 6 + 6 * Math.abs(Math.sin(ts / 700));
          fxctx.beginPath();
          fxctx.arc(t[0], t[1], r, 0, 6.283);
          fxctx.strokeStyle = `rgba(${ACCENT_RGB},${0.45 - (r - 6) / 26})`;
          fxctx.lineWidth = 1;
          fxctx.stroke();
          fxctx.beginPath();
          fxctx.arc(t[0], t[1], 3.4, 0, 6.283);
          fxctx.fillStyle = ACCENT;
          fxctx.fill();
        });
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
            fxctx.beginPath();
            fxctx.arc(p[0], p[1], 1.35, 0, 6.283);
            fxctx.fillStyle = `rgba(${ACCENT_RGB},${a})`;
            fxctx.fill();
          }
          const reach = Math.max(W, H) * 0.62;
          targets.filter((t) => !!t).map((t) => ({ t, d: Math.hypot(t[0] - pointer.x, t[1] - pointer.y) })).sort((a, b) => a.d - b.d).slice(0, 3).forEach(({ t, d }) => {
            const a = 0.34 * (1 - d / reach);
            if (a <= 0.01) return;
            fxctx.beginPath();
            fxctx.moveTo(pointer.x, pointer.y);
            fxctx.lineTo(t[0], t[1]);
            fxctx.strokeStyle = `rgba(${ACCENT_RGB},${a})`;
            fxctx.lineWidth = 1;
            fxctx.stroke();
          });
          fxctx.beginPath();
          fxctx.arc(pointer.x, pointer.y, 5.5, 0, 6.283);
          fxctx.strokeStyle = `rgba(${ACCENT_RGB},0.6)`;
          fxctx.lineWidth = 1;
          fxctx.stroke();
          fxctx.beginPath();
          fxctx.arc(pointer.x, pointer.y, 2, 0, 6.283);
          fxctx.fillStyle = ACCENT;
          fxctx.fill();
        }
        raf = requestAnimationFrame(frame);
      };
      const startLive = () => {
        if (liveStarted) return;
        liveStarted = true;
        raf = requestAnimationFrame(frame);
      };
      const runAssembly = () => {
        if (assembling || assembled) return;
        assembling = true;
        const ctx = base.getContext("2d");
        const { W, H, landPts } = info;
        const parts = landPts.map(([tx, ty]) => ({
          tx,
          ty,
          x: Math.random() * W * 1.4 - W * 0.2,
          y: Math.random() * H * 1.4 - H * 0.2,
          vx: 0,
          vy: 0
        }));
        const t0 = performance.now();
        const DUR = 1900;
        const step = (ts) => {
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
          info = drawDots(base, 0.2);
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
        { threshold: 0.2 }
      );
      io.observe(base);
      const removeResize = cleanupResize;
      cleanupResize = () => {
        removeResize?.();
        io.disconnect();
      };
    }).catch(() => {
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      cancelAnimationFrame(rafAssembly);
      cleanupResize?.();
      cleanupPointer?.();
    };
  }, [echo, reduce, hits]);
  return /* @__PURE__ */ jsxs("div", { className, style: { position: "relative" }, "aria-hidden": true, children: [
    /* @__PURE__ */ jsx("canvas", { ref: baseRef, style: { position: "absolute", inset: 0, width: "100%", height: "100%" } }),
    !echo && /* @__PURE__ */ jsx("canvas", { ref: fxRef, style: { position: "absolute", inset: 0, width: "100%", height: "100%" } })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/lib/scrollToAnchor.ts");
function scrollToAnchor(e, href) {
  const el = document.querySelector(href);
  if (!el) return;
  e.preventDefault();
  const lenis = window.__lenis;
  if (lenis) lenis.scrollTo(el, { offset: -88 });
  else el.scrollIntoView({ behavior: "smooth", block: "start" });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/HeroPlate.tsx");
function HeroPlate({ enter = true }) {
  return /* @__PURE__ */ jsxs("section", { className: enter ? "hero hero-in" : "hero", children: [
    /* @__PURE__ */ jsx("div", { className: "hero-echo", children: /* @__PURE__ */ jsx(DottedMarketMap, { echo: true, className: "h-full w-full" }) }),
    /* @__PURE__ */ jsx("div", { className: "hero-veil" }),
    /* @__PURE__ */ jsxs("div", { className: "hero-center", children: [
      /* @__PURE__ */ jsx("div", { className: "hero-kicker", children: "Private-market intelligence" }),
      /* @__PURE__ */ jsx("h1", { className: "hero-statement", children: "Private-market judgment, on the record." }),
      /* @__PURE__ */ jsx("p", { className: "hero-standfirst", children: "Aethria sources private companies, evaluates each opportunity against your fund mandate, and preserves every decision as institutional memory." }),
      /* @__PURE__ */ jsxs("div", { className: "hero-ctas", children: [
        /* @__PURE__ */ jsx("a", { href: "#access", className: "cta-primary", onClick: (e) => scrollToAnchor(e, "#access"), children: "Request access" }),
        /* @__PURE__ */ jsx("a", { href: "#market", className: "cta-secondary", onClick: (e) => scrollToAnchor(e, "#market"), children: "View the system" })
      ] })
    ] })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/Plate.tsx");
function Plate({
  id,
  index,
  title,
  capLeft,
  capRight,
  children,
  headingLevel = 2
}) {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const [isIn, setIsIn] = useState(false);
  useEffect(() => {
    if (reduce || typeof IntersectionObserver === "undefined") {
      setIsIn(true);
      return;
    }
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsIn(true);
          io.unobserve(el);
        }
      },
      { threshold: 0.28 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reduce]);
  return /* @__PURE__ */ jsxs("section", { ref, id, className: `plate${isIn ? " in" : ""}`, children: [
    /* @__PURE__ */ jsx("span", { className: "plate-cap-l", children: capLeft }),
    /* @__PURE__ */ jsx("span", { className: "plate-cap-r", children: capRight }),
    /* @__PURE__ */ jsxs("div", { className: "framed", children: [
      /* @__PURE__ */ jsxs("div", { className: "plate-head", children: [
        createElement("h" + headingLevel, { className: "plate-title reveal" }, title),
        /* @__PURE__ */ jsx("div", { className: "plate-num reveal d1", children: index })
      ] }),
      children
    ] })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/MarketPlate.tsx");
const HITS = [
  { lon: 103.82, lat: 1.35 },
  // Singapore
  { lon: 77.59, lat: 12.97 },
  // Bangalore
  { lon: -74.01, lat: 40.71 },
  // New York
  { lon: 151.21, lat: -33.87 },
  // Sydney
  { lon: -79.38, lat: 43.65 },
  // Toronto
  { lon: -0.12, lat: 51.5 },
  // London
  { lon: -122.42, lat: 37.77 }
  // San Francisco
];
const SCANNED_TOTAL = 12408;
const IN_THESIS = HITS.length;
function MarketPlate() {
  const reduce = useReducedMotion();
  const scannedRef = useRef(null);
  const rootRef = useRef(null);
  useEffect(() => {
    const el = scannedRef.current;
    const root = rootRef.current;
    if (!el || !root) return;
    if (reduce) {
      el.textContent = SCANNED_TOTAL.toLocaleString();
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        const counter = { v: 0 };
        gsap.to(counter, {
          v: SCANNED_TOTAL,
          duration: 2.1,
          ease: "power2.out",
          onUpdate: () => {
            el.textContent = Math.round(counter.v).toLocaleString();
          }
        });
      },
      { threshold: 0.3 }
    );
    obs.observe(root);
    return () => obs.disconnect();
  }, [reduce]);
  return /* @__PURE__ */ jsx(
    Plate,
    {
      id: "market",
      index: "01 — 08",
      title: "The Market",
      capLeft: "The Market — Plate 01",
      capRight: "Every company scanned · the few that fit",
      children: /* @__PURE__ */ jsxs("div", { ref: rootRef, children: [
        /* @__PURE__ */ jsx("div", { className: "market-stage reveal d2", children: /* @__PURE__ */ jsx(DottedMarketMap, { hits: HITS, className: "h-full w-full" }) }),
        /* @__PURE__ */ jsxs("p", { className: "caption reveal d3", children: [
          "Every company reads as a faint mark. The few inside your active thesis glow; scouts fire toward them and conviction spreads through the surrounding field. The field at press time —",
          " ",
          /* @__PURE__ */ jsx("span", { ref: scannedRef, className: "text-[var(--accent)]", children: SCANNED_TOTAL.toLocaleString() }),
          " ",
          "companies scanned · ",
          /* @__PURE__ */ jsx("span", { className: "text-[var(--accent)]", children: IN_THESIS }),
          " inside your thesis today."
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "reveal d3 mt-5 flex flex-wrap gap-7 border-t border-solid border-[var(--line)] pt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--ink-3)]", children: [
          /* @__PURE__ */ jsxs("span", { className: "inline-flex items-center gap-2", children: [
            /* @__PURE__ */ jsx("i", { className: "inline-block h-[7px] w-[7px] rounded-full bg-[var(--ink-3)]" }),
            " Scanned"
          ] }),
          /* @__PURE__ */ jsxs("span", { className: "inline-flex items-center gap-2", children: [
            /* @__PURE__ */ jsx("i", { className: "inline-block h-[7px] w-[7px] rounded-full bg-[var(--accent)]" }),
            " Inside your thesis"
          ] })
        ] })
      ] })
    }
  );
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/lib/CountUp.tsx");
function CountUp({ to, active, reduce }) {
  const [n, setN] = useState(reduce ? to : 0);
  useEffect(() => {
    if (reduce || !active) return;
    let raf = 0;
    const start = performance.now();
    const dur = 850;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / dur);
      setN(Math.round(to * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, to, reduce]);
  return /* @__PURE__ */ jsx(Fragment, { children: n });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/RecordPlate.tsx");
const DIMS = [
  { label: "Market", to: 9 },
  { label: "Product", to: 8 },
  { label: "Technical", to: 9 },
  { label: "Execution", to: 8 },
  { label: "Defensibility", to: 7 }
];
function RecordPlate() {
  const reduce = useReducedMotion();
  const [active, setActive] = useState(false);
  const rootRef = useRef(null);
  useEffect(() => {
    const root = rootRef.current;
    if (!root || reduce) {
      setActive(true);
      return;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        setActive(true);
      },
      { threshold: 0.3 }
    );
    obs.observe(root);
    return () => obs.disconnect();
  }, [reduce]);
  return /* @__PURE__ */ jsxs(Plate, { id: "record", index: "02 — 08", title: "The Record", capLeft: "The Record — Plate 02", capRight: "One verdict · five dimensions", children: [
    /* @__PURE__ */ jsxs("div", { ref: rootRef, className: "record", children: [
      /* @__PURE__ */ jsxs("div", { className: "record-top reveal d2", children: [
        /* @__PURE__ */ jsx("div", { className: "record-name", children: "Meridian Compute" }),
        /* @__PURE__ */ jsx("div", { className: "record-verdict", children: "Invest" })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "dims reveal d3", children: DIMS.map((dim) => /* @__PURE__ */ jsxs("div", { className: "dim", children: [
        /* @__PURE__ */ jsx("div", { className: "n", children: /* @__PURE__ */ jsx(CountUp, { to: dim.to, active, reduce: !!reduce }) }),
        /* @__PURE__ */ jsx("div", { className: "k", children: dim.label })
      ] }, dim.label)) }),
      /* @__PURE__ */ jsxs("div", { className: "record-reasoning reveal d3", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h5", { children: "Why it fits the mandate" }),
          /* @__PURE__ */ jsx("p", { children: "First credible team to own this layer of the stack. The timing window is open now." })
        ] }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h5", { children: "What could break the thesis" }),
          /* @__PURE__ */ jsx("p", { children: "Defensibility leans on a single integration partner. Replaceable inside eighteen months." })
        ] })
      ] })
    ] }),
    /* @__PURE__ */ jsx("p", { className: "caption left reveal d3", children: "B2B Infrastructure · Series A · London. A specimen record: reviewers score each dimension one to ten against your thesis; the partner engine rules invest, pass, or monitor." })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/ReviewPlate.tsx");
function ReviewPlate() {
  return /* @__PURE__ */ jsxs(
    Plate,
    {
      id: "review",
      index: "03 — 08",
      title: "The Review",
      capLeft: "The Review — Plate 03",
      capRight: "The disagreement, preserved",
      children: [
        /* @__PURE__ */ jsx("p", { className: "review-statement reveal d2", children: "Investment judgment is not consensus." }),
        /* @__PURE__ */ jsxs("div", { className: "review reveal d2", children: [
          /* @__PURE__ */ jsxs("div", { className: "side", children: [
            /* @__PURE__ */ jsxs("div", { className: "h for", children: [
              "Opportunist — for ",
              /* @__PURE__ */ jsx("span", { className: "num", children: "8" })
            ] }),
            /* @__PURE__ */ jsx("div", { className: "lede", children: "First credible team to own this layer of the stack." }),
            /* @__PURE__ */ jsx("p", { children: "The timing window is open now." })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "side", children: [
            /* @__PURE__ */ jsxs("div", { className: "h against", children: [
              "Skeptical — against ",
              /* @__PURE__ */ jsx("span", { className: "num", children: "4" })
            ] }),
            /* @__PURE__ */ jsx("div", { className: "lede", children: "Defensibility leans on a single integration partner." }),
            /* @__PURE__ */ jsx("p", { children: "Replaceable inside eighteen months." })
          ] })
        ] }),
        /* @__PURE__ */ jsx("p", { className: "caption reveal d3", children: "Even the balanced base case lands at 7 — real wedge and a credible team, but capital intensity compresses the early-stage return profile. Built to disagree: the split stays on the record, never averaged into a number that hides the argument." })
      ]
    }
  );
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/NewsroomPlate.tsx");
function NewsroomPlate() {
  return /* @__PURE__ */ jsxs(
    Plate,
    {
      id: "method",
      index: "04 — 08",
      title: "The Newsroom",
      capLeft: "The Newsroom — Plate 04",
      capRight: "Who works the story",
      children: [
        /* @__PURE__ */ jsxs("div", { className: "newsroom-flow reveal d2", "aria-label": "Pipeline order", children: [
          /* @__PURE__ */ jsx("span", { children: "Mandate" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Scouts" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Evidence" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Reviewers" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Partner" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Record" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Memory" }),
          /* @__PURE__ */ jsx("span", { className: "arrow", children: "→" }),
          /* @__PURE__ */ jsx("span", { children: "Portfolio" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "staff reveal d2", children: [
          /* @__PURE__ */ jsxs("div", { className: "col", children: [
            /* @__PURE__ */ jsx("h4", { children: "Scouts — source the field" }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Market-Driven" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "web + tavily" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Builder / Technical" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "web + tavily" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Pain-Point" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "web + tavily" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Contrarian" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "web + tavily" })
            ] })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "col", children: [
            /* @__PURE__ */ jsx("h4", { children: "Reviewers — score the mandate" }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Default" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "1–10 · 5 dims" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Skeptical" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "built to dissent" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Opportunist" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "built to back" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "row", children: [
              /* @__PURE__ */ jsx("span", { children: "Partner Engine" }),
              /* @__PURE__ */ jsx("span", { className: "role", children: "rules v1 · invest/pass/monitor" })
            ] })
          ] })
        ] }),
        /* @__PURE__ */ jsx("p", { className: "caption reveal d3", children: "It only looks for what you tell it to. A masthead of agents. Scouts source, reviewers argue, the partner rules, the portfolio watches, and the meta-agent calibrates the newsroom against real outcomes." })
      ]
    }
  );
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/CorrectionsPlate.tsx");
function CorrectionsPlate() {
  return /* @__PURE__ */ jsxs(
    Plate,
    {
      id: "corrections",
      index: "05 — 08",
      title: "Corrections & Revisions",
      capLeft: "Corrections & Revisions — Plate 05",
      capRight: "Every revision, versioned and logged",
      children: [
        /* @__PURE__ */ jsxs("div", { className: "corrections reveal d2", children: [
          /* @__PURE__ */ jsx("h4", { children: "Meta-Agent — daily pass" }),
          /* @__PURE__ */ jsxs("p", { children: [
            /* @__PURE__ */ jsx("b", { children: "Reweighted" }),
            " — scout weighting shifts with outcomes: market-driven up, pain-point down, against the active thesis."
          ] }),
          /* @__PURE__ */ jsxs("p", { children: [
            /* @__PURE__ */ jsx("b", { children: "Recalibrated" }),
            " — reviewer thresholds adjust so the score that gates invest/pass/monitor tracks real conviction, not drift."
          ] }),
          /* @__PURE__ */ jsxs("p", { children: [
            /* @__PURE__ */ jsx("b", { children: "Revised" }),
            " — underperforming scout prompts are revised and versioned before the next cycle runs."
          ] })
        ] }),
        /* @__PURE__ */ jsx("p", { className: "caption reveal d3", children: "Once a day the meta-agent reviews pipeline outcomes and calibrates the system that produced them — weights, thresholds, prompts — each revision versioned and logged, never silent." })
      ]
    }
  );
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/QueryPlate.tsx");
const CHAR_MIN_MS = 60;
const CHAR_MAX_MS = 90;
const MEMO_DELAY_MS = 500;
const TYPED_QUERY = `look up  ${DEMO_LOOKUP_QUERY.toLowerCase()}`;
function QueryPlate() {
  const reduce = useReducedMotion();
  const rootRef = useRef(null);
  const started = useRef(false);
  const timeoutRef = useRef(null);
  const [typed, setTyped] = useState(TYPED_QUERY);
  const [memoIn, setMemoIn] = useState(true);
  const [caretOn, setCaretOn] = useState(false);
  useEffect(() => {
    if (reduce) return;
    setTyped("");
    setMemoIn(false);
    setCaretOn(true);
    const runSequence = () => {
      if (started.current) return;
      started.current = true;
      let i = 0;
      const typeChar = () => {
        i += 1;
        setTyped(TYPED_QUERY.slice(0, i));
        if (i < TYPED_QUERY.length) {
          timeoutRef.current = window.setTimeout(typeChar, CHAR_MIN_MS + Math.random() * (CHAR_MAX_MS - CHAR_MIN_MS));
        } else {
          timeoutRef.current = window.setTimeout(() => setMemoIn(true), MEMO_DELAY_MS);
        }
      };
      timeoutRef.current = window.setTimeout(typeChar, CHAR_MIN_MS + Math.random() * (CHAR_MAX_MS - CHAR_MIN_MS));
    };
    const clearPendingTimeout = () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
    const root = rootRef.current;
    if (!root || typeof IntersectionObserver === "undefined") {
      runSequence();
      return clearPendingTimeout;
    }
    const obs = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        runSequence();
      },
      { threshold: 0.3 }
    );
    obs.observe(root);
    return () => {
      obs.disconnect();
      clearPendingTimeout();
    };
  }, [reduce]);
  return /* @__PURE__ */ jsxs(
    Plate,
    {
      id: "query",
      index: "06 — 08",
      title: "Place a Query",
      capLeft: "Place a Query — Plate 06",
      capRight: "Any name · a sourced record",
      children: [
        /* @__PURE__ */ jsxs("div", { ref: rootRef, className: "query reveal d2", "aria-hidden": true, children: [
          /* @__PURE__ */ jsxs("div", { className: "query-bar", children: [
            /* @__PURE__ */ jsx("span", { className: "p", children: "›" }),
            /* @__PURE__ */ jsx("span", { className: "query-text", children: typed }),
            caretOn ? /* @__PURE__ */ jsx("span", { className: "query-caret" }) : null
          ] }),
          /* @__PURE__ */ jsx("div", { className: `memo-reveal${memoIn ? " in" : ""}`, children: /* @__PURE__ */ jsx(LookupResultSnapshot, { ...DEMO_LOOKUP_RESULT }) })
        ] }),
        /* @__PURE__ */ jsx("p", { className: "caption reveal d3", children: "On-demand lookup turns any company name into a sourced investment record in seconds — benchmarked against your active thesis the moment results arrive." })
      ]
    }
  );
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/HoldingsPlate.tsx");
const HOLDINGS = [
  { name: "Meridian Compute", stage: "Series A", signal: "Strong", health: "On track" },
  { name: "Halden Systems", stage: "Seed", signal: "Watching", health: "On track" },
  { name: "Cormorant Labs", stage: "Series B", signal: "Strong", health: "At risk" }
];
function HoldingsPlate() {
  return /* @__PURE__ */ jsxs(Plate, { id: "holdings", index: "07 — 08", title: "Holdings", capLeft: "Holdings — Plate 07", capRight: "What the fund carries", children: [
    /* @__PURE__ */ jsxs("table", { className: "holdings reveal d2", children: [
      /* @__PURE__ */ jsx("thead", { children: /* @__PURE__ */ jsxs("tr", { children: [
        /* @__PURE__ */ jsx("th", { children: "Company" }),
        /* @__PURE__ */ jsx("th", { children: "Stage" }),
        /* @__PURE__ */ jsx("th", { children: "Signal" }),
        /* @__PURE__ */ jsx("th", { children: "Health" })
      ] }) }),
      /* @__PURE__ */ jsx("tbody", { children: HOLDINGS.map((h) => /* @__PURE__ */ jsxs("tr", { children: [
        /* @__PURE__ */ jsx("td", { className: "name", children: h.name }),
        /* @__PURE__ */ jsx("td", { children: h.stage }),
        /* @__PURE__ */ jsx("td", { children: /* @__PURE__ */ jsx("span", { className: "sig", children: h.signal }) }),
        /* @__PURE__ */ jsx("td", { children: h.health })
      ] }, h.name)) })
    ] }),
    /* @__PURE__ */ jsx("p", { className: "caption reveal d3", children: "Specimen holdings. Every accepted name is carried by the portfolio engine — execution tracked, signals watched, health checked — for as long as it stays in the fund." })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/AccessForm.tsx");
const PROCESSING_DURATION_MS = 1200;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const URL_REGEX = /^https?:\/\/.+/;
const WAITLIST_URL = "/api/waitlist";
const APP_URL = "";
const EASE_OUT_EXPO = "cubic-bezier(0.16, 1, 0.3, 1)";
const TRANSITION_FORM_OUT = "opacity 0.22s ease, transform 0.22s ease";
const TRANSITION_SUCCESS_REVEAL = `opacity 0.55s ${EASE_OUT_EXPO}, transform 0.55s ${EASE_OUT_EXPO}`;
function AccessForm() {
  const [searchParams] = useSearchParams();
  const prefilledEmail = searchParams.get("email")?.trim() ?? "";
  const [submitted, setSubmitted] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationError, setValidationError] = useState(false);
  const [position, setPosition] = useState(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState(prefilledEmail);
  const [role, setRole] = useState("");
  const [firm, setFirm] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);
  const [formOut, setFormOut] = useState(false);
  const [ellipsisStep, setEllipsisStep] = useState(0);
  const abortRef = useRef(null);
  useEffect(() => {
    if (prefilledEmail) setEmail(prefilledEmail);
  }, [prefilledEmail]);
  useEffect(() => {
    if (!processing) return;
    const t = setTimeout(() => {
      setProcessing(false);
      setFormOut(true);
    }, PROCESSING_DURATION_MS);
    return () => clearTimeout(t);
  }, [processing]);
  useEffect(() => {
    if (!formOut) return;
    const t1 = setTimeout(() => setSubmitted(true), 200);
    const t2 = setTimeout(() => setShowSuccess(true), 300);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [formOut]);
  useEffect(() => {
    if (!loading) return;
    const interval = setInterval(() => setEllipsisStep((p) => (p + 1) % 4), 220);
    return () => clearInterval(interval);
  }, [loading]);
  useEffect(() => () => abortRef.current?.abort(), []);
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setValidationError(false);
    const n = name.trim(), em = email.trim(), r = role.trim(), f = firm.trim();
    if (!n || !em || !r || !f) {
      setValidationError(true);
      return;
    }
    if (!EMAIL_REGEX.test(em)) {
      setError("Please enter a valid email address.");
      return;
    }
    const li = linkedin.trim();
    if (li && !URL_REGEX.test(li)) {
      setError("LinkedIn URL must start with https://");
      return;
    }
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    setLoading(true);
    try {
      const res = await fetch(WAITLIST_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortRef.current.signal,
        body: JSON.stringify({ name: n, email: em, role: r, firm: f, linkedin: li || void 0 })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const msg = typeof data.detail === "string" ? data.detail : data.detail?.message || `Request failed (${res.status}).`;
        throw new Error(msg);
      }
      const resData = await res.json().catch(() => ({}));
      if (resData.position != null) setPosition(resData.position);
      setLoading(false);
      setProcessing(true);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };
  const ne = validationError && !name.trim();
  const ee = validationError && !email.trim();
  const re = validationError && !role.trim();
  const fe = validationError && !firm.trim();
  if (submitted) {
    return /* @__PURE__ */ jsxs("div", { style: { opacity: showSuccess ? 1 : 0, transform: showSuccess ? "translateY(0)" : "translateY(12px)", transition: TRANSITION_SUCCESS_REVEAL }, children: [
      /* @__PURE__ */ jsx("p", { className: "mb-3 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--color-brand-mark-inverse)]", children: "Entry recorded" }),
      /* @__PURE__ */ jsx("h3", { className: "mb-4 editorial-display text-[clamp(1.6rem,3vw,2.1rem)] font-normal leading-[1.1] tracking-[-0.02em] text-[var(--text-inverse)]", children: "You're on the list." }),
      /* @__PURE__ */ jsxs("p", { className: "max-w-[42ch] font-sans text-[15px] leading-[1.65] text-[var(--text-inverse-secondary)]", children: [
        position != null ? /* @__PURE__ */ jsxs("span", { className: "block font-medium text-[var(--text-inverse)]", children: [
          "Position #",
          position
        ] }) : null,
        /* @__PURE__ */ jsx("span", { className: "mt-1 block", children: "We'll reach out when a spot opens." })
      ] }),
      APP_URL
    ] });
  }
  return /* @__PURE__ */ jsx("div", { style: { opacity: formOut ? 0 : 1, transform: formOut ? "translateY(-8px)" : "translateY(0)", transition: TRANSITION_FORM_OUT }, children: /* @__PURE__ */ jsx("div", { className: "relative border border-dashed border-[rgba(244,241,234,0.3)] p-6 sm:p-8", children: /* @__PURE__ */ jsxs("form", { onSubmit: handleSubmit, className: "flex flex-col gap-6", noValidate: true, children: [
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 gap-6 sm:grid-cols-2", children: [
      /* @__PURE__ */ jsx(InverseField, { id: "af-name", label: "Name", type: "text", value: name, onChange: setName, error: ne, autoComplete: "name", maxLength: 100 }),
      /* @__PURE__ */ jsx(InverseField, { id: "af-email", label: "Email", type: "email", value: email, onChange: setEmail, error: ee, autoComplete: "email", maxLength: 320 })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-1 gap-6 sm:grid-cols-2", children: [
      /* @__PURE__ */ jsx(InverseField, { id: "af-role", label: "Role", type: "text", value: role, onChange: setRole, error: re, autoComplete: "organization-title", maxLength: 100 }),
      /* @__PURE__ */ jsx(InverseField, { id: "af-firm", label: "Firm", type: "text", value: firm, onChange: setFirm, error: fe, autoComplete: "organization", maxLength: 200 })
    ] }),
    /* @__PURE__ */ jsx(
      InverseField,
      {
        id: "af-linkedin",
        label: "LinkedIn",
        optional: true,
        type: "url",
        value: linkedin,
        onChange: setLinkedin,
        autoComplete: "off",
        maxLength: 2e3,
        placeholder: "https://linkedin.com/in/..."
      }
    ),
    validationError && /* @__PURE__ */ jsx("p", { id: "af-validation-error", role: "alert", className: "font-mono text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--text-inverse)]", children: "Complete all required fields" }),
    error && /* @__PURE__ */ jsx("p", { role: "alert", className: "font-sans text-[14px] font-medium leading-relaxed text-[var(--text-inverse)]", children: error }),
    /* @__PURE__ */ jsxs(
      "button",
      {
        type: "submit",
        disabled: loading || processing,
        className: "group mt-1 inline-flex min-h-[46px] w-full cursor-pointer items-center justify-center bg-[var(--color-paper)] px-6 py-3 font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-oxford)] transition-colors duration-200 hover:bg-[var(--text-inverse)] disabled:cursor-not-allowed disabled:opacity-55",
        children: [
          /* @__PURE__ */ jsx("span", { children: loading ? `Submitting${".".repeat(ellipsisStep)}` : processing ? "Processing" : "Submit application" }),
          /* @__PURE__ */ jsx(
            "span",
            {
              className: `inline-block shrink-0 overflow-hidden whitespace-nowrap transition-[width] duration-200 ${loading || processing ? "w-6" : "w-2 group-hover:w-6"}`,
              "aria-hidden": true,
              children: " →"
            }
          )
        ]
      }
    )
  ] }) }) });
}
function InverseField({
  id,
  label,
  optional,
  type,
  value,
  onChange,
  error,
  autoComplete,
  maxLength,
  placeholder
}) {
  return /* @__PURE__ */ jsxs("div", { className: "flex flex-col", children: [
    /* @__PURE__ */ jsxs("label", { htmlFor: id, className: "font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--text-inverse-muted)]", children: [
      label,
      optional && /* @__PURE__ */ jsx("span", { className: "ml-1 font-normal normal-case opacity-60 tracking-normal", children: "(optional)" })
    ] }),
    /* @__PURE__ */ jsx(
      "input",
      {
        id,
        type,
        value,
        onChange: (e) => onChange(e.target.value),
        placeholder,
        className: `mt-2 w-full border-0 border-b border-solid bg-transparent pb-2.5 font-sans text-[15px] text-[var(--text-inverse)] outline-none transition-colors duration-300 placeholder:font-mono placeholder:text-[11px] placeholder:text-[rgba(244,241,234,0.35)] focus:border-[var(--color-brand-mark-inverse)] ${error ? "border-[#c98d86]" : "border-[rgba(244,241,234,0.28)]"}`,
        autoComplete,
        maxLength,
        required: !optional,
        "aria-required": !optional ? "true" : void 0,
        "aria-invalid": error ? "true" : void 0,
        "aria-describedby": error ? "af-validation-error" : void 0
      }
    )
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/plates/AccessPlate.tsx");
function AccessPlate() {
  return /* @__PURE__ */ jsxs(Fragment, { children: [
    /* @__PURE__ */ jsxs(Plate, { id: "access", index: "08 — 08", title: "Request Access", capLeft: "Access — Plate 08", capRight: "Seats open in small batches", children: [
      /* @__PURE__ */ jsxs("div", { className: "reveal d2", style: { textAlign: "center" }, children: [
        /* @__PURE__ */ jsx("p", { className: "hero-kicker", children: "Request access" }),
        /* @__PURE__ */ jsx("h3", { className: "hero-statement", style: { fontSize: "clamp(1.8rem, 4vw, 3.2rem)" }, children: "For funds that need judgment with memory." })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "reveal d3", style: { marginTop: "2.5rem", backgroundColor: "var(--color-oxford)", padding: "clamp(1.5rem, 4vw, 2.5rem)" }, children: /* @__PURE__ */ jsx(AccessForm, {}) })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "colophon", children: [
      /* @__PURE__ */ jsxs("div", { style: { maxWidth: "32ch" }, children: [
        /* @__PURE__ */ jsxs("span", { className: "wm", children: [
          "Aethria",
          /* @__PURE__ */ jsx("span", { style: { color: "var(--accent)" }, children: "." })
        ] }),
        /* @__PURE__ */ jsx("p", { children: "Private-market intelligence for funds that need the evidence trail, not another beautiful spreadsheet." })
      ] }),
      /* @__PURE__ */ jsx("div", { children: /* @__PURE__ */ jsxs("p", { children: [
        "Set in Playfair Display,",
        /* @__PURE__ */ jsx("br", {}),
        "Instrument Sans & Space Mono."
      ] }) }),
      /* @__PURE__ */ jsx("div", { children: /* @__PURE__ */ jsxs("p", { children: [
        "London · San Francisco",
        /* @__PURE__ */ jsx("br", {}),
        "Specimen Edition · © ",
        (/* @__PURE__ */ new Date()).getFullYear()
      ] }) })
    ] })
  ] });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/HomePage.tsx");
function HomePage() {
  const reduce = useReducedMotion();
  const [entered, setEntered] = useState(false);
  const [showLoader, setShowLoader] = useState(false);
  useEffect(() => {
    let seen = true;
    try {
      seen = typeof window === "undefined" || sessionStorage.getItem("aethria-intro-seen") === "1";
    } catch {
    }
    if (reduce || seen) {
      setEntered(true);
      return;
    }
    setShowLoader(true);
  }, [reduce]);
  useEffect(() => {
    if (window.location.hash !== "#access") return;
    const el = document.getElementById("access");
    if (!el) return;
    const t = setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "start" }), 300);
    return () => clearTimeout(t);
  }, []);
  return /* @__PURE__ */ jsxs(
    "div",
    {
      className: "relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden",
      style: { backgroundColor: "var(--surface-base)", color: "var(--text-primary)" },
      children: [
        showLoader && /* @__PURE__ */ jsx(
          GalleryLoader,
          {
            onLift: () => setEntered(true),
            onDone: () => setShowLoader(false)
          }
        ),
        /* @__PURE__ */ jsx(GalleryFrame, { enter: entered }),
        /* @__PURE__ */ jsx(HeroPlate, { enter: entered }),
        /* @__PURE__ */ jsxs("div", { className: "gallery", children: [
          /* @__PURE__ */ jsx(MarketPlate, {}),
          /* @__PURE__ */ jsx(RecordPlate, {}),
          /* @__PURE__ */ jsx(ReviewPlate, {}),
          /* @__PURE__ */ jsx(NewsroomPlate, {}),
          /* @__PURE__ */ jsx(CorrectionsPlate, {}),
          /* @__PURE__ */ jsx(QueryPlate, {}),
          /* @__PURE__ */ jsx(HoldingsPlate, {}),
          /* @__PURE__ */ jsx(AccessPlate, {})
        ] })
      ]
    }
  );
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/components/AnimatedRoutes.tsx");
const DURATION = 0.3;
const EASE = [0.16, 1, 0.3, 1];
const PAPER = "#D9D7D4";
let animateEntrances = false;
const privateModules = /* @__PURE__ */ Object.assign({});
const privateRoutes = {};
for (const key of Object.keys(privateModules)) {
  const segment = key.replace(/^\.\.\/private\//, "").replace(/\.tsx$/, "").toLowerCase();
  if (segment) {
    const path = "/" + segment;
    privateRoutes[path] = lazy(privateModules[key]);
  }
}
const PUBLIC_PATHS = ["/", "/home", "/request-access"];
function AnimatedRoutes() {
  const location = useLocation();
  const navigate = useNavigate();
  const pathname = location.pathname;
  useEffect(() => {
    if (pathname !== "/request-access") return;
    navigate(`/home${location.search}#access`, { replace: true });
  }, [pathname, location.search, navigate]);
  let element = null;
  if (pathname === "/" || pathname === "/home") element = /* @__PURE__ */ jsx(HomePage, {});
  else if (pathname === "/request-access") element = null;
  else if (privateRoutes[pathname]) {
    const PrivateComponent = privateRoutes[pathname];
    element = /* @__PURE__ */ jsx(Suspense, { fallback: /* @__PURE__ */ jsx("div", { style: { minHeight: "100dvh", background: PAPER } }), children: /* @__PURE__ */ jsx(PrivateComponent, {}) });
  }
  useEffect(() => {
    if (!element && !PUBLIC_PATHS.includes(pathname)) {
      navigate("/", { replace: true });
    }
  }, [pathname, navigate, element]);
  useEffect(() => {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", PAPER);
    document.documentElement.style.backgroundColor = PAPER;
    document.body.style.backgroundColor = PAPER;
  }, []);
  useEffect(() => {
    animateEntrances = true;
  }, []);
  if (element === null) return null;
  return /* @__PURE__ */ jsx(AnimatePresence, { mode: "wait", children: /* @__PURE__ */ jsx(
    motion.div,
    {
      initial: animateEntrances ? { opacity: 0, x: 12 } : false,
      animate: { opacity: 1, x: 0 },
      exit: { opacity: 0, x: -12 },
      transition: { duration: DURATION, ease: EASE },
      style: { minHeight: "100dvh" },
      children: element
    },
    pathname
  ) });
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/App.tsx");
function App() {
  useEffect(() => {
    const lenis = new Lenis({ lerp: 0.08, smoothWheel: true });
    window.__lenis = lenis;
    let id = requestAnimationFrame(function raf(time) {
      lenis.raf(time);
      id = requestAnimationFrame(raf);
    });
    return () => {
      cancelAnimationFrame(id);
      lenis.destroy();
      delete window.__lenis;
    };
  }, []);
  return /* @__PURE__ */ jsx(AnimatedRoutes, {});
}
globalThis.__VITE_REACT_SSG_TRACK_SSR_MODULE__?.("src/main.tsx");
const routes = [{ path: "*", element: /* @__PURE__ */ jsx(App, {}) }];
const createRoot = ViteReactSSG({ routes });
export {
  createRoot,
  routes
};
