import { Link } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { motion, Variants } from 'framer-motion';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import GrainOverlay from './components/GrainOverlay';
import IntelligenceMap from './components/IntelligenceMap';
import DashboardPreview from './components/DashboardPreview';

const headlineText = 'Intelligent investment discovery and evaluation system.';

const headlineContainerVariants: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.06,
    },
  },
};

const headlineWordVariants: Variants = {
  hidden: { y: '110%' },
  visible: {
    y: '0%',
    transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] },
  },
};

const subtextVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, delay: 0.4, ease: [0.16, 1, 0.3, 1] },
  },
};

const ctaVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: 0.5, delay: 0.9, ease: [0.16, 1, 0.3, 1] },
  },
};

export default function HomePage() {
  const closingRef = useRef<HTMLElement>(null);
  const [closingInView, setClosingInView] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const footerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setPrefersReducedMotion(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) setClosingInView(true);
  }, [prefersReducedMotion]);

  useEffect(() => {
    if (!prefersReducedMotion) return;
    const footer = footerRef.current;
    if (footer) footer.classList.add('home-footer-visible');
  }, [prefersReducedMotion]);

  useEffect(() => {
    const footer = footerRef.current;
    if (!footer) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          footer.classList.add('home-footer-visible');
          obs.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    obs.observe(footer);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const section = closingRef.current;
    if (!section) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      gsap.set(section.querySelectorAll('.conviction-line'), { yPercent: 0, opacity: 1, clearProps: 'transform' });
      const tagsEl = section.querySelector('.conviction-tags');
      if (tagsEl) gsap.set(tagsEl, { opacity: 1, y: 0, clearProps: 'transform' });
      return;
    }

    gsap.registerPlugin(ScrollTrigger);
    const watermark = section.querySelector<HTMLElement>('.conviction-watermark');
    const lines = section.querySelectorAll<HTMLElement>('.conviction-line');
    const tags = section.querySelector<HTMLElement>('.conviction-tags');

    const timeline = gsap.timeline({
      scrollTrigger: {
        trigger: section,
        start: 'top 80%',
        end: 'bottom 20%',
        scrub: 1.5,
      },
    });

    if (watermark) {
      timeline.to(
        watermark,
        {
          x: -80,
        },
        0,
      );
    }

    const lineTween = gsap.fromTo(
      lines,
      { yPercent: 100, opacity: 0 },
      {
        yPercent: 0,
        opacity: 1,
        duration: 0.9,
        ease: 'power2.out',
        stagger: 0.06,
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      },
    );

    let tagsTween: gsap.core.Tween | undefined;
    if (tags) {
      tagsTween = gsap.to(tags, {
        opacity: 1,
        y: 0,
        duration: 0.6,
        delay: 0.4,
        ease: 'power2.out',
        scrollTrigger: {
          trigger: section,
          start: 'top 80%',
        },
      });
    }

    return () => {
      timeline.scrollTrigger?.kill();
      timeline.kill();
      lineTween.scrollTrigger?.kill();
      lineTween.kill();
      tagsTween?.scrollTrigger?.kill();
      tagsTween?.kill();
    };
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

      <header className="site-header-bar flex items-center justify-between page-margin-x pt-[max(1.5rem,env(safe-area-inset-top))] sm:pt-8 pb-4 md:pb-6 shrink-0 z-20 gap-3">
        <Link
          data-cursor-expand
          to="/"
          className="font-display hover:opacity-80 transition-opacity duration-300 text-left flex-1 md:flex-none min-h-[44px] flex items-center shrink-0 min-w-0 text-[18px]"
          style={{ color: 'var(--color-oxford)' }}
        >
          Aethria
        </Link>
        <span
          className="font-mono text-[9px] uppercase whitespace-nowrap shrink-0 text-right"
          style={{
            color: 'rgba(0, 33, 71, 0.4)',
            letterSpacing: '0.14em',
          }}
        >
          INVESTMENT INTELLIGENCE
        </span>
      </header>

      <main className="flex-1 flex flex-col md:flex-row md:items-center min-h-0 shrink-0 min-w-0 overflow-x-hidden">
        {/* Left column */}
        <section
          className="home-hero-left page-margin-x order-1 flex md:w-[25%] flex-col justify-center py-8 sm:py-16 md:py-0 shrink-0"
          style={{ backgroundColor: 'var(--color-paper)' }}
        >
          <p
            className="font-mono text-[10px] uppercase"
            style={{
              color: 'rgba(0, 33, 71, 0.35)',
              letterSpacing: '0.1em',
            }}
          >
            2026 · EARLY ACCESS
          </p>
          <div style={{ height: 24 }} aria-hidden />
          <motion.p
            className="font-sans max-w-[32ch] md:max-w-none text-[16px] leading-relaxed"
            style={{
              color: 'rgba(0, 33, 71, 0.72)',
            }}
            variants={subtextVariants}
            initial="hidden"
            animate="visible"
          >
            Aethria runs a full evaluation pipeline autonomously. Scouts, scores, memos. Ready before a partner looks at the deal.
          </motion.p>
          <div style={{ height: 32 }} aria-hidden />
          <motion.div variants={ctaVariants} initial="hidden" animate="visible">
            <Link
              to="/request-access"
              data-cursor-expand
              className="font-mono uppercase inline-flex items-center justify-center w-full md:w-fit min-h-[44px] rounded-none bg-transparent transition-colors duration-200 ease-out hover:bg-[#002147] hover:text-[#F2F0EA]"
              style={{
                fontSize: 11,
                letterSpacing: '0.1em',
                color: 'rgba(0, 33, 71, 0.8)',
                border: '1px solid rgba(0, 33, 71, 0.6)',
                padding: '10px 24px',
              }}
            >
              REQUEST ACCESS
            </Link>
          </motion.div>
        </section>

        {/* Monolith — slides in from the right; headline fades in after */}
        <div
          data-cursor-expand
          className="order-2 relative flex items-center justify-center w-full md:flex-1 min-h-[360px] md:min-h-[70vh] aspect-auto p-6 sm:p-10 md:p-16 lg:p-20 xl:p-24 shrink-0 rounded-none home-monolith-in overflow-hidden"
          style={{ backgroundColor: 'var(--color-oxford)' }}
        >
          <div className="home-monolith-ambient" aria-hidden />
          <div className="home-monolith-grid" aria-hidden />
          <div className="home-monolith-frame-line" aria-hidden />
          <div
            className="absolute left-0 bottom-0 top-0 w-px pointer-events-none"
            style={{ backgroundColor: 'rgba(242, 240, 234, 0.12)' }}
            aria-hidden
          />
          <motion.h1
            data-cursor="headline"
            className="font-display text-[34px] sm:text-[2.85rem] lg:text-[3.5625rem] xl:text-[4.275rem] max-w-[18ch] md:max-w-[20ch] relative z-[1]"
            style={{ color: 'var(--color-paper)', lineHeight: 1.15 }}
            variants={headlineContainerVariants}
            initial="hidden"
            animate="visible"
          >
            {headlineText.split(' ').map((word, i, words) => (
              <span
                key={`${word}-${i}`}
                style={{
                  display: 'inline-block',
                  overflow: 'hidden',
                  paddingRight: i < words.length - 1 ? '0.35em' : 0,
                  paddingBottom: '0.2em',
                }}
              >
                <motion.span
                  variants={headlineWordVariants}
                  style={{ display: 'inline-block' }}
                >
                  {word}
                </motion.span>
              </span>
            ))}
          </motion.h1>
        </div>
      </main>
      <section
        className="flex min-h-[80vh] w-full flex-col overflow-hidden rounded-none"
        aria-labelledby="pipeline-heading"
      >
        <div className="w-full shrink-0" style={{ backgroundColor: 'var(--color-paper)' }}>
          <p id="pipeline-heading" className="pipeline-section-label page-margin-x pt-12 md:pt-14">
            THE PIPELINE
          </p>

          <div className="page-margin-x py-10 md:py-12">
            <div className="grid grid-cols-1 gap-0 divide-y divide-[rgba(0,33,71,0.1)] lg:grid-cols-4 lg:divide-x lg:divide-y-0 lg:items-stretch">
              {[
                {
                  label: 'SCOUT',
                  body: 'Proprietary agents monitor market signals continuously. By the time a deal reaches your desk, the groundwork is done.',
                  signal: 'discovery',
                },
                {
                  label: 'REVIEW',
                  body: 'Every opportunity evaluated across multiple dimensions. Conviction surfaces. Ambiguity is named, not buried.',
                  signal: 'conviction',
                },
                {
                  label: 'DECIDE',
                  body: 'Structured reasoning produces a clear position. Advance. Pass. Hold. No ambiguity, no delay.',
                  signal: 'precision',
                },
                {
                  label: 'PORTFOLIO',
                  body: 'Each decision informs the next. The system compounds its judgment over time.',
                  signal: 'continuity',
                },
              ].map(({ label, body, signal }) => (
                <div
                  key={label}
                  className="flex min-h-0 min-w-0 flex-col py-8 first:pt-0 last:pb-0 lg:h-full lg:py-0 lg:pl-8 lg:pr-8 lg:first:pl-0 lg:last:pr-0"
                >
                  <p
                    className="font-mono text-[10px] tracking-[0.14em]"
                    style={{ color: 'rgba(0, 33, 71, 0.4)' }}
                  >
                    {label}
                  </p>
                  <p className="font-sans mt-4 text-[14px] font-normal leading-[1.75] text-[rgba(0,33,71,0.68)]">
                    {body}
                  </p>
                  <div
                    className="pipeline-feature-signal font-sans mt-auto pt-6 italic text-[13px] text-[rgba(0,33,71,0.38)] lowercase"
                    style={{
                      fontWeight: 500,
                      letterSpacing: '0.01em',
                    }}
                  >
                    {signal}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div
          className="h-px w-full shrink-0"
          style={{
            background: 'linear-gradient(90deg, transparent 12%, var(--color-accent-soft) 50%, transparent 88%)',
          }}
          aria-hidden
        />

        <div
          className="flex min-h-[48vh] w-full flex-1 flex-col"
          style={{ backgroundColor: 'var(--color-oxford)' }}
        >
          <div className="intelligence-map-shell flex w-full flex-1 flex-col items-stretch justify-center page-margin-x py-12 md:py-16">
            <div className="flex w-full min-w-0 items-center justify-center">
              <IntelligenceMap variant="dark" />
            </div>
          </div>
        </div>
      </section>
      {/* Closing statement with conviction + live signal pills */}
      <section
        ref={closingRef}
        className="home-closing w-full page-margin-x pt-24 pb-24 relative overflow-hidden"
        style={{
          backgroundColor: 'var(--color-paper)',
          opacity: prefersReducedMotion || closingInView ? 1 : 0,
          transform: prefersReducedMotion || closingInView ? 'translateY(0)' : 'translateY(16px)',
          transition: prefersReducedMotion
            ? 'none'
            : 'opacity 500ms ease, transform 500ms cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <div className="flex flex-col lg:flex-row gap-10 lg:gap-16 items-start">
          <div className="flex-1 min-w-0">
            <h2 className="font-display text-[32px] md:text-[36px] max-w-full md:max-w-[540px] leading-tight" style={{ color: 'var(--color-oxford)', opacity: 0.9 }}>
              <span className="block overflow-hidden">
                <span className="inline-block translate-y-full conviction-line">
                  Run the pipeline.
                </span>
              </span>
              <span className="block overflow-hidden">
                <span className="inline-block translate-y-full conviction-line">
                  Keep the conviction.
                </span>
              </span>
            </h2>
            <p className="font-sans text-[15px] mt-6 max-w-[460px] leading-[1.75]" style={{ color: 'rgba(0, 33, 71, 0.58)' }}>
              Aethria discovers, scores, and recommends. You advance, pass, or hold.
            </p>
            <p className="font-mono text-[10px] uppercase tracking-[0.12em] mt-6 max-w-[480px] conviction-tags" style={{ color: 'rgba(0, 33, 71, 0.45)' }}>
              {[
                'Investment memos',
                'Escalations',
                'Concentration analytics',
                'Meta-agent',
                'Portfolio',
              ].map((tag) => (
                <span key={tag} className="conviction-tag">
                  {tag}
                </span>
              ))}
            </p>
            <Link
              to="/request-access"
              data-cursor-expand
              className="group font-mono text-[10px] uppercase tracking-[0.1em] cursor-pointer rounded-none transition-all duration-300 inline-flex items-center justify-center w-full md:w-fit min-h-[44px] h-10 px-6 bg-transparent border border-[var(--color-oxford)] md:border-[rgba(0,33,71,0.2)] text-[var(--color-oxford)] hover:bg-[var(--color-oxford)] hover:text-[var(--color-paper)] hover:border-[var(--color-oxford)] mt-8"
            >
              <span className="flex items-center justify-center">
                <span>REQUEST ACCESS</span>
                <span
                  className="inline-block overflow-hidden transition-all duration-200 ease-out origin-left flex-shrink-0 whitespace-nowrap w-2 group-hover:w-5"
                >
                  {'\u00A0›'}
                </span>
              </span>
            </Link>
          </div>

          {/* Right column: live signal pills */}
          <LiveSignalPills />
        </div>
        <span
          className="hidden md:block absolute left-1/2 top-1/2 font-display select-none pointer-events-none -translate-y-1/2 -translate-x-1/2 conviction-watermark"
          style={{
            fontSize: '22vw',
            lineHeight: 0.9,
            color: 'var(--color-oxford)',
            opacity: 0.04,
            whiteSpace: 'nowrap',
          }}
          aria-hidden
        >
          Conviction
        </span>
      </section>

      <DashboardPreview />

      <footer
        ref={footerRef}
        className="home-footer shrink-0 z-20 flex items-center justify-between page-margin-x pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] md:pt-5 md:pb-4 border-t"
        style={{ borderColor: 'rgba(0, 33, 71, var(--frame-opacity))', color: 'var(--color-oxford)', backgroundColor: 'var(--color-paper)' }}
      >
        <span className="font-sans text-[10px] md:text-[11px] tracking-wide" style={{ color: 'var(--color-oxford)', opacity: 0.65 }}>
          © Aethria
        </span>
        <span className="home-footer-tag font-mono text-[9px] uppercase tracking-[0.15em]" style={{ color: 'var(--color-oxford)', opacity: 0.5 }}>
          INVESTMENT INTELLIGENCE
        </span>
      </footer>
    </div>
  );
}

function LiveSignalPills() {
  const [dealsCount, setDealsCount] = useState(47);
  const [pipelineStatus, setPipelineStatus] = useState<'ACTIVE' | 'PROCESSING'>('ACTIVE');
  const [minutesAgo, setMinutesAgo] = useState(2);

  useEffect(() => {
    const dealsInterval = setInterval(() => {
      setDealsCount((prev) => prev + 1);
    }, 3500 + Math.random() * 2500);
    return () => clearInterval(dealsInterval);
  }, []);

  useEffect(() => {
    const statusInterval = setInterval(() => {
      setPipelineStatus((prev) => (prev === 'ACTIVE' ? 'PROCESSING' : 'ACTIVE'));
    }, 4000);
    return () => clearInterval(statusInterval);
  }, []);

  useEffect(() => {
    const minutesInterval = setInterval(() => {
      setMinutesAgo((prev) => prev + 1);
    }, 60000);
    return () => clearInterval(minutesInterval);
  }, []);

  return (
    <div className="flex-1 min-w-0 flex flex-col gap-4">
      {/* Pill 1 */}
      <SignalPill
        label="DEALS REVIEWED THIS CYCLE"
        value={`${dealsCount}`}
      />
      {/* Pill 2 */}
      <SignalPill
        label="PIPELINE STATUS"
        value={
          pipelineStatus === 'ACTIVE' ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '9999px',
                  backgroundColor: '#F2F0EA',
                  animation: 'pipeline-dot-pulse 2s ease-in-out infinite',
                }}
              />
              <span>ACTIVE</span>
            </span>
          ) : (
            'PROCESSING'
          )
        }
      />
      {/* Pill 3 */}
      <SignalPill
        label="LAST MEMO GENERATED"
        value={`${minutesAgo} min ago`}
      />
    </div>
  );
}

interface SignalPillProps {
  label: string;
  value: React.ReactNode;
}

function SignalPill({ label, value }: SignalPillProps) {
  return (
    <div
      className="signal-pill group flex items-center justify-between py-5 px-6 relative overflow-hidden border border-[rgba(0,33,71,0.14)]"
    >
      <div
        style={{
          fontFamily: '"Space Mono", monospace',
          fontSize: 10,
          letterSpacing: '0.18em',
          textTransform: 'uppercase',
          color: 'rgba(0, 33, 71, 0.5)',
        }}
      >
        {label}
      </div>
      <div className="font-sans text-[13px] font-medium tabular-nums" style={{ color: 'var(--color-oxford)' }}>
        {value}
      </div>
    </div>
  );
}
