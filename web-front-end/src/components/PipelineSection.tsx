import { motion, useReducedMotion, type Variants } from 'framer-motion';
import { ScrollReveal } from './ScrollReveal';
import { SCROLL_EASE } from '../motionTokens';

const DARK_DIVIDER = 'rgba(244, 241, 234, 0.14)';

const PIPELINE_PHASES = [
  {
    phase: 'I',
    label: 'SCOUT',
    body: 'Agents monitor market signals continuously against your fund thesis. When a name surfaces, context and sourcing are already assembled.',
    signal: 'thesis-gated discovery',
  },
  {
    phase: 'II',
    label: 'REVIEW',
    body: 'Structured evaluation across dimensions you define. Conviction emerges; uncertainty is explicit. On-demand lookup runs at any time.',
    signal: 'conviction',
  },
  {
    phase: 'III',
    label: 'DECIDE',
    body: 'Clear positions with reasoning attached. Advance, pass, or hold — no ambiguous queue.',
    signal: 'precision',
  },
  {
    phase: 'IV',
    label: 'PORTFOLIO',
    body: 'Decisions compound. Exposure, concentration, and follow-on judgment stay in view.',
    signal: 'continuity',
  },
] as const;

export default function PipelineSection() {
  const reduce = useReducedMotion();

  const listVariants: Variants = {
    hidden: {},
    visible: {
      transition: {
        staggerChildren: reduce ? 0 : 0.1,
        delayChildren: reduce ? 0 : 0.05,
      },
    },
  };

  const phaseVariants: Variants = {
    hidden: reduce ? { opacity: 1, y: 0 } : { opacity: 0, y: 18 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: reduce ? 0 : 0.48, ease: SCROLL_EASE },
    },
  };

  return (
    <section className="w-full" aria-labelledby="pipeline-heading">
      <motion.div
        className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
        style={{ backgroundColor: 'var(--color-paper)', color: 'var(--color-charcoal)' }}
      >
        <div className="page-margin-x pt-16 md:pt-24 pb-10 md:pb-12">
          <ScrollReveal y={16} amount={0.2}>
            <p className="section-numeral mb-6" aria-hidden="true">
              III
            </p>
            <h2
              id="pipeline-heading"
              className="text-[clamp(1.75rem,5.5vw,2.25rem)] font-normal leading-[1.15] tracking-[-0.02em] text-[#001433] md:text-[36px] md:tracking-normal"
            >
              The pipeline
            </h2>
            <p className="mt-4 max-w-xl font-sans text-[15px] leading-[1.7] text-[rgba(0,27,71,0.65)]">
              From signal to position. Four locked phases. No hand-offs lost in email.
            </p>
          </ScrollReveal>
        </div>
      </motion.div>

      <div className="w-full" style={{ backgroundColor: 'var(--color-oxford)', color: 'var(--color-paper)' }}>
        <motion.div
          className="page-margin-x py-12 md:py-16"
          variants={listVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.12, margin: '0px 0px -5% 0px' }}
        >
          <p className="mb-10 font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-muted)] md:mb-12">
            Phases I — IV · Single audit trail
          </p>

          {/* Mobile: vertical timeline */}
          <ol className="relative flex flex-col gap-0 lg:hidden">
            <div
              className="pointer-events-none absolute bottom-[7px] left-[5px] top-[7px] w-px"
              style={{
                backgroundImage: `repeating-linear-gradient(180deg, ${DARK_DIVIDER} 0, ${DARK_DIVIDER} 4px, transparent 4px, transparent 8px)`,
              }}
              aria-hidden
            />
            {PIPELINE_PHASES.map(({ phase, label, body, signal }, index) => (
              <motion.li
                key={label}
                variants={phaseVariants}
                className={`relative pl-8 ${index < PIPELINE_PHASES.length - 1 ? 'pb-10' : 'pb-0'}`}
              >
                <span
                  className="absolute left-0 top-1.5 h-[10px] w-[10px] rotate-45"
                  style={{ backgroundColor: 'var(--color-paper)' }}
                  aria-hidden
                />
                <motion.div className="flex flex-row items-baseline justify-between gap-3">
                  <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-inverse-muted)]">{phase}</span>
                  <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-secondary)]">
                    {label}
                  </span>
                </motion.div>
                <div className="mt-3 h-px w-full" style={{ backgroundColor: DARK_DIVIDER }} aria-hidden />
                <p className="mt-4 font-sans text-[15px] leading-[1.7] text-[var(--text-inverse-secondary)]">{body}</p>
                <p className="mt-4 font-sans text-[14px] italic leading-snug text-[var(--text-inverse-muted)] lowercase">
                  {signal}
                </p>
              </motion.li>
            ))}
          </ol>

          {/* Desktop: horizontal flow — one continuous audit-trail connector */}
          <ol className="relative hidden lg:flex lg:w-full lg:items-stretch lg:gap-0">
            <div
              className="pointer-events-none absolute top-[5px] z-0 h-px"
              style={{
                left: '5px',
                right: 'calc(25% - 5px)',
                backgroundImage: `repeating-linear-gradient(90deg, ${DARK_DIVIDER} 0, ${DARK_DIVIDER} 4px, transparent 4px, transparent 8px)`,
              }}
              aria-hidden
            />
            {PIPELINE_PHASES.map(({ phase, label, body, signal }) => (
              <motion.li key={label} variants={phaseVariants} className="relative z-[1] flex min-w-0 flex-1 flex-col px-0">
                <motion.div className="relative flex flex-1 flex-col pr-6">
                  <span
                    className="relative z-10 mb-4 inline-block h-[10px] w-[10px] shrink-0 rotate-45"
                    style={{ backgroundColor: 'var(--color-paper)' }}
                    aria-hidden
                  />
                  <motion.div className="flex shrink-0 flex-row items-baseline justify-between gap-3 pr-6">
                    <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-inverse-muted)]">{phase}</span>
                    <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--text-inverse-secondary)]">
                      {label}
                    </span>
                  </motion.div>
                  <div className="mt-3 mr-6 h-px shrink-0" style={{ backgroundColor: DARK_DIVIDER }} aria-hidden />
                  <p className="mt-4 flex-1 pr-6 font-sans text-[15px] leading-[1.7] text-[var(--text-inverse-secondary)]">
                    {body}
                  </p>
                  <p className="mt-4 shrink-0 pr-6 font-sans text-[14px] italic leading-snug text-[var(--text-inverse-muted)] lowercase">
                    {signal}
                  </p>
                </motion.div>
              </motion.li>
            ))}
          </ol>
        </motion.div>
      </div>
    </section>
  );
}
