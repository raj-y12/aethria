import { render, screen } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { useFocusTrap } from '../useFocusTrap';

function DisabledDialog() {
  const containerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(true, containerRef);

  return (
    <>
      <button type="button">Outside dialog</button>
      <div ref={containerRef} role="dialog" aria-label="Disabled dialog">
        <button type="button" disabled>Confirm</button>
        <button type="button" disabled>Cancel</button>
      </div>
    </>
  );
}

describe('useFocusTrap', () => {
  it('focuses the dialog container when every dialog control is disabled', () => {
    render(<DisabledDialog />);

    expect(screen.getByRole('dialog', { name: 'Disabled dialog' })).toHaveFocus();
  });

  it('keeps focus in the dialog for Tab and Shift+Tab when every control is disabled', () => {
    render(<DisabledDialog />);
    const dialog = screen.getByRole('dialog', { name: 'Disabled dialog' });

    dialog.tabIndex = -1;
    dialog.focus();

    const tab = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    expect(() => document.dispatchEvent(tab)).not.toThrow();
    expect(tab.defaultPrevented).toBe(true);
    expect(dialog).toHaveFocus();

    const shiftTab = new KeyboardEvent('keydown', {
      key: 'Tab',
      shiftKey: true,
      cancelable: true,
    });
    expect(() => document.dispatchEvent(shiftTab)).not.toThrow();
    expect(shiftTab.defaultPrevented).toBe(true);
    expect(dialog).toHaveFocus();
  });

  it('returns external Tab and Shift+Tab focus to the disabled dialog', () => {
    render(<DisabledDialog />);
    const outside = screen.getByRole('button', { name: 'Outside dialog' });
    const dialog = screen.getByRole('dialog', { name: 'Disabled dialog' });

    outside.focus();
    const tab = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    expect(() => document.dispatchEvent(tab)).not.toThrow();
    expect(tab.defaultPrevented).toBe(true);
    expect(dialog).toHaveFocus();

    outside.focus();
    const shiftTab = new KeyboardEvent('keydown', {
      key: 'Tab',
      shiftKey: true,
      cancelable: true,
    });
    expect(() => document.dispatchEvent(shiftTab)).not.toThrow();
    expect(shiftTab.defaultPrevented).toBe(true);
    expect(dialog).toHaveFocus();
  });
});
