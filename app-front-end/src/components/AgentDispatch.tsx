import { useState, useEffect, useRef } from 'react';

interface AgentDispatchProps {
  input: string;
  setInput: (val: string) => void;
  onSubmit: () => void;
  isBusy: boolean;
  message: string | null;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
}

function formatLookupMessage(msg: string): string {
  if (!msg) return '';

  const substitutions: Record<string, string> = {
    'Submitting lookup request...': 'Submitting lookup request...',
    'Lookup queued for': 'Lookup queued for',
    'Searching sources for': 'Searching sources for',
    'Found': 'Found',
    'Running analyst review': 'Running analyst review',
    'Lookup complete': 'Lookup complete.',
    'Could not submit': 'Could not submit lookup. Retry.',
  };

  for (const [key, replacement] of Object.entries(substitutions)) {
    if (msg.includes(key)) return msg.replace(key, replacement);
  }

  return msg;
}

export default function AgentDispatch({
  input,
  setInput,
  onSubmit,
  isBusy,
  message,
  lookupPhase,
}: AgentDispatchProps) {
  const [expanded, setExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (expanded && inputRef.current) {
      inputRef.current.focus();
    }
  }, [expanded]);

  // Auto-expand if busy/has message
  useEffect(() => {
    if (isBusy || message) setExpanded(true);
  }, [isBusy, message]);

  const lookupMessage = message ? formatLookupMessage(message) : null;

  return (
    <div className="relative w-full group">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="grid w-full min-h-[44px] grid-cols-[1fr_auto] items-center gap-phi-2 border-t border-oxford/[0.08] py-phi-2 text-left btn-interaction group/trigger"
        aria-expanded={expanded}
      >
        <span className="type-meta text-oxford/58 group-hover/trigger:text-oxford/82 transition-colors">
          Dispatch
        </span>
        <span
          className={`type-meta text-oxford/35 group-hover/trigger:text-oxford/55 transition-transform duration-300 ease-smooth ${expanded ? 'rotate-180' : 'rotate-0'
            }`}
          aria-hidden="true"
        >
          v
        </span>
        <span className="sr-only">
          {expanded ? 'Close dispatch panel' : 'Open dispatch panel'}
        </span>
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity] duration-300 ease-smooth ${expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
          }`}
      >
        <div className="overflow-hidden">
          <div className="px-phi-1 pb-phi-4 pt-phi-3">
            <div className="mb-phi-3 flex justify-end">
              <span className="type-meta text-oxford/45">
                {isBusy ? 'Running' : lookupMessage ? 'Active' : 'Ready'}
              </span>
            </div>

            <div className="relative pb-phi-1">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSubmit();
                  if (e.key === 'Escape' && !isBusy && !message) setExpanded(false);
                }}
                placeholder="Company name or URL"
                autoComplete="off"
                disabled={isBusy}
                className="w-full bg-transparent border-0 border-b border-oxford/10 px-0 py-2.5 font-sans text-[clamp(1rem,1.8vw,1.25rem)] font-medium text-oxford placeholder:text-oxford/22 outline-none focus:border-oxford/30 transition-colors duration-300"
              />
              {isBusy && (
                <span
                  className="absolute bottom-0 left-0 h-[1px] w-full bg-oxford/40"
                  style={{ animation: 'aethria-pulse 1.5s infinite' }}
                />
              )}
            </div>

            <div className="mt-phi-3 grid grid-cols-[minmax(0,1fr)_auto] items-start gap-phi-3">
              <div className="flex flex-col gap-1 min-h-[40px] justify-center pr-phi-2">
                {lookupMessage ? (
                  <p className="type-meta text-oxford/62 flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-oxford/40 rounded-none animate-pulse" />
                    {lookupMessage}
                  </p>
                ) : (
                  <p className="type-meta text-oxford/42">Paste a company name or URL.</p>
                )}
              </div>

              {!isBusy && (
                <button
                  type="button"
                  onClick={onSubmit}
                  disabled={!input.trim()}
                  className="group inline-flex items-center gap-2 px-0 min-h-[36px] type-meta text-oxford/60 hover:text-oxford transition-colors disabled:opacity-20"
                >
                  Run dispatch
                  <span className="group-hover:translate-x-1 transition-transform">→</span>
                </button>
              )}
            </div>

            {lookupPhase && (
              <div className="mt-phi-3 border-t border-oxford/5 pt-phi-3 flex gap-3">
                {['Scouting', 'Reviewing', 'Deciding'].map((phase) => {
                  const isActive = lookupPhase === phase;
                  const isPast = (lookupPhase === 'Reviewing' && phase === 'Scouting') ||
                    (lookupPhase === 'Deciding' && (phase === 'Scouting' || phase === 'Reviewing'));

                  return (
                    <div key={phase} className="flex-1 flex flex-col gap-2">
                      <div className="h-[2px] w-full bg-oxford/5 relative">
                        {(isActive || isPast) && (
                          <span
                            className={`absolute inset-0 origin-left h-full transition-transform duration-300 ease-smooth ${isActive ? 'bg-oxford/40' : 'bg-oxford/20'} scale-x-100`}
                          />
                        )}
                      </div>
                      <span className={`type-meta ${isActive ? 'text-oxford/60' : 'text-oxford/45'}`}>
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
