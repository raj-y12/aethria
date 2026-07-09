import { readdir, stat } from 'node:fs/promises';
import { join } from 'node:path';

const maxBytes = 500 * 1024;
const dir = new URL('../dist/assets/', import.meta.url);
const files = await readdir(dir);
const oversized = [];
for (const file of files) {
  const size = (await stat(join(dir.pathname, file))).size;
  if (size > maxBytes && /\.(js|css)$/.test(file)) oversized.push(`${file}=${size}`);
}
if (oversized.length) {
  console.error(`Bundle budget exceeded (${maxBytes} bytes): ${oversized.join(', ')}`);
  process.exit(1);
}
console.log(`Bundle budget passed: ${files.length} assets checked.`);
