import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { AnimatePresence, motion, useIsPresent } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { SpineNavButton, WorkspaceGlyph } from "./SystemBar";
import LookupReadyNotice, { type LookupReadyNoticeProps } from "./LookupReadyNotice";
import AgentLogoutModal from "./AgentLogoutModal";
import { useAgentLogoutFlow } from "../hooks/useAgentLogoutFlow";
import { usePrefersReducedMotion } from "../hooks";
import { transitionOrReduced } from "../design-system/motion";
import { tokens } from "../design-system/tokens";
import type { ExecutionReadiness } from "./institutional/ExecutionReadinessPanel";
import {
  SETTINGS_GROUPS,
  SETTINGS_SECTIONS,
  type SectionId,
  type SettingsPersistenceGroup,
} from "../settings/settingsModel";
import SettingsPage from "../settings/SettingsPage";
import OperationsStrip from "../settings/OperationsStrip";
import { fetchSettings } from "../api/settings";
import { getQueryConfig } from "../lib/queryIntent";

export type SpinePipelineState = "Live" | "Idle" | "Off" | "Issue" | "Stopping";

export interface SpineTelemetry {
  /** Items awaiting a human ruling — the one number that matters. */
  pendingEscalations: number;
  /** Open / in-progress items (shown when nothing needs a ruling). */
  openInProgressCount: number;
  totalCount: number;
  agentDecidedCount: number;
  humanRuledCount: number;
  newCount: number;
  pipelineState: SpinePipelineState;
  /** Durable execution readiness is separate from whether pipeline agents are enabled. */
  executionReadiness?: ExecutionReadiness;
}

export interface SpineMandate {
  hasThesis: boolean;
  fundName: string;
  summaryLine: string;
  versionNumber: number | null;
  amendedAt?: string | null;
}

/**
 * A room (e.g. Settings) can take over the spine's contextual regions: its
 * nav replaces the workspace nav, its footer replaces telemetry + mandate.
 * Identity (top) and operator (bottom) never change — one rail, always.
 */
export interface SpineOverride {
  nav: ReactNode;
  footer?: ReactNode;
}

interface AppSpineProps {
  telemetry: SpineTelemetry;
  mandate: SpineMandate;
  /** True while a Dispatch lookup runs in the background. */
  dispatchActive: boolean;
  dispatchReadyNotice: Omit<LookupReadyNoticeProps, 'placement' | 'className'>;
  onDispatch: () => void;
  override?: SpineOverride | null;
  /** Home owns the fixed settings/logout controls while this spine exits. */
  suppressFixedChrome?: boolean;
}

export const SPINE_WORKSPACES: Array<{
  href: string;
  label: string;
  shortcut: string;
}> = [
  { href: "/v1", label: "Home", shortcut: "1" },
  { href: "/v1/flow", label: "Flow", shortcut: "2" },
  { href: "/v1/portfolio", label: "Portfolio", shortcut: "3" },
  { href: "/v1/fund", label: "Fund", shortcut: "4" },
];

/** Reads the shared rail width so the Settings paper rail cannot drift from it. */
export const SPINE_WIDTH = "var(--spine-width)";

export function isSpineRouteActive(href: string, pathname: string): boolean {
  if (href === "/v1") {
    return pathname === "/v1" || pathname === "/v1/";
  }
  if (href === "/v1/flow") {
    return pathname.startsWith("/v1/flow") || pathname.startsWith("/v1/deal");
  }
  return pathname.startsWith(href);
}

/** Keep the outgoing spine's active workspace stable while Motion exits it. */
export function resolveSpinePathname(
  pathname: string,
  isPresent: boolean,
  lastPresentPathname: string,
): string {
  return isPresent ? pathname : lastPresentPathname;
}

