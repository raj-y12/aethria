import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { useClerk, useUser } from '@clerk/react';
import { useAgentsEnabled } from './useAgentsEnabled';
import { toggleAgents } from '../api/agents';

/**
 * Shared sign-out + agent gating modal flow (SystemBar fixed, AccountRailPanel).
 */
export function useAgentLogoutFlow() {
  const navigate = useNavigate();
  const { user } = useUser();
  const { signOut } = useClerk();
  const agentsEnabled = useAgentsEnabled();
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [agentActionPending, setAgentActionPending] = useState(false);
  const [agentActionError, setAgentActionError] = useState<string | null>(null);

  const displayName = user?.username ?? user?.primaryEmailAddress?.emailAddress ?? 'Account';

  const doLogout = useCallback(() => {
    localStorage.removeItem('aethria_last_activity');
    signOut?.().then(() => navigate('/sign-in', { replace: true }));
  }, [navigate, signOut]);

  const toggleAgentsAndLogout = useCallback(
    async (enabled: boolean) => {
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
    },
    [doLogout]
  );

  const logoutModalProps = {
    open: showLogoutModal,
    agentsEnabled,
    onCancel: () => setShowLogoutModal(false),
    onKeepRunning: () => {
      setShowLogoutModal(false);
      doLogout();
    },
    onTurnOffAndLogout: async () => {
      await toggleAgentsAndLogout(false);
    },
    onTurnOnAndLogout: async () => {
      await toggleAgentsAndLogout(true);
    },
  };

  return {
    displayName,
    agentActionPending,
    agentActionError,
    requestLogout: () => setShowLogoutModal(true),
    logoutModalProps,
  };
}
