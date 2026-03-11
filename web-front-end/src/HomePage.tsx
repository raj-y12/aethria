import { Link } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import GrainOverlay from './components/GrainOverlay';
import CustomCursor from './components/CustomCursor';

const pipelineColumns = [
  { label: 'SCOUT', body: 'Four parallel agents discovering opportunity signals.' },
  { label: 'REVIEWER', body: 'Three reviewer perspectives evaluate each hypothesis independently.' },
  { label: 'PARTNER', body: 'Rule-based decision engine with LLM fallback for edge cases.' },
  { label: 'PORTFOLIO', body: 'Execution, signals and portfolio memory layer.' },
];

export default function HomePage() {
  const pipelineRef = useRef<HTMLElement>(null);
  const [pipelineInView, setPipelineInView] = useState(false);
  const signalRef = useRef<HTMLElement>(null);
  const [signalInView, setSignalInView] = useState(false);
  const closingRef = useRef<HTMLElement>(null);
  const [closingInView, setClosingInView] = useState(false);

  useEffect(() => {
    const obs = new IntersectionObserver(([entry]) => entry.isIntersecting && setPipelineInView(true), { threshold: 0.15 });
    const el = pipelineRef.current;
    if (el) obs.observe(el);
    return () => obs.disconnect();
  }, []);
  useEffect(() => {
    const obs = new IntersectionObserver(([entry]) => entry.isIntersecting && setSignalInView(true), { threshold: 0.15 });
    const el = signalRef.current;
    if (el) obs.observe(el);
    return () => obs.disconnect();
  }, []);
  useEffect(() => {
    const obs = new IntersectionObserver(([entry]) => entry.isIntersecting && setClosingInView(true), { threshold: 0.15 });
    const el = closingRef.current;
    if (el) obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div className="min-h-[100dvh] flex flex-col relative overflow-x-hidden w-full" style={{ backgroundColor: 'var(--color-paper)' }}>
      <GrainOverlay />
      <CustomCursor />

      <header className="flex items-center justify-between page-margin-x pt-[max(1.5rem,env(safe-area-inset-top))] sm:pt-8 pb-4 md:pb-6 shrink-0">
        <Link
          data-cursor-expand
          to="/"
          className="font-display font-normal text-[17px] hover:opacity-80 transition-opacity md:block text-center md:text-left flex-1 md:flex-none"
          style={{ color: 'var(--color-oxford)' }}
        >
          Aethria
        </Link>
        <span
          className="font-mono text-[10px] uppercase tracking-[0.1em] opacity-70 hidden md:inline transition-opacity duration-300 hover:opacity-100"
          style={{ color: 'var(--color-oxford)' }}
        >
          Investment Intelligence
        </span>
      </header>

      <main className="flex-1 flex flex-col md:flex-row md:items-center min-h-0 shrink-0 min-w-0">
        {/* Left column first in DOM for mobile (top); desktop 25% */}
        <section className="home-hero-left page-margin-x order-1 flex md:w-[25%] flex-col justify-center py-8 sm:py-16 md:py-0 shrink-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.15em] opacity-50 mb-2" style={{ color: 'var(--color-oxford)' }}>
            REGISTRY / 2026 · EARLY ACCESS
          </p>
          <p className="font-sans text-[15px] max-w-[26ch] md:max-w-none opacity-70" style={{ color: 'var(--color-oxford)', lineHeight: 1.85 }}>
            Autonomous deal intelligence for venture capital.
          </p>
          <Link
            to="/request-access"
            data-cursor-expand
            className="font-mono text-[10px] uppercase tracking-[0.1em] cursor-pointer rounded-none transition-all duration-300 inline-flex items-center justify-center w-full md:w-fit min-h-[44px] h-10 px-6 bg-transparent border border-[var(--color-oxford)] md:border-[rgba(0,33,71,0.2)] hover:bg-[var(--color-oxford)] hover:text-[var(--color-paper)] hover:border-[var(--color-oxford)] mt-8"
            style={{ color: 'var(--color-oxford)' }}
          >
            REQUEST ACCESS
          </Link>
        </section>

        {/* Monolith — vertical light line on left, starting at bottom left */}
        <div
          data-cursor-expand
          className="order-2 relative flex items-center justify-center w-full md:flex-1 min-h-[280px] md:min-h-[70vh] aspect-auto p-6 sm:p-10 md:p-16 lg:p-20 xl:p-24 shrink-0 rounded-none"
          style={{ backgroundColor: 'var(--color-oxford)' }}
        >
          <div
            className="absolute left-0 bottom-0 top-0 w-px pointer-events-none"
            style={{ backgroundColor: 'rgba(242, 240, 234, 0.12)' }}
            aria-hidden
          />
          <h1
            className="font-display font-normal text-[28px] sm:text-[2.85rem] lg:text-[3.5625rem] xl:text-[4.275rem] max-w-[18ch] md:max-w-[20ch] relative z-[1]"
            style={{ color: 'var(--color-paper)', lineHeight: 1.05 }}
          >
            Intelligent investment discovery and evaluation system.
          </h1>
        </div>
      </main>

      {/* Pipeline strip */}
      <section
        ref={pipelineRef}
        className="w-full page-margin-x border-t flex flex-col md:flex-row min-w-0"
        style={{
          paddingTop: 'var(--section-padding-y)',
          paddingBottom: 'var(--section-padding-y)',
          backgroundColor: 'var(--color-paper)',
          borderTopColor: 'rgba(0, 33, 71, 0.08)',
          opacity: pipelineInView ? 1 : 0,
          transform: pipelineInView ? 'translateY(0)' : 'translateY(16px)',
          transition: 'opacity 500ms ease, transform 500ms cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {pipelineColumns.map((col, i) => (
          <div
            key={col.label}
            className="home-pipeline-column flex-1 flex flex-col border-t border-[rgba(0,33,71,0.08)] first:border-t-0 pt-6 first:pt-0 md:border-t-0 md:pt-0 md:border-r md:last:border-r-0 min-w-0"
            style={{
              opacity: pipelineInView ? 1 : 0,
              transform: pipelineInView ? 'translateY(0)' : 'translateY(16px)',
              transition: 'opacity 500ms ease, transform 500ms cubic-bezier(0.16, 1, 0.3, 1)',
              transitionDelay: pipelineInView ? `${i * 80}ms` : '0ms',
            }}
          >
            <div className="md:px-6 lg:px-8">
              <p className="font-mono text-[10px] uppercase tracking-[0.15em]" style={{ color: 'rgba(0, 33, 71, 0.45)' }}>
                {col.label}
              </p>
              <div className="w-4 h-px mt-3 mb-4" style={{ backgroundColor: 'rgba(0, 33, 71, 0.12)' }} />
              <p className="font-sans text-[13px] leading-[1.6]" style={{ color: 'rgba(0, 33, 71, 0.6)' }}>
                {col.body}
              </p>
            </div>
          </div>
        ))}
      </section>

      {/* Signal strip */}
      <section
        ref={signalRef}
        className="home-signal-strip w-full flex flex-col md:flex-row items-center justify-center gap-0 md:gap-2"
        style={{
          minHeight: 52,
          backgroundColor: 'var(--color-oxford)',
          opacity: signalInView ? 1 : 0,
          transform: signalInView ? 'translateY(0)' : 'translateY(16px)',
          transition: 'opacity 500ms ease, transform 500ms cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <p
          className="home-signal-text font-mono text-[10px] uppercase tracking-[0.18em] text-center px-4"
          style={{ color: 'var(--color-paper)', opacity: 0.65 }}
        >
          SCOUT AGENTS
          <span style={{ opacity: 0.25 }}>  ·  </span>
          REVIEWER PERSPECTIVES
          <br className="md:hidden" />
          <span style={{ opacity: 0.25 }}>  ·  </span>
          AUTONOMOUS DECISION ENGINE
          <span style={{ opacity: 0.25 }}>  ·  </span>
          SELF-OPTIMISATION
        </p>
      </section>

      {/* Closing statement */}
      <section
        ref={closingRef}
        className="home-closing w-full page-margin-x py-20"
        style={{
          backgroundColor: 'var(--color-paper)',
          opacity: closingInView ? 1 : 0,
          transform: closingInView ? 'translateY(0)' : 'translateY(16px)',
          transition: 'opacity 500ms ease, transform 500ms cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <h2 className="font-display font-normal text-[32px] max-w-full md:max-w-[520px]" style={{ color: 'var(--color-oxford)', opacity: 0.88 }}>
          Built for the speed of modern venture.
        </h2>
        <p className="font-sans text-[14px] mt-6 max-w-[440px] leading-[1.7]" style={{ color: 'rgba(0, 33, 71, 0.55)' }}>
          Aethria runs continuously — discovering, evaluating and deciding on opportunities while your team focuses on conviction.
        </p>
        <Link
          to="/request-access"
          data-cursor-expand
          className="font-mono text-[10px] uppercase tracking-[0.1em] cursor-pointer rounded-none transition-all duration-300 inline-flex items-center justify-center w-full md:w-fit min-h-[44px] h-10 px-6 bg-transparent border border-[var(--color-oxford)] md:border-[rgba(0,33,71,0.2)] hover:bg-[var(--color-oxford)] hover:text-[var(--color-paper)] hover:border-[var(--color-oxford)] mt-8"
          style={{ color: 'var(--color-oxford)' }}
        >
          REQUEST ACCESS
        </Link>
      </section>

      <footer
        className="home-footer-mobile w-full flex items-center justify-between page-margin-x py-6 md:py-7 shrink-0 pb-[max(1.5rem,env(safe-area-inset-bottom))] md:pb-7"
        style={{ color: 'var(--color-oxford)', backgroundColor: 'var(--color-paper)' }}
      >
        <span className="font-sans text-[12px]" style={{ color: 'var(--color-oxford)', opacity: 0.35 }}>
          © Aethria
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.15em]" style={{ color: 'var(--color-oxford)', opacity: 0.3 }}>
          INVESTMENT INTELLIGENCE
        </span>
      </footer>
    </div>
  );
}
