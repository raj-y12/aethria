import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it, vi } from 'vitest';
import type { SystemData } from '../../hooks/useSystemData';
import HomePage from '../HomePage';

vi.mock('../../components/AppFrame', () => ({
  useAppFrame: () => ({
    openDispatch: vi.fn(),
    dispatchActive: false,
    pipelineState: 'Live',
    pipelineStateReady: true,
  }),
}));

vi.mock('../../hooks/useFundReadiness', () => ({
  deriveMandatePrompt: () => 'ready',
  useFundReadiness: () => ({ mandatePublished: true, unknown: false, loading: false }),
}));

vi.mock('../../hooks/useAgentLogoutFlow', () => ({
  useAgentLogoutFlow: () => ({
    displayName: 'A-RAJ',
    agentActionPending: false,
    requestLogout: vi.fn(),
    logoutModalProps: {},
  }),
}));

vi.mock('../../components/AgentLogoutModal', () => ({ default: () => null }));

const data = {
  startups: [
    {
      id: 'lumo',
      scout: { name: 'Lumo' },
      partner: { human_review_required: true, recommendation: 'MONITOR' },
    },
    {
      id: 'quiet',
      scout: { name: 'Quiet Company' },
      human_resolution: { resolved_at: '2026-09-01T12:00:00Z' },
    },
  ],
  pendingEscalationCount: 1,
  watchlistAnalytics: { total: 2 },
  settings: { fund_identity: { fund_name: 'Aethria Fund' } },
  fundThesisRuntime: { active_version_number: 39, active_version_id: 'v39' },
} as unknown as SystemData;

describe('HomePage', () => {
  it('makes the ruling count and next action the dominant briefing', () => {
    render(
      <MemoryRouter>
        <HomePage data={data} sinceAway={null} />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '1 matter awaits your ruling.' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /On the desk: Lumo/ })).toBeInTheDocument();
    expect(screen.getByText('Pipeline live')).toBeInTheDocument();
    expect(screen.queryByText('1 in pipeline')).not.toBeInTheDocument();
    expect(screen.queryByText('Signed in as A-RAJ')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Portfolio.' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fund.' })).toBeInTheDocument();
  });
});
