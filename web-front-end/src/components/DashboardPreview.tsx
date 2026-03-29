import { useEffect, useRef, useState } from 'react';
import { motion, useAnimation, Variants } from 'framer-motion';

const OXFORD = '#002147';
const PAPER = '#F2F0EA';

const containerVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
};

const featureVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: 0.1 * index, duration: 0.4, ease: [0.16, 1, 0.3, 1] },
  }),
};

const memoCardVariants: Variants = {
  hidden: { opacity: 0, x: 28 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.65, delay: 0.2, ease: [0.16, 1, 0.3, 1] },
  },
};

const DIMENSION_SCORES: { label: string; score: string }[] = [
  { label: 'MARKET', score: '9/10' },
  { label: 'EXECUTION', score: '8/10' },
  { label: 'PRODUCT', score: '8/10' },
  { label: 'TECHNICAL', score: '9/10' },
  { label: 'DEFENSIBILITY', score: '7/10' },
];

export default function DashboardPreview() {
  const ref = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);
  const controls = useAnimation();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    if (inView) {
      controls.start('visible');
    }
  }, [inView, controls]);

  return (
    <section
      ref={ref}
      style={{
        background: `linear-gradient(180deg, ${PAPER} 0%, var(--color-paper-bright) 38%, ${PAPER} 100%)`,
        paddingTop: 120,
        paddingBottom: 120,
      }}
      className="w-full relative overflow-hidden"
    >
      <motion.div
        className="page-margin-x flex flex-col md:flex-row md:items-center gap-12 md:gap-16"
        variants={containerVariants}
        initial="hidden"
        animate={controls}
      >
        <div className="w-full md:w-[40%] max-w-xl shrink-0">
          <p
            style={{
              fontFamily: '"Space Mono", monospace',
              fontSize: 11,
              letterSpacing: '0.18em',
              textTransform: 'uppercase',
              color: 'rgba(0, 33, 71, 0.6)',
              marginBottom: 12,
            }}
          >
            INSIDE AETHRIA
          </p>
          <h2
            className="font-display"
            style={{
              fontSize: 'clamp(2rem, 4vw, 2.75rem)',
              lineHeight: 1.12,
              color: OXFORD,
              marginBottom: 24,
            }}
          >
            The system thinks
            <br />
            before you decide.
          </h2>

          <div className="flex flex-col gap-8 mt-6">
            {[
              {
                label: 'INVESTMENT MEMO',
                body: 'A complete reasoning chain produced autonomously. Thesis alignment, risk surface, and conviction score before a partner reviews the deal.',
              },
              {
                label: 'ESCALATION QUEUE',
                body: 'Edge cases surfaced with precision. Disagreement signals and confidence gaps flagged for human judgment, not buried in the pipeline.',
              },
              {
                label: 'PORTFOLIO SIGNALS',
                body: 'Concentration risk, sector exposure, and clustering patterns across active positions. Continuously updated.',
              },
            ].map((item, index) => (
              <motion.div
                key={item.label}
                custom={index}
                variants={featureVariants}
                initial="hidden"
                animate={controls}
                style={{
                  borderLeft: '1px solid rgba(0, 33, 71, 0.3)',
                  paddingLeft: 12,
                }}
              >
                <p
                  style={{
                    fontFamily: '"Space Mono", monospace',
                    fontSize: 11,
                    letterSpacing: '0.16em',
                    textTransform: 'uppercase',
                    color: OXFORD,
                    marginBottom: 6,
                  }}
                >
                  {item.label}
                </p>
                <p
                  className="font-sans text-[14px] leading-[1.65] text-[rgba(0,33,71,0.72)]"
                >
                  {item.body}
                </p>
              </motion.div>
            ))}
          </div>
        </div>

        <div className="flex w-full shrink-0 justify-center md:flex-1 md:justify-end md:pr-[min(4rem,5vw)]">
          <motion.article
            variants={memoCardVariants}
            initial="hidden"
            animate={controls}
            className="dashboard-memo-card w-full max-w-[540px] shrink-0 rounded-none md:w-[540px] md:max-w-[540px]"
            style={{
              backgroundColor: PAPER,
              border: '1px solid rgba(0, 33, 71, 0.09)',
              borderRadius: 0,
              padding: 36,
              boxSizing: 'border-box',
            }}
            aria-label="Investment memo preview"
          >
            <h3
              className="font-sans font-semibold tracking-tight"
              style={{
                fontSize: 24,
                color: OXFORD,
                lineHeight: 1.2,
              }}
            >
              Meridian Systems
            </h3>
            <p
              className="mt-1.5"
              style={{
                fontFamily: '"Space Mono", monospace',
                fontSize: 11,
                letterSpacing: '0.1em',
                color: 'rgba(0, 33, 71, 0.4)',
              }}
            >
              B2B INFRASTRUCTURE · SERIES A
            </p>

            <div
              style={{
                marginTop: 24,
                marginBottom: 24,
                height: 1,
                backgroundColor: 'rgba(0, 33, 71, 0.08)',
              }}
              aria-hidden
            />

            <p
              style={{
                fontFamily: '"Space Mono", monospace',
                fontSize: 11,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'rgba(0, 33, 71, 0.5)',
                marginBottom: 6,
              }}
            >
              INVESTMENT JUDGMENT
            </p>
            <p
              className="font-sans font-semibold tracking-[-0.03em]"
              style={{
                fontSize: 32,
                color: OXFORD,
                lineHeight: 1.15,
              }}
            >
              STRONG.
            </p>
            <p
              className="font-sans font-normal mt-[14px] text-[15px] leading-[1.6] text-[rgba(0,33,71,0.72)]"
            >
              Clear market timing, credible founding team, and defensible infrastructure play. Conviction is high pending
              final diligence on unit economics.
            </p>

            <div
              style={{
                marginTop: 24,
                marginBottom: 24,
                height: 1,
                backgroundColor: 'rgba(0, 33, 71, 0.08)',
              }}
              aria-hidden
            />

            <p
              style={{
                fontFamily: '"Space Mono", monospace',
                fontSize: 11,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'rgba(0, 33, 71, 0.5)',
                marginBottom: 18,
              }}
            >
              DIMENSION SCORES
            </p>
            <div className="grid w-full grid-cols-5 gap-x-2 gap-y-2 sm:gap-x-3">
              {DIMENSION_SCORES.map((row) => (
                <div
                  key={`dim-label-${row.label}`}
                  className="flex min-w-0 items-end justify-center text-center"
                >
                  <p
                    style={{
                      fontFamily: '"Space Mono", monospace',
                      fontSize: 10,
                      letterSpacing: '0.05em',
                      lineHeight: 1.2,
                      color: 'rgba(0, 33, 71, 0.4)',
                      margin: 0,
                      hyphens: 'auto',
                      overflowWrap: 'break-word',
                      wordBreak: 'normal',
                    }}
                  >
                    {row.label}
                  </p>
                </div>
              ))}
              {DIMENSION_SCORES.map((row) => (
                <p
                  key={`dim-score-${row.label}`}
                  className="min-w-0 text-center"
                  style={{
                    fontFamily: '"Space Mono", monospace',
                    fontSize: 24,
                    fontWeight: 700,
                    color: OXFORD,
                    lineHeight: 1.1,
                  }}
                >
                  {row.score}
                </p>
              ))}
            </div>
          </motion.article>
        </div>
      </motion.div>
    </section>
  );
}
