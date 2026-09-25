import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type {
  CounterfactualProposal,
  FundHypothesis,
  FundObservation,
} from '../../api/fundIntelligence';
import {
  formatObservationFamily,
  formatObservationSegment,
  observationEvidenceLabel,
  observationStatement,
  selectLeadHypothesis,
  selectLeadObservation,
  sufficiencyLabel,
} from '../../lib/fundIntelligencePresentation';
import { useFundReplayPreview, type FundIntelligenceData } from '../../hooks/useFundIntelligence';
import { useFocusTrap, usePrefersReducedMotion } from '../../hooks';
import EmptyState from '../EmptyState';

type InspectorSelection =
  | { kind: 'observation'; item: FundObservation }
  | { kind: 'hypothesis'; item: FundHypothesis }
  | null;

function SignalMeta({
  item,
  hypothesis = false,
}: {
  item: FundObservation | FundHypothesis;
  hypothesis?: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-phi-3 gap-y-phi-1 type-meta text-oxford/65">
      <span>{hypothesis ? 'Hypothesis' : formatObservationSegment(item.segment)}</span>
      <span aria-hidden>·</span>
      <span>{item.sample_size} episodes</span>
      <span aria-hidden>·</span>
      <span>{sufficiencyLabel(item.sufficiency)}</span>
    </div>
  );
}

/**
 * Supporting vs contradictory as one soft split bar: oxford for the weight of
 * support, escalation for what cuts against it. Counts sit beneath in mono.
 */
function EvidenceBalance({ item }: { item: FundObservation | FundHypothesis }) {
  const supporting = item.supporting_case_ids.length;
  const contradictory = item.contradictory_case_ids.length;
  return (
    <div className="flex flex-col gap-phi-2" aria-label={observationEvidenceLabel(item)}>
      <div className="flex h-[6px] w-full gap-[2px] overflow-hidden rounded-full bg-oxford/[0.08]" aria-hidden>
        {supporting ? <span className="rounded-full bg-oxford" style={{ flex: supporting }} /> : null}
        {contradictory ? <span className="rounded-full bg-escalation" style={{ flex: contradictory }} /> : null}
      </div>
      <div className="flex items-center justify-between gap-phi-3 type-meta text-oxford/55">
        <span>{supporting} supporting</span>
        <span>{contradictory} contradictory</span>
      </div>
    </div>
  );
}

const QUIET_LINK = 'type-action w-fit text-left text-oxford/55 transition-colors hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30';

/** A secondary signal as a clickable row inside the tinted side panel. */
function SignalRow({ statement, meta, item, onInspect }: { statement: string; meta: string; item: FundObservation | FundHypothesis; onInspect: () => void }) {
  return (
    <button
      type="button"
      onClick={onInspect}
      className="flex w-full flex-col gap-phi-2 rounded-[12px] px-phi-3 py-phi-3 text-left transition-colors hover:bg-oxford/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-oxford/30"
    >
      <span className="type-body-sm leading-relaxed text-oxford">{statement}</span>
      <span className="flex items-baseline justify-between gap-phi-3 type-meta text-oxford/55">
        <span>{meta}</span>
        <span className="tabular-nums">{item.supporting_case_ids.length} / {item.contradictory_case_ids.length}</span>
      </span>
    </button>
  );
}

function LoadingSurface({ label }: { label: string }) {
  return (
    <div className="flex flex-col gap-phi-4 px-phi-4 py-phi-6" aria-busy="true" aria-label={`Loading ${label}`}>
      <div className="h-3 w-32 animate-pulse bg-oxford/10" />
      <div className="h-10 max-w-2xl animate-pulse bg-oxford/10" />
      <div className="h-3 max-w-xl animate-pulse bg-oxford/10" />
      <div className="grid gap-phi-4 md:grid-cols-3">
        {[1, 2, 3].map((item) => <div key={item} className="h-24 animate-pulse border-t border-oxford/10" />)}
      </div>
    </div>
  );
}

function ErrorSurface({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col gap-phi-3 border-l-2 border-escalation/40 px-phi-4 py-phi-6" role="alert">
      <p className="type-label-section">{label} unavailable</p>
      <p className="type-body-sm max-w-xl text-oxford/65">Aethria could not load this historical readout. No decision records were changed.</p>
      <button type="button" onClick={onRetry} className="type-action w-fit border-b border-oxford/25 pb-0.5 text-oxford/70 hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30">
        Retry
      </button>
    </div>
  );
}

