import { Link } from 'react-router';
import { railEditorial } from '../design-system/railEditorial';
import { useAgentLogoutFlow } from '../hooks/useAgentLogoutFlow';
import AgentLogoutModal from './AgentLogoutModal';

interface AccountRailPanelProps {
  settingsPath: string;
}

const RAIL_ACTION_CLASS =
  `${railEditorial.meta} uppercase text-oxford/35 hover:text-oxford/60 transition-colors btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/35 py-phi-1`;

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
      <section aria-label="Operator" className="shrink-0 min-w-0">
        <div className="flex min-w-0 items-center justify-between gap-phi-2">
          <p
            className={`min-w-0 flex-1 truncate ${railEditorial.bodyStrong}`}
            title={displayName}
          >
            {displayName}
          </p>
          <div className="flex shrink-0 items-center gap-x-phi-4 gap-y-phi-1">
            <Link to={settingsPath} className={RAIL_ACTION_CLASS}>
              Settings
            </Link>
            <span className="font-mono text-[9px] text-oxford/22 px-phi-1" aria-hidden>
              ·
            </span>
            <button
              type="button"
              onClick={requestLogout}
              disabled={agentActionPending}
              className={`${RAIL_ACTION_CLASS} bg-transparent border-0 cursor-pointer disabled:opacity-50`}
            >
              {agentActionPending ? 'Updating...' : 'Log out'}
            </button>
          </div>
        </div>

        {agentActionError ? (
          <p className="mt-phi-1 type-meta text-escalation" role="status" aria-live="polite">
            {agentActionError}
          </p>
        ) : null}
      </section>

      <AgentLogoutModal {...logoutModalProps} />
    </>
  );
}
