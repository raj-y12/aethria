import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useMemoDecisionBrief } from '../useMemoDecisionBrief';

vi.mock('@tanstack/react-query', () => ({
  useQuery: ({ queryKey }: { queryKey: string[] }) => ({
    isLoading: false,
    isError: false,
    data: queryKey[1] === 'opportunity' ? { opportunity_id: 'opportunity' }
      : queryKey[1] === 'evaluation' ? {
        evaluation: {}, criteria: [], recommendation: null,
        dependencies: { state: 'stale', reasons: ['thesis_changed'], message: 'Your thesis changed. Refresh this review.' },
      } : queryKey[1] === 'evidence' ? { claims: [], evidence_items: [], artifacts: [], links: [] } : [],
  }),
}));

describe('useMemoDecisionBrief dependency validity', () => {
  it('shows the investment-facing refresh notice instead of hiding staleness behind missing evidence', () => {
    const { result } = renderHook(() => useMemoDecisionBrief('startup'));
    expect(result.current.stateMessage).toBe('Your thesis changed. Refresh this review.');
    expect(result.current.stateMessage).not.toContain('thesis_changed');
  });
});