/** Instrument readout — mirrors room headers, scaled for the oxford rail. */
function SpineReadout({
  label,
  value,
  tone = "default",
  onClick,
}: {
  label: string;
  value: string;
  tone?: "default" | "escalation";
  onClick?: () => void;
}) {
  const valueTone =
    tone === "escalation" ? "text-escalation-bright" : "text-white/[0.92]";
  const body = (
    <>
      <span
        className={`type-data text-[clamp(17px,1.35vw,21px)] leading-none ${valueTone}`}
      >
        {value}
      </span>
      <span className="type-label-section type-label-inverse mt-phi-1 leading-none">
        {label}
      </span>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex min-w-0 flex-col items-start text-left transition-opacity hover:opacity-80 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
      >
        {body}
      </button>
    );
  }

  return <div className="flex min-w-0 flex-col items-start">{body}</div>;
}

export function SettingsDock() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [panelSection, setPanelSection] = useState<SectionId | null>(null);
  const [panelGroup, setPanelGroup] = useState<SettingsPersistenceGroup | null>(
    null,
  );
  const [closing, setClosing] = useState(false);
  const [backSignal, setBackSignal] = useState(0);
  const reduceMotion = usePrefersReducedMotion();
  // Same ["settings"] cache the page and useSystemData share; only fetched once
  // the menu is opened. OperationsStrip writes its saves back into that cache.
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: () => fetchSettings().catch(() => null),
    ...getQueryConfig("STATIC"),
    enabled: settingsOpen,
  });
  const settingsMenuVariants = {
    hidden: { opacity: 0, y: 12, scale: 0.9 },
    visible: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.medium,
        ease: tokens.motion.ease,
        delayChildren: 0.03,
        staggerChildren: 0.04,
      }),
    },
    exit: {
      opacity: 0,
      y: 10,
      scale: 0.92,
      transition: transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.short,
        ease: tokens.motion.ease,
        when: 'afterChildren',
        staggerChildren: 0.02,
        staggerDirection: -1,
      }),
    },
  };
  const settingsMenuItemVariants = {
    hidden: { opacity: 0, y: 4 },
    visible: {
      opacity: 1,
      y: 0,
      transition: transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.short,
        ease: tokens.motion.ease,
      }),
    },
    exit: {
      opacity: 0,
      y: 4,
      transition: transitionOrReduced(reduceMotion, {
        duration: tokens.motion.duration.micro,
        ease: tokens.motion.ease,
      }),
    },
  };

  // Closing plays the open animation backwards (panel shrinks into the menu that
  // is already mounted underneath); the panel unmounts when it reaches the menu.
  useEffect(() => {
    if (!closing) return;
    const timer = window.setTimeout(
      () => {
        setPanelSection(null);
        setPanelGroup(null);
        setClosing(false);
      },
      reduceMotion ? 0 : 220,
    ); // matches aethria-settings-panel-shrink in index.css
    return () => window.clearTimeout(timer);
  }, [closing, reduceMotion]);

  const showBack = panelSection != null && !closing;

  return (
    <div
      className={`aethria-settings-dock${settingsOpen ? " is-open" : ""}${showBack ? " is-panel" : ""}`}
    >
      {panelSection ? (
        <div
          className={`aethria-settings-dock__pullout${closing ? " is-closing" : ""}`}
        >
          <SettingsPage
            embedded
            initialSection={panelSection}
            embeddedGroup={panelGroup ?? undefined}
            onClose={() => setClosing(true)}
            backSignal={backSignal}
          />
        </div>
      ) : null}
      <AnimatePresence initial={false}>
        {settingsOpen && (!panelSection || closing) ? (
          <motion.nav
            key="settings-categories"
            className="aethria-settings-dock__menu"
            aria-label="Settings categories"
            // Rises and scales out of the cog (see transform-origin in the CSS),
            // then lets each category follow in a quiet stagger.
            variants={settingsMenuVariants}
            initial={reduceMotion ? false : 'hidden'}
            animate="visible"
            exit="exit"
          >
            {SETTINGS_GROUPS.map((group) => {
              const firstSection = SETTINGS_SECTIONS.find(
                (section) => section.group === group.id,
              );
              if (!firstSection) return null;
              return (
                <motion.button
                  key={group.id}
                  type="button"
                  onClick={() => {
                    setPanelGroup(group.id);
                    setPanelSection(firstSection.id);
                  }}
                  className="aethria-settings-dock__item"
                  variants={settingsMenuItemVariants}
                  whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                >
                  {group.label}
                </motion.button>
              );
            })}
            {settingsQuery.data ? (
              <OperationsStrip
                variant="menu"
                settings={settingsQuery.data}
                storageUnavailable={false}
                onSettingsChange={() => undefined}
              />
            ) : null}
          </motion.nav>
        ) : null}
      </AnimatePresence>
      <motion.button
        type="button"
        className="aethria-settings-dock__toggle"
        aria-expanded={showBack ? undefined : settingsOpen}
        aria-label={
          showBack
            ? "Back to settings menu"
            : settingsOpen
              ? "Close settings categories"
              : "Open settings categories"
        }
        onClick={() => {
          if (panelSection) {
            if (!closing) setBackSignal((count) => count + 1);
            return;
          }
          setSettingsOpen((open) => !open);
          setPanelSection(null);
          setPanelGroup(null);
          setClosing(false);
        }}
        whileHover={reduceMotion ? undefined : { y: -1 }}
        whileTap={reduceMotion ? undefined : { scale: 0.94 }}
        transition={transitionOrReduced(reduceMotion, {
          duration: tokens.motion.duration.micro,
          ease: tokens.motion.ease,
        })}
      >
        <WorkspaceGlyph label="Settings" />
        <svg
          className="aethria-settings-dock__x"
          viewBox="0 0 18 18"
          fill="none"
          aria-hidden="true"
        >
          <path d="M4.5 4.5l9 9M13.5 4.5l-9 9" />
        </svg>
        <svg
          className="aethria-settings-dock__back"
          viewBox="0 0 18 18"
          fill="none"
          aria-hidden="true"
        >
          <path d="M11 3.5 5.5 9l5.5 5.5" />
        </svg>
      </motion.button>
    </div>
  );
}

