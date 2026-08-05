import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';

import MobileHeader from '../MobileHeader';

function MobileHeaderHarness() {
  const [isOpen, setIsOpen] = useState(false);

  return <MobileHeader isOpen={isOpen} onMenuToggle={() => setIsOpen((open) => !open)} />;
}

describe('MobileHeader', () => {
  it('announces the mobile menu expanded state when toggled', () => {
    render(
      <MemoryRouter>
        <MobileHeaderHarness />
      </MemoryRouter>,
    );

    const trigger = screen.getByRole('button', { name: 'Menu' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });
});
