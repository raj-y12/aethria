import { ScrollReveal } from './ScrollReveal';

/**
 * Section III — the belief.
 * Balderton's "Investing in companies and the people building them" beat, in
 * Aethria's language: a centered serif claim with one accent-underlined word,
 * followed by a three-up row of principle cards (their three-portrait row).
 */

const PRINCIPLES = [
  {
    label: 'Mandate-gated',
    body: 'No thesis, no pipeline. Every decision answers to the mandate you define.',
  },
  {
    label: 'Fully traceable',
    body: 'Sourcing, scoring, and dissent attached to every memo the system surfaces.',
  },
  {
    label: 'Human-in-loop',
    body: 'The system recommends, with reasoning. You advance, pass, or hold.',
  },
];

export default function BeliefSection() {
  return (
    <section
      className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="belief-heading"
    >
      <div className="page-margin-x mx-auto w-full max-w-[1100px] py-16 md:py-24">
        <ScrollReveal y={18} amount={0.3} className="mx-auto max-w-[760px] text-center">
          <p className="section-numeral mb-6" aria-hidden>
            III
          </p>
          <h2
            id="belief-heading"
            className="editorial-display text-[clamp(2.2rem,5.5vw,3.6rem)] text-[var(--color-oxford)]"
          >
            Conviction you can{' '}
            <span className="accent-underline">defend</span> in the room.
          </h2>
          <p className="mx-auto mt-6 max-w-[54ch] font-sans text-[16px] leading-[1.7] text-[var(--text-secondary)]">
            Aethria doesn’t hand you a score and a shrug. Every name arrives sourced, reviewed against your
            thesis, and carrying its full reasoning chain — so the judgment holds up when the committee opens
            the file.
          </p>
        </ScrollReveal>

        <ScrollReveal
          y={20}
          delay={0.08}
          amount={0.2}
          className="mt-12 grid grid-cols-1 gap-px overflow-hidden border border-solid border-[var(--section-divider)] bg-[var(--section-divider)] md:mt-16 md:grid-cols-3"
        >
          {PRINCIPLES.map((p) => (
            <div key={p.label} className="relative bg-[var(--color-paper)] p-7 md:p-8">
              <span className="accent-corner-dot" aria-hidden />
              <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-[var(--color-oxford)]">
                {p.label}
              </p>
              <p className="mt-3 font-sans text-[14px] leading-[1.65] text-[var(--text-secondary)]">{p.body}</p>
            </div>
          ))}
        </ScrollReveal>
      </div>
    </section>
  );
}
