import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useForegroundSync } from '../useForegroundSync';

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('useForegroundSync', () => {
  it('refreshes immediately when a hidden tab becomes visible', () => {
    const refresh = vi.fn();
    const wakeAgents = vi.fn();
    let visibility: DocumentVisibilityState = 'hidden';
    vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => visibility);
    renderHook(() => useForegroundSync({ refresh, wakeAgents }));

    visibility = 'visible';
    act(() => document.dispatchEvent(new Event('visibilitychange')));

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(wakeAgents).toHaveBeenCalledTimes(1);
  });

  it('coalesces the visibility and focus burst and rate-limits agent wakeups', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-14T12:00:00Z'));
    const refresh = vi.fn();
    const wakeAgents = vi.fn();
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
    renderHook(() => useForegroundSync({ refresh, wakeAgents }));

    act(() => {
      document.dispatchEvent(new Event('visibilitychange'));
      window.dispatchEvent(new Event('focus'));
      window.dispatchEvent(new Event('online'));
    });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(wakeAgents).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(1_100);
      window.dispatchEvent(new Event('focus'));
    });
    expect(refresh).toHaveBeenCalledTimes(2);
    expect(wakeAgents).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(60_000);
      window.dispatchEvent(new Event('focus'));
    });
    expect(refresh).toHaveBeenCalledTimes(3);
    expect(wakeAgents).toHaveBeenCalledTimes(2);
  });

  it('does nothing while the document is hidden', () => {
    const refresh = vi.fn();
    const wakeAgents = vi.fn();
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    renderHook(() => useForegroundSync({ refresh, wakeAgents }));

    act(() => window.dispatchEvent(new Event('focus')));

    expect(refresh).not.toHaveBeenCalled();
    expect(wakeAgents).not.toHaveBeenCalled();
  });
});