/** The lead observation, set as the tab's headline with its evidence beneath. */
function LeadObservation({ item, onInspect }: { item: FundObservation; onInspect: () => void }) {
  return (
    <article className="flex flex-col gap-phi-5">
      <span className="type-label-section">{formatObservationFamily(item.observation_type)}</span>
      <p className="type-display max-w-[30ch] text-[clamp(24px,2.3vw,34px)] font-medium leading-[1.16] text-oxford">
        {observationStatement(item)}
      </p>
      <div className="flex max-w-[34rem] flex-col gap-phi-4">
        <EvidenceBalance item={item} />
        <SignalMeta item={item} />
      </div>
      <button type="button" onClick={onInspect} className={QUIET_LINK}>
        Inspect evidence →
      </button>
    </article>
  );
}

function Provenance({ item }: { item: FundObservation }) {
  if (item.interpretation_as_of === 'none_available' || !item.interpretation_provenance.length) {
    return <p className="type-meta text-oxford/65">No retrospective interpretation is attached to these observations.</p>;
  }
  const provenance = item.interpretation_provenance[0];
  return (
    <p className="type-meta leading-relaxed text-oxford/65">
      Retrospective interpretation provenance · version {provenance?.version ?? '—'}
      {provenance?.source ? ` · ${provenance.source.replace(/_/g, ' ')}` : ''}
    </p>
  );
}

function EvidenceList({ label, ids }: { label: string; ids: string[] }) {
  return (
    <div className="flex flex-col gap-phi-2">
      <p className="type-label-section">{label} · {ids.length}</p>
      {ids.length ? (
        <ul className="flex flex-col gap-phi-1">
          {ids.map((id) => <li key={id} className="type-meta text-oxford/65">Decision reference · {id}</li>)}
        </ul>
      ) : <p className="type-meta text-oxford/65">None recorded</p>}
    </div>
  );
}

