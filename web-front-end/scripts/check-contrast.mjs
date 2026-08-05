// ponytail: WCAG 2.x relative-luminance formula, minimal — no color library dep.
function srgbToLinear(c) {
  const v = c / 255;
  return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
}
function luminance([r, g, b]) {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}
function contrast(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}
function blend(fg, bg, alpha) {
  return fg.map((c, i) => alpha * c + (1 - alpha) * bg[i]);
}

const paper = [0xd9, 0xd7, 0xd4];
const ink = [0x0a, 0x16, 0x29];
const AA_NORMAL_TEXT = 4.5;

// These alpha values back --ink-2 / text-oxford/65 — the tokens essential
// caption and metadata text now uses instead of the non-compliant --ink-3 (0.44).
const essentialTextAlphas = { 'ink-2 (0.66)': 0.66, 'oxford/65 (0.65)': 0.65 };

let failed = false;
for (const [name, alpha] of Object.entries(essentialTextAlphas)) {
  const ratio = contrast(blend(ink, paper, alpha), paper);
  const ok = ratio >= AA_NORMAL_TEXT;
  console.log(`${name}: ${ratio.toFixed(2)}:1 ${ok ? 'PASS' : 'FAIL'}`);
  if (!ok) failed = true;
}
if (failed) {
  console.error('Essential text token(s) below WCAG AA 4.5:1 on paper.');
  process.exit(1);
}
console.log('Contrast checks passed.');
