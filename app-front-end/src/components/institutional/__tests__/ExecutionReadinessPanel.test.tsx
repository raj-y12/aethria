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

  it('shows automatic retrying as active while the worker is processing work', () => {
    render(<ExecutionReadinessPanel status={{
      status: 'ok',
      durable_jobs: {
        required: true,
        ready: true,
        error: null,
        counts: {
          'pipeline_cycle:queued': 4,
          'pipeline_cycle:running': 2,
          'pipeline_cycle:retry_wait': 1,
        },
      },
    }} />);

    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText(/retrying.*automatically/i)).toBeInTheDocument();
    expect(screen.queryByText('Degraded')).not.toBeInTheDocument();
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
