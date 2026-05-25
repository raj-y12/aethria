"""
Portfolio Engine - Orchestrates all portfolio layer components.

Runs:
- Execution Agent (routes decisions)
- Signal Tracker (monitors watchlist)
- Feedback Loop (calculates metrics)
- Health Monitor (system checks)
"""
import asyncio
import logging
import os
from typing import Optional
from datetime import datetime, timedelta

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
        
        if portfolio_store is None:
            portfolio_store = PortfolioStore()
        self.portfolio_store = portfolio_store

        tenant_uid = getattr(self.portfolio_store, "_tenant_user_id", None)
        if not tenant_uid:
            tenant_uid = os.getenv("AETHRIA_AGENT_USER_ID", "").strip() or None
        use_sb = os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")
        if use_sb and not tenant_uid:
            raise RuntimeError(
                "PortfolioEngine requires explicit tenant: set PortfolioStore(..., user_id=...) "
                "or AETHRIA_AGENT_USER_ID when USE_SUPABASE_STORAGE is enabled"
            )
        offline = (tenant_uid or "offline_analytics").strip()

        # Initialize components
        self.rejection_analyzer = RejectionAnalyzer(
            data_dir=str(self.portfolio_store.data_dir),
            user_id=tenant_uid,
        )
        self.execution_agent = ExecutionAgent(
            self.portfolio_store, rejection_analyzer=self.rejection_analyzer,
        )
        self.signal_tracker = SignalTracker(self.portfolio_store)
        self.feedback_loop = FeedbackLoop(
            self.portfolio_store, discovery_storage=discovery_storage,
        )
        self.cost_controller = CostController(user_id=tenant_uid)
        self.health_monitor = HealthMonitor(self.portfolio_store, discovery_storage=self.discovery_storage)
        self.cluster_analyzer = ClusterAnalyzer(user_id=offline)
        
        # Intervals
        self.execution_interval = execution_interval
        self.signal_interval = signal_interval
        self.feedback_interval = feedback_interval
        self.health_interval = health_interval
        
        self.logger = logging.getLogger("portfolio.engine")
        self.running = False
        
        # Track last run times
        self.last_execution = datetime.now()
        self.last_signal = datetime.now()
        self.last_feedback = datetime.now()
        self.last_health = datetime.now()
    
    async def run_cycle(self):
        """Run one cycle of all portfolio components."""
        now = datetime.now()
        
        # Execution Agent: Process new Partner decisions
        if (now - self.last_execution).total_seconds() >= self.execution_interval:
            await self._run_execution()
            self.last_execution = now
        
        # Signal Tracker: Check watchlist
        if (now - self.last_signal).total_seconds() >= self.signal_interval:
            await self._run_signals()
            await self._run_watchlist_review()
            self.last_signal = now
        
        # Feedback Loop: Calculate metrics
        if (now - self.last_feedback).total_seconds() >= self.feedback_interval:
            await self._run_feedback()
            self.last_feedback = now
        
        # Health Monitor: Check system health
        if (now - self.last_health).total_seconds() >= self.health_interval:
            await self._run_health()
            self.last_health = now
    
    async def _run_execution(self):
        """Run Execution Agent to process new decisions."""
        try:
            # Get all entries from discovery storage
            all_entries = self.discovery_storage.get_all()
            
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
                if human_resolution and human_resolution.get("decision"):
                    partner_data = dict(partner_data)
                    partner_data["decision"] = human_resolution["decision"]
                elif partner_data.get("recommendation") and not partner_data.get("decision"):
                    partner_data = dict(partner_data)
                    partner_data["decision"] = legacy_from_recommendation(
                        partner_data.get("recommendation")
                    )
                
                startup_id = startup_data.get("id") if startup_data else entry.get("startup_id", entry.get("id"))
                
                # Check if already processed (exists in portfolio store)
                existing_startup = self.portfolio_store.get_startup(startup_id)
                if not existing_startup:
                    # Add startup to portfolio store
                    self.portfolio_store.add_startup(startup_data, agent_id="scout_v1")
                
                # Check if decision already recorded
                decisions = self.portfolio_store.get_all_decisions()
                decision_exists = any(
                    d.get("startup_id") == startup_id for d in decisions
                )
                
                if not decision_exists:
                    # Add decision
                    decision_id = self.portfolio_store.add_decision(
                        startup_id=startup_id,
                        partner_output=partner_data,
                        agent_id="partner_v1",
                    )
                    
                    # Execute decision (canonical YES/NO/MAYBE; default to NO for safety)
                    decision = partner_data.get("decision", "NO")
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
            
            if processed_count > 0:
                self.logger.info(f"Processed {processed_count} new decisions")
        
        except Exception as e:
            self.logger.error(f"Error in execution cycle: {e}", exc_info=True)
    
    async def _run_signals(self):
        """Run Signal Tracker to check watchlist."""
        try:
            signal_ids = self.signal_tracker.check_watchlist_entries()
            if signal_ids:
                self.logger.info(f"Detected {len(signal_ids)} signals")
        except Exception as e:
            self.logger.error(f"Error in signal cycle: {e}", exc_info=True)
    
    async def _run_watchlist_review(self):
        """Review watchlist entries for staleness and decay."""
        try:
            watchlist = self.portfolio_store.get_all_watchlist()
            if not watchlist:
                return

            now = datetime.now()
            signals = self.portfolio_store._read_file(self.portfolio_store.files["signals"])
            signal_startup_ids = {s.get("startup_id") for s in signals}

            for entry in watchlist:
                startup_id = entry.get("startup_id")
                added_at_str = entry.get("added_at")
                if not added_at_str:
                    continue
                added_at = datetime.fromisoformat(added_at_str)
                days = (now - added_at).days

                has_signals = startup_id in signal_startup_ids

                if days < 30:
                    continue
                elif days <= 60 and not has_signals:
                    entry["stale_warning"] = True
                    entry["days_on_watchlist"] = days
                    self.portfolio_store._append_record("watchlist", entry)
                    self.logger.info(f"Watchlist stale warning: {startup_id} ({days} days, no signals)")
                elif days > 60 and not has_signals:
                    self.logger.warning(f"Watchlist decay: {startup_id} ({days} days, no signals) - escalating")

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

    async def _run_feedback(self):
        """Run Feedback Loop to calculate metrics."""
        try:
            metric_ids = self.feedback_loop.calculate_all_metrics(period_days=30)
            if metric_ids:
                self.logger.info(f"Calculated {len(metric_ids)} metrics")
        except Exception as e:
            self.logger.error(f"Error in feedback cycle: {e}", exc_info=True)
    
    async def _run_health(self):
        """Run Health Monitor and cluster analysis."""
        try:
            health_ids = self.health_monitor.check_health()
            if health_ids:
                self.logger.info(f"Detected {len(health_ids)} health issues")
        except Exception as e:
            self.logger.error(f"Error in health cycle: {e}", exc_info=True)

        try:
            all_startups = self.discovery_storage.get_all()
            self.cluster_analyzer.analyze(all_startups)
        except Exception as e:
            self.logger.error(f"Error in cluster analysis: {e}", exc_info=True)
    
    async def run_forever(self):
        """Run Portfolio Engine continuously."""
        self.running = True
        self.logger.info("Portfolio Engine started")
        
        while self.running:
            try:
                await self.run_cycle()
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
