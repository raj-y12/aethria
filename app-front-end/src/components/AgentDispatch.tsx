import { useState, useEffect, useRef, type Ref, type KeyboardEvent } from 'react';
import { railEditorial } from '../design-system/railEditorial';
import { productInteraction, productText } from '../design-system/productSystem';

interface AgentDispatchProps {
  input: string;
  setInput: (val: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  isBusy: boolean;
  message: string | null;
  /** Allow parent to clear the message (e.g. after a failed lookup) */
  onClearMessage?: () => void;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
  displayMode?: 'drawer' | 'embedded' | 'embeddedCompact';
}

function formatLookupMessage(msg: string): string {
  if (!msg) return '';
  const substitutions: Record<string, string> = {
    'Submitting lookup request...': 'Submitting lookup request…',
    'Lookup queued for': 'Queued for',
    'Searching sources for': 'Searching for',
    'Found': 'Found',
    'Running analyst review': 'Running analyst review…',
    'Lookup complete': 'Lookup complete.',
    'Could not submit': 'Could not submit. Retry.',
  };
  for (const [key, replacement] of Object.entries(substitutions)) {
    if (msg.includes(key)) return msg.replace(key, replacement);
  }
  return msg;
}

const PHASES = ['Scouting', 'Reviewing', 'Deciding'] as const;
type Phase = (typeof PHASES)[number];
type LookupPhase = Phase | null;

function phaseState(lookupPhase: LookupPhase, phase: Phase) {
  const isCurrentPhase = lookupPhase === phase;
  const isPast =
    !!lookupPhase &&
    ((lookupPhase === 'Reviewing' && phase === 'Scouting') ||
      (lookupPhase === 'Deciding' && (phase === 'Scouting' || phase === 'Reviewing')));
  return { isCurrentPhase, isPast };
}

/** Single-line pipeline phase — no progress bars (sidebar / drawer). */
function LookupPhaseLine({ lookupPhase, className = '' }: { lookupPhase: LookupPhase; className?: string }) {
  if (!lookupPhase) return null;
  return (
    <p className={`type-meta text-oxford/[0.28] ${className}`} aria-live="polite">
      {PHASES.map((phase, i) => {
        const { isCurrentPhase, isPast } = phaseState(lookupPhase, phase);
        return (
          <span key={phase}>
            {i > 0 ? <span className="text-oxford/[0.18]"> · </span> : null}
            <span
              className={
                isCurrentPhase ? 'text-oxford/55' : isPast ? 'text-oxford/[0.36]' : 'text-oxford/[0.22]'
              }
            >
              {phase}
            </span>
          </span>
        );
      })}
    </p>
  );
}

const runBtnCls =
  `group shrink-0 inline-flex min-h-[36px] items-center gap-phi-2 ${productInteraction.action}`;

function DispatchPanelBody({
  inputRef,
  input,
  setInput,
  onSubmit,
  onCancel,
  isBusy,
  lookupMessage,
  onClearMessage,
  lookupPhase,
  variant,
  onInputKeyDown,
}: {
  inputRef: Ref<HTMLInputElement>;
  input: string;
  setInput: (v: string) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  isBusy: boolean;
  lookupMessage: string | null;
  onClearMessage?: () => void;
  lookupPhase: LookupPhase;
  variant: 'embedded' | 'drawer';
  onInputKeyDown?: (e: KeyboardEvent<HTMLInputElement>) => void;
}) {
  const isActive = isBusy || !!lookupMessage;
  const embedded = variant === 'embedded';
  const [focused, setFocused] = useState(false);

  const inputCls = embedded
    ? 'min-w-0 flex-1 bg-transparent border-0 px-0 py-phi-2 font-medium font-sans text-[13px] leading-[1.5] text-oxford placeholder:text-oxford/[0.28] outline-none disabled:cursor-not-allowed'
    : 'min-w-0 flex-1 bg-transparent border-0 px-0 py-phi-3 font-sans font-medium text-[1rem] text-oxford placeholder:text-oxford/[0.28] outline-none disabled:cursor-not-allowed';

  const showStatusSlot = isBusy || !!lookupMessage;
  const statusSlotCls = embedded
    ? `mt-phi-2 grid content-start gap-phi-1${showStatusSlot ? ' min-h-[44px]' : ''}`
    : `mt-phi-3 grid content-start gap-phi-1${showStatusSlot ? ' min-h-[48px]' : ''}`;

  const statusLeft = (() => {
    if (lookupMessage) {
      const msgCls = embedded
        ? `${railEditorial.body} flex items-center gap-phi-2 min-w-0 flex-1 text-oxford/70`
        : 'type-meta text-oxford/55 flex items-center gap-phi-2 min-w-0 flex-1';
      return (
        <>
          <p className={msgCls}>
            {!embedded && <span className="h-1.5 w-1.5 shrink-0 bg-oxford/35 pulse-fast" aria-hidden />}
            <span className="truncate">{lookupMessage}</span>
          </p>
          {onClearMessage && !isBusy && (
            <button
              type="button"
              onClick={onClearMessage}
              className="shrink-0 type-meta text-oxford/25 hover:text-oxford/55 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
              aria-label="Dismiss message"
            >
              ×
            </button>
          )}
        </>
      );
    }
    if (!isBusy) return null;
    return <p className={embedded ? `${railEditorial.meta} text-oxford/[0.32]` : 'type-meta text-oxford/35'}>Dispatch active.</p>;
  })();

  return (
    <>
      <div
        className={`relative flex items-center gap-phi-3 border-b transition-colors duration-200 ${
          focused ? 'border-oxford/45' : isActive ? 'border-oxford/[0.22]' : 'border-oxford/[0.12]'
        }`}
        aria-label="Pipeline dispatch"
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onSubmit();
            onInputKeyDown?.(e);
          }}
          placeholder="Company name or URL"
          autoComplete="off"
          disabled={isBusy}
          className={inputCls}
        />
        <button
          type="button"
          onClick={isBusy ? onCancel : onSubmit}
          disabled={isBusy ? !onCancel : !input.trim()}
          className={isBusy ? `${runBtnCls} text-oxford/40 hover:text-oxford/70 disabled:opacity-100` : runBtnCls}
        >
          {isBusy ? (
            'Cancel'
          ) : (
            <>
              {embedded ? 'Run' : 'Run lookup'}
              <span className="transition-transform group-hover:translate-x-px">→</span>
            </>
          )}
        </button>
        {isBusy && !embedded && (
          <span className="absolute bottom-0 left-0 h-px w-full bg-oxford/30 pulse-fast" aria-hidden />
        )}
      </div>

