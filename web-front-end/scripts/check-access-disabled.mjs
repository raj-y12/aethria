import { readFile } from 'node:fs/promises';

const files = [
  '../src/HomePage.tsx',
  '../src/TeamPage.tsx',
  '../src/components/GalleryFrame.tsx',
  '../src/components/HeroPlate.tsx',
  '../src/components/AnimatedRoutes.tsx',
];

const source = await Promise.all(files.map((file) => readFile(new URL(file, import.meta.url), 'utf8')));
const combined = source.join('\n');
const forbidden = [
  'AccessForm',
  'AccessModal',
  'Request access',
  'request-access',
  'raj@aethria.co',
];
const found = forbidden.filter((marker) => combined.includes(marker));

if (found.length) {
  console.error(`Access-disabled guard failed: ${found.join(', ')}`);
  process.exit(1);
}

console.log('Access-disabled guard passed.');
