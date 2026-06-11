import { chromium } from 'playwright';
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1512, height: 945 }, ignoreHTTPSErrors: true });
await page.goto('http://localhost:5181/screenshot/index.html?route=%2Fv1%2Fflow', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);
const info = await page.evaluate(() => {
  const sec = document.querySelector('[aria-label="Pipeline telemetry"]');
  const spans = sec.querySelectorAll('span, p');
  return Array.from(spans).slice(0, 6).map((el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return { text: el.textContent.slice(0, 20), color: cs.color, fontSize: cs.fontSize, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  });
});
console.log(JSON.stringify(info, null, 1));
await browser.close();
