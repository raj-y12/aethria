import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';
import SectionRule from './SectionRule';

const ACCENT = '#3d6b5e';
const INK = 'rgba(0,20,51,0.25)';
const INK_SOFT = 'rgba(0,20,51,0.2)';
const INK_DOT = 'rgba(0,20,51,0.4)';

interface Step {
  n: string;
  title: string;
  desc: string;
  viz: ReactNode;
}

const STEPS: Step[] = [
  {
    n: '01',
    title: 'Four scouts source it',
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
    title: 'Three reviewers argue it',
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
    title: 'One partner rules',
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
    title: 'The record is kept',
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

/** Method — a ruled four-column newspaper explainer: numbered figure above, serif copy below. */
export default function MethodSection() {
  const reduce = useReducedMotion();

  return (
    <section
      id="method"
      className="w-full"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="method-heading"
    >
      <SectionRule />
      <div className="page-margin-x py-[clamp(2.5rem,5.5vh,4rem)]">
        <div className="np-head flex items-baseline gap-x-4">
          <span className="np-folio">A4</span>
          <span className="np-label">Method</span>
        </div>

        <h2 id="method-heading" className="np-hed mt-5 max-w-[16ch] text-[var(--color-oxford)]">
          How the judgment is formed.
        </h2>

        <div className="mt-12 grid grid-cols-1 md:grid-cols-4">
          {STEPS.map((step, i) => (
            <motion.div
              key={step.n}
              className={`py-7 md:py-2 md:pr-8 ${i > 0 ? 'border-t border-solid border-[var(--section-divider)] md:border-l md:border-t-0 md:pl-8' : ''}`}
              initial={reduce ? false : { opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: reduce ? 0 : 0.6, ease: SCROLL_EASE, delay: reduce ? 0 : i * 0.07 }}
            >
              <p className="np-figure">{step.n}</p>
              <div className="mt-5 w-full max-w-[220px] text-[var(--color-oxford)]">{step.viz}</div>
              <h3 className="editorial-display mt-5 text-[1.4rem] font-normal leading-[1.12] tracking-[-0.015em] text-[var(--color-oxford)]">
                {step.title}
              </h3>
              <p className="np-serif mt-3 text-[14.5px] leading-[1.65] text-[var(--text-secondary)]">{step.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