function Inspector({ selection, onClose, proposal }: { selection: InspectorSelection; onClose: () => void; proposal?: CounterfactualProposal }) {
  const titleRef = useRef<HTMLHeadingElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);
  const replay = useFundReplayPreview(selection?.kind === 'hypothesis' ? selection.item.hypothesis_id : null);
  const reduceMotion = usePrefersReducedMotion();

  useEffect(() => {
    restoreRef.current = document.activeElement as HTMLElement | null;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      restoreRef.current?.focus();
    };
  }, [onClose]);

  useFocusTrap(Boolean(selection), dialogRef);

  useEffect(() => {
    if (selection) titleRef.current?.focus();
  }, [selection]);

  // Both branches return an AnimatePresence at the same spot, so React keeps
  // one instance and the drawer can slide out with its last content.
  if (!selection) return <AnimatePresence>{null}</AnimatePresence>;
  const isHypothesis = selection.kind === 'hypothesis';
  const item = selection.item;
  const hypothesisItem = isHypothesis ? selection.item as FundHypothesis : null;
  const observationItem = !isHypothesis ? selection.item as FundObservation : null;
  return (
    <AnimatePresence>
    <motion.div
      key="fund-inspector"
      className="fixed inset-0 z-40"
      role="presentation"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.24, ease: [0.16, 1, 0.3, 1] }}
    >
      <button type="button" className="absolute inset-0 h-full w-full cursor-default bg-oxford/15" aria-label="Close evidence inspector" onClick={onClose} />
      <motion.aside
        ref={dialogRef}
        initial={reduceMotion ? false : { x: 48 }}
        animate={{ x: 0 }}
        exit={reduceMotion ? undefined : { x: 48 }}
        transition={{ duration: reduceMotion ? 0 : 0.32, ease: [0.16, 1, 0.3, 1] }}
        className="absolute inset-y-0 right-0 flex w-full max-w-[460px] flex-col overflow-y-auto bg-paper" role="dialog" aria-modal="true" aria-labelledby="fund-inspector-title">
        <header className="flex items-start justify-between gap-phi-4 border-b border-oxford/10 px-phi-5 py-phi-5">
          <div>
            <p className="type-label-section">{isHypothesis ? 'Hypothesis basis' : 'Observation evidence'}</p>
            <h2 ref={titleRef} tabIndex={-1} id="fund-inspector-title" className="mt-phi-2 type-display text-[clamp(20px,2.2vw,29px)] leading-tight text-oxford">
              {isHypothesis ? hypothesisItem?.statement : observationStatement(observationItem as FundObservation)}
            </h2>
          </div>
          <button type="button" onClick={onClose} className="type-action shrink-0 px-phi-2 py-phi-1 text-oxford/65 hover:text-oxford focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-oxford/30" aria-label="Close evidence inspector">Close</button>
        </header>
        <div className="flex flex-col gap-phi-6 px-phi-5 py-phi-5">
          <EvidenceBalance item={item} />
          <SignalMeta item={item} hypothesis={isHypothesis} />
          {observationItem ? <Provenance item={observationItem} /> : null}
          <div className="grid gap-phi-5 sm:grid-cols-2">
            <EvidenceList label="Supporting" ids={item.supporting_case_ids} />
            <EvidenceList label="Contradictory" ids={item.contradictory_case_ids} />
          </div>
          <div className="flex flex-col gap-phi-2 border-t border-oxford/10 pt-phi-4">
            <p className="type-label-section">Historical scope</p>
            <p className="type-meta text-oxford/65">{item.time_window.from ?? 'Unknown'} → {item.time_window.to ?? 'Unknown'}</p>
            <p className="type-meta leading-relaxed text-oxford/65">Thesis: {item.thesis_versions.join(', ') || 'Not recorded'}</p>
            <p className="type-meta leading-relaxed text-oxford/65">Policy: {item.policy_versions.join(', ') || 'Not recorded'}</p>
          </div>
          <div className="flex flex-col gap-phi-2 border-t border-oxford/10 pt-phi-4">
            <p className="type-label-section">Limitations</p>
            <ul className="flex flex-col gap-phi-2">
              {item.limitations.map((limitation) => <li key={limitation} className="type-note leading-relaxed text-oxford/65">{limitation}</li>)}
            </ul>
          </div>
          {isHypothesis ? (
            <div className="flex flex-col gap-phi-3 border-t border-dashed border-oxford/20 pt-phi-4">
              <p className="type-label-section">Governed status</p>
              <div className="flex flex-wrap gap-x-phi-4 gap-y-phi-2 type-meta text-oxford/65">
                <span>Replay: {replay.isLoading ? 'Checking…' : replay.isError ? 'Unavailable' : replay.data?.replay_status === 'not_replayable' ? 'Not replayable' : 'Not evaluated'}</span>
                <span>Counterfactual: {proposal?.proposal_status === 'insufficient_basis' ? 'Insufficient basis' : proposal?.proposal_status ?? 'Not available'}</span>
              </div>
              {replay.data?.limitations.map((limitation) => <p key={limitation} className="type-note leading-relaxed text-oxford/65">{limitation}</p>)}
              <p className="type-meta text-oxford/65">No later outcome observations were used for this replay status.</p>
            </div>
          ) : null}
          {isHypothesis ? (
            <div className="flex flex-col gap-phi-2 border-t border-oxford/10 pt-phi-4">
              <p className="type-label-section">Source observations</p>
              {hypothesisItem?.source_observation_ids.map((id) => <p key={id} className="type-meta text-oxford/65">Observation reference · {id}</p>)}
            </div>
          ) : null}
        </div>
      </motion.aside>
    </motion.div>
    </AnimatePresence>
  );
}

/** Tab intro: a mono caption and one muted sentence. No rule beneath. */
function TabIntro({ label, body }: { label: string; body: string }) {
  return (
    <div className="flex flex-col gap-phi-2">
      <p className="type-label-section">{label}</p>
      <p className="type-body-sm max-w-2xl leading-relaxed text-oxford/55">{body}</p>
    </div>
  );
}

