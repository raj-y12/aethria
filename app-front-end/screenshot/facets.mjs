import { chromium } from 'playwright';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1512, height: 1400 }, ignoreHTTPSErrors: true });
await page.goto('http://localhost:5181/screenshot/index.html?route=%2Fv1%2Ffund', { waitUntil: 'networkidle' });
await page.waitForTimeout(1800);
for (const tab of ['Record', 'Patterns', 'Calibration', 'Evolution']) {
  await page.getByRole('tab', { name: tab }).click();
  await page.waitForTimeout(1100);
  await page.screenshot({ path: `/tmp/facet-${tab.toLowerCase()}.png` });
  console.log('shot', tab);
}
await browser.close();
