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
    expect(screen.getByRole(tone === 'error' ? 'alert' : 'status')).toHaveTextContent(message);
  });

  it('keeps restored-default feedback and Undo together', () => {
    renderTopBar({ message: 'Defaults restored', tone: 'restored', canUndo: true });
    expect(screen.getByText('Defaults restored')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Undo' })).toBeVisible();
  });

  it('uses an alert for deployment errors and keeps Deploy dominant', () => {
    renderTopBar({ message: 'Memo output is invalid', tone: 'error' });
    expect(screen.getByRole('alert')).toHaveTextContent('Memo output is invalid');
    expect(screen.getByRole('button', { name: 'Deploy changes' })).toHaveClass('btn-aethria-solid', 'min-h-11');
  });
});
