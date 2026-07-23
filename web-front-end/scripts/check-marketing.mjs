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

const checks = [
  ['lede present', () => html.includes('Private-market judgment, on the record')],
  ['reviewer dims present', () =>
    ['Market', 'Product', 'Technical', 'Execution', 'Defensibility'].every((d) => html.includes(d))],
  ['JSON-LD present', () => html.includes('application/ld+json')],
  ['no fonts.googleapis.com', () => !html.includes('fonts.googleapis.com')],
  ['theme-color grey stock', () => /theme-color" content="#D9D7D4/i.test(html)],
  ['no scroll-cue marker', () => !html.toLowerCase().includes('scrollcue')],
];

const failed = checks.filter(([, fn]) => !fn()).map(([name]) => name);
if (failed.length) {
  console.error(`Marketing guard failed (${source}): ${failed.join(', ')}`);
  process.exit(1);
}
console.log(`Marketing guard passed: ${checks.length} checks against ${source}.`);
