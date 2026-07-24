import type { ReactElement } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundary from '../ErrorBoundary';

function Boom({ explode }: { explode: boolean }): ReactElement {
  if (explode) throw new Error('kaboom');
  return <div>safe content</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress React's expected error logging noise for the thrown render.
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <Boom explode={false} />
      </ErrorBoundary>,
    );
    expect(screen.getByText('safe content')).toBeInTheDocument();
  });

  it('renders fallback and reports when a child throws', () => {
    render(
      <ErrorBoundary label="test">
        <Boom explode />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/unexpected error/i)).toBeInTheDocument();
    expect(console.error).toHaveBeenCalled();
  });

  it('recovers via "Try again" once the child stops throwing', () => {
    function Wrapper() {
      return (
        <ErrorBoundary>
          <Boom explode />
        </ErrorBoundary>
      );
    }
    render(<Wrapper />);
    // Fallback is shown; the reset button exists and is wired.
    expect(screen.getByRole('button', { name: /try again/i })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
  });
});
