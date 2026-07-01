import { motion, useReducedMotion } from 'framer-motion';
import { ScrollReveal } from './ScrollReveal';
import SectionKicker from './SectionKicker';
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
      <div className="page-margin-x py-[clamp(7rem,18vh,13rem)]">
        <ScrollReveal y={20} amount={0.2} className="max-w-[900px]">
          <SectionKicker folio="05" label="The review" className="mb-8" />
          <h2
            id="disagreement-heading"
            className="editorial-display font-normal text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            Three reviewers, one record. The disagreement is the{' '}
            <span className="italic text-[var(--color-accent)]">point</span>.
          </h2>
          <p className="mt-8 max-w-[56ch] font-sans text-[17px] leading-[1.75] text-[var(--text-secondary)]">
            Every company is scored independently by three reviewer modes. Aethria does not average them into a
            comfortable number — it preserves the split and hands the partner layer the real picture.
          </p>
        </ScrollReveal>

        {/* Reviewer rows — hairline-divided, no boxes */}
        <div className="mt-20 md:mt-28">
          {REVIEWERS.map((r, i) => (
            <motion.div
              key={r.persona}
              className="grid grid-cols-1 gap-5 border-t border-solid border-[var(--section-divider)] py-10 md:grid-cols-[minmax(0,0.5fr)_minmax(0,1fr)_auto] md:items-baseline md:gap-12 md:py-12"
              initial={reduce ? false : { opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: reduce ? 0 : 0.7, ease: SCROLL_EASE, delay: reduce ? 0 : i * 0.06 }}
            >
              <div>
                <p className="font-mono text-[12px] uppercase tracking-[0.12em] text-[var(--color-oxford)]">
                  {r.persona}
                </p>
                <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
                  {r.mode}
                </p>
              </div>
              <p className="max-w-[46ch] font-sans text-[clamp(1.05rem,1.5vw,1.25rem)] font-light leading-[1.6] text-[var(--text-secondary)]">
                {r.take}
              </p>
              <div className="flex items-center gap-3 md:justify-end md:self-start">
                <span
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ backgroundColor: VERDICT_DOT[r.verdict] }}
                  aria-hidden
                />
                <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
                  {r.verdict} · {r.splitScore}/10
                </span>
              </div>
            </motion.div>
          ))}
          <div className="border-t border-solid border-[var(--section-divider)]" />
        </div>

        {/* Partner resolution — one quiet line, generous air */}
        <ScrollReveal y={18} amount={0.4} className="mt-20 max-w-[820px] md:mt-28">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)]">
            Partner layer · recorded decision
          </p>
          <p className="mt-6 editorial-display text-[clamp(2rem,5vw,3.6rem)] font-normal leading-[1.0] tracking-[-0.02em] text-[var(--color-oxford)]">
            The split resolves to <span className="italic text-[var(--color-accent)]">Monitor</span>.
          </p>
          <p className="mt-6 max-w-[52ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
            Versioned partner logic reconciles the disagreement into one logged verdict — with every reviewer's dissent
            kept on the record, not erased by it.
          </p>
        </ScrollReveal>
      </div>
    </section>
  );
}
