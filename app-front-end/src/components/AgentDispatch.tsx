import { useState, useEffect, useRef, type Ref, type KeyboardEvent } from 'react';
import { railEditorial } from '../design-system/railEditorial';
import { productInteraction, productText } from '../design-system/productSystem';

interface AgentDispatchProps {
  input: string;
  setInput: (val: string) => void;
  onSubmit: () => void;
  isBusy: boolean;
  message: string | null;
  /** Allow parent to clear the message (e.g. after a failed lookup) */
  onClearMessage?: () => void;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
  alwaysOpen?: boolean;
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
    <p className={`type-meta text-oxford/28 ${className}`} aria-live="polite">
      {PHASES.map((phase, i) => {
        const { isCurrentPhase, isPast } = phaseState(lookupPhase, phase);
        return (
          <span key={phase}>
            {i > 0 ? <span className="text-oxford/18"> · </span> : null}
            <span
              className={
                isCurrentPhase ? 'text-oxford/55' : isPast ? 'text-oxford/36' : 'text-oxford/22'
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
    ? 'min-w-0 flex-1 bg-transparent border-0 px-0 py-phi-2 font-medium font-sans text-[13px] leading-[1.5] text-oxford placeholder:text-oxford/28 outline-none disabled:cursor-not-allowed'
    : 'min-w-0 flex-1 bg-transparent border-0 px-0 py-phi-3 font-sans font-medium text-[1rem] text-oxford placeholder:text-oxford/28 outline-none disabled:cursor-not-allowed';

  const statusRowCls = embedded
    ? 'mt-phi-2 flex min-h-0 items-start justify-between gap-phi-3'
    : 'mt-phi-3 flex min-h-0 items-start justify-between gap-phi-3';

  const showStatusRow = Boolean(lookupMessage) || (!embedded && !isBusy);

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
    if (!embedded && !isBusy) {
      return <p className="type-meta text-oxford/30">Name or URL, then Enter.</p>;
    }
    return null;
  })();

  return (
    <>
      <div
        className={`relative flex items-center gap-phi-3 border-b transition-colors duration-200 ${
          focused ? 'border-oxford/45' : isActive ? 'border-oxford/22' : 'border-oxford/[0.12]'
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
          onClick={onSubmit}
          disabled={!input.trim() || isBusy}
          className={runBtnCls}
        >
          {isBusy ? (
            <>
              Running
              <span className="text-oxford/35 tabular-nums">…</span>
            </>
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

      {showStatusRow && (
        <div className={statusRowCls}>
          <div className="flex min-w-0 flex-1 items-center gap-phi-2">{statusLeft}</div>
        </div>
      )}

      <LookupPhaseLine
        lookupPhase={isBusy ? lookupPhase : null}
        className={embedded ? 'mt-phi-2' : 'mt-phi-3'}
      />
    </>
  );
}

export default function AgentDispatch({
  input,
  setInput,
  onSubmit,
  isBusy,
  message,
  onClearMessage,
  lookupPhase,
  alwaysOpen = false,
}: AgentDispatchProps) {
  const [expanded, setExpanded] = useState(alwaysOpen);
  const isExpanded = alwaysOpen || expanded;
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isExpanded && inputRef.current && !alwaysOpen) inputRef.current.focus();
  }, [alwaysOpen, isExpanded]);

  useEffect(() => {
    if (alwaysOpen || isBusy || message) setExpanded(true);
  }, [alwaysOpen, isBusy, message]);

  const lookupMessage = message ? formatLookupMessage(message) : null;
  const isActive = isBusy || !!lookupMessage;

  return (
    <div className="w-full">
      {!alwaysOpen && (
        <div className="w-full flex items-center gap-phi-3 px-phi-4 min-h-[44px] border-t border-oxford/[0.08]">
          <span className={`${productText.mutedLabel} shrink-0`}>Dispatch</span>
          <span
            className={`flex-1 h-px bg-oxford/[0.06] ${isActive ? 'pulse-soft' : ''}`}
            aria-hidden
          />
          <span className="flex items-center gap-phi-2 shrink-0">
            {isActive && (
              <span className="h-1.5 w-1.5 shrink-0 bg-oxford/40 pulse-fast" aria-hidden />
            )}
            <span
              className={`type-meta transition-colors ${isActive ? 'text-oxford/55' : 'text-oxford/25'}`}
            >
              {isBusy ? 'Running' : lookupMessage ? 'Active' : 'Ready'}
            </span>
          </span>
          <button
            type="button"
            onClick={() => setExpanded((p) => !p)}
            className={`${productInteraction.action} w-4 shrink-0 select-none text-center`}
            aria-expanded={isExpanded}
          >
            {isExpanded ? '−' : '+'}
            <span className="sr-only">{isExpanded ? 'Close dispatch panel' : 'Open dispatch panel'}</span>
          </button>
        </div>
      )}

      {alwaysOpen ? (
        <div className="min-w-0">
          <DispatchPanelBody
            inputRef={inputRef}
            input={input}
            setInput={setInput}
            onSubmit={onSubmit}
            isBusy={isBusy}
            lookupMessage={lookupMessage}
            onClearMessage={onClearMessage}
            lookupPhase={lookupPhase}
            variant="embedded"
          />
        </div>
      ) : (
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
      )}
    </div>
  );
}
