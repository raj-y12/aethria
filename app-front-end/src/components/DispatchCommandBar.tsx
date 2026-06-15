import { useEffect, useRef, useState, type ReactNode } from 'react';
import AgentDispatch from './AgentDispatch';
import CandidatePicker from './CandidatePicker';
import Reveal from './Reveal';
import { useFocusTrap } from '../hooks';
import type { LookupCandidate } from '../api/startups';

export interface LookupProgress {
  query: string;
  name: string | null;
  sector: string | null;
  /** Company identity confirmed (single match / candidate picked / lookup queued). */
  resolved: boolean;
  found: boolean;
  reviewed: boolean;
}

export interface LookupChip {
  id: string;
  label: string;
  status: 'scouting' | 'reviewing' | 'decided';
  active: boolean;
}

export interface LookupFailure {
  query: string;
  message: string;
}

interface DispatchCommandBarProps {
  open: boolean;
  onClose: () => void;
  input: string;
  setInput: (v: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  isBusy: boolean;
  message: string | null;
  onClearMessage?: () => void;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
  /** In-flight lookup, drives progressive reveal. Null until a lookup is queued. */
  progress?: LookupProgress | null;
  /** Result overview (LookupResultSnapshot) shown once the lookup has a decision. */
  result?: ReactNode;
  /** Unresolved lookup (company not found / ambiguous) — drives the failure view. */
  failure?: LookupFailure | null;
  /** Leave the failure view back to a fresh compose surface ("Try again"). */
  onRetry?: () => void;
  /** Tracked lookups (active + backgrounded) shown as a focusable chip stack. */
  chips?: LookupChip[];
  onFocusChip?: (id: string) => void;
  candidates?: LookupCandidate[];
  /** Resolver found no clear match — prompt for a website inside the stages screen. */
  needsWebsite?: boolean;
  onPickCandidate?: (candidate: LookupCandidate) => void;
  onRefineWebsite?: (websiteHint: string) => void;
}

type StepState = 'done' | 'active' | 'pending';

function ProgressSteps({ progress }: { progress: LookupProgress }) {
  const steps: { label: string; state: StepState }[] = [
    { label: 'Identify', state: progress.resolved ? 'done' : 'active' },
    {
      label: 'Discover',
      state: progress.found ? 'done' : progress.resolved ? 'active' : 'pending',
    },
    { label: 'Review', state: progress.reviewed ? 'done' : progress.found ? 'active' : 'pending' },
    { label: 'Decide', state: progress.reviewed ? 'active' : 'pending' },
  ];
  return (
    <div className="flex items-center justify-center gap-phi-2" aria-label="Analysis progress">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center gap-phi-2">
          {i > 0 ? <span className="h-px w-6 bg-oxford/15" aria-hidden /> : null}
          <span className="inline-flex items-center gap-phi-2">
            <span
              className={`h-1.5 w-1.5 shrink-0 rounded-none ${
                step.state === 'done'
                  ? 'bg-oxford'
                  : step.state === 'active'
                    ? 'bg-oxford signal-dot-breathe'
                    : 'bg-oxford/20'
              }`}
              aria-hidden
            />
            <span
              className={`font-mono text-[11px] uppercase tracking-[0.12em] ${
                step.state === 'done'
                  ? 'text-oxford/70'
                  : step.state === 'active'
                    ? 'text-oxford'
                    : 'text-oxford/30'
              }`}
            >
              {step.label}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

type DispatchFooterAction = { label: string; onClick: () => void };

function DispatchFooterBar({ actions }: { actions: DispatchFooterAction[] }) {
  return (
    <div className="mt-phi-7 flex flex-wrap items-center justify-center gap-x-1 gap-y-1">
      {actions.map((action, index) => (
        <span key={action.label} className="inline-flex items-center">
          {index > 0 ? (
            <span className="type-meta px-1 text-oxford/20" aria-hidden>
              ·
            </span>
          ) : null}
          <button
            type="button"
            onClick={action.onClick}
            className="type-meta border-b border-oxford/10 px-1 pb-0.5 uppercase tracking-[0.12em] text-oxford/30 transition-colors hover:text-oxford/50 btn-interaction cursor-pointer"
          >
            {action.label}
          </button>
        </span>
      ))}
    </div>
  );
}

/**
 * ⌘K dispatch — full-screen takeover styled to match the front door (Today).
 * Chrome enter/exit (sidebar slide) is owned by AppFrame; content uses Reveal.
 */
export default function DispatchCommandBar({
  open,
  onClose,
  input,
  setInput,
  onSubmit,
  onCancel,
  isBusy,
  message,
  progress,
  result,
  failure,
  onRetry,
  chips = [],
  onFocusChip,
  candidates,
  needsWebsite = false,
  onPickCandidate,
  onRefineWebsite,
}: DispatchCommandBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  useFocusTrap(open, containerRef);
  const [compose, setCompose] = useState(false);
  useEffect(() => {
    if (!open) setCompose(false);
  }, [open]);

  const view: 'result' | 'failure' | 'progress' | 'compose' = compose
    ? 'compose'
    : result
      ? 'result'
      : failure
        ? 'failure'
        : progress
          ? 'progress'
          : 'compose';

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open || view !== 'compose') return;
    const id = window.setTimeout(() => {
      containerRef.current?.querySelector('input')?.focus();
    }, 550);
    return () => window.clearTimeout(id);
  }, [open, view]);

