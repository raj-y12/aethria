import { Link } from 'react-router';
import { railEditorial } from '../design-system/railEditorial';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import AgentLogoutModal from './AgentLogoutModal';

interface AccountRailPanelProps {
  settingsPath: string;
}

export default function AccountRailPanel({ settingsPath }: AccountRailPanelProps) {
  const {
    displayName,
    agentActionPending,
    agentActionError,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();

  return (
    <>
      <section aria-label="Operator" className="shrink-0 min-w-0 pb-phi-1">
        <p className={railEditorial.label}>Operator</p>
        <p className={`font-sans text-[13px] font-medium leading-none text-oxford/72 truncate`} title={displayName}>
          {displayName}
        </p>

        <div className="mt-phi-3 flex items-center gap-phi-3">
          <Link
            to={settingsPath}
            className="font-mono text-[9px] uppercase tracking-[0.14em] text-oxford/30 hover:text-oxford/60 transition-colors btn-interaction"
          >
            Settings
          </Link>
          <span className="font-mono text-[9px] text-oxford/18" aria-hidden>·</span>
          <button
            type="button"
            onClick={requestLogout}
            disabled={agentActionPending}
            className="font-mono text-[9px] uppercase tracking-[0.14em] text-oxford/30 hover:text-oxford/55 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction disabled:opacity-50"
          >
            {agentActionPending ? 'Updating…' : 'Log out'}
          </button>
        </div>

        {agentActionError ? (
          <p className="mt-phi-2 font-mono text-[10px] text-escalation" role="status" aria-live="polite">
            {agentActionError}
          </p>
        ) : null}
      </section>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
