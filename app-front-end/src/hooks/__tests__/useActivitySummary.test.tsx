import { StrictMode, type ReactNode } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchActivitySummary = vi.fn();
const markActivitySeen = vi.fn();

vi.mock('../../api/activity', () => ({
  fetchActivitySummary,
  markActivitySeen,
}));

describe('useSinceAwaySummary', () => {
  beforeEach(() => {
    vi.resetModules();
    fetchActivitySummary.mockReset();
    markActivitySeen.mockReset().mockResolvedValue(undefined);
    sessionStorage.clear();
  });

  it('starts a fresh away window while hidden and reports work when the tab returns', async () => {
    fetchActivitySummary
      .mockResolvedValueOnce({
        found: 0,
        reviewed: 0,
        decided: 0,
        agent_decided: 0,
        escalations: 0,
      })
      .mockResolvedValueOnce({
        found: 2,
        reviewed: 1,
        decided: 1,
        agent_decided: 1,
        escalations: 0,
      });

    let visibility: DocumentVisibilityState = 'visible';
    vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => visibility);
    const { useSinceAwaySummary } = await import('../useActivitySummary');
    const { result } = renderHook(() => useSinceAwaySummary('user_one'));

    await waitFor(() => expect(fetchActivitySummary).toHaveBeenCalledTimes(1));

    visibility = 'hidden';
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await waitFor(() => expect(markActivitySeen).toHaveBeenCalledTimes(1));

    visibility = 'visible';
    act(() => document.dispatchEvent(new Event('visibilitychange')));

    await waitFor(() => expect(fetchActivitySummary).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(result.current?.found).toBe(2));
  });

  it('single-flights the initial report across a StrictMode remount', async () => {
    fetchActivitySummary.mockResolvedValue({
      found: 1,
      reviewed: 0,
      decided: 0,
      agent_decided: 0,
      escalations: 0,
    });
    const { useSinceAwaySummary } = await import('../useActivitySummary');

    renderHook(() => useSinceAwaySummary('user_one'), {
      wrapper: ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>,
    });

    await waitFor(() => expect(fetchActivitySummary).toHaveBeenCalled());
    expect(fetchActivitySummary).toHaveBeenCalledTimes(1);
  });

  it('does not reuse one tenant report after the signed-in user changes', async () => {
    fetchActivitySummary
      .mockResolvedValueOnce({ found: 1, reviewed: 0, decided: 0, agent_decided: 0, escalations: 0 })
      .mockResolvedValueOnce({ found: 3, reviewed: 0, decided: 0, agent_decided: 0, escalations: 0 });
    const activityModule = await import('../useActivitySummary');
    const useSummary = activityModule.useSinceAwaySummary as (userId: string) =>
      ReturnType<typeof activityModule.useSinceAwaySummary>;
    const { result, rerender } = renderHook(
      ({ userId }) => useSummary(userId),
      { initialProps: { userId: 'user_one' } },
    );

    await waitFor(() => expect(result.current?.found).toBe(1));
    rerender({ userId: 'user_two' });

    await waitFor(() => expect(fetchActivitySummary).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(result.current?.found).toBe(3));
  });
});
