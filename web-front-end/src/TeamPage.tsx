import { useEffect } from 'react';
import GalleryFrame from './components/GalleryFrame';

const LINKEDIN = 'https://www.linkedin.com/in/raj-dhanush-yendamuri/';
const GITHUB = 'https://github.com/raj-y12';
const FOUNDER_IMAGE = '/raj-yendamuri.jpg';

const principles = [
  {
    title: 'Show the source',
    body: 'Sources, assumptions, and gaps stay visible before a recommendation becomes a decision.',
  },
  {
    title: 'Keep the person in charge',
    body: 'Aethria prepares the record and preserves the debate. The final investment decision stays with the people responsible for it.',
  },
  {
    title: 'Make every decision useful later',
    body: 'Each decision becomes context for the next one, so a fund can improve how it thinks over time.',
  },
];

export default function TeamPage() {
  useEffect(() => {
    document.title = 'Aethria — Venture judgment, on the record';
    document.querySelector('meta[name="description"]')?.setAttribute(
      'content',
      'Aethria keeps venture judgment on the record for funds that want their reasoning to compound.',
    );
    document.querySelector('meta[property="og:title"]')?.setAttribute(
      'content',
      'Aethria — Venture judgment, on the record',
    );
    document.querySelector('meta[property="og:description"]')?.setAttribute(
      'content',
      'A more deliberate decision layer for venture teams.',
    );
    document.querySelector('meta[property="og:url"]')?.setAttribute('content', 'https://aethria.co/team');
    const canonical = document.querySelector('link[rel="canonical"]') ?? document.createElement('link');
    canonical.setAttribute('rel', 'canonical');
    canonical.setAttribute('href', 'https://aethria.co/team');
    if (!canonical.parentNode) document.head.append(canonical);
  }, []);

  return (
    <div className="team-page">
      <GalleryFrame active="team" quiet />
      <main className="team-main">
        <section className="team-hero surface-image-led" aria-labelledby="team-title">
          <div className="team-hero-copy">
            <p className="team-kicker">Founder-led / Dublin / 2026</p>
            <h1 id="team-title">Aethria keeps venture judgment on the record.</h1>
            <p className="team-hero-lede">
              Raj Yendamuri is building the decision layer for funds that want their reasoning to hold up over time.
            </p>
            <a className="team-text-link" href="#story">
              Read the story <span aria-hidden="true">↘</span>
            </a>
          </div>

          <aside className="team-founder-card" aria-label="Founder profile">
            <div className="team-photo-frame" data-image-slot="founder">
              <span className="team-photo-bracket team-photo-bracket-left" aria-hidden="true" />
              <div className="team-photo-circle">
                <img src={FOUNDER_IMAGE} alt="Raj Yendamuri" width="427" height="427" />
              </div>
              <span className="team-photo-bracket team-photo-bracket-right" aria-hidden="true" />
            </div>
            <div className="team-founder-details">
              <div>
                <p className="team-founder-name">Raj Yendamuri</p>
                <p className="team-founder-role">Founder, Aethria</p>
              </div>
              <div className="team-founder-links">
                <a href={LINKEDIN} target="_blank" rel="noopener noreferrer">
                  LinkedIn
                </a>
                <a href={GITHUB} target="_blank" rel="noopener noreferrer">
                  GitHub
                </a>
              </div>
            </div>
          </aside>
        </section>

        <section id="story" className="team-section team-slice team-story-section" aria-labelledby="story-title">
          <div className="team-section-label">Why it exists</div>
          <div className="team-section-body">
            <h2 id="story-title">Most investment decisions disappear into the process.</h2>
            <p>
              The evidence is somewhere, the reasoning is somewhere else, and the next similar decision starts from
              scratch. That makes judgment difficult to inspect and even harder to improve.
            </p>
            <p>
              Raj built Aethria end-to-end to bring a fund thesis, a sourced opportunity, the evidence behind it, and
              the human decision that follows into one durable record.
            </p>

            <div className="team-record" aria-label="Aethria decision record">
              <div className="team-record-top">
                <span>Decision record</span>
                <span>Sample / 001</span>
              </div>
              <div className="team-record-flow" aria-label="Fund thesis to evidence to human decision">
                <span>FUND THESIS</span>
                <span className="team-record-arrow" aria-hidden="true">→</span>
                <span>EVIDENCE</span>
                <span className="team-record-arrow" aria-hidden="true">→</span>
                <span>HUMAN DECISION</span>
              </div>
              <p>Context stays attached to the call, so the next decision has somewhere to begin.</p>
            </div>
          </div>
        </section>

        <section className="team-section team-slice team-principles-section" aria-labelledby="principles-title">
          <div className="team-section-label">How we work</div>
          <div className="team-section-body">
            <h2 id="principles-title">A clear process leaves room for judgment.</h2>
            <div className="team-principles">
              {principles.map((principle) => (
                <article className="team-principle" key={principle.title}>
                  <p className="team-principle-mark">Working principle</p>
                  <h3>{principle.title}</h3>
                  <p>{principle.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="team-section team-slice team-today-section" aria-labelledby="today-title">
          <div className="team-section-label">The invitation</div>
          <div className="team-section-body">
            <h2 id="today-title">Built for funds that want their judgment to compound.</h2>
            <p>
              Aethria is a founder-led product from Dublin for venture teams building a more deliberate investment
              process.
            </p>
            <dl className="team-facts">
              <div>
                <dt>Founder</dt>
                <dd>Raj Yendamuri</dd>
              </div>
              <div>
                <dt>Based</dt>
                <dd>Dublin, Ireland</dd>
              </div>
            </dl>
          </div>
        </section>
      </main>

    </div>
  );
}
