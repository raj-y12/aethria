import { Link } from 'react-router-dom';
import { ScrollReveal } from './ScrollReveal';

/**
 * Section VI — Field Notes.
 * Balderton's news/editorial grid (1 featured + 2 small), in Aethria's identity.
 * We have no founder photography, so the "image" blocks are Oxford panels with a
 * faded serif glyph — the institutional stand-in for their portrait/event photos.
 *
 * NOTE: there is no /notes route yet, so every card currently points at
 * /request-access. Wire these to real article pages when the content exists.
 */

type Note = {
  category: string;
  title: string;
  blurb: string;
  glyph: string;
};

const FEATURED: Note = {
  category: 'Method · Provenance',
  title: 'Why every memo carries its full reasoning chain',
  blurb:
    'Conviction without lineage is just opinion. How Aethria attaches sourcing, scoring, and dissent to every recommendation — so a “yes” and a “pass” are equally defensible.',
  glyph: '¶',
};

const NOTES: Note[] = [
  {
    category: 'Field note',
    title: 'Scouting against a thesis, not a trend',
    blurb:
      'Four scout personas, one mandate. Why discovery starts from your fund thesis rather than the week’s headlines.',
    glyph: 'I',
  },
  {
    category: 'Field note',
    title: 'What a defensible “pass” looks like',
    blurb:
      'Most pipelines lose the no’s. We keep the reasoning — concentration, timing, and conviction gaps, on the record.',
    glyph: 'III',
  },
];

function Panel({ glyph, className = '' }: { glyph: string; className?: string }) {
  return (
    <div
      className={`relative flex shrink-0 items-center justify-center overflow-hidden bg-[var(--color-oxford)] ${className}`}
      aria-hidden
    >
      <div className="home-monolith-ambient" />
      <span
        className="font-display leading-none text-[var(--color-paper)] opacity-[0.16]"
        style={{ fontSize: 'clamp(4rem, 12vw, 8rem)' }}
      >
        {glyph}
      </span>
      <span className="absolute bottom-4 left-4 h-px w-12 bg-[var(--color-brass-line)]" />
    </div>
  );
}

export default function FieldNotes() {
  return (
    <section
      className="paper-dot-grid w-full border-b border-solid border-[var(--section-divider)]"
      style={{ backgroundColor: 'var(--color-paper)' }}
      aria-labelledby="notes-heading"
    >
      <div className="page-margin-x py-16 md:py-24">
        <ScrollReveal y={16} amount={0.25}>
          <p className="section-numeral mb-6" aria-hidden>
            VI
          </p>
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <h2
              id="notes-heading"
              className="editorial-display max-w-xl text-[clamp(2rem,5vw,3rem)] text-[var(--color-oxford)]"
            >
              How we think about the <span className="accent-underline">work</span>
            </h2>
            <Link to="/request-access" className="accent-link" data-cursor-expand>
              <span>All field notes</span>
              <span aria-hidden>→</span>
            </Link>
          </div>
        </ScrollReveal>

        {/* Featured */}
        <ScrollReveal y={20} delay={0.06} amount={0.15} className="mt-12 md:mt-16">
          <Link
            to="/request-access"
            data-cursor-expand
            className="group grid grid-cols-1 items-stretch gap-8 md:grid-cols-2 md:gap-12"
          >
            <div className="order-2 flex flex-col justify-center md:order-1">
              <p className="accent-eyebrow">{FEATURED.category}</p>
              <h3 className="mt-5 text-[clamp(1.5rem,3.4vw,2rem)] font-normal leading-[1.18] tracking-[-0.01em] text-[var(--color-oxford)]">
                {FEATURED.title}
              </h3>
              <p className="mt-4 max-w-[46ch] font-sans text-[15px] leading-[1.7] text-[var(--text-secondary)]">
                {FEATURED.blurb}
              </p>
              <span className="accent-link mt-7">
                <span>Read the method</span>
                <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-1">
                  →
                </span>
              </span>
            </div>
            <Panel glyph={FEATURED.glyph} className="order-1 min-h-[220px] md:order-2 md:min-h-[340px]" />
          </Link>
        </ScrollReveal>

        {/* Two small */}
        <div className="mt-12 grid grid-cols-1 gap-10 md:mt-16 md:grid-cols-2 md:gap-12">
          {NOTES.map((note, i) => (
            <ScrollReveal key={note.title} y={18} delay={0.06 + i * 0.06} amount={0.2}>
              <Link
                to="/request-access"
                data-cursor-expand
                className="group flex flex-col gap-5 sm:flex-row sm:items-start"
              >
                <Panel glyph={note.glyph} className="h-[140px] w-full sm:h-[124px] sm:w-[150px]" />
                <div className="min-w-0 flex-1">
                  <p className="accent-eyebrow">{note.category}</p>
                  <h3 className="mt-4 text-[clamp(1.15rem,2.4vw,1.35rem)] font-normal leading-[1.25] tracking-[-0.01em] text-[var(--color-oxford)]">
                    {note.title}
                  </h3>
                  <p className="mt-3 font-sans text-[14px] leading-[1.65] text-[var(--text-secondary)]">
                    {note.blurb}
                  </p>
                  <span className="accent-link mt-4">
                    <span>Learn more</span>
                    <span aria-hidden className="transition-transform duration-200 group-hover:translate-x-1">
                      →
                    </span>
                  </span>
                </div>
              </Link>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
