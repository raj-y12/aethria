"""
Cost & Token Discipline Enforcement.

Tracks and enforces budgets, token limits, and cooldowns.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json
from pathlib import Path


logger = logging.getLogger(__name__)


class CostController:
    """
    Enforces cost discipline across all agents.
    
    Features:
    - Call budgets per agent
    - Token ceilings
    - Cooldown timers
    - Automatic throttling
    """
    
    def __init__(self, budget_file: str = "data/portfolio/budgets.json"):
        """
        Initialize Cost Controller.
        
        Args:
            budget_file: Path to budget tracking file
        """
        self.budget_file = Path(budget_file)
        self.budget_file.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("cost.controller")
        
        # Default budgets (per day)
        self.default_budgets = {
            "scout": {"calls": 100, "tokens": 100000},
            "reviewer": {"calls": 200, "tokens": 200000},
            "partner": {"calls": 1000, "tokens": 0},  # Partner uses no tokens
        }
        
        # Cooldown periods (seconds)
        self.cooldowns = {
            "scout": 60,
            "reviewer": 30,
            "partner": 10,
        }
        
        self._load_budgets()
    
    def _load_budgets(self):
        """Load budget state from file."""
        if self.budget_file.exists():
            try:
                with open(self.budget_file, 'r') as f:
                    self.budgets = json.load(f)
            except:
                self.budgets = {}
        else:
            self.budgets = {}
    
    def _save_budgets(self):
        """Save budget state to file."""
        with open(self.budget_file, 'w') as f:
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
        budget["last_call_time"][agent_id] = datetime.now().isoformat()
        
        self._save_budgets()
        
        self.logger.info(
            f"Recorded call: {agent_type}/{agent_id} "
            f"({budget['calls_today']} calls, {budget['tokens_today']} tokens today)"
        )
    
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
            "last_reset": budget.get("last_reset_date"),
        }
