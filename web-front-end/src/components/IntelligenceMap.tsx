import { useEffect, useRef, useState, useId } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { MotionPathPlugin } from 'gsap/MotionPathPlugin';

gsap.registerPlugin(ScrollTrigger, MotionPathPlugin);

const OXFORD = '#001433';
const PAPER = '#F4F1EA';

const COLORS = {
  dark: {
    edge: 'rgba(244, 241, 234, 0.15)',
    edgeDash: 'rgba(244, 241, 234, 0.1)',
    scout: 'rgba(244, 241, 234, 0.4)',
    reviewer: 'rgba(244, 241, 234, 0.7)',
    partner: 'rgba(244, 241, 234, 0.7)',
    portfolio: PAPER,
    meta: 'rgba(244, 241, 234, 0.55)',
    label: 'rgba(244, 241, 234, 0.5)',
    pulse: PAPER,
    pulseMeta: 'rgba(244, 241, 234, 0.3)',
  },
  light: {
    edge: 'rgba(0, 20, 51, 0.15)',
    edgeDash: 'rgba(0, 20, 51, 0.1)',
    scout: 'rgba(0, 20, 51, 0.35)',
    reviewer: 'rgba(0, 20, 51, 0.55)',
    partner: 'rgba(0, 20, 51, 0.55)',
    portfolio: 'rgba(0, 20, 51, 0.85)',
    meta: 'rgba(0, 20, 51, 0.5)',
    label: 'rgba(0, 20, 51, 0.5)',
    pulse: OXFORD,
    pulseMeta: 'rgba(0, 20, 51, 0.3)',
  },
} as const;

type Theme = (typeof COLORS)[keyof typeof COLORS];

type NodeKey =
  | 's1'
  | 's2'
  | 's3'
  | 's4'
  | 'reviewer'
  | 'partner'
  | 'portfolio'
  | 'meta';

/** Wide, tall coordinate space; node x/y are fractions of W/H per layout spec. */
const VIEW_W = 1420;
const VIEW_H = 520;

const pct = (xPct: number, yPct: number) => ({ x: xPct * VIEW_W, y: yPct * VIEW_H });

const NODES: Record<
  NodeKey,
  { x: number; y: number; r: number; label: string; scout?: boolean; meta?: boolean }
> = {
  s1: { ...pct(0.12, 0.55), r: 8, label: 'MARKET', scout: true },
  s2: { ...pct(0.15, 0.35), r: 8, label: 'BUILDER', scout: true },
  s3: { ...pct(0.12, 0.7), r: 8, label: 'PAIN', scout: true },
  s4: { ...pct(0.18, 0.45), r: 8, label: 'CONTRARIAN', scout: true },
  reviewer: { ...pct(0.42, 0.48), r: 12, label: 'REVIEWER' },
  partner: { ...pct(0.63, 0.48), r: 12, label: 'PARTNER ENGINE' },
  portfolio: { ...pct(0.85, 0.5), r: 18, label: 'PORTFOLIO' },
  meta: { ...pct(0.8, 0.18), r: 8, label: 'META-AGENT', meta: true },
};

const EDGES: { from: NodeKey; to: NodeKey; dashed?: boolean }[] = [
  { from: 's1', to: 'reviewer' },
  { from: 's2', to: 'reviewer' },
  { from: 's3', to: 'reviewer' },
  { from: 's4', to: 'reviewer' },
  { from: 'reviewer', to: 'partner' },
  { from: 'partner', to: 'portfolio' },
  { from: 'meta', to: 'reviewer', dashed: true },
  { from: 'meta', to: 'partner', dashed: true },
];

const PULSE_BY_EDGE: Record<
  string,
  { duration: number; ease: string; delay?: number; opacity?: number }
> = {
  's1-reviewer': { duration: 2.2, ease: 'none', delay: 0 },
  's2-reviewer': { duration: 2.2, ease: 'none', delay: 0.35 },
  's3-reviewer': { duration: 2.2, ease: 'none', delay: 0.7 },
  's4-reviewer': { duration: 2.2, ease: 'none', delay: 1.05 },
  'reviewer-partner': { duration: 1.8, ease: 'none', delay: 1.4 },
  'partner-portfolio': { duration: 2.4, ease: 'power2.in' },
  'meta-reviewer': { duration: 4, ease: 'none', opacity: 0.35 },
  'meta-partner': { duration: 4, ease: 'none', delay: 0.8, opacity: 0.35 },
};

function nodeColor(k: NodeKey, theme: Theme): string {
  if (k.startsWith('s')) return theme.scout;
  if (k === 'reviewer') return theme.reviewer;
  if (k === 'partner') return theme.partner;
  if (k === 'portfolio') return theme.portfolio;
  return theme.meta;
}

function edgeKey(from: NodeKey, to: NodeKey): string {
  return `${from}-${to}`;
}

interface IntelligenceMapProps {
  variant?: 'dark' | 'light';
}

