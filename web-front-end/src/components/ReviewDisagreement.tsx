import { motion, useReducedMotion } from 'framer-motion';
import { ScrollReveal } from './ScrollReveal';
import { SCROLL_EASE } from '../motionTokens';

/**
 * Reviewer-disagreement proof block. Three reviewer personas (Default / Skeptical /
 * Opportunist — see backend/models.py SingleReview) score the same company against the
 * active thesis and genuinely diverge. Rendered as a calm, hairline-divided editorial
 * comparison (no boxes) so the page keeps its warm, spacious rhythm.
 */

type Verdict = 'STRONG' | 'MEDIUM' | 'WEAK';

const VERDICT_DOT: Record<Verdict, string> = {
  STRONG: '#7aab9a', // verdigris
  MEDIUM: 'rgba(0,20,51,0.4)', // neutral ink
  WEAK: '#b07b75', // muted clay
};

type Reviewer = {
  persona: string;
  mode: string;
  verdict: Verdict;
  take: string;
  splitScore: number;
};

const REVIEWERS: Reviewer[] = [
  {
    persona: 'Default',
    mode: 'Balanced base case',
    verdict: 'MEDIUM',
    take: 'Real wedge and a credible team, but capital intensity compresses the early-stage return profile.',
    splitScore: 7,
  },
  {
    persona: 'Skeptical',
    mode: 'Adversarial diligence',
    verdict: 'WEAK',
    take: 'Defensibility leans on a single integration partner. Replaceable inside eighteen months.',
    splitScore: 4,
  },
  {
    persona: 'Opportunist',
    mode: 'Upside-weighted',
    verdict: 'STRONG',
    take: 'First credible team to own this layer of the stack. The timing window is open now.',
    splitScore: 8,
  },
];

export default function ReviewDisagreement() {
  const reduce = useReducedMotion();

  return (
    <section
      id="disagreement"
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="disagreement-heading"
    >
      <div className="page-margin-x py-[clamp(2rem,4.5vh,3rem)]">
        <p className="np-head np-label">A7 — The Review</p>

        {/* Split statement — headline and gloss run side by side, not stacked, so this
            doesn't repeat the kicker→title→paragraph cadence used elsewhere on the page. */}
        <ScrollReveal
          y={20}
          amount={0.2}
          className="mt-6 grid grid-cols-1 items-end gap-10 md:grid-cols-[1.35fr_1fr] md:gap-16"
        >
          <h2
            id="disagreement-heading"
            className="editorial-display font-normal text-[clamp(2.2rem,5.6vw,4.4rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            Three reviewers, one record. The disagreement is the{' '}
            <span className="italic text-[var(--color-accent)]">point</span>.
          </h2>
          <p className="np-serif text-[16.5px] leading-[1.75] text-[var(--text-secondary)] md:pb-1">
            Every company is scored independently by three reviewer modes. Aethria does not average them into a
            comfortable number — it preserves the split and hands the partner layer the real picture.
          </p>
        </ScrollReveal>

        {/* Op-ed spread — three reviewer opinions run as real newspaper columns, split
            by a single hairline column rule (never a box), each with its own byline. */}
        <p className="mt-10 font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--text-subtle)] md:mt-14">
          Today — three opinions on one company
        </p>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3">
          {REVIEWERS.map((r, i) => (
            <motion.div
              key={r.persona}
              className={`py-6 pr-0 md:py-7 md:pr-9 ${i > 0 ? 'border-t border-solid border-[var(--section-divider)] md:border-l md:border-t-0 md:pl-9' : ''}`}
              initial={reduce ? false : { opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: reduce ? 0 : 0.7, ease: SCROLL_EASE, delay: reduce ? 0 : i * 0.08 }}
            >
              <h3 className="editorial-display text-[1.2rem] font-normal leading-[1.15] tracking-[-0.01em] text-[var(--color-oxford)]">
                {r.mode}
              </h3>
              <p className="mt-2 font-mono text-[9.5px] uppercase tracking-[0.12em] text-[var(--text-subtle)]">
                By the {r.persona} reviewer
              </p>
              <p className="np-serif mt-3 text-[15px] italic leading-[1.6] text-[var(--text-secondary)]">
                "{r.take}"
              </p>
              <div className="mt-4 flex items-center gap-3">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: VERDICT_DOT[r.verdict] }}
                  aria-hidden
                />
                <span className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
                  {r.verdict} · {r.splitScore}/10
                </span>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Partner resolution */}
        <ScrollReveal y={12} amount={0.4} className="mt-10">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-subtle)]">
            The split resolves to <span className="text-[var(--color-accent)]">Monitor</span>
          </p>
        </ScrollReveal>
      </div>
    </section>
  );
}
