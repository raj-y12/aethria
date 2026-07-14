import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import SettingsActionDialog from '../SettingsActionDialog';

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  });
});

function renderDialog(overrides: Partial<React.ComponentProps<typeof SettingsActionDialog>> = {}) {
  const props: React.ComponentProps<typeof SettingsActionDialog> = {
    open: true,
    title: 'Restore defaults?',
    description: 'Your live policy will stay unchanged.',
    confirmLabel: 'Restore defaults',
    onCancel: vi.fn(),
    onConfirm: vi.fn(),
    ...overrides,
  };
  const view = render(<SettingsActionDialog {...props} />);
  return { ...view, props };
}

describe('SettingsActionDialog', () => {
  it('styles the actions like the full-screen log-out takeover', () => {
    renderDialog();

    expect(screen.getByRole('button', { name: 'Restore defaults' })).toHaveClass('btn-aethria-solid');
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass('type-action');
  });

  it('moves focus into the dialog when it opens', async () => {
    renderDialog();

    const dialog = screen.getByRole('dialog', { name: 'Restore defaults?' });
    await waitFor(() => expect(dialog).toContainElement(document.activeElement as HTMLElement));
  });

  it('focuses the dialog fallback when it opens busy', async () => {
    renderDialog({ busy: true });

    const dialog = screen.getByRole('dialog', { name: 'Restore defaults?' });
    await waitFor(() => expect(dialog).toHaveFocus());

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(dialog).toHaveFocus();
  });

  it('moves focus to an enabled action when a busy dialog becomes ready', async () => {
    const { rerender, props } = renderDialog({ busy: true });
    const dialog = screen.getByRole('dialog', { name: 'Restore defaults?' });
    await waitFor(() => expect(dialog).toHaveFocus());

    rerender(<SettingsActionDialog {...props} busy={false} />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus());
  });

  it('keeps Tab and Shift+Tab inside the dialog', async () => {
    renderDialog();
    const cancel = screen.getByRole('button', { name: 'Cancel' });
    const confirm = screen.getByRole('button', { name: 'Restore defaults' });
    await waitFor(() => expect(cancel).toHaveFocus());

    cancel.focus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(confirm).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(cancel).toHaveFocus();
  });

  it('cancels on Escape unless an action is busy', () => {
    const onCancel = vi.fn();
    const { rerender } = renderDialog({ onCancel });

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);

    rerender(
      <SettingsActionDialog
        open
        title="Restore defaults?"
        description="Your live policy will stay unchanged."
        confirmLabel="Restore defaults"
        busy
        onCancel={onCancel}
        onConfirm={vi.fn()}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onConfirm from the primary action', () => {
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });

    fireEvent.click(screen.getByRole('button', { name: 'Restore defaults' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('restores focus to the trigger after closing', async () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'Open';
    document.body.appendChild(trigger);
    trigger.focus();
    const { rerender } = renderDialog();

    rerender(
      <SettingsActionDialog
        open={false}
        title="Restore defaults?"
        description="Your live policy will stay unchanged."
        confirmLabel="Restore defaults"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });
});
