import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ExecutionReadinessPanel from '../ExecutionReadinessPanel';

describe('ExecutionReadinessPanel', () => {
  it('separates a blocked execution plane from agent enablement', () => {
    render(<ExecutionReadinessPanel status={{
      status: 'ok',
      durable_jobs: { required: true, ready: false, error: 'database_unavailable', counts: {} },
    }} />);

    expect(screen.getByText('Blocked')).toBeInTheDocument();
    expect(screen.getByText(/durable execution is required/i)).toBeInTheDocument();
    expect(screen.queryByText(/agents are off/i)).not.toBeInTheDocument();
  });

  it('shows recoverable and terminal durable work as degraded', () => {
    render(<ExecutionReadinessPanel status={{
      status: 'ok',
      durable_jobs: {
        required: true,
        ready: true,
        error: null,
        counts: {
          'company_lookup:accepted': 2,
          'company_lookup:running': 1,
          'company_lookup:retry_wait': 3,
          'company_lookup:dead_letter': 1,
          'outbox:pending': 4,
        },
      },
    }} />);

    expect(screen.getByText('Degraded')).toBeInTheDocument();
    expect(screen.getByLabelText('Retry wait')).toHaveTextContent('3');
    expect(screen.getByLabelText('Dead letter')).toHaveTextContent('1');
    expect(screen.getByLabelText('Outbox')).toHaveTextContent('4');
  });

  it('reports healthy readiness when the required worker is ready and no jobs need intervention', () => {
    render(<ExecutionReadinessPanel status={{
      status: 'ok',
      durable_jobs: { required: true, ready: true, error: null, counts: { 'company_lookup:queued': 2 } },
    }} />);

    expect(screen.getByText('Healthy')).toBeInTheDocument();
    expect(screen.getByLabelText('Queued')).toHaveTextContent('2');
  });
});
