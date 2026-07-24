import { describe, expect, it } from 'vitest';
import { tokens } from '../tokens';
import { DECISION_BADGE_CLASS } from '../verdictBadgeTokens';

describe('memo-calibrated mono typography roles', () => {
  it('defines the label and metadata roles at the approved scale', () => {
    expect(tokens.type.labelSection).toEqual({
      size: '10px', lineHeight: 1.45, letterSpacing: '0.09em', fontWeight: 400,
      font: 'mono', uppercase: true,
    });
    expect(tokens.type.meta).toEqual({
      size: '11px', lineHeight: 1.5, letterSpacing: '0.04em', fontWeight: 400,
      font: 'mono',
    });
  });

  it('keeps TypeScript token values aligned with the CSS contract', () => {
    expect(tokens.type.data).toEqual({
      size: '13px',
      lineHeight: 1.35,
      letterSpacing: '-0.015em',
      fontWeight: 600,
      font: 'mono',
      tabular: true,
    });
    expect(tokens.type.status).toEqual({
      size: '10px',
      lineHeight: 1.4,
      letterSpacing: '0.075em',
      fontWeight: 600,
      font: 'mono',
      uppercase: true,
    });
    expect(tokens.type.action).toEqual({
      size: '10px',
      lineHeight: 1.4,
      letterSpacing: '0.075em',
      fontWeight: 400,
      font: 'mono',
      uppercase: true,
    });
  });

  it('protects semantic verdict text colours from role defaults', () => {
    // Escalation is the one filled "fire alarm" chip — it needs the !important
    // override to guarantee white text against its filled background.
    expect(DECISION_BADGE_CLASS.escalation).toContain('!text-white');
    // Every other verdict is a transparent outline chip (marketing parity —
    // label reads the verdict, not fill colour): plain `text-oxford` classes
    // already win over the zero-specificity `:where(.type-status)` role
    // default, so no `!important` override is needed or expected there.
    const outlineVariants = Object.entries(DECISION_BADGE_CLASS).filter(([variant]) => variant !== 'escalation');
    expect(outlineVariants.every(([, classes]) => classes.includes('text-oxford'))).toBe(true);
    expect(outlineVariants.every(([, classes]) => !classes.includes('!text-'))).toBe(true);
  });
});