export default function IntelligenceMap({ variant = 'light' }: IntelligenceMapProps) {
  const uid = useId().replace(/:/g, '');
  const rootRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hovered, setHovered] = useState<NodeKey | null>(null);
  const [compact, setCompact] = useState(false);

  const theme = COLORS[variant];

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const apply = () => setCompact(mq.matches);
    apply();
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, []);

  useEffect(() => {
    const root = rootRef.current;
    const svg = svgRef.current;
    if (!root || !svg) return;

    const paths = Array.from(svg.querySelectorAll<SVGPathElement>('[data-edge-path]'));
    const nodeInner = Array.from(svg.querySelectorAll<SVGGElement>('[data-node-inner]'));
    const pulses = Array.from(svg.querySelectorAll<SVGCircleElement>('[data-pulse]'));

    const ctx = gsap.context(() => {
      gsap.set(svg, { opacity: 0 });
      gsap.set(nodeInner, { scale: 0, transformOrigin: 'center center' });
      paths.forEach((p) => {
        const len = p.getTotalLength();
        p.style.strokeDasharray = `${len}`;
        p.style.strokeDashoffset = `${len}`;
      });

      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: root,
          start: 'top 80%',
          once: true,
        },
      });

      tl.to(svg, { opacity: 1, duration: 0.8, ease: 'power2.out' })
        .to(
          nodeInner,
          { scale: 1, duration: 0.45, ease: 'back.out(1.4)', stagger: 0.08 },
          '-=0.2',
        )
        .to(
          paths,
          {
            strokeDashoffset: 0,
            duration: 1,
            ease: 'power2.inOut',
            stagger: 0.1,
          },
          '-=0.25',
        )
        .add(() => {
          pulses.forEach((dot) => {
            const pathDomId = dot.getAttribute('data-path-id');
            if (!pathDomId) return;
            const ek = dot.getAttribute('data-edge-key');
            const cfg = ek ? PULSE_BY_EDGE[ek] : undefined;
            if (!cfg) return;
            const selector = `#${CSS.escape(pathDomId)}`;
            gsap.set(dot, { opacity: cfg.opacity ?? 0.95 });
            gsap.to(dot, {
              motionPath: {
                path: selector,
                align: selector,
                alignOrigin: [0.5, 0.5],
                autoRotate: false,
              },
              duration: cfg.duration,
              ease: cfg.ease,
              repeat: -1,
              delay: cfg.delay ?? 0,
            });
          });
        });
    }, root);

    return () => ctx.revert();
  }, [uid, compact, variant]);

  const showMeta = !compact;
  const scaleNodes = compact ? 0.7 : 1;

  const pathD = (from: NodeKey, to: NodeKey) => {
    const a = NODES[from];
    const b = NODES[to];
    return `M ${a.x} ${a.y} L ${b.x} ${b.y}`;
  };

  const pathDomId = (from: NodeKey, to: NodeKey) => `path-${from}-${to}-${uid}`;

  return (
    <div ref={rootRef} className="flex h-full min-h-0 w-full flex-1 flex-col border-0">
      <div className="relative h-full min-h-0 w-full flex-1 overflow-visible border-0">
        <svg
          ref={svgRef}
          className="relative z-[1] block h-full w-full"
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Intelligence pipeline network: scouts, reviewer, partner, portfolio, and meta-agent"
        >
          <defs>
            <filter id={`glow-${uid}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <g className="pointer-events-auto">
            {EDGES.map(({ from, to, dashed }) => {
              if (!showMeta && (from === 'meta' || to === 'meta')) return null;
              const d = pathD(from, to);
              const id = pathDomId(from, to);
              return (
                <path
                  key={id}
                  id={id}
                  data-edge-path
                  d={d}
                  fill="none"
                  stroke={dashed ? theme.edgeDash : theme.edge}
                  strokeWidth={dashed ? 1 : 1.25}
                  strokeLinecap="round"
                  strokeDasharray={dashed ? '6 10' : undefined}
                />
              );
            })}

            {EDGES.map(({ from, to }) => {
              if (!showMeta && (from === 'meta' || to === 'meta')) return null;
              const isMeta = from === 'meta' || to === 'meta';
              const pid = pathDomId(from, to);
              const ek = edgeKey(from, to);
              return (
                <circle
                  key={`pulse-${pid}`}
                  data-pulse
                  data-path-id={pid}
                  data-edge-key={ek}
                  r={isMeta ? 2.5 : 4}
                  fill={isMeta ? theme.pulseMeta : theme.pulse}
                  opacity={isMeta ? 0.35 : 0.95}
                />
              );
            })}

            {(Object.keys(NODES) as NodeKey[]).map((key) => {
              if (!showMeta && key === 'meta') return null;
              const n = NODES[key];
              const r = n.r * scaleNodes;
              const isHover = hovered === key;
              const fill = nodeColor(key, theme);
              return (
                <g key={key} transform={`translate(${n.x} ${n.y})`} style={{ cursor: 'default' }}>
                  <g
                    data-node-inner
                    onMouseEnter={() => setHovered(key)}
                    onMouseLeave={() => setHovered(null)}
                  >
                    <circle
                      r={r}
                      fill={fill}
                      opacity={isHover ? 1 : undefined}
                      filter={isHover ? `url(#glow-${uid})` : undefined}
                      transform={`scale(${isHover ? 1.4 : 1})`}
                      style={{ transition: 'transform 0.25s ease, opacity 0.25s ease' }}
                    />
                    <text
                      y={r + 18}
                      textAnchor="middle"
                      fill={theme.label}
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 11,
                        letterSpacing: '0.1em',
                      }}
                    >
                      {n.label}
                    </text>
                    {n.meta ? (
                      <circle
                        r={r + 5}
                        fill="none"
                        stroke={theme.meta}
                        strokeWidth={1}
                        opacity={0.35}
                        className="animate-pulse"
                      />
                    ) : null}
                  </g>
                </g>
              );
            })}
          </g>
        </svg>
      </div>
    </div>
  );
}
