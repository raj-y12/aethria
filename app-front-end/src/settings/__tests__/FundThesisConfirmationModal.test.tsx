import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import FundThesisConfirmationModal from '../FundThesisConfirmationModal';
import modalSource from '../FundThesisConfirmationModal.tsx?raw';

const changes = [
  {
    key: 'sectors' as const,
    label: 'Sectors',
    previous: 'Fintech',
    proposed: 'Climate',
  },
];

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe('FundThesisConfirmationModal', () => {
  it('uses the Dispatch takeover composition', () => {
    expect(modalSource).toContain('paper-dot-grid');
    expect(modalSource).toContain('items-center justify-center');
    expect(modalSource).toContain('Policy deployment');
    expect(modalSource).toContain('Confirm policy changes');
    expect(modalSource).toContain('Deploy policy changes');
    expect(modalSource).not.toContain('<header');
    expect(modalSource).not.toContain('<footer');
  });

  it('renders stacked mobile comparison labels and keeps the desktop headings responsive', () => {
    render(
      <FundThesisConfirmationModal
        open
        changes={changes}
        firstPublication={false}
        busy={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const change = screen.getByRole('region', { name: 'Sectors' });
    expect(within(change).getByText('Currently live')).toHaveClass('md:hidden');
    expect(within(change).getByText('Proposed')).toHaveClass('md:hidden');
    expect(screen.getByTestId('desktop-comparison-headings')).toHaveClass('hidden', 'md:grid');
    expect(change).toHaveClass('grid-cols-1', 'md:grid-cols-[minmax(9rem,22%)_minmax(0,1fr)_minmax(0,1fr)]');
  });

  it('keeps long comparison values shrinkable and able to wrap anywhere', () => {
    render(
      <FundThesisConfirmationModal
        open
        changes={changes}
        firstPublication={false}
        busy={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByText('Fintech').parentElement).toHaveClass('min-w-0');
    expect(screen.getByText('Fintech')).toHaveClass('break-words', '[overflow-wrap:anywhere]');
    expect(screen.getByText('Climate').parentElement).toHaveClass('min-w-0');
  });

  it('uses restrained Dispatch underlines without shrinking the action targets', () => {
    render(
      <FundThesisConfirmationModal
        open
        changes={changes}
        firstPublication={false}
        busy={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const cancel = screen.getByRole('button', { name: /go back/i });
    const confirm = screen.getByRole('button', { name: /deploy policy changes/i });
    expect(cancel).toHaveClass('min-h-11');
    expect(within(cancel).getByText('Go back')).toHaveClass('border-b', 'border-oxford/10', 'hover:border-oxford/40');
    // The confirm action is the canonical solid primary (36px), matching the
    // log-out takeover — no 44px override.
    expect(confirm).toHaveClass('btn-aethria-solid');
    expect(confirm).not.toHaveClass('min-h-11');
  });

  it('matches the Dispatch upward reveal cadence with reduced-motion overrides', () => {
    expect(modalSource).toContain('duration: reduceMotion ? 0 : 0.5');
    expect(modalSource).toContain('delay: reduceMotion ? 0 : 0.42');
    expect(modalSource.match(/translateY\(10px\)/g)?.length).toBeGreaterThanOrEqual(5);
    expect(modalSource).not.toContain('duration: reduceMotion ? 0 : 0.4');
    expect(modalSource).not.toContain('duration: reduceMotion ? 0 : 0.45');
  });

  it('requires an explicit confirmation after showing the live and proposed values', () => {
    const onConfirm = vi.fn();
    render(
      <FundThesisConfirmationModal
        open
        changes={changes}
        firstPublication={false}
        busy={false}
        onCancel={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    expect(screen.getByRole('dialog', { name: /confirm policy changes/i })).toBeInTheDocument();
    expect(screen.getAllByText('Currently live')).toHaveLength(2);
    expect(screen.getByText('Fintech')).toBeInTheDocument();
    expect(screen.getAllByText('Proposed')).toHaveLength(2);
    expect(screen.getByText('Climate')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /deploy policy changes/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('cancels on Escape without confirming', () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <FundThesisConfirmationModal
        open
        changes={changes}
        firstPublication={false}
        busy={false}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
    );

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('explains first publication and focuses the manual confirmation', async () => {
    render(
      <FundThesisConfirmationModal
        open
        changes={[{
          key: 'mandateName',
          label: 'Mandate name',
          previous: 'No thesis currently deployed',
          proposed: 'Core mandate',
        }]}
        firstPublication
        busy={false}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByText('No thesis currently deployed')).toBeInTheDocument();
    expect(screen.getByText(/publishing your first fund thesis/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /deploy policy changes/i })).toHaveFocus();
    });
  });

  it('blocks both exits while a confirmed deployment is busy', () => {
    render(
      <FundThesisConfirmationModal
        open
        changes={changes}
        firstPublication={false}
        busy
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /deploying policy/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /go back/i })).toBeDisabled();
  });
});
