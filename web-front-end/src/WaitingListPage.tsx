import { useState } from 'react';

export default function WaitingListPage() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitted(true);
  };

  return (
    <div className="h-screen bg-canvas overflow-hidden">
      {/* Full-viewport container with layered, angled planes — architectural asymmetry */}
      <div className="relative h-full w-full">
        {/* Base layer — warmest canvas */}
        <div
          className="absolute inset-0"
          style={{ backgroundColor: '#fcfcfc' }}
        />
        
        {/* Left angled plane — cooler mist, diagonal edge */}
        <div
          className="absolute inset-y-0 left-0 w-[35%] min-w-[250px]"
          style={{
            backgroundColor: '#f8f9fb',
            clipPath: 'polygon(0 0, calc(100% - 3vw) 0, 100% 100%, 0 100%)',
          }}
        />
        
        {/* Center overlapping plane — deepest mist, subtle diagonal */}
        <div
          className="absolute inset-y-0 left-[25%] w-[50%] min-w-[320px]"
          style={{
            backgroundColor: '#f2f4f8',
            clipPath: 'polygon(0 0, 100% 0, calc(100% - 2vw) 100%, 3vw 100%)',
          }}
        />
        
        {/* Right accent plane — light canvas with angled entry */}
        <div
          className="absolute inset-y-0 right-0 w-[32%] min-w-[220px]"
          style={{
            backgroundColor: '#fafbfc',
            clipPath: 'polygon(4vw 0, 100% 0, 100% 100%, 0 100%)',
          }}
        />

        {/* Navigation — full width, grid-aligned, asymmetric spacing for architectural feel */}
        <nav className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-8 lg:px-12 pt-8 pb-5">
          <a
            href="/"
            className="font-display font-bold text-graphite text-[17px] tracking-[0.04em] hover:text-oxford transition-colors"
          >
            Aethria
          </a>
          <div className="flex gap-8 text-graphite text-[13px] tracking-[0.04em]">
            <a href="/" className="hover:text-oxford transition-colors">
              Home
            </a>
          </div>
        </nav>

        {/* Narrow content column — centered */}
        <div className="relative z-[1] flex items-center h-full w-full justify-center py-20">
          <div className="w-full max-w-reading px-6 sm:px-10">
            {/* Vertical rhythm via spacing only — no section wrappers */}
            <p className="font-display text-graphite/70 text-[10px] uppercase tracking-[0.24em] mb-8">
              Early access
            </p>

            <h1 className="font-display text-oxford text-[1.75rem] sm:text-[2rem] leading-[1.35] font-normal mb-6 max-w-[28ch]">
              Decision intelligence for capital allocation.
            </h1>

            <p className="font-sans text-graphite text-[15px] leading-[1.65] max-w-[32ch] mb-8">
              Aethria supports institutional allocators with clarity and rigour. Join the waiting list for early access.
            </p>

            {/* Form — embedded, quiet, no card/box */}
            {!submitted ? (
              <form onSubmit={handleSubmit} className="max-w-md">
                <div className="border-b border-graphite/30 pb-1 focus-within:border-graphite/60 transition-colors">
                  <label htmlFor="email" className="sr-only">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                    className="w-full bg-transparent font-sans text-graphite text-[15px] placeholder:text-graphite/40 py-2 outline-none"
                    required
                  />
                </div>
                <button
                  type="submit"
                  className="mt-4 font-sans text-graphite text-[12px] uppercase tracking-[0.18em] hover:text-oxford transition-colors"
                >
                  Request access
                </button>
              </form>
            ) : (
              <p className="font-sans text-graphite text-[14px]">
                Thank you. We'll be in touch.
              </p>
            )}
          </div>
        </div>

        {/* Footer — absolute positioned at bottom, inside planes */}
        <footer className="absolute bottom-0 left-0 right-0 z-10 flex items-center justify-between px-8 lg:px-12 py-4">
        <span className="font-sans text-graphite/60 text-[11px] tracking-[0.06em]">
          © Aethria
        </span>
          <span className="font-sans text-graphite/40 text-[11px] tracking-[0.04em]">
            Investment intelligence
          </span>
        </footer>
      </div>
    </div>
  );
}
