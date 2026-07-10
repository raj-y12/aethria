import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MemoSectionTitle from '../MemoSectionTitle';

describe('MemoSectionTitle', () => {
  it('renders a numbered semantic heading without exposing the number to assistive technology', () => {
    render(<MemoSectionTitle number="03" id="memo-limits">What Limits Conviction</MemoSectionTitle>);

    expect(screen.getByRole('heading', { level: 2, name: 'What Limits Conviction' })).toHaveAttribute(
      'id',
      'memo-limits',
    );
    expect(screen.getByText('03')).toHaveAttribute('aria-hidden', 'true');
  });
});
