import { useMemo } from 'react';
import { motion, type Variants } from 'framer-motion';
import CountUp from './CountUp';
import { usePrefersReducedMotion } from '../hooks';
import { tokens } from '../design-system/tokens';
import {
  computeConfiguredScore,
  createDefaultFundConfiguration,
  type FundConfiguration,
} from '../lib/fundConfiguration';
import type { Startup, SingleReview } from '../types/startup';

/**
 * The Decision Stage — the dominant object of the Flow workspace.
 *
 * The whole product funnels into one act: make a judgment. The stage gives
 * that act its gravity: one huge conviction number, the state of the call,
 * the company's name at display scale, and the three instruments that say
 * how the machine arrived here (thesis fit, reviewer agreement, partner
 * confidence). Everything else lives in the memo below it.
 */

interface DecisionStageProps {
  startup: Startup;
  fundConfiguration?: FundConfiguration;
  /** Quiet utility action (e.g. IC pack PDF) — sits on the kicker line, not in its own header band. */
  action?: React.ReactNode;
}

/** Conviction on the canonical 0–100 scale — same semantics as the queue. */
function convictionScore(startup: Startup, config: FundConfiguration): number | null {
  const agg = startup.review?.overall_score ?? startup.review?.aggregate_score;
  if (typeof agg === 'number' && Number.isFinite(agg)) {
    return Math.round(agg <= 10 ? agg * 10 : agg);
  }
  const configured = computeConfiguredScore(startup, config);
  return Number.isFinite(configured) && configured > 0 ? Math.round(configured) : null;
}

