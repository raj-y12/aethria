import type { ReactNode } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { SCROLL_EASE } from '../motionTokens';
import SectionRule from './SectionRule';

const ACCENT = '#3d6b5e';

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
      <svg viewBox="0 0 240 150" fill="none">
        {/* four scout sources sweep inward to a single found company */}
        <g fontFamily="Space Mono, monospace" fontSize="7.5" letterSpacing="0.5" fill="rgba(0,20,51,0.5)" textAnchor="end">
          <text x="66" y="27">MARKET</text>
          <text x="66" y="63">BUILDER</text>
          <text x="66" y="99">PAIN·POINT</text>
          <text x="66" y="135">CONTRARIAN</text>
        </g>
        <g stroke="rgba(0,20,51,0.26)" strokeWidth="1">
          <path d="M82 24 C140 24 168 62 194 72" />
          <path d="M82 60 C132 60 158 68 194 74" />
          <path d="M82 96 C132 96 158 84 194 78" />
          <path d="M82 132 C140 132 168 90 194 80" />
        </g>
        <g fill="#f4f1ea" stroke="rgba(0,20,51,0.48)" strokeWidth="1">
          <circle cx="82" cy="24" r="2.6" />
          <circle cx="82" cy="60" r="2.6" />
          <circle cx="82" cy="96" r="2.6" />
          <circle cx="82" cy="132" r="2.6" />
        </g>
        <circle cx="196" cy="76" r="9" fill="none" stroke="rgba(61,107,94,0.4)" strokeWidth="1" />
        <circle cx="196" cy="76" r="3.6" fill={ACCENT} />
        <text x="196" y="100" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="7.5" letterSpacing="1" fill="rgba(0,20,51,0.5)">
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
      <svg viewBox="0 0 240 150" fill="none">
        {/* three scores plotted as needles; the dashed verdigris line is the disagreement */}
        <line x1="34" y1="120" x2="206" y2="120" stroke="rgba(0,20,51,0.34)" strokeWidth="1" />
        <g stroke="rgba(0,20,51,0.34)" strokeWidth="1">
          <line x1="34" y1="116" x2="34" y2="124" />
          <line x1="206" y1="116" x2="206" y2="124" />
        </g>
        <g stroke="rgba(0,20,51,0.4)" strokeWidth="1">
          <line x1="72" y1="120" x2="72" y2="55" />
          <line x1="120" y1="120" x2="120" y2="75" />
          <line x1="168" y1="120" x2="168" y2="48" />
        </g>
        <polyline points="72,55 120,75 168,48" stroke="rgba(61,107,94,0.6)" strokeWidth="1" strokeDasharray="2.5 2.5" />
        <g fill="#f4f1ea" stroke="rgba(0,20,51,0.5)" strokeWidth="1">
          <circle cx="72" cy="55" r="2.6" />
          <circle cx="120" cy="75" r="2.6" />
          <circle cx="168" cy="48" r="2.6" />
        </g>
        <g fontFamily="Space Mono, monospace" fontSize="9" fill="rgba(0,20,51,0.55)" textAnchor="middle">
          <text x="72" y="42">7.4</text>
          <text x="120" y="62">5.1</text>
          <text x="168" y="35">8.2</text>
        </g>
        <text x="120" y="142" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="7.5" letterSpacing="1" fill="rgba(61,107,94,0.9)">
          SPLIT KEPT
        </text>
      </svg>
    ),
  },
  {
    n: '03',
    title: 'One partner rules',
    desc: 'A versioned, rule-based partner engine records an invest, pass, or monitor decision — only the edge cases reach an LLM.',
    viz: (
      <svg viewBox="0 0 240 150" fill="none">
        {/* a verdict dial — pass · monitor · invest, needle ruled to the call */}
        <path d="M68 116 A52 52 0 0 1 172 116" stroke="rgba(0,20,51,0.3)" strokeWidth="1" />
        <g stroke="rgba(0,20,51,0.3)" strokeWidth="1">
          <line x1="68" y1="116" x2="60" y2="116" />
          <line x1="120" y1="64" x2="120" y2="56" />
          <line x1="172" y1="116" x2="180" y2="116" />
        </g>
        <circle cx="68" cy="116" r="2.4" fill="#f4f1ea" stroke="rgba(0,20,51,0.45)" strokeWidth="1" />
        <circle cx="120" cy="64" r="3" fill={ACCENT} />
        <circle cx="172" cy="116" r="2.4" fill="#f4f1ea" stroke="rgba(0,20,51,0.45)" strokeWidth="1" />
        <line x1="120" y1="116" x2="120" y2="72" stroke={ACCENT} strokeWidth="1.5" />
        <circle cx="120" cy="116" r="3" fill={ACCENT} />
        <g fontFamily="Space Mono, monospace" fontSize="7.5" fill="rgba(0,20,51,0.5)" textAnchor="middle">
          <text x="58" y="130">PASS</text>
          <text x="184" y="130">INVEST</text>
        </g>
        <text x="120" y="48" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="9" letterSpacing="0.5" fill={ACCENT}>
          MONITOR
        </text>
        <text x="120" y="141" textAnchor="middle" fontFamily="Space Mono, monospace" fontSize="7" fill="rgba(0,20,51,0.4)">
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
      <svg viewBox="0 0 240 150" fill="none">
        {/* the bound record — a filed page, heading rule, and a verdigris seal */}
        <rect x="78" y="18" width="84" height="114" stroke="rgba(0,20,51,0.34)" strokeWidth="1" />
        <line x1="86" y1="18" x2="86" y2="132" stroke="rgba(0,20,51,0.16)" strokeWidth="1" />
        <text x="154" y="33" textAnchor="end" fontFamily="Space Mono, monospace" fontSize="6.5" letterSpacing="0.5" fill="rgba(0,20,51,0.42)">
          § 01
        </text>
        <line x1="96" y1="46" x2="148" y2="46" stroke="rgba(0,20,51,0.5)" strokeWidth="1.5" />
        <g stroke="rgba(0,20,51,0.2)" strokeWidth="1">
          <line x1="96" y1="60" x2="150" y2="60" />
          <line x1="96" y1="70" x2="150" y2="70" />
          <line x1="96" y1="80" x2="142" y2="80" />
          <line x1="96" y1="90" x2="150" y2="90" />
          <line x1="96" y1="100" x2="138" y2="100" />
        </g>
        <circle cx="140" cy="115" r="6.5" fill="none" stroke="rgba(61,107,94,0.45)" strokeWidth="1" />
        <circle cx="140" cy="115" r="2.6" fill={ACCENT} />
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
