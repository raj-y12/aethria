import { DEMO_LOOKUP_QUERY, DEMO_LOOKUP_RESULT, LookupCommandBar, LookupResultSnapshot } from '@aethria/product-chrome';
import Plate from '../Plate';

/** Plate 06 — place a query: the real on-demand lookup, reused from product-chrome. */
export default function QueryPlate() {
  return (
    <Plate
      id="query"
      index="06 — 08"
      title="Place a Query"
      capLeft="Place a Query — Plate 06"
      capRight="Any name · a sourced record"
    >
      <div className="query reveal d2" aria-hidden>
        <LookupCommandBar query={DEMO_LOOKUP_QUERY} trailing="run" />
        <LookupResultSnapshot {...DEMO_LOOKUP_RESULT} />
      </div>
      <p className="caption reveal d3">
        On-demand lookup turns any company name into a sourced investment record in seconds — benchmarked against
        your active thesis the moment results arrive.
      </p>
    </Plate>
  );
}
