import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface AgentDispatchProps {
  input: string;
  setInput: (val: string) => void;
  onSubmit: () => void;
  isBusy: boolean;
  message: string | null;
  lookupPhase: 'Scouting' | 'Reviewing' | 'Deciding' | null;
}

/**
 * Transforms standard lookup messages into high-tension tactical agent logs.
 */
function formatTacticalLog(msg: string): string {
  if (!msg) return '';

  const substitutions: Record<string, string> = {
    'Submitting lookup request...': 'CMD_INIT: Dispatching intelligence agents...',
    'Lookup queued for': 'CMD_QUEUED: Analysis pending for',
    'Searching sources for': 'AGENT_DISPATCH: Confirming identity and sourcing alpha...',
    'Found': 'IDENTITY_LOCKED: Commencing deep-review scoring...',
    'Running analyst review': 'MODEL_V1.4: Executing scoring algorithms...',
    'Lookup complete': 'MISSION_SUCCESS: Intelligence report finalized.',
    'Could not submit': 'ERROR: Signal interference. Retry command.',
  };

  for (const [key, replacement] of Object.entries(substitutions)) {
    if (msg.includes(key)) return msg.replace(key, replacement);
  }

  return `CMD_FEED: ${msg}`;
}

const LOG_VARIANTS = {
  initial: { opacity: 0, x: -4 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: 4 },
};

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

  const tacticalLog = message ? formatTacticalLog(message) : null;

  return (
    <div className="relative w-full border-t border-oxford/10 px-phi-4 pt-phi-2 mt-phi-2 lg:mt-phi-3 group">
      <AnimatePresence mode="wait">
        {!expanded ? (
          <motion.button
            key="dispatch-trigger"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            onClick={() => setExpanded(true)}
            className="flex w-full min-h-[44px] items-center justify-between py-phi-2 text-left btn-interaction group/trigger"
          >
            <span className="type-meta tracking-[0.1em] text-oxford/55 group-hover/trigger:text-oxford/80 transition-colors">
              Dispatch
            </span>
            <span className="shrink-0 tabular-nums text-oxford/20" aria-hidden>+</span>
          </motion.button>
        ) : (
          <motion.div
            key="dispatch-active"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
          >
            <div className="pb-phi-4 pt-phi-2">
              <div className="flex items-center justify-between mb-phi-4">
                <span className="type-meta tracking-[0.1em] text-oxford/55">
                  Agent_Dispatch
                </span>
                {!isBusy && !message && (
                  <button
                    onClick={() => setExpanded(false)}
                    className="type-meta min-h-[44px] inline-flex items-center text-oxford/55 hover:text-oxford/80 tracking-[0.1em] transition-colors"
                  >
                    Close
                  </button>
                )}
              </div>

              <div className="relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') onSubmit();
                    if (e.key === 'Escape' && !isBusy && !message) setExpanded(false);
                  }}
                  placeholder="Enter Company Name or URL"
                  autoComplete="off"
                  disabled={isBusy}
                  className="w-full bg-transparent border-0 border-b border-oxford/10 px-0 py-2 font-sans font-semibold text-2xl sm:text-3xl text-oxford placeholder:text-oxford/10 outline-none focus:border-oxford/30 transition-colors duration-500"
                />

                <AnimatePresence>
                  {isBusy && (
                    <motion.div
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: 1 }}
                      exit={{ opacity: 0 }}
                      className="absolute bottom-0 left-0 h-[1px] w-full bg-oxford/40 origin-left"
                      style={{ animation: 'aethria-pulse 1.5s infinite' }}
                    />
                  )}
                </AnimatePresence>
              </div>

              <div className="mt-phi-4 flex items-center justify-between">
                <div className="flex flex-col gap-1 min-h-[40px] justify-center">
                  <AnimatePresence mode="wait">
                    {tacticalLog ? (
                      <motion.p
                        key={tacticalLog}
                        variants={LOG_VARIANTS}
                        initial="initial"
                        animate="animate"
                        exit="exit"
                        className="type-meta text-oxford/70 flex items-center gap-2"
                      >
                        <span className="w-1.5 h-1.5 bg-oxford/40 rounded-none animate-pulse" />
                        {tacticalLog}
                      </motion.p>
                    ) : (
                      <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="type-meta text-oxford/55"
                      >
                        AWAITING_COMMAND...
                      </motion.p>
                    )}
                  </AnimatePresence>
                </div>

                {!isBusy && (
                  <button
                    type="button"
                    onClick={onSubmit}
                    disabled={!input.trim()}
                    className="group flex items-center gap-2 px-0 min-h-[44px] type-meta tracking-[0.1em] text-oxford/55 hover:text-oxford transition-colors disabled:opacity-20"
                  >
                    Run_Analysis
                    <span className="group-hover:translate-x-1 transition-transform">→</span>
                  </button>
                )}
              </div>

              {/* Progress Indicator */}
              <AnimatePresence>
                {lookupPhase && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="mt-6 border-t border-oxford/5 pt-4 flex gap-4"
                  >
                    {['Scouting', 'Reviewing', 'Deciding'].map((phase) => {
                      const isActive = lookupPhase === phase;
                      const isPast = (lookupPhase === 'Reviewing' && phase === 'Scouting') ||
                        (lookupPhase === 'Deciding' && (phase === 'Scouting' || phase === 'Reviewing'));

                      return (
                        <div key={phase} className="flex-1 flex flex-col gap-2">
                          <div className="h-[2px] w-full bg-oxford/5 relative">
                            {(isActive || isPast) && (
                              <motion.div
                                initial={{ scaleX: 0 }}
                                animate={{ scaleX: 1 }}
                                className={`absolute inset-0 origin-left h-full ${isActive ? 'bg-oxford/40' : 'bg-oxford/20'}`}
                                transition={{ duration: 1, ease: "circOut" }}
                              />
                            )}
                          </div>
                          <span className={`type-meta tracking-widest uppercase ${isActive ? 'text-oxford/60' : 'text-oxford/45'}`}>
                            {phase}
                          </span>
                        </div>
                      )
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
