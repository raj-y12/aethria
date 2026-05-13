"""
Cost & Token Discipline Enforcement.

Tracks and enforces budgets, token limits, and cooldowns.
Uses Supabase `portfolio_budgets` when configured with tenant context;
falls back to local file only when Supabase is unavailable.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import os

from supabase_doc_store import doc_get, doc_set
from utils.settings_loader import load_settings, runtime_limits_from_settings

logger = logging.getLogger(__name__)


class CostController:
    """
    Enforces cost discipline across all agents.
    """
    
    def __init__(self, budget_file: str = "data/portfolio/budgets.json", user_id: Optional[str] = None):
        self.budget_file = Path(budget_file)
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("cost.controller")
        self.user_id = (user_id or "").strip() or None
        self.default_budgets = {
            "scout": {"calls": 100, "tokens": 100000},
            "reviewer": {"calls": 200, "tokens": 200000},
            "partner": {"calls": 1000, "tokens": 0},
        }
        self.cooldowns = {"scout": 60, "reviewer": 30, "partner": 10}
        self.daily_cost_ceiling = 0.0
        self.weekly_cost_ceiling = 0.0
        self.token_cost_per_1k_usd = self._configured_token_cost()
        self._apply_saved_limits()
        self._load_budgets()

    @staticmethod
    def _configured_token_cost() -> float:
        raw = os.getenv("AETHRIA_TOKEN_COST_PER_1K_USD", "0.001")
        try:
            return max(0.0, float(raw))
        except (TypeError, ValueError):
            return 0.001

    def _apply_saved_limits(self) -> None:
        if not self.user_id:
            return
        try:
            limits = runtime_limits_from_settings(load_settings(self.user_id))
        except Exception as e:
            self.logger.warning("Saved runtime limits unavailable; using defaults: %s", e)
            return
        token_limit = int(limits.get("max_tokens_per_run", 0) or 0)
        if token_limit > 0:
            for agent_type in self.default_budgets:
                self.default_budgets[agent_type]["tokens"] = token_limit
        cooldown_seconds = int(limits.get("cooldown_seconds", 0) or 0)
        for agent_type in self.cooldowns:
            self.cooldowns[agent_type] = cooldown_seconds
        self.daily_cost_ceiling = float(limits.get("daily_cost_ceiling", 0.0) or 0.0)
        self.weekly_cost_ceiling = float(limits.get("weekly_cost_ceiling", 0.0) or 0.0)

    def _using_supabase(self) -> bool:
        return bool(self.user_id and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    
    def _load_budgets(self):
        """Load budget state from Supabase (preferred) or file fallback."""
        if self._using_supabase():
            try:
                data = doc_get("portfolio_budgets", user_id=self.user_id)
                if isinstance(data, dict):
                    self.budgets = data
                else:
                    self.budgets = {}
                return
            except Exception as e:
                self.logger.warning("Supabase budget load failed; using file fallback: %s", e)
        if self.budget_file.exists():
            try:
                with open(self.budget_file, "r") as f:
                    self.budgets = json.load(f)
            except Exception:
                self.budgets = {}
        else:
            self.budgets = {}
    
    def _save_budgets(self):
        """Save budget state to Supabase (preferred) or file fallback."""
        if self._using_supabase():
            try:
                doc_set("portfolio_budgets", self.budgets, user_id=self.user_id)
                return
            except Exception as e:
                self.logger.warning("Supabase budget save failed; using file fallback: %s", e)
        with open(self.budget_file, "w") as f:
            json.dump(self.budgets, f, indent=2)
    
    def _reset_daily_budgets(self):
        """Reset daily budgets if new day."""
        now = datetime.now()
        today = now.date().isoformat()
        
        for agent_type in self.default_budgets:
            agent_budget = self.budgets.get(agent_type, {})
            last_reset = agent_budget.get("last_reset_date")
            
            if last_reset != today:
                agent_budget["last_reset_date"] = today
                agent_budget["calls_today"] = 0
                agent_budget["tokens_today"] = 0
                agent_budget["cost_today"] = 0.0
                agent_budget["last_call_time"] = {}
                self.budgets[agent_type] = agent_budget
        
        self._save_budgets()
    
    def can_make_call(
        self,
        agent_type: str,
        agent_id: str,
        estimated_tokens: int = 0,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if agent can make a call.
        
        Args:
            agent_type: "scout", "reviewer", or "partner"
            agent_id: Specific agent identifier
            estimated_tokens: Estimated tokens for this call
        
        Returns:
            (allowed, reason_if_denied)
        """
        self._reset_daily_budgets()
        
        if agent_type not in self.default_budgets:
            return False, f"Unknown agent type: {agent_type}"
        
        budget = self.budgets.get(agent_type, {})
        default = self.default_budgets[agent_type]
        
        # Check call budget
        calls_today = budget.get("calls_today", 0)
        if calls_today >= default["calls"]:
            return False, f"Daily call budget exceeded ({calls_today}/{default['calls']})"
        
        # Check token budget
        tokens_today = budget.get("tokens_today", 0)
        if tokens_today + estimated_tokens > default["tokens"]:
            return False, f"Daily token budget would be exceeded"

        if self.daily_cost_ceiling > 0 and self.token_cost_per_1k_usd > 0:
            cost_today = sum(
                float(v.get("cost_today", 0.0) or 0.0)
                for v in self.budgets.values()
                if isinstance(v, dict)
            )
            estimated_cost = (max(0, int(estimated_tokens or 0)) / 1000.0) * self.token_cost_per_1k_usd
            if cost_today + estimated_cost > self.daily_cost_ceiling:
                return False, f"Daily cost ceiling would be exceeded"
        
        # Check cooldown
        last_calls = budget.get("last_call_time", {})
        last_call = last_calls.get(agent_id)
        
        if last_call:
            last_call_time = datetime.fromisoformat(last_call)
            cooldown_seconds = self.cooldowns.get(agent_type, 60)
            
            if (datetime.now() - last_call_time).total_seconds() < cooldown_seconds:
                return False, f"Cooldown period not expired"
        
        return True, None
    
    def record_call(
        self,
        agent_type: str,
        agent_id: str,
        tokens_used: int = 0,
    ):
        """
        Record a call made by an agent.
        
        Args:
            agent_type: Agent type
            agent_id: Agent identifier
            tokens_used: Tokens consumed
        """
        self._reset_daily_budgets()
        
        if agent_type not in self.budgets:
            self.budgets[agent_type] = {
                "last_reset_date": datetime.now().date().isoformat(),
                "calls_today": 0,
                "tokens_today": 0,
                "last_call_time": {},
            }
        
        budget = self.budgets[agent_type]
        budget["calls_today"] = budget.get("calls_today", 0) + 1
        budget["tokens_today"] = budget.get("tokens_today", 0) + tokens_used
        budget["cost_today"] = round(
            float(budget.get("cost_today", 0.0) or 0.0)
            + (max(0, int(tokens_used or 0)) / 1000.0) * self.token_cost_per_1k_usd,
            8,
        )
        budget["last_call_time"][agent_id] = datetime.now().isoformat()
        
        self._save_budgets()
        
        self.logger.info(
            f"Recorded call: {agent_type}/{agent_id} "
            f"({budget['calls_today']} calls, {budget['tokens_today']} tokens today)"
        )
    
    def check_budget(
        self,
        agent_type: str,
        agent_id: str,
        estimated_tokens: int = 0,
    ) -> tuple[bool, Optional[str]]:
        """
        Simpler budget check wrapper around can_make_call.
        
        Returns:
            (allowed, reason_if_denied)
        """
        return self.can_make_call(agent_type, agent_id, estimated_tokens)

    def record_usage(
        self,
        agent_type: str,
        agent_id: str,
        tokens_used: int = 0,
    ):
        """
        Simpler usage recording wrapper around record_call.
        """
        self.record_call(agent_type, agent_id, tokens_used)

    def get_budget_status(self, agent_type: str) -> Dict[str, Any]:
        """Get current budget status for agent type."""
        self._reset_daily_budgets()
        
        if agent_type not in self.default_budgets:
            return {}
        
        budget = self.budgets.get(agent_type, {})
        default = self.default_budgets[agent_type]
        
        return {
            "calls_used": budget.get("calls_today", 0),
            "calls_limit": default["calls"],
            "tokens_used": budget.get("tokens_today", 0),
            "tokens_limit": default["tokens"],
            "cost_used": budget.get("cost_today", 0.0),
            "daily_cost_ceiling": self.daily_cost_ceiling,
            "last_reset": budget.get("last_reset_date"),
        }

    def get_all_budget_status(self) -> Dict[str, Any]:
        """Return budget status for all agent types."""
        self._reset_daily_budgets()
        result: Dict[str, Any] = {}
        for agent_type in self.default_budgets:
            result[agent_type] = self.get_budget_status(agent_type)
        return result
