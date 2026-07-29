import { describe, expect, it } from 'vitest';
import memoSource from '../../components/InvestmentMemoContent.tsx?raw';
import {
  buildFounderSectionModel,
  formatFounderBackground,
  formatMissingFounderFields,
} from '../founderMemo';
import type { FounderResolution } from '../../types/startup';

const RESOLUTION: FounderResolution = {
  company: 'Acme',
  resolution_status: 'FOUND',
  founders: [
    {
      name: 'Ada Byron',
      role: 'Co-founder & CEO',
      linkedin_url: 'https://linkedin.com/in/ada-byron',
      previous_employment: ['Stripe'],
      education: ['Imperial College London'],
      confidence: 0.8,
    },
  ],
  missing_fields: ['x_url', 'github_url'],
};

describe('founder section model', () => {
  it('surfaces structured founders when the resolver found them', () => {
    const model = buildFounderSectionModel({ founderResolution: RESOLUTION });
    expect(model.candidates).toHaveLength(1);
    expect(model.names).toEqual(['Ada Byron']);
    expect(model.emptyMessage).toBeNull();
  });

  it('says nobody was found when the resolver ran and found nobody', () => {
    const model = buildFounderSectionModel({
      founderResolution: {
        company: 'Acme',
        resolution_status: 'NOT_FOUND',
        founders: [],
        missing_fields: ['founder_names', 'role'],
      },
    });
    expect(model.names).toEqual([]);
    expect(model.emptyMessage).toMatch(/no founder could be confirmed/i);
  });

  it('distinguishes "not gathered" from "not found"', () => {
    const model = buildFounderSectionModel({});
    expect(model.emptyMessage).toMatch(/not been gathered/i);
  });

  it('never reports founder_names itself as an unconfirmed field', () => {
    const model = buildFounderSectionModel({
      founderResolution: {
        company: 'Acme',
        founders: [],
        missing_fields: ['founder_names', 'role'],
      },
    });
    expect(model.missing).toEqual(['role']);
  });

  it('falls back to company resolution names', () => {
    const model = buildFounderSectionModel({
      companyResolution: { query: 'Acme', canonical_name: 'Acme', founder_names: ['Grace Hopper'] },
    });
    expect(model.names).toEqual(['Grace Hopper']);
    expect(model.emptyMessage).toBeNull();
  });

  it('falls back to scout founder names last', () => {
    const model = buildFounderSectionModel({ scoutFounderNames: ['Alan Turing'] });
    expect(model.names).toEqual(['Alan Turing']);
  });

  it('prefers structured founders over legacy name lists', () => {
    const model = buildFounderSectionModel({
      founderResolution: RESOLUTION,
      companyResolution: { query: 'Acme', canonical_name: 'Acme', founder_names: ['Someone Else'] },
      scoutFounderNames: ['Another Person'],
    });
    expect(model.names).toEqual(['Ada Byron']);
  });

  it('ignores blank names', () => {
    const model = buildFounderSectionModel({
      founderResolution: { company: 'Acme', founders: [{ name: '  ' }] },
      scoutFounderNames: ['', '   '],
    });
    expect(model.names).toEqual([]);
    expect(model.emptyMessage).not.toBeNull();
  });
});

describe('founder formatting', () => {
  it('joins employment and education', () => {
    expect(formatFounderBackground(RESOLUTION.founders![0])).toBe(
      'Previously Stripe · Imperial College London',
    );
  });

  it('returns an empty string when there is no background', () => {
    expect(formatFounderBackground({ name: 'Ada Byron' })).toBe('');
  });

  it('labels missing fields for readers', () => {
    expect(formatMissingFounderFields(['linkedin_url', 'role'])).toBe('LinkedIn profile, role');
  });

  it('falls back to a humanised key for unknown fields', () => {
    expect(formatMissingFounderFields(['some_new_field'])).toBe('some new field');
  });
});

describe('memo founder section rendering', () => {
  it('renders the founder section unconditionally', () => {
    // Regression: the section used to be wrapped in a truthiness guard, so a
    // company with no founder data showed no Founder heading at all.
    const heading = '<MemoSectionTitle number="02" id="memo-founder">Founder</MemoSectionTitle>';
    const idx = memoSource.indexOf(heading);
    expect(idx).toBeGreaterThan(-1);
    const preceding = memoSource.slice(Math.max(0, idx - 400), idx);
    expect(preceding).not.toMatch(/founderNames\.length > 0 \|\|/);
    expect(preceding).toContain('<motion.section');
  });

  it('shows profile links and conflict warnings when present', () => {
    expect(memoSource).toContain('memoFounderLinks');
    expect(memoSource).toContain('memoFounderConflict');
  });
});
