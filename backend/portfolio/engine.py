"""
Portfolio Engine - Orchestrates all portfolio layer components.

Runs:
- Execution Agent (routes decisions)
- Signal Tracker (monitors watchlist)
- Feedback Loop (calculates metrics)
- Health Monitor (system checks)
"""
import asyncio
import inspect
import logging
import os
import env_config
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from utils.timeutil import utcnow, ensure_aware

from portfolio.store import PortfolioStore
from portfolio.execution import ExecutionAgent
from portfolio.signals import SignalTracker
from portfolio.feedback import FeedbackLoop
from portfolio.cost_control import CostController
from portfolio.health import HealthMonitor
from portfolio.rejection import RejectionAnalyzer
from analytics.clustering import ClusterAnalyzer
from utils.storage import Storage
from utils.partner_codes import legacy_from_recommendation
from utils.job_schedule import claim_due_jobs
from pipeline_execution import StageExecutionResult


logger = logging.getLogger(__name__)


class PortfolioEngine:
    """
    Main engine for Portfolio Memory & Learning layer.
    
    Orchestrates:
    - Execution Agent (processes Partner decisions)
    - Signal Tracker (monitors watchlist)
    - Feedback Loop (agent metrics)
    - Health Monitor (system health)
    """
    
    def __init__(
        self,
        discovery_storage: Storage,
        portfolio_store: Optional[PortfolioStore] = None,
        execution_interval: int = 10,  # Check for new decisions every 10s
        signal_interval: int = 3600,  # Check watchlist every hour
        feedback_interval: int = 86400,  # Calculate metrics daily
        health_interval: int = 3600,  # Health check every hour
        settings: Optional[Dict[str, Any]] = None,
        startup_repository: Any = None,
    ):
        """
        Initialize Portfolio Engine.
        
        Args:
            discovery_storage: Storage instance (from Scout/Reviewer/Partner)
            portfolio_store: PortfolioStore instance (optional, creates if None)
            execution_interval: Seconds between execution checks
            signal_interval: Seconds between signal checks
            feedback_interval: Seconds between feedback calculations
            health_interval: Seconds between health checks
        """
        self.discovery_storage = discovery_storage
        self.startup_repository = startup_repository
        self._watchlist_escalation_ids: list[str] = []
        
        if portfolio_store is None:
            portfolio_store = PortfolioStore()
        self.portfolio_store = portfolio_store

        tenant_uid = getattr(self.portfolio_store, "_tenant_user_id", None)
        if not tenant_uid:
            tenant_uid = os.getenv("AETHRIA_AGENT_USER_ID", "").strip() or None
        if env_config.is_production_env() and not tenant_uid:
            raise RuntimeError(
                "PortfolioEngine requires explicit tenant: set PortfolioStore(..., user_id=...) "
                "or AETHRIA_AGENT_USER_ID in production"
            )
        offline = (tenant_uid or "offline_analytics").strip()
        self.tenant_user_id = tenant_uid

        # Initialize components
        self.rejection_analyzer = RejectionAnalyzer(
            data_dir=str(self.portfolio_store.data_dir),
            user_id=tenant_uid,
            batch2_state=getattr(self.portfolio_store, "batch2_state", None),
        )
        self.execution_agent = ExecutionAgent(
            self.portfolio_store, rejection_analyzer=self.rejection_analyzer,
        )
        self.signal_tracker = SignalTracker(self.portfolio_store)
        self.feedback_loop = FeedbackLoop(
            self.portfolio_store, discovery_storage=discovery_storage,
        )
        self.cost_controller = CostController(user_id=tenant_uid, settings=settings)
        self.health_monitor = HealthMonitor(self.portfolio_store, discovery_storage=self.discovery_storage)
        self.cluster_analyzer = ClusterAnalyzer(user_id=offline)
        self.execution_scan_limit = max(
            1,
            min(int(os.getenv("PORTFOLIO_EXECUTION_SCAN_LIMIT", "200")), 500),
        )
        self.cluster_analysis_limit = max(
            1,
            min(int(os.getenv("PORTFOLIO_CLUSTER_ANALYSIS_LIMIT", "500")), 1000),
        )
        
        # Intervals
        self.execution_interval = execution_interval
        self.signal_interval = signal_interval
        self.feedback_interval = feedback_interval
        self.health_interval = health_interval
        
        self.logger = logging.getLogger("portfolio.engine")
        self.running = False
        
        # Track last run times
        self.last_execution = utcnow()
        self.last_signal = utcnow()
        self.last_feedback = utcnow()
        self.last_health = utcnow()
    
    async def run_cycle(self) -> StageExecutionResult:
        """Run due portfolio jobs and account for every claimed subjob."""
        now = utcnow()
        if self.tenant_user_id:
            try:
                claimed = claim_due_jobs(
                    self.tenant_user_id,
                    {
                        "execution": self.execution_interval,
                        "signals": self.signal_interval,
                        "feedback": self.feedback_interval,
                        "health": self.health_interval,
                    },
                )
                due = await claimed if inspect.isawaitable(claimed) else claimed
            except Exception as exc:
                self.logger.error("Portfolio schedule claim failed: %s", exc, exc_info=True)
                return StageExecutionResult.failed_result(
                    stage="portfolio",
                    code="portfolio_schedule_unavailable",
                    detail="The Portfolio schedule could not be claimed.",
                    recovery_action=(
                        "Restore the durable schedule store and retry the Portfolio cycle."
                    ),
                    attempted=1,
                    failed=1,
                )
        else:
            due = set()
            if (now - self.last_execution).total_seconds() >= self.execution_interval:
                due.add("execution")
            if (now - self.last_signal).total_seconds() >= self.signal_interval:
                due.add("signals")
            if (now - self.last_feedback).total_seconds() >= self.feedback_interval:
                due.add("feedback")
            if (now - self.last_health).total_seconds() >= self.health_interval:
                due.add("health")

        ordered_due = [
            name
            for name in ("execution", "signals", "feedback", "health")
            if name in due
        ]
        if not ordered_due:
            return StageExecutionResult.skipped_result(
                stage="portfolio",
                code="portfolio_no_due_work",
                detail="No Portfolio subjob is due in this cycle.",
            )

        succeeded = 0
        failed = 0
        for job_name in ordered_due:
            try:
                if job_name == "execution":
                    await self._run_execution()
                    self.last_execution = now
                elif job_name == "signals":
                    await self._run_signals()
                    await self._run_watchlist_review()
                    self.last_signal = now
                elif job_name == "feedback":
                    await self._run_feedback()
                    self.last_feedback = now
                else:
                    await self._run_health()
                    self.last_health = now
                succeeded += 1
            except Exception as exc:
                failed += 1
                self.logger.error(
                    "Portfolio subjob %s failed: %s",
                    job_name,
                    exc,
                    exc_info=True,
                )

        attempted = len(ordered_due)
        if failed:
            return StageExecutionResult.failed_result(
                stage="portfolio",
                code="portfolio_subjob_failures",
                detail=(
                    f"Portfolio completed {succeeded} of {attempted} due subjobs; "
                    "one or more subjobs failed."
                ),
                recovery_action=(
                    "Inspect Portfolio persistence and subjob logs, restore the "
                    "failed dependency, and retry."
                ),
                attempted=attempted,
                succeeded=succeeded,
                failed=failed,
            )
        return StageExecutionResult.completed(
            stage="portfolio",
            code="portfolio_completed",
            detail=f"Portfolio completed {succeeded} due subjob(s).",
            attempted=attempted,
            succeeded=succeeded,
        )
    
    async def _run_execution(self):
        """Run Execution Agent to process new decisions."""
        # Stage body is blocking store I/O; one hop off the event loop.
        await asyncio.to_thread(self._run_execution_sync)

    def _run_execution_sync(self):
        try:
            all_entries = self._get_execution_entries()
            existing_decision_startup_ids = {
                d.get("startup_id")
                for d in self.portfolio_store.get_all_decisions()
                if d.get("startup_id")
            }
            
            processed_count = 0
            
            for entry in all_entries:
                startup_data = entry.get("scout_info") or entry.get("scout")
                review_data = entry.get("review_info") or entry.get("review")
                partner_data = entry.get("partner_info") or entry.get("partner")
                
                # Only process entries with Partner decisions
                if not partner_data:
                    continue
                
                # Check for human resolution override
                human_resolution = entry.get("human_resolution")
                is_resolved = bool(human_resolution and human_resolution.get("decision"))
                if is_resolved:
                    partner_data = dict(partner_data)
                    partner_data["decision"] = human_resolution["decision"]
                elif partner_data.get("recommendation") and not partner_data.get("decision"):
                    partner_data = dict(partner_data)
                    partner_data["decision"] = legacy_from_recommendation(
                        partner_data.get("recommendation")
                    )

                # Unresolved escalations are not decisions yet — the Partner
                # deferred to human judgment (human_review_required=True with no
                # human_resolution). Skip routing entirely so they don't land on
                # the watchlist (or in decisions); they stay in the escalation
                # queue (startups.partner_human_review_required) until ruled. Once
                # a human rules, human_resolution.decision is set and the row flows
                # through normal routing above (MAYBE → watchlist, etc.).
                if partner_data.get("human_review_required") and not is_resolved:
                    continue

                # The canonical id is the entry's top-level startup_id. The old
                # `startup_data.get("id")` read scout_info, which has no "id"
                # key, so it always returned None — poisoning every decision /
                # watchlist / rejection with a null startup_id and collapsing the
                # dedup set to {None}, which skipped nearly every startup.
                startup_id = (
                    entry.get("startup_id")
                    or entry.get("id")
                    or (startup_data or {}).get("startup_id")
                    or (startup_data or {}).get("id")
                )
                
                # Check if already processed (exists in portfolio store)
                existing_startup = self.portfolio_store.get_startup(startup_id)
                if not existing_startup:
                    # Add startup to portfolio store
                    self.portfolio_store.add_startup(startup_data, agent_id="scout_v1")
                
                # Check if decision already recorded
                if startup_id not in existing_decision_startup_ids:
                    # The scan projection omits review_info (heavy, unused for
                    # already-executed rows); recover it per-row for new decisions.
                    if review_data is None and hasattr(self.discovery_storage, "get_startup"):
                        full = self.discovery_storage.get_startup(startup_id)
                        if full is not None:
                            full_entry = full.to_dict() if hasattr(full, "to_dict") else full
                            review_data = full_entry.get("review_info") or full_entry.get("review")
                    # Add decision
                    decision_id = self.portfolio_store.add_decision(
                        startup_id=startup_id,
                        partner_output=partner_data,
                        agent_id="partner_v1",
                    )
                    
                    # Execute decision (canonical YES/NO/MAYBE; default to NO for safety)
                    decision = partner_data.get("decision", "NO")
                    if str(decision).strip().upper() in {"INVEST", "PASS", "MONITOR"}:
                        decision = legacy_from_recommendation(str(decision))
                    rationale = partner_data.get("rationale", "")
                    key_risks = review_data.get("key_risks", []) if review_data else []
                    scout_type = startup_data.get("scout_type", "") if startup_data else ""
                    
                    self.execution_agent.execute_decision(
                        startup_id=startup_id,
                        decision_id=decision_id,
                        decision=decision,
                        rationale=rationale,
                        key_risks=key_risks,
                        review_output=review_data,
                        scout_type=scout_type,
                    )
                    
                    processed_count += 1
                    existing_decision_startup_ids.add(startup_id)
            
            if processed_count > 0:
                self.logger.info(f"Processed {processed_count} new decisions")
            del all_entries
            del existing_decision_startup_ids
            return processed_count
        
        except Exception as e:
            self.logger.error(f"Error in execution cycle: {e}", exc_info=True)
            raise

    def _get_execution_entries(self):
        """Bounded partner-decision scan for portfolio execution."""
        if hasattr(self.discovery_storage, "get_startups_with_decision"):
            startups = self.discovery_storage.get_startups_with_decision(limit=self.execution_scan_limit)
            return [s.to_dict() if hasattr(s, "to_dict") else s for s in startups]
        return self.discovery_storage.get_all()[: self.execution_scan_limit]
    
    async def _run_signals(self):
        """Run Signal Tracker to check watchlist."""
        # Stage body is blocking store I/O; one hop off the event loop.
        await asyncio.to_thread(self._run_signals_sync)

    def _run_signals_sync(self):
        try:
            signal_ids = self.signal_tracker.check_watchlist_entries()
            if signal_ids:
                self.logger.info(f"Detected {len(signal_ids)} signals")
        except Exception as e:
            self.logger.error(f"Error in signal cycle: {e}", exc_info=True)
            raise
    
    async def _run_watchlist_review(self):
        """Review watchlist entries for staleness and decay."""
        # Stage body is blocking store I/O; one hop off the event loop.
        self._watchlist_escalation_ids = []
        await asyncio.to_thread(self._run_watchlist_review_sync)
        if self.startup_repository is not None:
            for startup_id in self._watchlist_escalation_ids:
                await self.startup_repository.mark_partner_human_review(
                    self.tenant_user_id, startup_id
                )

    def _run_watchlist_review_sync(self):
        try:
            watchlist = self.portfolio_store.get_all_watchlist()
            if not watchlist:
                return

            now = utcnow()
            signals = self.portfolio_store.get_all_signals()
            signal_startup_ids = {s.get("startup_id") for s in signals}

            for entry in watchlist:
                startup_id = entry.get("startup_id")
                added_at_str = entry.get("added_at")
                if not added_at_str:
                    continue
                added_at = ensure_aware(datetime.fromisoformat(added_at_str))
                days = (now - added_at).days

                has_signals = startup_id in signal_startup_ids

                if days < 30:
                    continue
                elif days <= 60 and not has_signals:
                    changed = self.portfolio_store.update_watchlist_fields(
                        entry.get("id"),
                        {"stale_warning": True, "days_on_watchlist": days},
                    )
                    if changed:
                        self.logger.info(
                            f"Watchlist stale warning: {startup_id} ({days} days, no signals)"
                        )
                elif days > 60 and not has_signals:
                    self.logger.warning(f"Watchlist decay: {startup_id} ({days} days, no signals) - escalating")

                    if self.startup_repository is not None:
                        self._watchlist_escalation_ids.append(str(startup_id))
                    else:
                        st = self.discovery_storage.get_startup(startup_id)
                        pi = (
                            dict(st.partner_info.model_dump(mode="json"))
                            if st and st.partner_info
                            else {}
                        )
                        pi["human_review_required"] = True
                        self.discovery_storage.update_startup_partial(startup_id, {"partner_info": pi})
                    self.portfolio_store.add_signal(
                        startup_id=startup_id,
                        signal_type="negative",
                        strength=0.3,
                        description=f"Watchlist decay: {days}+ days, no signals detected. Escalated to human review.",
                        agent_id="watchlist_reviewer_v1",
                    )
        except Exception as e:
            self.logger.error(f"Error in watchlist review: {e}", exc_info=True)
            raise

    async def _run_feedback(self):
        """Run Feedback Loop to calculate metrics."""
        # Stage body is blocking store I/O; one hop off the event loop.
        await asyncio.to_thread(self._run_feedback_sync)

    def _run_feedback_sync(self):
        try:
            metric_ids = self.feedback_loop.calculate_all_metrics(period_days=30)
            if metric_ids:
                self.logger.info(f"Calculated {len(metric_ids)} metrics")
        except Exception as e:
            self.logger.error(f"Error in feedback cycle: {e}", exc_info=True)
            raise
    
    async def _run_health(self):
        """Run Health Monitor and cluster analysis."""
        # Stage body is blocking store I/O; one hop off the event loop.
        await asyncio.to_thread(self._run_health_sync)

    def _run_health_sync(self):
        try:
            health_ids = self.health_monitor.check_health()
            if health_ids:
                self.logger.info(f"Detected {len(health_ids)} health issues")
        except Exception as e:
            self.logger.error(f"Error in health cycle: {e}", exc_info=True)
            raise

        # HealthMonitor runs the same clustering pass with bounded reads.
    
    async def run_forever(self):
        """Run Portfolio Engine continuously."""
        self.running = True
        self.logger.info("Portfolio Engine started")
        
        while self.running:
            try:
                result = await self.run_cycle()
                self.logger.info(
                    "Portfolio cycle state=%s code=%s attempted=%s succeeded=%s failed=%s skipped=%s",
                    result.state.value,
                    result.code,
                    result.attempted,
                    result.succeeded,
                    result.failed,
                    result.skipped,
                )
                await asyncio.sleep(5)  # Small sleep to prevent tight loop
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down...")
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in run loop: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    def stop(self):
        """Stop the Portfolio Engine gracefully."""
        self.logger.info("Stopping Portfolio Engine...")
        self.running = False


async def main():
    """Main entry point for Portfolio Engine."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Get configuration
    storage_path = os.getenv("STORAGE_PATH", "data/discoveries.json")
    portfolio_dir = os.getenv("PORTFOLIO_DIR", "data/portfolio")
    
    # Initialize storage
    from utils.storage import Storage
    discovery_storage = Storage(file_path=storage_path)
    
    # Create and run engine
    engine = PortfolioEngine(
        discovery_storage=discovery_storage,
        portfolio_store=PortfolioStore(data_dir=portfolio_dir),
    )
    
    try:
        await engine.run_forever()
    except KeyboardInterrupt:
        engine.stop()
        logger.info("Portfolio Engine stopped")


if __name__ == "__main__":
    asyncio.run(main())
