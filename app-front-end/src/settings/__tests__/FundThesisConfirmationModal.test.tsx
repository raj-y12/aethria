import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import FundThesisConfirmationModal from '../FundThesisConfirmationModal';

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

    expect(screen.getByRole('dialog', { name: /confirm fund thesis change/i })).toBeInTheDocument();
    expect(screen.getByText('Currently live')).toBeInTheDocument();
    expect(screen.getByText('Fintech')).toBeInTheDocument();
    expect(screen.getByText('Proposed')).toBeInTheDocument();
    expect(screen.getByText('Climate')).toBeInTheDocument();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /yes, update fund thesis/i }));
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
      expect(screen.getByRole('button', { name: /yes, update fund thesis/i })).toHaveFocus();
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

    expect(screen.getByRole('button', { name: /updating fund thesis/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /go back/i })).toBeDisabled();
  });
});
