import { useState, useEffect, useRef } from 'react';

interface AgentDispatchProps {
  input: string;
  setInput: (val: string) => void;
  onSubmit: () => void;
  isBusy: boolean;
  message: string | null;
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

export default function AgentDispatch({
  input,
  setInput,
  onSubmit,
  isBusy,
  message,
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
      {/* ── Status header ───────────────────────────────────────── */}
      <div
        className={`w-full flex items-center gap-phi-3 px-phi-4 ${alwaysOpen ? 'min-h-[36px]' : 'min-h-[44px] border-t border-oxford/[0.08]'}`}
      >
        <span className="type-meta uppercase tracking-[0.12em] text-oxford/40 group-hover/trigger:text-oxford/65 transition-colors shrink-0">
          Dispatch
        </span>

        {/* Rule — pulses when active */}
        <span
          className={`flex-1 h-px bg-oxford/[0.06] ${isActive ? 'pulse-soft' : ''}`}
          aria-hidden
        />

        {/* Status */}
        <span className="flex items-center gap-phi-2 shrink-0">
          {isActive && (
            <span
              className="h-1.5 w-1.5 shrink-0 bg-oxford/40 pulse-fast"
              aria-hidden
            />
          )}
          <span className={`type-meta uppercase tracking-[0.12em] transition-colors ${isActive ? 'text-oxford/55' : 'text-oxford/25'}`}>
            {isBusy ? 'Running' : lookupMessage ? 'Active' : 'Ready'}
          </span>
        </span>

        {!alwaysOpen && (
          <button
            type="button"
            onClick={() => setExpanded((p) => !p)}
            className="type-meta text-oxford/25 hover:text-oxford/50 transition-colors w-4 text-center shrink-0 select-none btn-interaction"
            aria-expanded={isExpanded}
          >
            {isExpanded ? '−' : '+'}
            <span className="sr-only">{isExpanded ? 'Close dispatch panel' : 'Open dispatch panel'}</span>
          </button>
        )}
      </div>

      {/* ── Panel ────────────────────────────────────────────────── */}
      <div
        className={`grid transition-[grid-template-rows,opacity] duration-300 ease-smooth ${
          isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
        }`}
      >
        <div className="overflow-hidden">
          <div className={`px-phi-4 ${alwaysOpen ? 'pt-phi-1 pb-phi-3' : 'pt-phi-3 pb-phi-5'}`}>

            {/* Input */}
            <div className="relative">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSubmit();
                  if (e.key === 'Escape' && !alwaysOpen && !isBusy && !message) setExpanded(false);
                }}
                placeholder="Company name or URL"
                autoComplete="off"
                disabled={isBusy}
                className={`w-full bg-transparent border-0 border-b border-oxford/[0.10] px-0 font-sans font-medium text-oxford placeholder:text-oxford/25 outline-none focus:border-oxford/30 transition-colors duration-300 disabled:cursor-not-allowed ${alwaysOpen ? 'py-phi-2 text-[0.95rem]' : 'py-phi-3 text-[1rem]'}`}
              />
              {/* Animated underline while running */}
              {isBusy && (
                <span
                  className="absolute bottom-0 left-0 h-px w-full bg-oxford/30 pulse-fast"
                  aria-hidden
                />
              )}
            </div>

            {/* Message + action row */}
            <div className={`flex items-center justify-between gap-phi-3 ${alwaysOpen ? 'mt-phi-2 min-h-[22px]' : 'mt-phi-3 min-h-[28px]'}`}>
              <div className="flex-1 min-w-0">
                {lookupMessage ? (
                  <p className="type-meta text-oxford/55 flex items-center gap-phi-2 min-w-0">
                    <span
                      className="h-1.5 w-1.5 shrink-0 bg-oxford/35 pulse-fast"
                      aria-hidden
                    />
                    <span className="truncate">{lookupMessage}</span>
                  </p>
                ) : !isBusy ? (
                  <p className="type-meta text-oxford/25">
                    Enter a name or URL to look up a company.
                  </p>
                ) : null}
              </div>

              {!isBusy && (
                <button
                  type="button"
                  onClick={onSubmit}
                  disabled={!input.trim()}
                  className="group shrink-0 inline-flex items-center gap-phi-2 type-meta uppercase tracking-[0.12em] text-oxford/45 hover:text-oxford disabled:opacity-20 transition-colors btn-interaction"
                >
                  Run
                  <span className="transition-transform group-hover:translate-x-px">→</span>
                </button>
              )}
            </div>

            {/* Phase tracker */}
            {lookupPhase && (
              <div className={`border-t border-oxford/[0.06] flex gap-phi-3 ${alwaysOpen ? 'mt-phi-3 pt-phi-2' : 'mt-phi-4 pt-phi-3'}`}>
                {PHASES.map((phase) => {
                  const isCurrentPhase = lookupPhase === phase;
                  const isPast =
                    (lookupPhase === 'Reviewing' && phase === 'Scouting') ||
                    (lookupPhase === 'Deciding' && (phase === 'Scouting' || phase === 'Reviewing'));

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
                        className={`type-meta uppercase tracking-[0.12em] transition-colors ${
                          isCurrentPhase
                            ? 'text-oxford/60'
                            : isPast
                            ? 'text-oxford/30'
                            : 'text-oxford/18'
                        }`}
                      >
                        {phase}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
