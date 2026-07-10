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
    expect(DECISION_BADGE_CLASS.escalation).toContain('!text-white');
    expect(Object.values(DECISION_BADGE_CLASS).every((classes) => classes.includes('!text-'))).toBe(true);
  });
});
