import assert from 'node:assert/strict';
import { escapeHtml, parseHttpsUrl } from '../api/waitlist.ts';

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

console.log('Waitlist escaping/validation checks passed.');
