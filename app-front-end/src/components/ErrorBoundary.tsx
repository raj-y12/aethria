import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Short context label for telemetry, e.g. "workspace" or "settings". */
  label?: string;
  /** Optional custom fallback. When omitted, the default editorial panel renders. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches render-time errors in its subtree so a single thrown component never
 * blanks the whole app. Reports to the console (the seam to wire real telemetry
 * into) and offers recovery without a full reload where possible.
 *
 * Place one at the root as a last resort and one around each major route so a
 * crash in a page keeps the surrounding app shell alive.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Centralized client-side error report. Wire to telemetry (Sentry/LogRocket/etc.) here.
    console.error(
      `[ErrorBoundary${this.props.label ? `:${this.props.label}` : ''}]`,
      error,
      info.componentStack,
    );
  }

  private reset = () => this.setState({ error: null });

  private reload = () => window.location.reload();

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    if (this.props.fallback) return this.props.fallback(error, this.reset);

    return (
      <div
        role="alert"
        className="flex min-h-[60dvh] w-full items-center justify-center px-phi-4 py-phi-6"
      >
        <div className="max-w-md text-center">
          <p className="type-meta text-oxford/60">Something went wrong</p>
          <h2 className="mt-phi-2 font-display text-[1.4rem] text-oxford">
            This view hit an unexpected error.
          </h2>
          <p className="mt-phi-3 type-meta text-oxford/60">
            The rest of the app is still running. Try again, or reload if it persists.
          </p>
          <div className="mt-phi-5 flex items-center justify-center gap-phi-3">
            <button
              type="button"
              onClick={this.reset}
              className="min-h-[36px] border border-oxford/[0.22] px-phi-4 type-meta text-oxford/70 hover:border-oxford/45 hover:text-oxford transition-colors btn-interaction"
            >
              Try again
            </button>
            <button
              type="button"
              onClick={this.reload}
              className="min-h-[36px] type-meta text-oxford/60 hover:text-oxford/70 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
            >
              Reload
            </button>
          </div>
        </div>
      </div>
    );
  }
}
