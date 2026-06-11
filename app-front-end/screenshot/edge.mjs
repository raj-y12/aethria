import { chromium } from 'playwright';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1512, height: 945 }, ignoreHTTPSErrors: true });
for (const [name, route] of [['empty-today','/v1'],['empty-flow','/v1/flow'],['empty-portfolio','/v1/portfolio']]) {
  await page.goto(`http://localhost:5181/screenshot/index.html?route=${encodeURIComponent(route)}&empty=1`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `/tmp/${name}.png` });
  console.log('shot', name);
}
// Mobile memo modal
const m = await browser.newPage({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
await m.goto('http://localhost:5181/screenshot/index.html?route=%2Fv1%2Fflow', { waitUntil: 'networkidle' });
await m.waitForTimeout(2000);
await m.screenshot({ path: '/tmp/mobile-flow.png' });
await m.getByText('Veeve').first().click();
await m.waitForTimeout(1600);
await m.screenshot({ path: '/tmp/mobile-memo.png' });
console.log('shot mobile');
await browser.close();
