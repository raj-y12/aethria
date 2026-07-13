import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  getDecisionThresholdBoundaries,
} from '../../lib/decisionThresholds';
import {
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../../lib/fundConfiguration';
import DecisionThresholdsPanel, { scoreFromPointer } from '../DecisionThresholdsPanel';

function ThresholdHarness() {
  const [draft, setDraft] = useState(createDefaultFundConfiguration());
  const updateThreshold = <K extends keyof FundConfiguration['thresholds']>(
    key: K,
    value: FundConfiguration['thresholds'][K],
  ) => {
    setDraft((current) => ({
      ...current,
      thresholds: { ...current.thresholds, [key]: value },
    }));
  };

  return (
    <DecisionThresholdsPanel
      draft={draft}
      updateDraft={setDraft}
      updateThreshold={updateThreshold}
    />
  );
}

describe('scoreFromPointer', () => {
  it('converts pointer position to a clamped integer score', () => {
    expect(scoreFromPointer(150, 100, 200)).toBe(25);
    expect(scoreFromPointer(50, 100, 200)).toBe(0);
    expect(scoreFromPointer(350, 100, 200)).toBe(100);
    expect(scoreFromPointer(100, 100, 0)).toBe(0);
  });
});

describe('DecisionThresholdsPanel ladder', () => {
  it('offers exact numeric entry for each decision boundary with live valid ranges', () => {
    render(<ThresholdHarness />);
    const boundaries = getDecisionThresholdBoundaries(createDefaultFundConfiguration());

    const monitor = screen.getByRole('spinbutton', { name: 'Monitor starts at' });
    const invest = screen.getByRole('spinbutton', { name: 'Invest starts at' });
    const autoPass = screen.getByRole('spinbutton', { name: 'Auto-pass below' });

    expect(monitor).toHaveAttribute('min', '2');
    expect(monitor).toHaveAttribute('max', String(boundaries.monitorInvestBoundary - 1));
    expect(invest).toHaveAttribute('min', String(boundaries.passMonitorBoundary + 1));
    expect(invest).toHaveAttribute('max', '100');
    expect(autoPass).toHaveAttribute('min', '0');
    expect(autoPass).toHaveAttribute('max', String(boundaries.passMonitorBoundary - 1));
  });

  it('routes exact entry through the same boundary update as the visual control', () => {
    render(<ThresholdHarness />);
    const original = getDecisionThresholdBoundaries(createDefaultFundConfiguration());

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Monitor starts at' }), {
      target: { value: String(original.passMonitorBoundary + 1) },
    });

    expect(screen.getByRole('slider', { name: 'Monitor starts' })).toHaveAttribute(
      'aria-valuenow',
      String(original.passMonitorBoundary + 1),
    );
    expect(screen.getByRole('spinbutton', { name: 'Invest starts at' })).toHaveAttribute(
      'min',
      String(original.passMonitorBoundary + 2),
    );
  });

  it('explains visual, keyboard, and exact score entry', () => {
    render(<ThresholdHarness />);

    expect(screen.getByText('Drag a marker, use arrow keys, or enter an exact score.')).toBeInTheDocument();
  });

  it('exposes three named sliders with their valid ranges', () => {
    render(<ThresholdHarness />);
    const boundaries = getDecisionThresholdBoundaries(createDefaultFundConfiguration());

    expect(screen.getByRole('slider', { name: 'Auto-pass ceiling' })).toHaveAttribute(
      'aria-valuenow',
      String(boundaries.autoPassCeiling),
    );
    expect(screen.getByRole('slider', { name: 'Monitor starts' })).toHaveAttribute(
      'aria-valuemin',
      '2',
    );
    expect(screen.getByRole('slider', { name: 'Invest starts' })).toHaveAttribute(
      'aria-valuemax',
      '100',
    );
  });

  it('nudges a boundary with arrow keys without crossing the next boundary', () => {
    render(<ThresholdHarness />);
    const original = getDecisionThresholdBoundaries(createDefaultFundConfiguration());
    const monitor = screen.getByRole('slider', { name: 'Monitor starts' });

    fireEvent.keyDown(monitor, { key: 'ArrowRight' });

    expect(monitor).toHaveAttribute('aria-valuenow', String(original.passMonitorBoundary + 1));
    const displayedBoundary = Number(monitor.getAttribute('aria-valuenow'));
    expect(displayedBoundary).toBeLessThan(
      getDecisionThresholdBoundaries(createDefaultFundConfiguration()).monitorInvestBoundary,
    );
  });

  it('moves a boundary to its valid endpoint with Home and End', () => {
    render(<ThresholdHarness />);
    const autoPass = screen.getByRole('slider', { name: 'Auto-pass ceiling' });

    fireEvent.keyDown(autoPass, { key: 'Home' });
    expect(autoPass).toHaveAttribute('aria-valuenow', '0');

    fireEvent.keyDown(autoPass, { key: 'End' });
    const monitorStart = Number(
      screen.getByRole('slider', { name: 'Monitor starts' }).getAttribute('aria-valuenow'),
    );
    expect(autoPass).toHaveAttribute('aria-valuenow', String(monitorStart - 1));
  });
});
