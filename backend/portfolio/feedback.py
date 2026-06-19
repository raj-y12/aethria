"""
Feedback Loop - Agent Performance Metrics.

Calculates and persists metrics for all agents.
Machine-readable for future Meta-Agent use.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from utils.timeutil import utcnow, ensure_aware
from collections import defaultdict

from portfolio.store import PortfolioStore


logger = logging.getLogger(__name__)


class FeedbackLoop:
    """
    Calculates agent performance metrics.
    
    Metrics:
    - Acceptance rate (for Partners)
    - Rejection reversal rate
    - Time-to-signal
    - Discovery quality (for Scouts)
    - Signal accuracy (for Reviewers)
    """
    
    def __init__(self, portfolio_store: PortfolioStore, discovery_storage=None):
        """
        Initialize Feedback Loop.
        
        Args:
            portfolio_store: PortfolioStore instance
            discovery_storage: Optional Storage instance for reading reviewed startups
        """
        self.store = portfolio_store
        self.discovery_storage = discovery_storage
        self.logger = logging.getLogger("feedback.loop")
    
    def calculate_all_metrics(
        self,
        period_days: int = 30,
    ) -> List[str]:
        """
        Calculate all agent metrics for a time period.
        
        Args:
            period_days: Number of days to look back
        
        Returns:
            List of metric IDs created
        """
        period_end = utcnow()
        period_start = period_end - timedelta(days=period_days)
        
        self.logger.info(
            f"Calculating metrics for period {period_start.isoformat()} to "
            f"{period_end.isoformat()}"
        )
        
        metric_ids = []
        
        # Partner metrics
        partner_metrics = self._calculate_partner_metrics(period_start, period_end)
        metric_ids.extend(partner_metrics)
        
        # Scout metrics
        scout_metrics = self._calculate_scout_metrics(period_start, period_end)
        metric_ids.extend(scout_metrics)
        
        # Reviewer metrics
        reviewer_metrics = self._calculate_reviewer_metrics(period_start, period_end)
        metric_ids.extend(reviewer_metrics)
        
        # Verdict distribution and calibration
        self._calculate_verdict_distribution()
        
        return metric_ids
    
    def _calculate_partner_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> List[str]:
        """Calculate Partner agent metrics."""
        decisions = self.store.get_all_decisions()
        
        # Filter by period
        period_decisions = [
            d for d in decisions
            if self._in_period(d.get("decided_at", ""), period_start, period_end)
        ]
        
        if not period_decisions:
            return []
        
        # Group by agent
        by_agent = defaultdict(list)
        for d in period_decisions:
            agent_id = d.get("partner_agent_id", "partner_unknown")
            by_agent[agent_id].append(d)
        
        metric_ids = []
        
        for agent_id, agent_decisions in by_agent.items():
            # Normalize legacy decision labels before metrics:
            # INVEST->YES, WATCH->MAYBE, PASS->NO.
            normalized = []
            for d in agent_decisions:
                decision = str(d.get("decision", "")).upper()
                if decision == "INVEST":
                    decision = "YES"
                elif decision == "WATCH":
                    decision = "MAYBE"
                elif decision == "PASS":
                    decision = "NO"
                normalized.append(decision)

            # Acceptance rate: YES / total
            yes_count = sum(1 for d in normalized if d == "YES")
            total_count = len(agent_decisions)
            acceptance_rate = yes_count / total_count if total_count > 0 else 0.0
            
            metric_id = self.store.add_agent_metric(
                agent_id=agent_id,
                agent_type="partner",
                metric_name="acceptance_rate",
                metric_value=acceptance_rate,
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                sample_size=total_count,
            )
            metric_ids.append(metric_id)
            
            # Decision distribution
            maybe_count = sum(1 for d in normalized if d == "MAYBE")
            no_count = sum(1 for d in normalized if d == "NO")
            
            self.logger.info(
                f"Partner {agent_id}: {yes_count} YES, {maybe_count} MAYBE, "
                f"{no_count} NO (acceptance_rate: {acceptance_rate:.2%})"
            )
        
        return metric_ids
    
    def _calculate_scout_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> List[str]:
        """Calculate Scout agent metrics."""
        startups = self.store.get_all_startups()
        
        # Filter by period
        period_startups = [
            s for s in startups
            if self._in_period(s.get("discovered_at", ""), period_start, period_end)
        ]
        
        if not period_startups:
            return []
        
        # Group by scout type
        by_scout_type = defaultdict(list)
        for s in period_startups:
            scout_type = s.get("scout_type", "unknown")
            by_scout_type[scout_type].append(s)
        
        metric_ids = []
        
        # Get all decisions to calculate acceptance rate per scout
        all_decisions = self.store.get_all_decisions()
        decision_by_startup = {
            d.get("startup_id"): d for d in all_decisions
        }
        
        # Get portfolio to see which were accepted
        portfolio = self.store.get_all_portfolio()
        accepted_startup_ids = {p.get("startup_id") for p in portfolio}
        
        for scout_type, scout_startups in by_scout_type.items():
            agent_id = f"scout_{scout_type}"
            
            # Calculate discovery-to-acceptance rate
            accepted_count = sum(
                1 for s in scout_startups
                if s.get("id") in accepted_startup_ids
            )
            total_count = len(scout_startups)
            acceptance_rate = accepted_count / total_count if total_count > 0 else 0.0
            
            metric_id = self.store.add_agent_metric(
                agent_id=agent_id,
                agent_type="scout",
                metric_name="discovery_acceptance_rate",
                metric_value=acceptance_rate,
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                sample_size=total_count,
            )
            metric_ids.append(metric_id)
            
            # Average confidence
            avg_confidence = sum(
                s.get("scout_confidence", 0.0) for s in scout_startups
            ) / total_count if total_count > 0 else 0.0
            
            metric_id = self.store.add_agent_metric(
                agent_id=agent_id,
                agent_type="scout",
                metric_name="average_confidence",
                metric_value=avg_confidence,
                period_start=period_start.isoformat(),
                period_end=period_end.isoformat(),
                sample_size=total_count,
            )
            metric_ids.append(metric_id)
            
            self.logger.info(
                f"Scout {scout_type}: {total_count} discoveries, "
                f"{accepted_count} accepted (rate: {acceptance_rate:.2%}, "
                f"avg_confidence: {avg_confidence:.2f})"
            )
        
        return metric_ids
    
    def _calculate_reviewer_metrics(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> List[str]:
        """Calculate Reviewer agent metrics."""
        # For now, we don't have reviewer agent IDs in the data
        # This would need to be added to the review records
        # For now, return empty list
        return []
    
    def _calculate_verdict_distribution(self) -> None:
        """
        Calculate STRONG/MEDIUM/WEAK verdict distribution from last 50 reviewed startups.
        Writes verdict_distribution and calibration_warning to agent_metrics.
        """
        if not self.discovery_storage:
            return
        try:
            reviewed = self.discovery_storage.get_startups_with_review(limit=50)
            if not reviewed:
                return
            
            counts = {"STRONG": 0, "MEDIUM": 0, "WEAK": 0}
            for s in reviewed:
                verdict = s.review_info.verdict if s.review_info else None
                if verdict in counts:
                    counts[verdict] += 1
            
            total = sum(counts.values())
            if total == 0:
                return
            
            calibration_warning = None
            weak_pct = counts["WEAK"] / total
            strong_pct = counts["STRONG"] / total
            if weak_pct > 0.80:
                calibration_warning = "Too strict or scout quality degraded (>80% WEAK)"
            elif strong_pct > 0.60:
                calibration_warning = "Too lenient (>60% STRONG)"
            
            now = utcnow()
            self.store.add_agent_metric(
                agent_id="reviewer_calibration",
                agent_type="reviewer",
                metric_name="verdict_distribution",
                metric_value=total,
                period_start=now.isoformat(),
                period_end=now.isoformat(),
                sample_size=total,
            )
            
            import json
            metrics_file = self.store.files["agent_metrics"]
            metrics = self.store._read_file(metrics_file)
            
            dist_record = {
                "id": "verdict_distribution",
                "verdict_distribution": counts,
                "calibration_warning": calibration_warning,
                "calculated_at": now.isoformat(),
                "sample_size": total,
            }
            
            found = False
            for i, m in enumerate(metrics):
                if m.get("id") == "verdict_distribution":
                    metrics[i] = dist_record
                    found = True
                    break
            if not found:
                metrics.append(dist_record)
            
            self.store._write_file(metrics_file, metrics)
            
            if calibration_warning:
                self.logger.warning(f"Calibration: {calibration_warning}")
            self.logger.info(
                f"Verdict distribution (last {total}): "
                f"STRONG={counts['STRONG']}, MEDIUM={counts['MEDIUM']}, WEAK={counts['WEAK']}"
            )
        except Exception as e:
            self.logger.error(f"Error calculating verdict distribution: {e}", exc_info=True)

    def _in_period(self, timestamp_str: str, period_start: datetime, period_end: datetime) -> bool:
        """Check if timestamp is in period."""
        if not timestamp_str:
            return False
        
        try:
            timestamp = ensure_aware(datetime.fromisoformat(timestamp_str))
            return period_start <= timestamp <= period_end
        except (ValueError, TypeError):
            return False
