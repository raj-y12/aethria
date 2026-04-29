import { Link } from 'react-router';
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
      <section
        aria-label="Account"
        className="shrink-0 bg-paper border border-oxford/[0.08] px-phi-4 py-phi-3"
      >
        <div className="flex items-center gap-phi-3">
          <p className="type-meta text-oxford/35 tracking-[0.08em]">Account</p>
        </div>

        <p
          className="mt-phi-2 type-body-sm font-semibold tracking-[0.04em] leading-tight text-oxford truncate"
          title={displayName}
        >
          {displayName}
        </p>

        <div className="mt-phi-3 flex items-center gap-phi-2 border-t border-oxford/[0.06] pt-phi-3">
          <Link
            to={settingsPath}
            className="type-meta text-oxford/45 hover:text-oxford transition-colors btn-interaction"
          >
            Settings
          </Link>
          <span className="type-meta text-oxford/20" aria-hidden>
            /
          </span>
          <button
            type="button"
            onClick={requestLogout}
            disabled={agentActionPending}
            className="type-meta text-oxford/38 hover:text-oxford/70 bg-transparent border-0 p-0 cursor-pointer transition-colors btn-interaction disabled:opacity-50"
          >
            {agentActionPending ? 'Updating...' : 'Log out'}
          </button>
        </div>

        {agentActionError ? (
          <p className="mt-phi-2 type-meta text-escalation/80" role="status" aria-live="polite">
            {agentActionError}
          </p>
        ) : null}
      </section>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
