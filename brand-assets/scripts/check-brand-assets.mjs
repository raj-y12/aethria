import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import process from 'node:process';

const root = resolve(import.meta.dirname, '..');
const indexPath = resolve(root, 'index.html');
const assetNames = [
  'favicon.svg',
  'logo-icon-light.svg',
  'logo-icon-transparent.svg',
  'logo-monogram-dark.svg',
  'logo-monogram-light.svg',
  'logo-wordmark-dark.svg',
  'logo-wordmark-light.svg',
];

const index = await readFile(indexPath, 'utf8');

if (index.includes('createRadialGradient') || index.includes('buildBlobs') || index.includes('drawBlob')) {
  throw new Error('Brand studio must use the linear motion-streak renderer, not radial blobs.');
}

for (const assetName of assetNames) {
  const asset = await readFile(resolve(root, 'assets', assetName), 'utf8');
  if (!asset.includes('data-brand-bracket')) {
    throw new Error(`${assetName} is missing its loader-style bracket mark.`);
  }
}

if (!index.includes('function drawStreakField') || !index.includes('function drawBrackets')) {
  throw new Error('Brand studio must expose shared streak and bracket drawing helpers.');
}

if (!index.includes('var gap = 26 * s;') || !index.includes('var arm = 14 * s;')) {
  throw new Error('Canvas brackets must match the gallery loader’s 26px offset and 14px arm.');
}

if (!index.includes('angle: -0.035 + (rng() - 0.5) * 0.035')) {
  throw new Error('Motion field must use the reference’s near-horizontal blur direction.');
}

console.log(`Brand assets verified: ${assetNames.length} bracketed SVGs and motion-streak studio.`);
