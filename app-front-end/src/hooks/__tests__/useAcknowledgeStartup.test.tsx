import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Startup } from '../../types/startup';

const acknowledgeStartup = vi.fn();

vi.mock('../../api/startups', () => ({
  acknowledgeStartup: (...args: unknown[]) => acknowledgeStartup(...args),
}));

function startup(overrides: Partial<Startup> = {}): Startup {
  return {
    id: 'startup-1',
    is_new_to_user: true,
    timestamps: {},
    ...overrides,
  } as Startup;
}

describe('useAcknowledgeStartup', () => {
  beforeEach(() => {
    acknowledgeStartup.mockReset();
  });

  it('rolls back the optimistic write when the server returns no result', async () => {
    // Regression (audit HIGH-H12): acknowledgeStartup() returning null used
    // to do nothing -- the cache stayed optimistically "seen" forever even
    // though the server never recorded it.
    acknowledgeStartup.mockResolvedValue(null);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const original = startup();
    queryClient.setQueryData(['startups', 'list'], [original]);

    const { useAcknowledgeStartup } = await import('../useAcknowledgeStartup');
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useAcknowledgeStartup(), { wrapper });

    act(() => {
      result.current(original);
    });

    // Optimistic write applied immediately.
    expect(queryClient.getQueryData<Startup[]>(['startups', 'list'])?.[0].is_new_to_user).toBe(false);

    await waitFor(() => expect(acknowledgeStartup).toHaveBeenCalledWith('startup-1'));
    await waitFor(() =>
      expect(queryClient.getQueryData<Startup[]>(['startups', 'list'])?.[0].is_new_to_user).toBe(true),
    );
  });

  it('rolls back the optimistic write when the request throws', async () => {
    acknowledgeStartup.mockRejectedValue(new Error('network error'));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const original = startup();
    queryClient.setQueryData(['startups', 'list'], [original]);

    const { useAcknowledgeStartup } = await import('../useAcknowledgeStartup');
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useAcknowledgeStartup(), { wrapper });

    act(() => {
      result.current(original);
    });

    await waitFor(() =>
      expect(queryClient.getQueryData<Startup[]>(['startups', 'list'])?.[0].is_new_to_user).toBe(true),
    );
  });

  it('applies the server response when acknowledgement succeeds', async () => {
    const updated = startup({ is_new_to_user: false });
    acknowledgeStartup.mockResolvedValue(updated);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    queryClient.setQueryData(['startups', 'list'], [startup()]);

    const { useAcknowledgeStartup } = await import('../useAcknowledgeStartup');
    const onSynced = vi.fn();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useAcknowledgeStartup(onSynced), { wrapper });

    act(() => {
      result.current(startup());
    });

    await waitFor(() => expect(onSynced).toHaveBeenCalledWith(updated));
  });
});