export function FundObservationsPanel({ data }: { data: FundIntelligenceData }) {
  const [selection, setSelection] = useState<InspectorSelection>(null);
  const reduceMotion = usePrefersReducedMotion();
  const lead = selectLeadObservation(data.observations);
  const secondary = data.observations.filter((item) => item.observation_id !== lead?.observation_id).slice(0, 3);
  const remaining = data.observations.filter((item) => item.observation_id !== lead?.observation_id && !secondary.some((secondaryItem) => secondaryItem.observation_id === item.observation_id)).slice(0, 6);

  if (data.observationsLoading && !data.observations.length) return <LoadingSurface label="fund intelligence" />;
  if (data.observationsError && !data.observations.length) return <ErrorSurface label="Fund Intelligence" onRetry={data.retryObservations} />;
  if (!data.observations.length) return <EmptyState label="Observed fund behavior" body="Aethria will reveal recurring patterns after enough completed historical decisions have accumulated." />;

  const inspect = (item: FundObservation) => () => setSelection({ kind: 'observation', item });

  // Same spread as the Mandate tab: the lead observation is the headline, the
  // other patterns sit in one soft panel beside it. Whitespace, not rules.
  return (
    <div className="flex flex-col gap-phi-7 px-phi-4 pb-phi-7 pt-phi-2">
      <TabIntro label="Observed fund behavior" body="Aethria’s readout of how this fund has behaved across recorded decisions." />
      {lead ? (
        <motion.div initial={reduceMotion ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="grid gap-phi-7 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:items-start">
          <LeadObservation item={lead} onInspect={inspect(lead)} />
          {secondary.length ? (
            <div className="rounded-[18px] bg-oxford/[0.04] p-phi-3">
              <p className="type-label-section px-phi-3 pb-phi-1 pt-phi-3">Other observed patterns</p>
              {secondary.map((item) => (
                <SignalRow key={item.observation_id} item={item} statement={observationStatement(item)} meta={formatObservationFamily(item.observation_type)} onInspect={inspect(item)} />
              ))}
            </div>
          ) : null}
        </motion.div>
      ) : null}
      {remaining.length ? (
        <section className="flex flex-col gap-phi-3">
          <div className="flex items-baseline justify-between gap-phi-3"><h2 className="type-label-section">Pattern field</h2><span className="type-meta text-oxford/55">Historical associations</span></div>
          <div className="grid gap-x-phi-5 gap-y-phi-1 md:grid-cols-2">
            {remaining.map((item) => (
              <SignalRow key={item.observation_id} item={item} statement={observationStatement(item)} meta={formatObservationFamily(item.observation_type)} onInspect={inspect(item)} />
            ))}
          </div>
        </section>
      ) : null}
      <Inspector selection={selection} onClose={() => setSelection(null)} />
    </div>
  );
}

export function FundHypothesesPanel({ data }: { data: FundIntelligenceData }) {
  const [selection, setSelection] = useState<InspectorSelection>(null);
  const lead = selectLeadHypothesis(data.hypotheses);
  const secondary = data.hypotheses.filter((item) => item.hypothesis_id !== lead?.hypothesis_id).slice(0, 2);
  const proposal = selection?.kind === 'hypothesis'
    ? data.proposals.find((item) => item.source_hypothesis_id === selection.item.hypothesis_id)
    : undefined;

  if (data.hypothesesLoading && !data.hypotheses.length) return <LoadingSurface label="fund learning" />;
  if (data.hypothesesError && !data.hypotheses.length) return <ErrorSurface label="Fund Learning" onRetry={data.retryHypotheses} />;
  if (!data.hypotheses.length) {
    return <EmptyState label="Possible reconsiderations" body={data.observations.length ? 'Aethria has observations, but none have reached the basis required for a hypothesis yet.' : 'Learning hypotheses will appear after descriptive observations have accumulated.'} />;
  }

  const family = (item: FundHypothesis) => item.hypothesis_family.replace(/_/g, ' ');

  return (
    <div className="flex flex-col gap-phi-7 px-phi-4 pb-phi-7 pt-phi-2">
      <TabIntro label="Possible reconsiderations" body="Tentative interpretations of repeated fund behavior. These do not change policy." />
      {lead ? (
        <div className="grid gap-phi-7 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] lg:items-start">
          <article className="flex flex-col gap-phi-5">
            <p className="type-label-section">Tentative hypothesis · {family(lead)}</p>
            <p className="type-display max-w-[30ch] text-[clamp(24px,2.3vw,34px)] font-medium leading-[1.16] text-oxford">{lead.statement}</p>
            <SignalMeta item={lead} hypothesis />
            <button type="button" onClick={() => setSelection({ kind: 'hypothesis', item: lead })} className={QUIET_LINK}>Inspect basis →</button>
          </article>
          <div className="flex flex-col gap-phi-5 rounded-[18px] bg-oxford/[0.04] p-phi-5">
            <span className="type-label-section">Basis</span>
            <EvidenceBalance item={lead} />
            <div className="flex flex-col gap-phi-1 type-body-sm text-oxford/55"><span>Descriptive association</span><span>{sufficiencyLabel(lead.sufficiency)}</span><span>Replay status available on inspection</span></div>
          </div>
        </div>
      ) : null}
      {secondary.length ? (
        <section className="flex flex-col gap-phi-3">
          <h2 className="type-label-section">Other possible reconsiderations</h2>
          <div className="grid gap-x-phi-5 gap-y-phi-1 md:grid-cols-2">
            {secondary.map((item) => (
              <SignalRow key={item.hypothesis_id} item={item} statement={item.statement} meta={`${family(item)} · ${sufficiencyLabel(item.sufficiency)}`} onInspect={() => setSelection({ kind: 'hypothesis', item })} />
            ))}
          </div>
        </section>
      ) : null}
      <Inspector selection={selection} proposal={proposal} onClose={() => setSelection(null)} />
    </div>
  );
}
