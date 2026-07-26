import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import SettingsMobileNav from '../SettingsMobileNav';

describe('SettingsMobileNav', () => {
  it('renders the shared persistence groups in a native select', () => {
    render(
      <SettingsMobileNav
        activeSection="thesis"
        attentionSection={null}
        onSelect={() => undefined}
      />,
    );

    expect(screen.getByRole('combobox', { name: 'Settings section' })).toBeInstanceOf(HTMLSelectElement);
    expect(screen.getByRole('group', { name: 'Fund thesis — publishes a thesis version' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Decision policy — publishes a policy version' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Workspace runtime — saves immediately' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'System — read-only' })).toBeInTheDocument();
  });

  it('selects the requested settings section', () => {
    const onSelect = vi.fn();
    render(
      <SettingsMobileNav
        activeSection="thesis"
        attentionSection={null}
        onSelect={onSelect}
      />,
    );

    fireEvent.change(screen.getByRole('combobox', { name: 'Settings section' }), {
      target: { value: 'budget' },
    });

    expect(onSelect).toHaveBeenCalledWith('budget');
  });

  it('adds a visible suffix to the section that needs attention', () => {
    render(
      <SettingsMobileNav
        activeSection="thesis"
        attentionSection="thresholds"
        onSelect={() => undefined}
      />,
    );

    expect(screen.getByRole('option', { name: 'Thresholds — Needs attention' })).toBeInTheDocument();
  });
});
