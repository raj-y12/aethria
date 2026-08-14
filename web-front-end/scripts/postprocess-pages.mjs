import { readFile, writeFile } from 'node:fs/promises';

const teamPath = new URL('../dist/team.html', import.meta.url);
let html = await readFile(teamPath, 'utf8');

html = html.replace(/<title>[^<]*<\/title>/, '<title>Aethria — Venture judgment, on the record</title>');
html = html.replace(
  /<meta name="description"[^>]*>/,
  '<meta name="description" content="Aethria keeps venture judgment on the record for funds that want their reasoning to compound.">',
);
html = html.replace(
  /<meta property="og:title"[^>]*>/,
  '<meta property="og:title" content="Aethria — Venture judgment, on the record">',
);
html = html.replace(
  /<meta property="og:description"[^>]*>/,
  '<meta property="og:description" content="A more deliberate decision layer for venture teams.">',
);
html = html.replace(
  /<meta property="og:url"[^>]*>/,
  '<meta property="og:url" content="https://aethria.co/team">',
);
html = html.replace('</title>', '</title><link rel="canonical" href="https://aethria.co/team">');

await writeFile(teamPath, html);