function reviewerMean(rv: SingleReview): number | null {
  const vals = [rv.market_score, rv.product_score, rv.technical_score, rv.execution_score, rv.defensibility_score]
    .map((v) => Number(v))
    .filter((v) => Number.isFinite(v));
  if (!vals.length) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

type StageTone = 'ink' | 'escalation' | 'muted';

function stageState(startup: Startup): { word: string; tone: StageTone } {
  const ruled = startup.human_resolution?.decision;
  if (ruled && startup.human_resolution?.resolved_at) {
    const word = ruled === 'YES' ? 'RULED — INVEST' : ruled === 'NO' ? 'RULED — PASS' : 'RULED — MONITOR';
    return { word, tone: 'ink' };
  }
  if (startup.partner?.human_review_required) {
    return { word: 'NEEDS YOUR RULING', tone: 'escalation' };
  }
  const rec = startup.partner?.recommendation;
  if (rec) return { word: `PARTNER VERDICT — ${rec}`, tone: 'ink' };
  if (startup.review) return { word: 'AWAITING PARTNER', tone: 'muted' };
  return { word: 'IN REVIEW', tone: 'muted' };
}

const STAGE_ITEM: Variants = {
  hidden: { opacity: 0, transform: 'translateY(10px)' },
  visible: {
    opacity: 1,
    transform: 'translateY(0px)',
    transition: { duration: 0.45, ease: tokens.motion.ease },
  },
};

function Track({ pct, split = false, delay = 0 }: { pct: number; split?: boolean; delay?: number }) {
  const reduceMotion = usePrefersReducedMotion();
  const clamped = Math.min(1, Math.max(0, pct / 100));
  return (
    <div className="relative h-px w-full bg-oxford/10">
      <motion.div
        className={`absolute inset-0 origin-left ${split ? 'bg-escalation/55' : 'bg-oxford/45'}`}
        initial={reduceMotion ? { scaleX: clamped } : { scaleX: 0 }}
        animate={{ scaleX: clamped }}
        transition={{ duration: 0.9, delay: reduceMotion ? 0 : delay, ease: [0.16, 1, 0.3, 1] }}
      />
    </div>
  );
}

function Instrument({
  label,
  reading,
  children,
}: {
  label: string;
  reading: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-phi-2">
      <div className="flex items-baseline justify-between gap-phi-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/40">{label}</span>
        <span className="whitespace-nowrap font-mono text-[11px] font-semibold tabular-nums tracking-[0.04em] text-oxford/75">
          {reading}
        </span>
      </div>
      {children}
    </div>
  );
}

export default function DecisionStage({ startup, fundConfiguration, action }: DecisionStageProps) {
  const reduceMotion = usePrefersReducedMotion();
  const config = fundConfiguration ?? createDefaultFundConfiguration();

  const score = useMemo(() => convictionScore(startup, config), [startup, config]);
  const state = stageState(startup);

  const kicker = [startup.scout.sector, startup.scout.funding_stage, startup.scout.location]
    .map((v) => (v ?? '').toString().trim())
    .filter(Boolean)
    .join(' · ');

  const standfirst = (
    startup.scout.one_line ??
    startup.partner?.snapshot?.key_signal ??
    startup.partner?.thesis ??
    startup.review?.overall_summary ??
    ''
  )
    .toString()
    .replace(/\s+/g, ' ')
    .trim();

  // ── Instruments ────────────────────────────────────────────────────────────
  const thesisTen = useMemo(() => {
    const raw = startup.review?.thesis_alignment_score;
    if (raw == null || !Number.isFinite(Number(raw))) return null;
    const n = Number(raw);
    return n <= 1 ? n * 10 : n;
  }, [startup.review?.thesis_alignment_score]);

  const reviewerMeans = useMemo(
    () =>
      (startup.review?.reviews ?? [])
        .map(reviewerMean)
        .filter((v): v is number => v != null),
    [startup.review?.reviews],
  );
  const spread = reviewerMeans.length >= 2 ? Math.max(...reviewerMeans) - Math.min(...reviewerMeans) : null;
  const split = startup.review?.reviewer_disagreement === true || (spread != null && spread >= 2);

  const confidencePct =
    typeof startup.partner?.confidence === 'number'
      ? Math.round(Math.max(0, Math.min(1, startup.partner.confidence)) * 100)
      : null;

  const hasInstruments = thesisTen != null || reviewerMeans.length > 0 || confidencePct != null;

  const stateToneClass =
    state.tone === 'escalation'
      ? 'text-escalation'
      : state.tone === 'muted'
        ? 'text-oxford/40'
        : 'text-oxford/80';

  const focalQuestion = (startup.review?.aethria_view?.focal_question ?? '').toString().trim();

  return (
    <motion.section
      aria-label={startup.scout.name}
      className="pt-phi-1 pb-phi-7"
      initial={reduceMotion ? false : 'hidden'}
      animate="visible"
      variants={reduceMotion ? undefined : { hidden: {}, visible: { transition: { staggerChildren: 0.07 } } }}
    >
      {/* Compression: one quiet line of context, with the utility action on its right. */}
      {kicker || action ? (
        <motion.div
          variants={STAGE_ITEM}
          className="flex min-w-0 items-baseline justify-between gap-phi-4"
        >
          <p className="min-w-0 truncate font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/[0.38]">
            {kicker}
          </p>
          {action ? <div className="shrink-0">{action}</div> : null}
        </motion.div>
      ) : null}

      {/* Release: the number owns the canvas. */}
      <motion.div variants={STAGE_ITEM} className="mt-phi-6 flex items-end gap-phi-4">
        <span
          className="font-mono font-bold leading-[0.85] tracking-[-0.05em] tabular-nums text-oxford"
          style={{ fontSize: 'clamp(72px, 9.5vw, 148px)' }}
          aria-label={score != null ? `Conviction ${score} of 100` : 'Conviction forming'}
        >
          {score != null ? <CountUp to={score} delay={0.15} reduceMotion={reduceMotion} /> : '—'}
        </span>
        <span className="pb-[6px] font-mono text-[10px] uppercase leading-[1.5] tracking-[0.12em] text-oxford/[0.38]">
          /100
          <br />
          conviction
        </span>
      </motion.div>

      {/* The state of the call — the moment of tension. */}
      <motion.p
        variants={STAGE_ITEM}
        className={`mt-phi-5 font-mono text-[13px] font-bold uppercase tracking-[0.18em] ${stateToneClass}`}
      >
        {state.word}
      </motion.p>

      {/* The subject — sans matches the selected docket row; size stays stage scale. */}
      <motion.h2
        variants={STAGE_ITEM}
        className="mt-phi-5 break-words font-sans font-semibold leading-[1.05] text-oxford"
        style={{ fontSize: 'clamp(34px, 3.8vw, 56px)' }}
      >
        {startup.scout.name}
      </motion.h2>

      {standfirst ? (
        <motion.p
          variants={STAGE_ITEM}
          className="mt-phi-4 max-w-[36rem] font-sans text-[16px] leading-[1.55] text-oxford/70"
        >
          {standfirst}
        </motion.p>
      ) : null}

      {/* The instruments: how the machine got here. */}
      {hasInstruments ? (
        <motion.div
          variants={STAGE_ITEM}
          className="mt-phi-7 grid grid-cols-1 gap-x-phi-6 gap-y-phi-4 border-t border-oxford/[0.08] pt-phi-5 sm:grid-cols-3"
        >
          {thesisTen != null ? (
            <Instrument label="Thesis fit" reading={`${thesisTen.toFixed(1)} /10`}>
              <Track pct={thesisTen * 10} delay={0.25} />
            </Instrument>
          ) : null}

          {reviewerMeans.length > 0 ? (
            <Instrument
              label={`Reviewers · ${reviewerMeans.length}`}
              reading={split ? `SPLIT${spread != null ? ` · Δ${spread.toFixed(1)}` : ''}` : 'ALIGNED'}
            >
              {/* Agreement map: each reviewer's mean as a tick on the 0–10 axis. */}
              <div className="relative h-px w-full bg-oxford/10" aria-hidden>
                {reviewerMeans.map((mean, i) => (
                  <motion.span
                    key={i}
                    className={`absolute top-[-4px] h-[11px] w-[2px] ${split ? 'bg-escalation/70' : 'bg-oxford/70'}`}
                    style={{ left: `${Math.min(100, Math.max(0, mean * 10))}%` }}
                    initial={reduceMotion ? { opacity: 1 } : { opacity: 0, transform: 'translateY(4px)' }}
                    animate={{ opacity: 1, transform: 'translateY(0px)' }}
                    transition={{ duration: 0.4, delay: reduceMotion ? 0 : 0.3 + i * 0.08, ease: tokens.motion.ease }}
                  />
                ))}
              </div>
            </Instrument>
          ) : null}

          {confidencePct != null ? (
            <Instrument label="Partner confidence" reading={`${confidencePct}%`}>
              <Track pct={confidencePct} delay={0.35} />
            </Instrument>
          ) : null}
        </motion.div>
      ) : null}

      {/* What decides it — the single question the deal hinges on. */}
      {focalQuestion ? (
        <motion.div variants={STAGE_ITEM} className="mt-phi-5 border-l-2 border-oxford/25 pl-phi-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-oxford/[0.38]">What decides it</p>
          <p className="mt-phi-1 max-w-[34rem] font-sans text-[14px] leading-[1.5] text-oxford/80">
            {focalQuestion}
          </p>
        </motion.div>
      ) : null}
    </motion.section>
  );
}