const PIPELINE_TONE: Record<SpinePipelineState, { text: string; dot: string }> =
  {
    Live: { text: "text-white/[0.72]", dot: "bg-white signal-dot-breathe" },
    Idle: { text: "text-white/60", dot: "bg-white/35" },
    Off: { text: "text-white/60", dot: "bg-white/[0.18]" },
    Stopping: { text: "text-white/60", dot: "bg-white/40 pulse-soft" },
    Issue: {
      text: "text-escalation-bright",
      dot: "bg-escalation-bright escalation-dot-active",
    },
  };

/**
 * The spine — full-height oxford rail, present on every workspace. Carries the
 * product identity (wordmark), the three workspaces + Dispatch, the single
 * number that needs judgment, the active mandate, and the operator. Everything
 * else belongs to the workspace it serves.
 */
export default function AppSpine({
  telemetry,
  mandate,
  dispatchActive,
  dispatchReadyNotice,
  onDispatch,
  override,
  suppressFixedChrome = false,
}: AppSpineProps) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const isPresent = useIsPresent();
  const lastPresentPathname = useRef(pathname);
  if (isPresent) lastPresentPathname.current = pathname;
  const activePathname = resolveSpinePathname(
    pathname,
    isPresent,
    lastPresentPathname.current,
  );
  const hideFixedChrome =
    suppressFixedChrome || isSpineRouteActive('/v1', pathname);
  const reduceMotion = usePrefersReducedMotion();
  const {
    displayName,
    agentActionPending,
    agentActionError,
    requestLogout,
    logoutModalProps,
  } = useAgentLogoutFlow();

  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const tick = () => setTime(new Date());
    tick();
    const t = setInterval(tick, 60_000);
    return () => clearInterval(t);
  }, []);
  const timeShort = time.toLocaleTimeString("en-GB", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
  });
  const dateShort = time
    .toLocaleDateString("en-GB", { day: "numeric", month: "short" })
    .toUpperCase();

  const hasEscalations = telemetry.pendingEscalations > 0;
  const pipelineTone = PIPELINE_TONE[telemetry.pipelineState];

  return (
    <>
      <div className="aethria-spine-dock">
        <aside
          className="aethria-spine hidden lg:flex h-full min-h-0 flex-none flex-col justify-between bg-oxford px-phi-4 pb-phi-4 pt-phi-5"
          aria-label="Aethria"
          style={{ width: SPINE_WIDTH }}
        >
          <div className="flex min-h-0 flex-col gap-phi-4">
            {/* ── Identity ─────────────────────────────────────────── */}
            <div className="px-2">
              <Link
                to="/v1"
                className="font-wordmark text-[clamp(19px,1.5vw,24px)] font-medium leading-tight text-paper btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
              >
                Aethria
                <span className="wordmark-dot wordmark-dot--inverse">.</span>
              </Link>
              <p
                className="type-meta type-meta-inverse mt-phi-2 tabular-nums"
                aria-hidden
              >
                {timeShort} · {dateShort}
              </p>
            </div>

            {override ? (
              /* ── Room nav (e.g. Settings sections) ──────────────── */
              <nav
                className="flex min-h-0 flex-col gap-0.5 overflow-y-auto"
                aria-label="Section navigation"
              >
                {override.nav}
              </nav>
            ) : (
              /* ── Workspaces ─────────────────────────────────────── */
              <AnimatePresence initial={false}>
                <motion.nav
                  key="workspace-navigation"
                  className="flex flex-col gap-0.5"
                  aria-label="Workspaces"
                  initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
                  transition={transitionOrReduced(reduceMotion, {
                    duration: tokens.motion.duration.short,
                    ease: tokens.motion.ease,
                  })}
                >
                  {SPINE_WORKSPACES.map((item, index) => (
                    <SpineNavButton
                      key={item.href}
                      label={item.label}
                      active={isSpineRouteActive(item.href, activePathname)}
                      ariaPressed={isSpineRouteActive(item.href, activePathname)}
                      onClick={() => navigate(item.href)}
                      shortcut={item.shortcut}
                      compact
                      surface="oxford"
                      indicatorId="spine-workspaces-active"
                      motionIndex={index}
                    />
                  ))}
                </motion.nav>
              </AnimatePresence>
            )}
          </div>

          <div className="flex min-h-0 flex-col gap-phi-4">
            {override ? (
              (override.footer ?? null)
            ) : (
              <>
                {/* ── Pipeline readouts + mandate — a ruled section, not a slab ── */}
                <section
                  aria-label="Pipeline and mandate"
                  className="border-t border-white/10 px-2 pt-phi-4"
                >
                  <div className="flex items-baseline justify-between gap-phi-2">
                    <span className="type-label-section type-label-inverse">
                      Pipeline
                    </span>
                    <span
                      className={`type-status inline-flex shrink-0 items-center gap-phi-2 ${pipelineTone.text}`}
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-none ${pipelineTone.dot}`}
                        aria-hidden
                      />
                      {telemetry.pipelineState}
                    </span>
                  </div>

                  {telemetry.executionReadiness ? (
                    <div
                      className="mt-phi-2 flex items-center justify-between gap-phi-2"
                      aria-label="Execution readiness"
                    >
                      <span className="type-meta type-meta-inverse">
                        Execution
                      </span>
                      <span
                        className={`type-status ${telemetry.executionReadiness === "blocked" || telemetry.executionReadiness === "degraded" ? "text-escalation-bright" : "text-white/60"}`}
                      >
                        {telemetry.executionReadiness.replace(
                          /^./,
                          (character) => character.toUpperCase(),
                        )}
                      </span>
                    </div>
                  ) : null}

                  {telemetry.pipelineState === "Issue" ? (
                    <Link
                      to="/v1/settings"
                      className="type-action mt-phi-2 block text-escalation-bright/85 transition-colors hover:text-escalation-bright btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
                    >
                      Needs attention →
                    </Link>
                  ) : null}

                  {/* One number that needs judgment — Need ruling when there is
                    work to rule, otherwise Open. The room headers carry the full
                    readout set; the spine stays a single ambient signal. */}
                  <div className="mt-phi-4" aria-live="polite">
                    <SpineReadout
                      label={hasEscalations ? "Need ruling" : "Open"}
                      value={(hasEscalations
                        ? telemetry.pendingEscalations
                        : telemetry.openInProgressCount
                      ).toLocaleString()}
                      tone={hasEscalations ? "escalation" : "default"}
                      onClick={
                        hasEscalations
                          ? () => navigate("/v1/flow?queue=escalated")
                          : () => navigate("/v1/flow")
                      }
                    />
                    <p className="type-meta type-meta-inverse mt-phi-2 tabular-nums">
                      {hasEscalations
                        ? `${telemetry.openInProgressCount.toLocaleString()} open`
                        : `${telemetry.totalCount.toLocaleString()} in pipeline`}
                      {telemetry.newCount > 0
                        ? ` · ${telemetry.newCount.toLocaleString()} new`
                        : ""}
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={() =>
                      navigate(mandate.hasThesis ? "/v1/fund" : "/v1/settings")
                    }
                    aria-label={
                      mandate.hasThesis
                        ? `Active mandate: ${mandate.fundName || "configured"} — open Fund`
                        : "No active thesis — open settings"
                    }
                    className="group mt-phi-4 block w-full min-w-0 border-t border-white/10 pt-phi-3 text-left btn-interaction btn-interaction--no-press focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
                  >
                    <span className="type-label-section type-label-inverse">
                      Mandate
                      {mandate.hasThesis && mandate.versionNumber != null
                        ? ` · v${mandate.versionNumber}`
                        : ""}
                      {!mandate.hasThesis ? " · set up" : ""}
                    </span>
                    <span className="mt-phi-1 block min-w-0 truncate font-sans text-[12px] font-medium leading-snug text-white/85 transition-colors group-hover:text-white">
                      {mandate.hasThesis
                        ? mandate.fundName || "Active mandate"
                        : "No active thesis"}
                    </span>
                    {mandate.hasThesis && mandate.amendedAt ? (
                      <span className="type-meta type-meta-inverse mt-0.5 block min-w-0 truncate transition-colors group-hover:text-white">
                        Amended {mandate.amendedAt} →
                      </span>
                    ) : null}
                  </button>
                </section>
              </>
            )}

            {/* ── Operator — Today footer voice ── */}
            <footer
              aria-label="Operator"
              className="min-w-0 border-t border-white/10 px-2 pt-phi-3"
            >
              <p
                className="type-label-section type-label-inverse truncate"
                title={displayName}
              >
                {displayName}
              </p>
              <div className="mt-phi-2 flex items-center gap-phi-4">
                <button
                  type="button"
                  onClick={requestLogout}
                  disabled={agentActionPending}
                  className="type-action type-action-inverse transition-colors hover:text-white disabled:opacity-50 btn-interaction focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/35"
                >
                  {agentActionPending ? "Updating…" : "Log out"}
                </button>
              </div>
              {agentActionError ? (
                <p
                  className="type-meta mt-phi-2 text-escalation-bright"
                  role="status"
                  aria-live="polite"
                >
                  {agentActionError}
                </p>
              ) : null}
            </footer>
          </div>
        </aside>

        <div className="aethria-spine-dispatch-anchor">
          <LookupReadyNotice {...dispatchReadyNotice} placement="dispatch" />
          <SpineNavButton
            label="Dispatch"
            active={false}
            ariaPressed={false}
            onClick={onDispatch}
            shortcut="⌘K"
            compact
            surface="oxford"
            running={dispatchActive}
            className="aethria-spine-dispatch-float"
          />
        </div>
      </div>

      {hideFixedChrome ? null : (
        <>
          <motion.button
            type="button"
            className="aethria-logout-float"
            aria-label="Log out"
            title="Log out"
            onClick={requestLogout}
            disabled={agentActionPending}
            whileHover={reduceMotion ? undefined : { y: -1 }}
            whileTap={reduceMotion ? undefined : { scale: 0.94 }}
            transition={transitionOrReduced(reduceMotion, {
              duration: tokens.motion.duration.micro,
              ease: tokens.motion.ease,
            })}
          >
            <WorkspaceGlyph label="logout" />
          </motion.button>

          <SettingsDock />

          <AgentLogoutModal {...logoutModalProps} />
        </>
      )}
    </>
  );
}
