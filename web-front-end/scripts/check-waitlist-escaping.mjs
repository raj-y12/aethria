import assert from 'node:assert/strict';
import { escapeHtml, parseHttpsUrl, isRateLimited } from '../api/waitlist.ts';

assert.equal(
  escapeHtml('<img src=x onerror=alert(1)>'),
  '&lt;img src=x onerror=alert(1)&gt;',
);
assert.equal(escapeHtml(`"><script>`), '&quot;&gt;&lt;script&gt;');
assert.equal(escapeHtml("O'Brien & Co"), 'O&#39;Brien &amp; Co');

assert.equal(parseHttpsUrl('https://linkedin.com/in/someone'), 'https://linkedin.com/in/someone');
assert.equal(parseHttpsUrl('javascript:alert(1)'), null);
assert.equal(parseHttpsUrl('http://linkedin.com/in/someone'), null);
assert.equal(parseHttpsUrl('not a url'), null);

// Regression (audit M10): /api/waitlist had no rate limiting at all.
const rlIp = 'test-ip-' + Date.now();
const rlNow = Date.now();
for (let i = 0; i < 5; i++) {
  assert.equal(isRateLimited(rlIp, rlNow), false, `request ${i + 1} should be allowed`);
}
assert.equal(isRateLimited(rlIp, rlNow), true, '6th request within the window should be limited');

console.log('Waitlist escaping/validation checks passed.');
