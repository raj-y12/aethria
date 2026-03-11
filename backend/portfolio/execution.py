"""
Execution Agent - Post-Decision Handler.

Routes Partner decisions to appropriate portfolio stores.
Deterministic, no API calls.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from portfolio.store import PortfolioStore


logger = logging.getLogger(__name__)


class ExecutionAgent:
    """
    Execution Agent routes Partner decisions to appropriate stores.
    
    Routes (canonical Partner decisions):
    - YES   → portfolio.json
    - NO    → rejections.json
    - MAYBE → watchlist.json
    """
    
    def __init__(self, portfolio_store: PortfolioStore, agent_id: str = "execution_v1", rejection_analyzer=None):
        """
        Initialize Execution Agent.
        
        Args:
            portfolio_store: PortfolioStore instance
            agent_id: Agent identifier
            rejection_analyzer: Optional RejectionAnalyzer for learning from rejections
        """
        self.store = portfolio_store
        self.agent_id = agent_id
        self.rejection_analyzer = rejection_analyzer
        self.logger = logging.getLogger("execution.agent")
    
    def execute_decision(
        self,
        startup_id: str,
        decision_id: str,
        decision: str,
        rationale: str,
        key_risks: list,
        follow_up_triggers: Optional[list] = None,
        review_output: Optional[dict] = None,
        scout_type: str = "",
    ) -> str:
        """
        Execute a Partner decision by routing to appropriate store.
        
        Args:
            startup_id: Startup record ID
            decision_id: Decision record ID
            decision: canonical Partner decision: "YES", "NO", or "MAYBE"
            rationale: Decision rationale
            key_risks: List of key risk strings
            follow_up_triggers: Optional list of follow-up triggers
        
        Returns:
            Record ID of the created record
        """
        if decision == "YES":
            return self._add_to_portfolio(
                startup_id, decision_id, key_risks, follow_up_triggers or []
            )
        elif decision == "NO":
            return self._add_to_rejections(
                startup_id, decision_id, rationale, key_risks,
                review_output=review_output, scout_type=scout_type,
            )
        elif decision == "MAYBE":
            return self._add_to_watchlist(startup_id, decision_id, rationale)
        else:
            raise ValueError(f"Unknown decision type: {decision}")
    
    def _add_to_portfolio(
        self,
        startup_id: str,
        decision_id: str,
        key_risks: list,
        follow_up_triggers: list,
    ) -> str:
        """Add accepted company to portfolio."""
        portfolio_id = self.store.add_to_portfolio(
            startup_id=startup_id,
            decision_id=decision_id,
            key_risks=key_risks,
            follow_up_triggers=follow_up_triggers,
            agent_id=self.agent_id,
        )
        
        self.logger.info(
            f"Added startup {startup_id} to portfolio (portfolio_id: {portfolio_id})"
        )
        return portfolio_id
    
    def _add_to_rejections(
        self,
        startup_id: str,
        decision_id: str,
        rationale: str,
        key_risks: list,
        review_output: Optional[dict] = None,
        scout_type: str = "",
    ) -> str:
        """Add rejected company."""
        reason_code = self._extract_reason_code(rationale, key_risks)
        
        rejection_id = self.store.add_rejection(
            startup_id=startup_id,
            decision_id=decision_id,
            reason_code=reason_code,
            rationale=rationale,
            key_risks=key_risks,
            agent_id=self.agent_id,
        )
        
        self.logger.info(
            f"Added startup {startup_id} to rejections (rejection_id: {rejection_id}, "
            f"reason: {reason_code})"
        )
        
        # Analyze rejection patterns
        if self.rejection_analyzer and review_output:
            try:
                dimension_scores = {
                    "market_score": review_output.get("market_score", 0),
                    "product_score": review_output.get("product_score", 0),
                    "technical_score": review_output.get("technical_score", 0),
                    "execution_score": review_output.get("execution_score", 0),
                }
                avg_score = sum(dimension_scores.values()) / max(len(dimension_scores), 1)
                self.rejection_analyzer.analyze_rejection(
                    sector=review_output.get("sector", "Unknown"),
                    avg_score=avg_score,
                    verdict=review_output.get("verdict", "WEAK"),
                    diligence_red_flags=review_output.get("diligence_red_flags", []),
                    dimension_scores=dimension_scores,
                    scout_type=scout_type,
                )
            except Exception as e:
                self.logger.error(f"Failed to analyze rejection: {e}")
        
        return rejection_id
    
    def _add_to_watchlist(
        self,
        startup_id: str,
        decision_id: str,
        rationale: str,
    ) -> str:
        """Add company to watchlist."""
        # Extract summary for caching
        cached_summary = rationale[:500] if rationale else ""
        
        watchlist_id = self.store.add_to_watchlist(
            startup_id=startup_id,
            decision_id=decision_id,
            check_interval_days=30,  # Default 30 days
            cached_summary=cached_summary,
            agent_id=self.agent_id,
        )
        
        self.logger.info(
            f"Added startup {startup_id} to watchlist (watchlist_id: {watchlist_id})"
        )
        return watchlist_id
    
    def _extract_reason_code(self, rationale: str, key_risks: list) -> str:
        """
        Extract reason code from rationale and risks.
        
        Returns:
            Reason code string
        """
        rationale_lower = rationale.lower()
        risks_lower = [r.lower() for r in key_risks]
        
        # Check for critical risks
        if any("regulatory" in r or "execution impossibility" in r for r in risks_lower):
            return "CRITICAL_RISK"
        
        # Check for low scores
        if "below threshold" in rationale_lower or "low score" in rationale_lower:
            return "LOW_SCORE"
        
        # Check for weak verdict
        if "weak" in rationale_lower:
            return "WEAK_VERDICT"
        
        # Default
        return "OTHER"
