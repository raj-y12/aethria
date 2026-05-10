import { useState, useEffect, useRef, type Ref, type KeyboardEvent } from 'react';
import { railEditorial } from '../design-system/railEditorial';

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

function LookupPhaseStrip({
  lookupPhase,
  spacingClass,
  reserveHeight,
}: {
  lookupPhase: LookupPhase;
  spacingClass: string;
  reserveHeight: boolean;
}) {
  const track = (
    <>
      {PHASES.map((phase) => {
        const { isCurrentPhase, isPast } = phaseState(lookupPhase, phase);
        return (
          <div key={phase} className="flex-1 flex flex-col gap-phi-2">
            <div className="h-px w-full bg-oxford/[0.06] relative overflow-hidden">
              {(isCurrentPhase || isPast) && (
                <span
                  className={`absolute inset-0 h-full origin-left ${isPast ? 'bg-oxford/15' : 'bg-oxford/35'} ${isCurrentPhase ? 'pulse-fast' : ''}`}
                />
              )}
            </div>
            <span
              className={`type-meta transition-colors ${
                isCurrentPhase ? 'text-oxford/60' : isPast ? 'text-oxford/35' : 'text-oxford/22'
              }`}
            >
              {phase}
            </span>
          </div>
        );
      })}
    </>
  );

  if (reserveHeight) {
    return (
      <div
        className={`border-t border-oxford/[0.06] flex gap-phi-3 ${spacingClass} transition-opacity duration-200 ${
          lookupPhase ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        aria-hidden={!lookupPhase}
      >
        {track}
      </div>
    );
  }
  if (!lookupPhase) return null;
  return <div className={`border-t border-oxford/[0.06] flex gap-phi-3 ${spacingClass}`}>{track}</div>;
}

const runBtnCls =
  'group shrink-0 inline-flex items-center gap-phi-2 type-meta text-oxford/45 hover:text-oxford disabled:opacity-20 transition-colors btn-interaction';

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
    ? `w-full bg-transparent border-0 border-b ${focused ? 'border-oxford/38' : 'border-oxford/[0.10]'} px-0 py-phi-2 font-medium ${railEditorial.bodyMetrics} text-oxford placeholder:text-oxford/25 outline-none transition-colors duration-300 disabled:cursor-not-allowed`
    : `w-full bg-transparent border-0 border-b ${focused ? 'border-oxford/38' : 'border-oxford/[0.10]'} px-0 py-phi-3 font-sans font-medium text-[1rem] text-oxford placeholder:text-oxford/25 outline-none transition-colors duration-300 disabled:cursor-not-allowed`;

  const statusRowCls = embedded
    ? 'flex items-center justify-between gap-phi-3 mt-phi-1.5 min-[1100px]:mt-phi-2 min-h-[22px]'
    : 'flex items-center justify-between gap-phi-3 mt-phi-3 min-h-[28px]';

  const phaseSpacing = embedded
    ? 'mt-phi-2 pt-phi-1.5 min-[1100px]:mt-phi-3 min-[1100px]:pt-phi-2'
    : 'mt-phi-4 pt-phi-3';

  const statusLeft = (() => {
    if (lookupMessage) {
      const msgCls = embedded
        ? `${railEditorial.body} flex items-center gap-phi-2 min-w-0 flex-1`
        : 'type-meta text-oxford/55 flex items-center gap-phi-2 min-w-0 flex-1';
      return (
        <>
          <p className={msgCls}>
            {(embedded ? isActive : true) && (
              <span className="h-1.5 w-1.5 shrink-0 bg-oxford/35 pulse-fast" aria-hidden />
            )}
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
    if (embedded) {
      return (
        <p
          className={`${railEditorial.bodyMetrics} transition-colors ${
            isActive ? 'text-[rgba(var(--color-oxford-rgb),0.78)]' : 'text-[rgba(var(--color-oxford-rgb),0.35)]'
          }`}
        >
          {isBusy ? 'Pipeline running…' : focused ? 'Name, domain, or founder signal' : 'Company name or URL'}
        </p>
      );
    }
    if (!isBusy) {
      return <p className="type-meta text-oxford/25">Enter a name or URL to look up a company.</p>;
    }
    return null;
  })();

  return (
    <>
      <div className="relative">
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
        {isBusy && (
          <span className="absolute bottom-0 left-0 h-px w-full bg-oxford/30 pulse-fast" aria-hidden />
        )}
      </div>

      <div className={statusRowCls}>
        <div className="flex-1 min-w-0 flex items-center gap-phi-2">{statusLeft}</div>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!input.trim() || isBusy}
          className={runBtnCls}
        >
          {isBusy ? 'Running' : 'Run lookup'}
          <span className={`transition-transform ${isBusy ? 'pulse-fast' : 'group-hover:translate-x-px'}`}>
            {isBusy ? '·' : '→'}
          </span>
        </button>
      </div>

      <LookupPhaseStrip lookupPhase={lookupPhase} spacingClass={phaseSpacing} reserveHeight={embedded} />
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
          <span className="type-label-tab text-oxford/40 shrink-0">Dispatch</span>
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
            className="type-meta text-oxford/25 hover:text-oxford/50 transition-colors w-4 text-center shrink-0 select-none btn-interaction"
            aria-expanded={isExpanded}
          >
            {isExpanded ? '−' : '+'}
            <span className="sr-only">{isExpanded ? 'Close dispatch panel' : 'Open dispatch panel'}</span>
          </button>
        </div>
      )}

      {alwaysOpen ? (
        <div className="min-w-0">
          <p className={railEditorial.label}>Dispatch</p>
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
