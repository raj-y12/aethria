import Plate from '../Plate';

/** Specimen holdings — representative names, not real portfolio data. */
const HOLDINGS = [
  { name: 'Meridian Compute', stage: 'Series A', signal: 'Strong', health: 'On track' },
  { name: 'Halden Systems', stage: 'Seed', signal: 'Watching', health: 'On track' },
  { name: 'Cormorant Labs', stage: 'Series B', signal: 'Strong', health: 'At risk' },
] as const;

/** Plate 07 — holdings, a specimen slice of the portfolio table. */
export default function HoldingsPlate() {
  return (
    <Plate id="holdings" index="07 — 08" title="Holdings" capLeft="Holdings — Plate 07" capRight="What the fund carries">
      <table className="holdings reveal d2">
        <thead>
          <tr>
            <th>Company</th>
            <th>Stage</th>
            <th>Signal</th>
            <th>Health</th>
          </tr>
        </thead>
        <tbody>
          {HOLDINGS.map((h) => (
            <tr key={h.name}>
              <td className="name">{h.name}</td>
              <td>{h.stage}</td>
              <td>
                <span className="sig">{h.signal}</span>
              </td>
              <td>{h.health}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="caption reveal d3">
        Specimen holdings. Every accepted name is carried by the portfolio engine — execution tracked, signals
        watched, health checked — for as long as it stays in the fund.
      </p>
    </Plate>
  );
}
