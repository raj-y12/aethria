import Plate from '../Plate';

/** Plate 04 — the newsroom, a staff/index plate of the real agent personas. */
export default function NewsroomPlate() {
  return (
    <Plate
      id="method"
      index="04 — 08"
      title="The Newsroom"
      capLeft="The Newsroom — Plate 04"
      capRight="Who works the story"
    >
      <div className="newsroom-flow reveal d2" aria-label="Pipeline order">
        <span>Mandate</span>
        <span className="arrow">→</span>
        <span>Scouts</span>
        <span className="arrow">→</span>
        <span>Evidence</span>
        <span className="arrow">→</span>
        <span>Reviewers</span>
        <span className="arrow">→</span>
        <span>Partner</span>
        <span className="arrow">→</span>
        <span>Record</span>
        <span className="arrow">→</span>
        <span>Memory</span>
        <span className="arrow">→</span>
        <span>Portfolio</span>
      </div>
      <div className="staff reveal d2">
        <div className="col">
          <h4>Scouts — source the field</h4>
          <div className="row">
            <span>Market-Driven</span>
            <span className="role">web + exa</span>
          </div>
          <div className="row">
            <span>Builder / Technical</span>
            <span className="role">web + exa</span>
          </div>
          <div className="row">
            <span>Pain-Point</span>
            <span className="role">web + exa</span>
          </div>
          <div className="row">
            <span>Contrarian</span>
            <span className="role">web + exa</span>
          </div>
        </div>
        <div className="col">
          <h4>Reviewers — score the mandate</h4>
          <div className="row">
            <span>Default</span>
            <span className="role">1–10 · 5 dims</span>
          </div>
          <div className="row">
            <span>Skeptical</span>
            <span className="role">built to dissent</span>
          </div>
          <div className="row">
            <span>Opportunist</span>
            <span className="role">built to back</span>
          </div>
          <div className="row">
            <span>Partner Engine</span>
            <span className="role">rules v1 · invest/pass/monitor</span>
          </div>
        </div>
      </div>
      <p className="caption reveal d3">
        It only looks for what you tell it to. A masthead of agents. Scouts source, reviewers argue, the partner
        rules, the portfolio watches, and the meta-agent calibrates the newsroom against real outcomes.
      </p>
    </Plate>
  );
}
