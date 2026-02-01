import { useState } from 'react';
import { PageWrapper, Section, Divider, ContentColumn } from '../layout';

export default function WaitingListPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitted(true);
  };

  return (
    <PageWrapper variant="ivory">
      <header className="w-full px-4 xs:px-6 sm:px-8 lg:px-12 pt-6 sm:pt-8 pb-4 sm:pb-6">
        <div className="flex items-center justify-between">
          <a
            href="/"
            className="font-display text-oxford text-[17px] tracking-tight hover:opacity-80 transition-opacity duration-300"
          >
            Aethria
          </a>
          <a
            href="/"
            className="font-body text-charcoal/60 text-[13px] tracking-wide hover:text-oxford transition-colors duration-300"
          >
            Home
          </a>
        </div>
        <Divider fullWidth className="mt-6" />
      </header>

      <main className="w-full flex-1 flex flex-col">
        <Section spacing="lg" dividerBelow>
          <ContentColumn variant="content">
            <p className="font-body text-charcoal/60 text-[10px] uppercase tracking-[0.24em] mb-6">
              Early access
            </p>
            <h1 className="font-sans text-oxford text-[1.5rem] sm:text-[1.75rem] lg:text-[2rem] leading-[1.35] font-medium mb-4 sm:mb-6 max-w-[28ch]">
              Decision intelligence for capital allocation.
            </h1>
            <p className="font-body text-charcoal text-[15px] leading-[1.65] max-w-[32ch] mb-8">
              Aethria supports institutional allocators with clarity and rigour. Join the waiting list for early access.
            </p>
            {!submitted ? (
              <form onSubmit={handleSubmit} className="max-w-md">
                <div className="border-b border-charcoal/20 pb-1 focus-within:border-charcoal/40 transition-colors duration-300">
                  <label htmlFor="email" className="sr-only">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                    className="w-full bg-transparent font-body text-charcoal text-[15px] placeholder:text-charcoal/40 py-2 outline-none"
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="mt-4 font-body text-charcoal text-[12px] uppercase tracking-[0.18em] hover:text-oxford transition-colors duration-300"
                >
                  Request access
                </button>
              </form>
            ) : (
              <p className="font-body text-charcoal text-[14px]">
                Thank you. We’ll be in touch.
              </p>
            )}
          </ContentColumn>
        </Section>
      </main>

      <footer className="w-full px-4 xs:px-6 sm:px-8 lg:px-12 py-4 sm:py-6">
        <Divider fullWidth className="mb-6" />
        <div className="flex items-center justify-between">
          <span className="font-body text-charcoal/60 text-[11px] tracking-wide">
            © Aethria
          </span>
          <span className="font-body text-charcoal/40 text-[11px] tracking-wide">
            Investment intelligence
          </span>
        </div>
      </footer>
    </PageWrapper>
  );
}
