import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { useClerk, useUser } from '@clerk/react';
import { useAgentsEnabled } from '../hooks/useAgentsEnabled';
import { toggleAgents } from '../api/agents';
import AgentLogoutModal from './AgentLogoutModal';

interface AccountRailPanelProps {
  settingsPath: string;
}

export default function AccountRailPanel({ settingsPath }: AccountRailPanelProps) {
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();
  const agentsEnabled = useAgentsEnabled();
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [agentActionPending, setAgentActionPending] = useState(false);
  const [agentActionError, setAgentActionError] = useState<string | null>(null);
  const displayName = user?.username ?? user?.primaryEmailAddress?.emailAddress ?? 'Account';

  const doLogout = () => {
    localStorage.removeItem('aethria_last_activity');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  };

  const toggleAgentsAndLogout = async (enabled: boolean) => {
    setAgentActionPending(true);
    setAgentActionError(null);
    try {
      await toggleAgents(enabled);
      doLogout();
    } catch {
      setAgentActionError('Unable to update agent state. Please retry.');
    } finally {
      setAgentActionPending(false);
    }
  };

  return (
    <>
      <section
        aria-label="Account"
        className="shrink-0 bg-paper border border-oxford/[0.08] px-phi-4 py-phi-3"
      >
        <div className="flex items-center gap-phi-3">
          <p className="type-meta text-oxford/35 uppercase tracking-[0.1em]">Account</p>
        </div>

        <p className="mt-phi-2 type-body-sm font-semibold uppercase tracking-[0.08em] leading-tight text-oxford truncate" title={displayName}>
          {displayName}
        </p>

        <div className="mt-phi-3 flex items-center gap-phi-2 border-t border-oxford/[0.06] pt-phi-3">
          <Link
            to={settingsPath}
            className="type-meta text-oxford/45 hover:text-oxford transition-colors btn-interaction"
          >
            Settings
          </Link>
          <span className="type-meta text-oxford/20" aria-hidden>/</span>
          <button
            type="button"
            onClick={() => setShowLogoutModal(true)}
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

      <AgentLogoutModal
        open={showLogoutModal}
        agentsEnabled={agentsEnabled}
        onCancel={() => setShowLogoutModal(false)}
        onKeepRunning={() => { setShowLogoutModal(false); doLogout(); }}
        onTurnOffAndLogout={async () => { await toggleAgentsAndLogout(false); }}
        onTurnOnAndStay={async () => { await toggleAgentsAndLogout(true); }}
      />
    </>
  );
}
