import { useState } from 'react';
import { Link } from 'react-router-dom';
import GrainOverlay from './components/GrainOverlay';
import CustomCursor from './components/CustomCursor';

const OXFORD = '#002147';
const PAPER = '#F2F0EA';

export default function HomePage() {
  const [ctaHover, setCtaHover] = useState(false);

  return (
    <div
      className="min-h-[100dvh] h-[100dvh] flex flex-col relative"
      style={{ backgroundColor: PAPER }}
    >
      <GrainOverlay />
      <CustomCursor />
      {/* Header */}
      <header className="flex items-center justify-between px-6 sm:px-8 lg:px-12 pt-6 sm:pt-8 pb-4 md:pb-6">
        <Link
          data-cursor-expand
          to="/"
          className="font-display font-normal text-[17px] hover:opacity-80 transition-opacity md:block text-center md:text-left flex-1 md:flex-none"
          style={{ color: OXFORD }}
        >
          Aethria
        </Link>
        <span
          className="font-mono text-[10px] uppercase tracking-widest opacity-70 hidden md:inline transition-opacity duration-300 hover:opacity-100"
          style={{ color: OXFORD }}
        >
          Investment Intelligence
        </span>
      </header>

      {/* Main: monolith first in DOM for mobile; desktop order swaps so description left (25%), monolith right (75% full-bleed) */}
      <main className="flex-1 flex flex-col md:flex-row min-h-0">
        {/* Monolith: full-width on mobile (aspect-ratio auto); 25%–100% on desktop; zero rounded corners */}
        <div
          data-cursor-expand
          className="order-1 md:order-2 flex items-center justify-center md:justify-start w-full md:flex-1 min-h-[50vh] md:min-h-0 aspect-auto p-10 sm:p-14 md:p-16 lg:p-20 xl:p-24 shrink-0 rounded-none"
          style={{ backgroundColor: OXFORD }}
        >
          <h1
            className="font-display font-normal text-4xl sm:text-[2.85rem] lg:text-[3.5625rem] xl:text-[4.275rem] max-w-[18ch] md:max-w-[20ch]"
            style={{ color: PAPER, lineHeight: 1.05 }}
          >
            Intelligent investment discovery and evaluation system.
          </h1>
        </div>

        {/* Description: below monolith on mobile (generous padding); left 25% on desktop */}
        <section className="order-2 md:order-1 flex md:w-[25%] flex-col justify-center px-6 lg:px-12 pr-4 py-12 sm:py-16 md:py-0 shrink-0">
          <p
            className="font-sans text-[15px] max-w-[26ch] opacity-70"
            style={{ color: OXFORD, lineHeight: 1.85 }}
          >
            Aethria supports institutional allocators with clarity and rigour. Join the waiting list for early access to the platform.
          </p>
        </section>
      </main>

      {/* CTA: left edge aligned with Blue Hero Block (25%); clear separation from main */}
      <div
        className="relative z-10 mt-auto flex-shrink-0 px-6 sm:px-8 lg:px-12 pt-10 sm:pt-12 md:pt-6 md:pl-[25%] md:pr-0 pb-[max(2rem,calc(2rem+env(safe-area-inset-bottom,0px)))] sm:pb-[max(2.5rem,calc(2.5rem+env(safe-area-inset-bottom,0px)))] md:pb-[max(2rem,calc(2rem+env(safe-area-inset-bottom,0px)))]"
        style={{ color: OXFORD, backgroundColor: PAPER }}
      >
        <Link
          to="/request-access"
          data-cursor-expand
          className="inline-flex items-baseline font-mono text-[10px] uppercase tracking-widest opacity-70 hover:opacity-100 transition-all duration-200 group"
          style={{ color: OXFORD }}
          onMouseEnter={() => setCtaHover(true)}
          onMouseLeave={() => setCtaHover(false)}
        >
          <span className={ctaHover ? 'translate-x-0.5 inline-block transition-transform duration-200' : 'inline-block transition-transform duration-200'}>
            REQUEST ACCESS
          </span>
          <span
            className="inline-block overflow-hidden origin-left ml-1 flex-shrink-0 whitespace-nowrap"
            style={{
              width: ctaHover ? '1em' : '0.5em',
              transition: 'width 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            {'\u00A0—'}
          </span>
        </Link>
      </div>
    </div>
  );
}