  const handleSubmit = () => {
    onSubmit();
    setCompose(false);
  };

  // "Try again" from the failure view: clear the failure and reopen compose.
  const handleRetry = () => {
    onRetry?.();
    setCompose(true);
  };

  // While the identity is still being confirmed (resolving / disambiguation),
  // the stages screen leads with "Confirm Company" rather than "Analyzing".
  const confirming = view === 'progress' && progress != null && !progress.resolved;
  const eyebrow =
    view === 'result'
      ? 'Dispatch Complete'
      : view === 'failure'
        ? 'Not Found'
        : view === 'progress'
          ? confirming
            ? 'Confirm Company'
            : 'Analyzing'
          : 'Dispatch';
  const title =
    view === 'result'
      ? 'Here’s what we found'
      : view === 'failure'
        ? failure!.query
        : view === 'progress'
          ? progress!.name || progress!.query
          : 'Look up a company';
  const lookupRunning = isBusy || Boolean(progress);
  const footerActions: DispatchFooterAction[] =
    view === 'result'
      ? [
          { label: 'Back', onClick: () => setCompose(true) },
          { label: 'Exit', onClick: onClose },
        ]
      : view === 'failure'
        ? [
            { label: 'Try again', onClick: handleRetry },
            { label: 'Exit', onClick: onClose },
          ]
        : view === 'progress'
          ? [
              { label: 'Back', onClick: () => setCompose(true) },
              ...(onCancel ? [{ label: 'Cancel', onClick: onCancel }] : []),
              { label: 'Exit', onClick: onClose },
            ]
          : [
              ...(chips.length >= 1 ? [{ label: 'Back', onClick: () => setCompose(false) }] : []),
              ...(lookupRunning && onCancel
                ? [{ label: 'Cancel', onClick: onCancel }]
                : [{ label: 'Exit', onClick: onClose }]),
            ];
  const showChips = chips.length >= 2 || (view === 'compose' && chips.length >= 1);

  if (!open) return null;

