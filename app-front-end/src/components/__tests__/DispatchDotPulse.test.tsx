// Vitest provides Node's filesystem APIs at runtime; the app's browser build has no Node typings.
// @ts-expect-error Node-only test helper.
import { readFileSync } from 'node:fs';
// @ts-expect-error Node-only test helper.
import { resolve } from 'node:path';
import { fireEvent, render } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DispatchDotPulse from '../DispatchDotPulse';

declare const process: { cwd(): string };

describe('DispatchDotPulse', () => {
  beforeEach(() => {
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      disconnect() {}
    });
  });

  it('keeps dot coordinates stable across animation iterations', () => {
    const { container } = render(<DispatchDotPulse active />);
    const dot = container.querySelector<HTMLElement>('.dot-grid-pulse');
    expect(dot).not.toBeNull();
    const before = `${dot!.style.left}:${dot!.style.top}`;
    fireEvent.animationIteration(dot!);
    expect(`${dot!.style.left}:${dot!.style.top}`).toBe(before);
  });

  it('does not attach a per-animation relocation handler', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/components/DispatchDotPulse.tsx'), 'utf8');
    expect(source).not.toContain('onAnimationIteration');
    expect(source).not.toContain('relocate(');
  });
});
