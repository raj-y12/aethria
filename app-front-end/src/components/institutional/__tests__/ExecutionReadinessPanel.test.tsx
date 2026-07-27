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

  it('shows active work while retaining terminal history as a readout', () => {
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

    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByLabelText('Retry wait')).toHaveTextContent('3');
    expect(screen.getByLabelText('Dead letter')).toHaveTextContent('1');
    expect(screen.getByLabelText('Outbox')).toHaveTextContent('4');
  });

  it('keeps historical terminal work visible without calling the pipeline degraded', () => {
    render(<ExecutionReadinessPanel status={{
      status: 'ok',
      durable_jobs: { required: true, ready: true, error: null, counts: { 'pipeline_cycle:dead_letter': 1 } },
    }} recentJobs={[{
      job_id: 'job-1', job_type: 'pipeline_cycle', status: 'dead_letter', attempts: 3,
      max_attempts: 3, pipeline_run_id: 'run-1', accepted_at: '', next_attempt_at: '',
      failure_code: 'scout_persona_failures',
    }]} />);

    expect(screen.getByText('Historical')).toBeInTheDocument();
    expect(screen.getByText(/latest code: scout_persona_failures/i)).toBeInTheDocument();
    expect(screen.queryByText('Degraded')).not.toBeInTheDocument();
  });

  it('does not use lookup failures as the pipeline diagnostic', () => {
    render(<ExecutionReadinessPanel status={{
      status: 'ok',
      durable_jobs: { required: true, ready: true, error: null, counts: { 'pipeline_cycle:dead_letter': 1 } },
    }} recentJobs={[{
      job_id: 'job-lookup', job_type: 'company_lookup', status: 'dead_letter', attempts: 3,
      max_attempts: 3, pipeline_run_id: 'run-lookup', accepted_at: '', next_attempt_at: '',
      failure_code: 'lookup_attempt_failed',
    }]} />);

    expect(screen.queryByText(/Latest code:/i)).not.toBeInTheDocument();
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
