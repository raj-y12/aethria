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
        aria-live="assertive"
        className="aethria-error-boundary aethria-atmosphere page-transition-enter relative flex min-h-[100dvh] w-full items-center justify-center overflow-hidden bg-paper px-phi-4 py-phi-6 lg:px-phi-7"
      >
        <div className="grain" aria-hidden />
        <div className="grain" aria-hidden />
        <div className="focus-frame w-full max-w-4xl px-phi-5 py-phi-6 text-oxford sm:px-phi-7 sm:py-phi-7">
          <div className="flex flex-wrap items-center justify-between gap-phi-3 border-b border-oxford/[0.12] pb-phi-3">
            <div className="flex items-center gap-phi-2">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-escalation" aria-hidden />
              <p className="type-label-section m-0 text-oxford/65">System interruption</p>
            </div>
            <p className="type-meta m-0 text-oxford/45">
              {this.props.label ? this.props.label.toUpperCase() : 'WORKSPACE'} · RECOVERY AVAILABLE
            </p>
          </div>

          <div className="grid gap-phi-7 py-phi-7 lg:grid-cols-[minmax(0,1fr)_minmax(210px,0.42fr)] lg:items-end">
            <div>
              <p className="type-meta m-0 text-oxford/45">Unexpected render state / 01</p>
              <h2 className="mt-phi-3 max-w-[18ch] font-sans text-[clamp(2rem,4vw,3.6rem)] font-semibold leading-[0.98] tracking-[-0.055em] text-oxford">
                This view hit an unexpected error.
              </h2>
              <p className="mt-phi-4 max-w-[48ch] type-body-sm leading-relaxed text-oxford/65">
                The rest of the app is still running. Try the view again, or reload the session if the interruption persists.
              </p>
            </div>

            <div className="border-t border-oxford/[0.12] pt-phi-4 lg:border-l lg:border-t-0 lg:pl-phi-5 lg:pt-0">
              <p className="type-label-section m-0 text-oxford/45">Recovery options</p>
              <div className="mt-phi-3 flex flex-wrap items-center gap-phi-3 lg:flex-col lg:items-stretch">
            <span className="aethria-cta-frame">
              <button type="button" onClick={this.reset} className="aethria-cta type-action">
                Try again
              </button>
            </span>
            <button
              type="button"
              onClick={this.reload}
              className="min-h-[38px] border-0 border-b border-oxford/25 bg-transparent px-0 pb-0.5 text-left type-meta text-oxford/65 transition-colors hover:border-oxford/60 hover:text-oxford btn-interaction"
            >
              Reload
            </button>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-phi-3 border-t border-oxford/[0.12] pt-phi-3">
            <p className="type-meta m-0 text-oxford/45">The surrounding shell remains active.</p>
            <p className="type-meta m-0 tabular-nums text-oxford/45">STATUS / DEGRADED</p>
          </div>
        </div>
      </div>
    );
  }
}