  return (
    <div
      ref={containerRef}
      className="paper-dot-grid absolute inset-0 z-20 flex min-h-0 flex-col overflow-y-auto overscroll-contain bg-paper"
      role="dialog"
      aria-modal="true"
      aria-label="Look up a company"
    >
      <div className="flex min-h-full w-full flex-1 flex-col items-center justify-center px-phi-6 py-phi-7">
        {showChips ? (
          <Reveal delay={0.02} y={-6} className="mb-phi-7 flex flex-wrap items-center justify-center gap-phi-2">
            {chips.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  onFocusChip?.(c.id);
                  setCompose(false);
                }}
                aria-pressed={c.active}
                className={`inline-flex items-center gap-phi-2 border px-phi-3 py-phi-1 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors btn-interaction ${
                  c.active
                    ? 'border-oxford/30 bg-oxford/[0.06] text-oxford'
                    : 'border-oxford/[0.12] text-oxford/45 hover:border-oxford/25 hover:text-oxford/70'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-none ${
                    c.status === 'decided'
                      ? 'bg-oxford'
                      : c.status === 'reviewing'
                        ? 'bg-oxford signal-dot-breathe'
                        : 'bg-oxford/30 signal-dot-breathe'
                  }`}
                  aria-hidden
                />
                <span className="max-w-[14ch] truncate">{c.label}</span>
                {c.status === 'decided' ? <span className="text-oxford/40" aria-hidden>✓</span> : null}
              </button>
            ))}
          </Reveal>
        ) : null}

        <div key={view} className="flex w-full flex-col items-center">
          <Reveal delay={0.1}>
            <p className="type-meta mb-phi-3 uppercase tracking-[0.16em] text-oxford/40">{eyebrow}</p>
          </Reveal>

          <Reveal delay={0.16} y={12}>
            <h1
              className={`type-display m-0 text-center text-[clamp(28px,4vw,52px)] font-medium leading-[1.1] text-oxford ${
                view === 'result' ? 'max-w-none whitespace-nowrap' : 'max-w-[15ch]'
              }`}
            >
              {title}
            </h1>
          </Reveal>

          {view === 'result' ? (
            <Reveal delay={0.24} className="mt-phi-6 flex w-full max-w-xl flex-col items-center">
              {result}
            </Reveal>
          ) : view === 'failure' ? (
            <Reveal delay={0.24} className="mt-phi-6 flex w-full max-w-md flex-col items-center gap-phi-5">
              <article
                className="w-full border border-solid border-oxford/10 bg-paper px-phi-5 py-phi-5"
                aria-label={`Lookup could not resolve ${failure!.query}`}
              >
                <div className="mb-phi-3 flex items-baseline justify-between gap-phi-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.11em] text-oxford/40">Result</p>
                  <p className="text-right font-mono text-[10px] uppercase tracking-[0.1em] text-oxford/35">
                    Unresolved
                  </p>
                </div>
                <h3 className="font-sans text-xl font-semibold leading-tight tracking-tight text-oxford sm:text-2xl">
                  No confirmed match
                </h3>
                <p className="mt-phi-3 font-sans text-[15px] leading-[1.6] text-oxford/58">
                  {failure!.message}
                </p>
                <button
                  type="button"
                  onClick={handleRetry}
                  className="mt-phi-4 w-full border border-solid border-oxford/12 bg-oxford px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.12em] text-paper transition-opacity hover:opacity-90"
                >
                  Try another lookup
                </button>
              </article>
            </Reveal>
          ) : view === 'progress' ? (
            <Reveal delay={0.24} className="mt-phi-3 flex flex-col items-center gap-phi-5">
              {progress!.sector ? (
                <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-oxford/40">
                  {progress!.sector}
                </p>
              ) : null}
              <ProgressSteps progress={progress!} />
              {message ? (
                <p className="type-body max-w-[40ch] text-center text-oxford/45" aria-live="polite">
                  {message}
                </p>
              ) : null}
              {(candidates && candidates.length > 0) || needsWebsite ? (
                onPickCandidate && onRefineWebsite ? (
                  <div className="w-full max-w-md text-left">
                    <CandidatePicker
                      candidates={candidates ?? []}
                      onPick={onPickCandidate}
                      onRefine={onRefineWebsite}
                      busy={isBusy}
                      heading={
                        candidates && candidates.length > 0
                          ? undefined
                          : 'No exact match — add the company website to pin the right one.'
                      }
                    />
                  </div>
                ) : null
              ) : null}
            </Reveal>
          ) : (
            <>
              <Reveal delay={0.24} className="mt-phi-3">
                <p className="type-body mb-phi-8 max-w-[34ch] text-center text-oxford/50">
                  Search any company against your active mandate and it lands in the queue.
                </p>
              </Reveal>
              <Reveal delay={0.32} className="flex w-full max-w-md flex-col items-center gap-phi-4">
                <div className="w-full">
                  <AgentDispatch
                    input={input}
                    setInput={setInput}
                    onSubmit={handleSubmit}
                    onCancel={onCancel}
                    isBusy={isBusy}
                    message={null}
                    lookupPhase={null}
                    displayMode="embedded"
                  />
                </div>
              </Reveal>
            </>
          )}
        </div>

        <Reveal delay={0.42}>
          <DispatchFooterBar actions={footerActions} />
        </Reveal>
      </div>
    </div>
  );
}
