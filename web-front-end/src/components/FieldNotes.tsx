import { Link } from 'react-router-dom';
import { ScrollReveal } from './ScrollReveal';

/**
 * Section VI — Field Notes.
 * An editorial index (numbered rows + hairlines) rather than image cards —
 * Aethria has no founder photography, and the document-ledger treatment matches
 * the site's institutional language (rules, numerals, mono labels).
 *
 * NOTE: there is no /notes route yet, so every row points at /request-access.
 * Wire these to real article pages when the content exists.
 */

type Note = {
  category: string;
  title: string;
  blurb: string;
};

const NOTES: Note[] = [
  {
    category: 'Method · Provenance',
    title: 'Why every memo carries its full reasoning chain',
    blurb:
      'Conviction without lineage is just opinion. How Aethria attaches sourcing, scoring, and dissent to every recommendation — so a “yes” and a “pass” are equally defensible.',
  },
  {
    category: 'Field Note · Scouting',
    title: 'Scouting against a thesis, not a trend',
    blurb:
      'Four scout personas, one mandate. Why discovery starts from your fund thesis rather than the week’s headlines.',
  },
  {
    category: 'Field Note · Decisions',
    title: 'What a defensible “pass” looks like',
    blurb:
      'Most pipelines lose the no’s. We keep the reasoning — concentration, timing, and conviction gaps, on the record.',
  },
];

export default function FieldNotes() {
  return (
    <section
      id="method"
      className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="notes-heading"
    >
      <div className="page-margin-x py-16 md:py-24">
        {/* Section header */}
        <ScrollReveal
          y={16}
          amount={0.25}
          className="flex flex-col gap-6 border-b border-solid border-[var(--section-divider)] pb-10 md:flex-row md:items-end md:justify-between md:gap-12 md:pb-12"
        >
          <div className="max-w-2xl">
            <p className="section-numeral mb-5" aria-hidden>
              VI
            </p>
            <h2
              id="notes-heading"
              className="editorial-display text-[clamp(2rem,5vw,3rem)] text-[var(--color-oxford)]"
            >
              How we think about the work
            </h2>
          </div>
          <p className="max-w-[38ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
            Field notes on method, provenance, and the discipline behind a decision you can defend.
          </p>
        </ScrollReveal>

        {/* Editorial index */}
        <div>
          {NOTES.map((note, i) => (
            <ScrollReveal key={note.title} y={14} delay={0.04 + i * 0.06} amount={0.2}>
              <Link
                to="/request-access"
                data-cursor-expand
                className="group grid grid-cols-1 gap-4 border-b border-solid border-[var(--section-divider)] py-8 transition-colors duration-200 hover:bg-[rgba(0,20,51,0.018)] md:grid-cols-[150px_minmax(0,1fr)_auto] md:items-baseline md:gap-12 md:py-10"
              >
                {/* index + kicker */}
                <div className="flex items-baseline gap-4 md:flex-col md:gap-3">
                  <span className="font-mono text-[13px] tracking-[0.08em] text-[var(--text-subtle)] tabular-nums">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--label-muted)]">
                    {note.category}
                  </span>
                </div>

                {/* headline + dek */}
                <div className="min-w-0">
                  <h3 className="font-display text-[clamp(1.35rem,2.6vw,1.8rem)] font-medium leading-[1.18] tracking-[-0.01em] text-[var(--color-oxford)]">
                    {note.title}
                  </h3>
                  <p className="mt-3 max-w-[64ch] font-sans text-[14px] leading-[1.65] text-[var(--text-secondary)]">
                    {note.blurb}
                  </p>
                </div>

                {/* arrow */}
                <span className="accent-link md:justify-self-end md:pt-1">
                  <span>Read</span>
                  <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-1">
                    →
                  </span>
                </span>
              </Link>
            </ScrollReveal>
          ))}
        </div>

        <ScrollReveal y={12} amount={0.4} className="mt-10 flex justify-center md:mt-12">
          <Link to="/request-access" data-cursor-expand className="accent-link">
            <span>All field notes</span>
            <span aria-hidden>→</span>
          </Link>
        </ScrollReveal>
      </div>
    </section>
  );
}
