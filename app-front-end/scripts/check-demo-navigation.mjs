import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../demo/main.tsx', import.meta.url), 'utf8');
const required = ['Exit demo', 'https://aethria.co/'];
const missing = required.filter((marker) => !source.includes(marker));

if (missing.length) {
  console.error(`Demo navigation guard failed: ${missing.join(', ')}`);
  process.exit(1);
}

console.log('Demo navigation guard passed.');
