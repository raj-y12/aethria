import { useEffect, useRef, type ReactNode } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { motion, useReducedMotion } from 'framer-motion';

gsap.registerPlugin(ScrollTrigger);

const ACCENT = '#3d6b5e';
const INK = 'rgba(0,20,51,0.25)';
const INK_SOFT = 'rgba(0,20,51,0.2)';
const INK_DOT = 'rgba(0,20,51,0.4)';

interface Step {
  n: string;
  title: ReactNode;
  desc: string;
  viz: ReactNode;
}

const STEPS: Step[] = [
  {
    n: '01',
    title: (
      <>
        Four scouts
        <br />
        source it
      </>
    ),
    desc: 'Market, builder, pain-point, and contrarian scouts search the live web for real companies — never a static list.',
    viz: (
      <svg viewBox="0 0 260 130">
        <g fontFamily="Space Mono, monospace" fontSize="9" letterSpacing="0.5" fill="rgba(0,20,51,0.55)" textAnchor="end">
          <text x="98" y="25">MARKET</text>
          <text x="98" y="55">BUILDER</text>
          <text x="98" y="85">PAIN-POINT</text>
          <text x="98" y="115">CONTRARIAN</text>
        </g>
        <g stroke={INK} strokeWidth={1}>
          <line x1="112" y1="22" x2="212" y2="65" />
          <line x1="112" y1="52" x2="212" y2="65" />
          <line x1="112" y1="82" x2="212" y2="65" />
          <line x1="112" y1="112" x2="212" y2="65" />
        </g>
        <g fill={INK_DOT}>
          <circle cx="112" cy="22" r="3.5" />
          <circle cx="112" cy="52" r="3.5" />
          <circle cx="112" cy="82" r="3.5" />
          <circle cx="112" cy="112" r="3.5" />
        </g>
        <circle cx="212" cy="65" r="7" fill={ACCENT} />
        <text x="212" y="90" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="8" letterSpacing="1" fill="rgba(0,20,51,0.5)">
          COMPANY
        </text>
      </svg>
    ),
  },
  {
    n: '02',
    title: (
      <>
        Three reviewers
        <br />
        argue it
      </>
    ),
    desc: 'Independent reviewers score each company against your thesis and disagree on purpose. The dissent is kept.',
    viz: (
      <svg viewBox="0 0 190 120">
        <g fontFamily="Space Mono, monospace" fontSize="11" fill="rgba(0,20,51,0.55)">
          <text x="20" y="35">7.4</text>
          <text x="80" y="35">5.1</text>
          <text x="140" y="35">8.2</text>
        </g>
        <g stroke={INK_SOFT} fill="none">
          <rect x="20" y="48" width="36" height="44" />
          <rect x="78" y="62" width="36" height="30" />
          <rect x="136" y="40" width="36" height="52" />
        </g>
        <line x1="20" y1="104" x2="172" y2="104" stroke={ACCENT} strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    n: '03',
    title: (
      <>
        One partner
        <br />
        rules
      </>
    ),
    desc: 'A versioned, rule-based partner engine records an invest, pass, or monitor decision — only the edge cases reach an LLM.',
    viz: (
      <svg viewBox="0 0 190 120">
        <circle cx="95" cy="60" r="40" fill="none" stroke={INK_SOFT} />
        <circle
          cx="95"
          cy="60"
          r="40"
          fill="none"
          stroke={ACCENT}
          strokeWidth="2"
          strokeDasharray="180 120"
          strokeLinecap="round"
          transform="rotate(-90 95 60)"
        />
        <text x="95" y="58" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="11" fill={ACCENT}>
          MONITOR
        </text>
        <text x="95" y="74" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="8" fill="rgba(0,20,51,0.4)">
          v1 · ruled
        </text>
      </svg>
    ),
  },
  {
    n: '04',
    title: (
      <>
        The record
        <br />
        is kept
      </>
    ),
    desc: 'Every decision is bound into one investment record with the evidence trail attached, ready to open.',
    viz: (
      <svg viewBox="0 0 190 120">
        <g stroke={INK_SOFT} fill="none">
          <rect x="50" y="18" width="90" height="84" />
          <line x1="62" y1="38" x2="128" y2="38" />
          <line x1="62" y1="54" x2="128" y2="54" />
          <line x1="62" y1="70" x2="110" y2="70" />
        </g>
        <circle cx="124" cy="86" r="6" fill={ACCENT} />
      </svg>
    ),
  },
];

export default function MethodSection() {
  const reduce = useReducedMotion();
  const rootRef = useRef<HTMLElement | null>(null);
  const fillRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    const fill = fillRef.current;
    if (!root || !fill || reduce) return;
    const ctx = gsap.context(() => {
      gsap.to(fill, {
        scaleY: 1,
        ease: 'none',
        scrollTrigger: { trigger: root, start: 'top 65%', end: 'bottom 80%', scrub: 0.9 },
      });
    }, root);
    return () => ctx.revert();
  }, [reduce]);

  return (
    <section
      id="method"
      ref={rootRef}
      className="relative w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="method-heading"
    >
      <div className="page-margin-x py-[clamp(2.5rem,6vh,4rem)]">
        <p className="mb-8 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[var(--color-accent)]">
          A4 — How the judgment is formed
        </p>

        {/* drawn spine (desktop only) */}
        <div className="pointer-events-none absolute left-1/2 top-0 hidden h-full w-px -translate-x-1/2 overflow-hidden bg-[var(--section-divider)] md:block">
          <div ref={fillRef} className="absolute inset-0 origin-top scale-y-0 bg-[var(--color-accent)]" />
        </div>

        <div className="relative">
          {STEPS.map((step, i) => {
            const copyRight = i % 2 === 0; // 01,03 → copy right; 02,04 → copy left
            const copyEl = (
              <motion.div
                className={`max-w-[34ch] ${copyRight ? 'md:text-left' : 'md:text-right'}`}
                initial={reduce ? false : { opacity: 0, y: 22, filter: 'blur(6px)' }}
                whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
              >
                <h3 className="editorial-display font-normal text-[clamp(1.6rem,3.4vw,2.8rem)] leading-[1.02] tracking-[-0.015em] text-[var(--color-oxford)]">
                  {step.title}
                </h3>
                <p className="mt-4 font-sans text-[15px] font-light leading-[1.65] text-[var(--text-secondary)]">
                  {step.desc}
                </p>
              </motion.div>
            );
            const vizEl = (
              <motion.div
                className="w-[clamp(150px,20vw,260px)] text-[var(--color-oxford)]"
                initial={reduce ? false : { opacity: 0, y: 22, filter: 'blur(6px)' }}
                whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.08 }}
              >
                {step.viz}
              </motion.div>
            );
            const nodeEl = (
              <div className="relative flex items-center justify-center">
                <span className="absolute right-full mr-1 hidden h-px w-[1.6rem] bg-[var(--section-divider)] md:block" />
                <span className="absolute left-full ml-1 hidden h-px w-[1.6rem] bg-[var(--section-divider)] md:block" />
                <span className="z-[3] flex h-[2.6rem] w-[2.6rem] items-center justify-center rounded-full border border-[var(--section-divider)] bg-[var(--color-paper)] font-mono text-[11px] tracking-[0.1em] text-[var(--color-accent)]">
                  {step.n}
                </span>
              </div>
            );

            return (
              <div
                key={step.n}
                className="relative grid grid-cols-1 gap-6 py-8 md:grid-cols-[1fr_7rem_1fr] md:items-center md:gap-0 md:py-10"
              >
                {/* left cell (col 1) — content pushed toward the spine */}
                <div className="order-2 flex md:order-none md:col-start-1 md:row-start-1 md:justify-end">
                  {copyRight ? vizEl : copyEl}
                </div>
                {/* node (col 2) — centered on the spine */}
                <div className="order-1 flex justify-center md:order-none md:col-start-2 md:row-start-1">
                  {nodeEl}
                </div>
                {/* right cell (col 3) — content pushed toward the spine */}
                <div className="order-3 md:order-none md:col-start-3 md:row-start-1">
                  {copyRight ? copyEl : vizEl}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