      {showStatusSlot ? (
        <div className={statusSlotCls}>
          {statusLeft ? (
            <div className="flex min-w-0 flex-1 items-center gap-phi-2">{statusLeft}</div>
          ) : null}
          <LookupPhaseLine lookupPhase={isBusy ? lookupPhase : null} />
        </div>
      ) : null}
    </>
  );
}

export default function AgentDispatch({
  input,
  setInput,
  onSubmit,
  onCancel,
  isBusy,
  message,
  onClearMessage,
  lookupPhase,
  displayMode = 'drawer',
}: AgentDispatchProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const lookupMessage = message ? formatLookupMessage(message) : null;
  const hasStatus = !!lookupMessage;
  const isRunning = isBusy;
  const isDrawer = displayMode === 'drawer';
  const isCompactEmbedded = displayMode === 'embeddedCompact';
  const [expanded, setExpanded] = useState(displayMode === 'embedded');
  const isExpanded =
    displayMode === 'embedded' ? true : isDrawer ? expanded : expanded || isRunning;

  useEffect(() => {
    if (isExpanded && inputRef.current && displayMode !== 'embedded') inputRef.current.focus();
  }, [displayMode, isExpanded]);

  const showCompactShell = isCompactEmbedded && !isExpanded;
  const shellTone = isRunning ? 'Running' : hasStatus ? 'Status' : 'Ready';
  const shellBody = lookupMessage ?? 'Dispatch a company lookup.';

  return (
    <div className="w-full">
      {showCompactShell ? (
        <div className="flex min-w-0 items-center justify-between gap-phi-3 border border-oxford/[0.08] bg-paper px-phi-3 py-phi-3">
          <div className="min-w-0">
            <p className={`${railEditorial.meta} text-oxford/[0.68]`}>{shellTone}</p>
            <div className="mt-phi-1 flex min-w-0 items-start gap-phi-2">
              <p className={`${railEditorial.meta} min-w-0 flex-1 ${hasStatus ? 'text-oxford/[0.52]' : 'text-oxford/[0.32]'}`}>
                <span className="block truncate">{shellBody}</span>
              </p>
              {onClearMessage && hasStatus ? (
                <button
                  type="button"
                  onClick={onClearMessage}
                  className="shrink-0 type-meta text-oxford/25 hover:text-oxford/55 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
                  aria-label="Dismiss message"
                >
                  ×
                </button>
              ) : null}
            </div>
          </div>
          <button
            type="button"
            onClick={() => setExpanded(true)}
            className={runBtnCls}
          >
            Run
            <span className="transition-transform group-hover:translate-x-px">→</span>
          </button>
        </div>
      ) : null}

      {isDrawer && (
        <div className="w-full flex items-center gap-phi-3 px-phi-4 min-h-[44px] border-t border-oxford/[0.08]">
          <span className={`${productText.mutedLabel} shrink-0`}>Dispatch</span>
          <span
            className={`flex-1 h-px bg-oxford/[0.06] ${isRunning ? 'pulse-soft' : ''}`}
            aria-hidden
          />
          <span className="flex items-center gap-phi-2 shrink-0">
            {isRunning && (
              <span className="h-1.5 w-1.5 shrink-0 bg-oxford/40 pulse-fast" aria-hidden />
            )}
            <span
              className={`type-meta transition-colors ${isRunning ? 'text-oxford/55' : hasStatus ? 'text-oxford/40' : 'text-oxford/25'}`}
            >
              {isRunning ? 'Running' : hasStatus ? 'Status' : 'Ready'}
            </span>
          </span>
          <button
            type="button"
            onClick={() => setExpanded((p) => !p)}
            className={`${productInteraction.action} w-4 shrink-0 select-none text-center`}
            aria-expanded={isExpanded}
          >
            <span
              aria-hidden
              className={`inline-block leading-none transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
            >
              ›
            </span>
            <span className="sr-only">{isExpanded ? 'Close dispatch panel' : 'Open dispatch panel'}</span>
          </button>
        </div>
      )}

      {!showCompactShell && !isDrawer ? (
        <div className="min-w-0">
          {isCompactEmbedded && !isRunning ? (
            <div className="mb-phi-2 flex items-center justify-between gap-phi-3">
              <p className={`${railEditorial.meta} text-oxford/[0.36]`}>
                {hasStatus ? 'Latest dispatch status.' : 'Ready for a targeted lookup.'}
              </p>
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="type-meta text-oxford/[0.28] hover:text-oxford/55 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction"
              >
                Hide
              </button>
            </div>
          ) : null}
          <DispatchPanelBody
            inputRef={inputRef}
            input={input}
            setInput={setInput}
            onSubmit={onSubmit}
            onCancel={onCancel}
            isBusy={isBusy}
            lookupMessage={lookupMessage}
            onClearMessage={onClearMessage}
            lookupPhase={lookupPhase}
            variant="embedded"
            onInputKeyDown={(e) => {
              if (isCompactEmbedded && e.key === 'Escape' && !isRunning) setExpanded(false);
            }}
          />
        </div>
      ) : !showCompactShell ? (
        <div
          className={`grid ${isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
          style={{
            transition: 'grid-template-rows 200ms cubic-bezier(0.16,1,0.3,1), opacity 200ms cubic-bezier(0.16,1,0.3,1)',
          }}
        >
          <div className="overflow-hidden">
            <div className="px-phi-4 pt-phi-3 pb-phi-5">
              <DispatchPanelBody
                inputRef={inputRef}
                input={input}
                setInput={setInput}
                onSubmit={onSubmit}
                onCancel={onCancel}
                isBusy={isBusy}
                lookupMessage={lookupMessage}
                onClearMessage={onClearMessage}
                lookupPhase={lookupPhase}
                variant="drawer"
                onInputKeyDown={(e) => {
                  if (e.key === 'Escape' && !isBusy && !message) setExpanded(false);
                }}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
