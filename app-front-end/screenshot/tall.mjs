import { chromium } from 'playwright';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1512, height: 3600 }, ignoreHTTPSErrors: true });
await page.goto('http://localhost:5181/screenshot/index.html?route=%2Fv1%2Fflow', { waitUntil: 'networkidle' });
await page.waitForTimeout(2600);
await page.screenshot({ path: '/tmp/flow-tall.png' });
await browser.close();
console.log('done');
