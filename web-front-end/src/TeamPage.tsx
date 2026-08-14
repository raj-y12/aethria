import { useState } from 'react';
import AccessModal from './components/AccessModal';
import GalleryFrame from './components/GalleryFrame';
import GithubActivityGrid from './components/GithubActivityGrid';
import Plate from './components/Plate';

const LINKEDIN = 'https://www.linkedin.com/in/raj-dhanush-yendamuri/';
const GITHUB = 'https://github.com/raj-y12';

/** Links carry the accent and a proper underline offset — the plate has no other link affordance. */
const linkStyle = {
  color: 'var(--accent)',
  textDecoration: 'underline',
  textDecorationThickness: '1px',
  textUnderlineOffset: '0.25em',
} as const;

/**
 * Team/about page — verifiable founder and company info per Google Cloud Startups
 * review requirements, filed in the same record format the product itself produces.
 */
export default function TeamPage() {
  const [accessOpen, setAccessOpen] = useState(false);

  return (
    <div
      className="relative flex min-h-[100dvh] w-full flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--surface-base)', color: 'var(--text-primary)' }}
    >
      <GalleryFrame onAccess={() => setAccessOpen(true)} />
      <div className="gallery">
        <Plate id="team" index="01 — 02" title="The Team" capLeft="The Team — Plate 01" capRight="Who builds Aethria">
          <div className="record">
            <div className="record-top reveal d2">
              <div className="record-name">Raj Yendamuri</div>
              <div className="record-verdict">Founder</div>
            </div>
            <p className="review-statement reveal d2" style={{ margin: 0, maxWidth: '42ch' }}>
              Raj built Aethria end-to-end: a decision pipeline that sources private-market opportunities, argues
              them against a fund&rsquo;s mandate, and files a ruling with its evidence intact.
            </p>
            <div className="record-reasoning reveal d3">
              <div>
                <h5>The conviction</h5>
                <p>
                  Venture judgment fails at the unglamorous layer — queue discipline, risk controls, audit trail,
                  decision memory — and that layer is an engineering problem.
                </p>
              </div>
              <div>
                <h5>Verify</h5>
                <p>
                  <a href={LINKEDIN} target="_blank" rel="noopener noreferrer" style={linkStyle}>
                    LinkedIn
                  </a>
                  <span style={{ margin: '0 0.6rem', color: 'var(--ink-4)' }}>·</span>
                  <a href={GITHUB} target="_blank" rel="noopener noreferrer" style={linkStyle}>
                    GitHub
                  </a>
                </p>
              </div>
            </div>
          </div>
          <div className="reveal d3" style={{ marginTop: '2.5rem' }}>
            <GithubActivityGrid username="raj-y12" />
          </div>
        </Plate>

        <Plate
          id="house"
          index="02 — 02"
          title="The House"
          capLeft="The House — Plate 02"
          capRight="Where we stand · how we rule"
        >
          <div className="reveal d2">
            <div className="tenet">
              <span className="mark">Traceability</span>
              <div>
                <p className="claim">Every score and decision carries the evidence that produced it.</p>
                <p className="gloss">
                  A verdict arrives with its sources, the policy version it was judged under, and the stage that
                  issued it. A ruling you cannot audit is not a ruling.
                </p>
              </div>
            </div>
            <div className="tenet">
              <span className="mark">Fail closed</span>
              <div>
                <p className="claim">Thin evidence blocks the decision, by name.</p>
                <p className="gloss">
                  Missing mandate, ambiguous identity, or evidence too thin to stand returns a named block rather
                  than a plausible guess — the judgment it declines to make is part of the judgment.
                </p>
              </div>
            </div>
            <div className="tenet">
              <span className="mark">The ruling</span>
              <div>
                <p className="claim">A person rules, and that ruling is the record.</p>
                <p className="gloss">
                  Reviewers argue a company from opposing briefs and the disagreement is kept, not averaged away.
                  The pipeline recommends and escalates; the authoritative decision stays human.
                </p>
              </div>
            </div>
          </div>
          <div className="house-facts reveal d3">
            <span>
              Founded <strong>2026</strong>
            </span>
            <span>
              Based <strong>Dublin, Ireland</strong>
            </span>
            <span>
              <a href="mailto:raj@aethria.co" style={linkStyle}>
                raj@aethria.co
              </a>
            </span>
          </div>
        </Plate>
      </div>

      <AccessModal open={accessOpen} onClose={() => setAccessOpen(false)} />
    </div>
  );
}
