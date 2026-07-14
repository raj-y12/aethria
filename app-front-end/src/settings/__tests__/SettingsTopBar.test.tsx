import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SettingsTopBar, { type SettingsStatusTone } from '../SettingsTopBar';

vi.mock('../../hooks', () => ({ usePrefersReducedMotion: () => true }));

function renderTopBar({
  message,
  tone,
  saving = false,
  live = false,
  canUndo = false,
}: {
  message: string;
  tone: SettingsStatusTone;
  saving?: boolean;
  live?: boolean;
  canUndo?: boolean;
}) {
  render(
    <SettingsTopBar
      live={live}
      saving={saving}
      message={message}
      tone={tone}
      canUndo={canUndo}
      onBack={vi.fn()}
      onRestoreDefaults={vi.fn()}
      onUndo={vi.fn()}
      onDeploy={vi.fn()}
      actionLabel={saving ? 'Deploying…' : 'Deploy changes'}
    />,
  );
}

describe('SettingsTopBar deployment feedback', () => {
  it.each([
    ['Live', 'live'],
    ['Draft changes', 'draft'],
    ['Deploying…', 'progress'],
    ['Scoring weights must total 100', 'error'],
    ['Deployed successfully', 'success'],
  ] as const)('keeps the %s state visible', (message, tone) => {
    renderTopBar({ message, tone, saving: tone === 'progress', live: tone === 'live' });
    const status = screen.getByRole(tone === 'error' ? 'alert' : 'status');
    expect(status).toHaveTextContent(message);
    expect(status).toHaveClass('!text-xs');
  });

  it('keeps restored-default feedback and Undo together', () => {
    renderTopBar({ message: 'Defaults restored', tone: 'restored', canUndo: true });
    expect(screen.getByText('Defaults restored')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Undo' })).toBeVisible();
  });

  it('sizes the top-bar actions to the log-out button scale', () => {
    renderTopBar({ message: 'Defaults restored', tone: 'restored', canUndo: true });

    // Buttons use the canonical mono action scale (like the log-out modal), not
    // the 12px override.
    for (const name of ['Aethria', 'Restore defaults', 'Undo']) {
      const button = screen.getByRole('button', { name });
      expect(button).toHaveClass('type-action');
      expect(button).not.toHaveClass('!text-xs');
    }
  });

  it('uses an alert for deployment errors and keeps Deploy dominant', () => {
    renderTopBar({ message: 'Memo output is invalid', tone: 'error' });
    expect(screen.getByRole('alert')).toHaveTextContent('Memo output is invalid');
    const deploy = screen.getByRole('button', { name: 'Deploy changes' });
    expect(deploy).toHaveClass('btn-aethria-solid');
    expect(deploy).not.toHaveClass('min-h-11');
  });
});
