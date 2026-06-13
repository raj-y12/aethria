/* Screenshot driver: node screenshot/shots.mjs */
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const BASE = 'http://localhost:5181/screenshot/index.html';
const OUT = 'screenshot/shots';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-device-scale-factor=2'],
});
const page = await browser.newPage({
  viewport: { width: 1512, height: 945 },
  ignoreHTTPSErrors: true, // sandbox egress proxy re-signs TLS (Google Fonts)
});
page.on('pageerror', (e) => console.log('PAGE ERROR:', e.message));
page.on('console', (m) => {
  if (m.type() === 'error') console.log('CONSOLE:', m.text().slice(0, 300));
});

const routes = [
  ['today', '/v1'],
  ['flow', '/v1/flow'],
  ['portfolio', '/v1/portfolio'],
  ['fund', '/v1/fund'],
  ['settings', '/v1/settings'],
];

for (const [name, route] of routes) {
  await page.goto(`${BASE}?route=${encodeURIComponent(route)}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2600); // let reveals/count-ups settle
  await page.screenshot({ path: `${OUT}/${name}.png` });
  console.log('shot', name);
}

// Dispatch takeover, opened from the front door key
await page.goto(`${BASE}?route=${encodeURIComponent('/v1')}`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1800);
await page.getByRole('button', { name: /dispatch/i }).first().click();
await page.waitForTimeout(1200);
await page.screenshot({ path: `${OUT}/dispatch.png` });
console.log('shot dispatch');

await browser.close();
