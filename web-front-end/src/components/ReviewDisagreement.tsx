import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { ScrollReveal } from './ScrollReveal';
import SectionKicker from './SectionKicker';
import { SCROLL_EASE } from '../motionTokens';

/**
 * Reviewer-disagreement proof block — the page's product "crescendo".
 *
 * Mirrors the real product: three reviewer personas (Default / Skeptical / Opportunist,
 * see backend/models.py SingleReview) score the same company against the active thesis and
 * genuinely diverge. The record preserves the disagreement instead of averaging it into a
 * single number, then the partner layer resolves it into a logged decision. Rendered on the
 * continuous paper canvas (no dark band) so the page reads as one uninterrupted document.
 */

type Verdict = 'STRONG' | 'MEDIUM' | 'WEAK';

const VERDICT_STYLE: Record<Verdict, { bg: string; text: string }> = {
  STRONG: { bg: '#7aab9a', text: '#06231a' }, // verdigris
  MEDIUM: { bg: '#b39a6b', text: '#2a2113' }, // brass
  WEAK: { bg: '#b07b75', text: '#2c1311' }, // muted clay
};

type Reviewer = {
  persona: string;
  mode: string;
  verdict: Verdict;
  take: string;
  /** Score (1–10) on the dimension the panel diverges most on. */
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

const SPLIT_DIMENSION = 'Defensibility';

function VerdictChip({ verdict }: { verdict: Verdict }) {
  const style = VERDICT_STYLE[verdict];
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-none px-2 py-1 font-mono text-[9px] font-semibold uppercase leading-none tracking-[0.1em]"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {verdict}
    </span>
  );
}

/** Horizontal 1–10 track marking where the three reviewers landed on the split dimension. */
function DivergenceTrack() {
  const reduce = useReducedMotion();
  return (
    <div className="w-full">
      <div className="mb-3 flex items-baseline justify-between">
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
          Where they split · {SPLIT_DIMENSION}
        </p>
        <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--text-subtle)]">1–10</p>
      </div>
      <div className="relative mb-9 h-px w-full bg-[var(--section-divider)]">
        {REVIEWERS.map((r, i) => {
          const left = `${((r.splitScore - 1) / 9) * 100}%`;
          return (
            <motion.div
              key={r.persona}
              className="absolute top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
              style={{ left }}
              initial={reduce ? false : { opacity: 0, scale: 0.6 }}
              whileInView={reduce ? undefined : { opacity: 1, scale: 1 }}
              viewport={{ once: true, amount: 0.6 }}
              transition={{ duration: reduce ? 0 : 0.4, delay: reduce ? 0 : 0.15 + i * 0.08, ease: SCROLL_EASE }}
            >
              <span
                className="h-2.5 w-2.5 rounded-full ring-2 ring-[var(--color-paper)]"
                style={{ backgroundColor: VERDICT_STYLE[r.verdict].bg }}
              />
              <span className="mt-2 font-mono text-[11px] font-bold leading-none text-[var(--color-oxford)] tabular-nums">
                {r.splitScore}
              </span>
            </motion.div>
          );
        })}
      </div>

      <ul className="flex list-none flex-wrap gap-x-5 gap-y-2 p-0">
        {REVIEWERS.map((r) => (
          <li key={r.persona} className="flex items-center gap-2">
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: VERDICT_STYLE[r.verdict].bg }}
            />
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[var(--label-muted)]">
              {r.persona}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function ReviewDisagreement() {
  const reduce = useReducedMotion();

  const gridVariants: Variants = {
    hidden: {},
    visible: { transition: { staggerChildren: reduce ? 0 : 0.1, delayChildren: reduce ? 0 : 0.06 } },
  };

  const cardVariants: Variants = {
    hidden: reduce ? {} : { opacity: 0, y: 22 },
    visible: { opacity: 1, y: 0, transition: { duration: reduce ? 0 : 0.55, ease: SCROLL_EASE } },
  };

  return (
    <section
      id="disagreement"
      className="w-full border-t border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="disagreement-heading"
    >
      <div className="page-margin-x py-[clamp(6rem,16vh,12rem)]">
        <ScrollReveal y={20} amount={0.2} className="max-w-[900px]">
          <SectionKicker folio="05" label="The review" className="mb-8" />
          <h2
            id="disagreement-heading"
            className="editorial-display font-normal text-[clamp(2.4rem,6vw,4.75rem)] leading-[0.98] tracking-[-0.02em] text-[var(--color-oxford)]"
          >
            Three reviewers, one record. The disagreement is the{' '}
            <span className="italic text-[var(--color-accent)]">point</span>.
          </h2>
          <p className="mt-8 max-w-[58ch] font-sans text-[16px] leading-[1.75] text-[var(--text-secondary)]">
            Every company is scored independently by three reviewer modes. Aethria does not average them into a
            comfortable number — it preserves the split, surfaces the dimension they fight over, and hands the partner
            layer the real picture.
          </p>
        </ScrollReveal>

        <motion.div
          className="mt-16 grid grid-cols-1 gap-px overflow-hidden border border-solid border-[var(--section-divider)] bg-[var(--section-divider)] md:mt-24 md:grid-cols-3"
          variants={gridVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.15 }}
        >
          {REVIEWERS.map((r) => (
            <motion.article
              key={r.persona}
              variants={cardVariants}
              className="flex min-w-0 flex-col bg-[var(--color-paper)] p-7 md:p-8"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--color-oxford)]">
                    {r.persona}
                  </p>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.1em] text-[var(--label-muted)]">
                    {r.mode}
                  </p>
                </div>
                <VerdictChip verdict={r.verdict} />
              </div>
              <p className="mt-6 font-sans text-[15px] leading-[1.65] text-[var(--text-secondary)]">{r.take}</p>
            </motion.article>
          ))}
        </motion.div>

        <ScrollReveal
          y={18}
          delay={0.06}
          amount={0.3}
          className="mt-12 flex flex-col gap-10 border-t border-solid border-[var(--section-divider)] pt-12 md:flex-row md:items-center md:justify-between md:gap-16"
        >
          <div className="w-full md:max-w-[420px]">
            <DivergenceTrack />
          </div>

          <div className="flex w-full shrink-0 items-start gap-5 md:w-auto md:max-w-[420px]">
            <div
              className="mt-0.5 h-12 w-1 shrink-0 self-stretch"
              style={{ backgroundColor: VERDICT_STYLE.MEDIUM.bg }}
              aria-hidden
            />
            <div className="min-w-0">
              <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--label-muted)]">
                Partner layer · recorded decision
              </p>
              <p className="mt-2 font-sans text-[clamp(1.25rem,3vw,1.6rem)] font-semibold leading-tight text-[var(--color-oxford)]">
                MONITOR
              </p>
              <p className="mt-2 max-w-[42ch] font-sans text-[14px] leading-[1.6] text-[var(--text-secondary)]">
                Versioned partner logic reconciles the split into a logged verdict — with every reviewer's dissent
                attached to the record, not erased by it.
              </p>
            </div>
          </div>
        </ScrollReveal>
      </div>
    </section>
  );
}
