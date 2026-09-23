import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MemoDecisionLead from '../MemoDecisionLead';
import type { MemoDecisionBrief } from '../../../lib/memoDecisionBrief';

const base: MemoDecisionBrief = {
  status: 'ready_for_ruling',
  lean: 'monitor',
  leanProvenance: 'rule-derived',
  mandate: 'unknown',
  coverage: 'sufficient',
  agreement: 'unknown',
  ruling: null,
  drivers: ['Rule-derived recommendation based on current evidence.'],
  claims: [],
  derivations: [],
  risks: [],
};

describe('MemoDecisionLead', () => {
  it('uses a concise decision heading and exposes all reasoning without disclosure', () => {
    render(<MemoDecisionLead brief={{ ...base, drivers: ['First reason.', 'Second reason.'] }} />);
    expect(screen.getByRole('heading', { name: 'Monitor', level: 2 })).toBeInTheDocument();
    expect(screen.getByText('First reason.')).toBeVisible();
    expect(screen.getByText('Second reason.')).toBeVisible();
    expect(document.querySelector('details')).toBeNull();
  });

  it('attributes a rule-derived recommendation to the system', () => {
    render(<MemoDecisionLead brief={base} />);
    expect(screen.getByText('Recommendation')).toBeInTheDocument();
    expect(screen.getByText('Monitor')).toBeInTheDocument();
    expect(screen.queryByText('Partner’s view')).not.toBeInTheDocument();
  });

  it('attributes the recommendation to Partner only when canonical provenance says so', () => {
    render(<MemoDecisionLead brief={{ ...base, leanProvenance: 'partner-judgment', lean: 'more_diligence' }} />);
    expect(screen.getByText('Partner’s view')).toBeInTheDocument();
    expect(screen.getByText('More diligence')).toBeInTheDocument();
  });

  it('keeps a blocked rule-derived state distinct from More diligence', () => {
    render(<MemoDecisionLead brief={{ ...base, status: 'blocked', lean: 'none', coverage: 'missing' }} stateMessage="Evidence is incomplete — verify the missing source." />);
    expect(screen.getByText('Recommendation')).toBeInTheDocument();
    expect(screen.getByText('Evidence is incomplete — verify the missing source.')).toBeInTheDocument();
    expect(screen.queryByText('More diligence')).not.toBeInTheDocument();
  });

  it('keeps a recorded human ruling separate from the canonical recommendation', () => {
    render(<MemoDecisionLead brief={{ ...base, ruling: { ruling_id: 'r1', decision: 'pass', rationale: 'No.', created_at: '2026-09-17' }, status: 'recorded' }} />);
    expect(screen.getByText('Recommendation')).toBeInTheDocument();
    expect(screen.getByText('Human ruling recorded: pass')).toBeInTheDocument();
  });

  it('fails closed without showing legacy rationale while canonical data is unavailable', () => {
    render(<MemoDecisionLead brief={{ ...base, status: 'unavailable', lean: 'none', leanProvenance: 'missing', drivers: [] }} />);
    expect(screen.getByText('Decision rationale unavailable.')).toBeInTheDocument();
    expect(screen.queryByText('More diligence')).not.toBeInTheDocument();
  });
});
