import { readFile } from 'node:fs/promises';

const candidates = ['../dist/home.html', '../dist/index.html'];
let html;
let source;
for (const rel of candidates) {
  try {
    html = await readFile(new URL(rel, import.meta.url), 'utf8');
    source = rel;
    break;
  } catch {
    // try next candidate
  }
}
if (html === undefined) {
  console.error(`Marketing guard: neither ${candidates.join(' nor ')} exists — run the build first.`);
  process.exit(1);
}

const teamHtml = await readFile(new URL('../dist/team.html', import.meta.url), 'utf8').catch(() => undefined);
if (teamHtml === undefined) {
  console.error('Marketing guard: dist/team.html does not exist — run the build first.');
  process.exit(1);
}

const checks = [
  ['lede present', () => html.includes('Private-market judgment, on the record')],
  ['home evidence spine present', () =>
    ['Aethria', 'Fund thesis', 'Evidence trail', 'Human decision'].every((marker) => html.includes(marker))],
  ['hero keeps editorial restraint', () => !html.includes('Decision surface') && !html.includes('Live / 001')],
  ['reviewer dims present', () =>
    ['Market', 'Product', 'Technical', 'Execution', 'Defensibility'].every((d) => html.includes(d))],
  ['query dispatch sequence present', () =>
    ['data-query-flow="dispatch-sequence"', 'data-dispatch-stages="Identify Discover Review Decide"'].every((marker) => html.includes(marker))],
  ['home drops repeated plate furniture', () =>
    !['The Market — Plate 01', 'The Record — Plate 02', 'The Review — Plate 03', 'The Newsroom — Plate 04'].some(
      (marker) => html.includes(marker)
    )],
  ['home includes quiet colophon footer', () =>
    ['Private-market intelligence for funds that need the evidence trail', 'Dublin, Ireland', 'Specimen Edition'].every(
      (marker) => html.includes(marker)
    )],
  ['JSON-LD present', () => html.includes('application/ld+json')],
  ['no fonts.googleapis.com', () => !html.includes('fonts.googleapis.com')],
  ['theme-color grey stock', () => /theme-color" content="#D9D7D4/i.test(html)],
  ['no scroll-cue marker', () => !html.toLowerCase().includes('scrollcue')],
  ['team page uses thesis-led structure', () =>
    ['Aethria keeps venture judgment on the record.', 'Most investment decisions disappear into the process.', 'How we work'].every((heading) =>
      teamHtml.includes(heading)
    )],
  ['team page has route-specific metadata', () =>
    ['<title>Aethria — Venture judgment, on the record</title>', 'content="Aethria keeps venture judgment on the record', 'href="https://aethria.co/team"'].every(
      (marker) => teamHtml.includes(marker)
    )],
  ['team page includes the decision record', () =>
    ['FUND THESIS', 'EVIDENCE', 'HUMAN DECISION'].every((marker) => teamHtml.includes(marker))],
  ['team page uses concrete principles', () =>
    ['Show the source', 'Keep the person in charge', 'Make every decision useful later'].every((principle) =>
      teamHtml.includes(principle)
    )],
  ['team page has a founder photo slot', () =>
    teamHtml.includes('data-image-slot="founder"') && teamHtml.includes('/raj-yendamuri.jpg') && !teamHtml.includes('team-photo-placeholder')],
  ['team page drops internal and template language', () =>
    !teamHtml.includes('The House') && !teamHtml.includes('The ruling') && !teamHtml.includes('Meet the founder')],
];

const failed = checks.filter(([, fn]) => !fn()).map(([name]) => name);
if (failed.length) {
  console.error(`Marketing guard failed (${source}): ${failed.join(', ')}`);
  process.exit(1);
}
console.log(`Marketing guard passed: ${checks.length} checks against ${source}.`);
