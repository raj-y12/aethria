#!/usr/bin/env python3
"""
Test Portfolio Memory & Learning Layer end-to-end.
"""
import asyncio
import sys
import os
import json
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from utils.storage import Storage
from portfolio.store import PortfolioStore
from portfolio.engine import PortfolioEngine
from portfolio.execution import ExecutionAgent
from portfolio.signals import SignalTracker
from portfolio.feedback import FeedbackLoop
from portfolio.cost_control import CostController
from portfolio.health import HealthMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

@pytest.mark.skip(reason="Integration test — requires live Supabase with UUID-compatible startup ids (run directly: python tests/test_portfolio_layer.py)")
async def test_portfolio_layer():
    """Test all portfolio layer components."""
    print("=" * 80)
    print("Portfolio Memory & Learning Layer - Test")
    print("=" * 80)
    print()
    
    # Initialize
    portfolio_store = PortfolioStore(data_dir="data/portfolio_test", user_id="test_user")
    
    # Test 1: Add startup
    print("Test 1: Adding startup to portfolio store...")
    scout_output = {
        "id": "test-startup-1",
        "name": "Test Startup",
        "one_line": "A test startup",
        "sector": "Tech",
        "problem": "Test problem",
        "solution": "Test solution",
        "target_users": "Test users",
        "why_now": "Test timing",
        "scout_type": "market_driven",
        "confidence": 0.75,
    }
    startup_id = portfolio_store.add_startup(scout_output, agent_id="scout_test")
    print(f"✓ Added startup: {startup_id}")
    print()
    
    # Test 2: Add decision
    print("Test 2: Adding partner decision...")
    partner_output = {
        "decision": "YES",
        "confidence": 8,
        "rationale": "Strong opportunity",
        "next_action": "Intro founder",
        "human_review_required": True,
    }
    decision_id = portfolio_store.add_decision(
        startup_id=startup_id,
        partner_output=partner_output,
        agent_id="partner_test",
    )
    print(f"✓ Added decision: {decision_id}")
    print()
    
    # Test 3: Execution Agent
    print("Test 3: Testing Execution Agent...")
    execution_agent = ExecutionAgent(portfolio_store, agent_id="execution_test")
    execution_id = execution_agent.execute_decision(
        startup_id=startup_id,
        decision_id=decision_id,
        decision="YES",
        rationale="Strong opportunity",
        key_risks=["Market risk"],
        follow_up_triggers=["Q1 results"],
    )
    print(f"✓ Executed decision: {execution_id}")
    
    # Check portfolio
    portfolio = portfolio_store.get_all_portfolio()
    print(f"✓ Portfolio contains {len(portfolio)} companies")
    print()
    
    # Test 4: Add to watchlist
    print("Test 4: Testing watchlist...")
    watchlist_id = portfolio_store.add_to_watchlist(
        startup_id=startup_id,
        decision_id=decision_id,
        check_interval_days=7,
        cached_summary="Test summary",
    )
    print(f"✓ Added to watchlist: {watchlist_id}")
    
    watchlist = portfolio_store.get_all_watchlist()
    print(f"✓ Watchlist contains {len(watchlist)} companies")
    print()
    
    # Test 5: Signal Tracker
    print("Test 5: Testing Signal Tracker...")
    signal_tracker = SignalTracker(portfolio_store, agent_id="signal_test")
    signal_ids = signal_tracker.check_watchlist_entries()
    print(f"✓ Signal tracker checked watchlist: {len(signal_ids)} signals")
    print()
    
    # Test 6: Feedback Loop
    print("Test 6: Testing Feedback Loop...")
    feedback_loop = FeedbackLoop(portfolio_store)
    metric_ids = feedback_loop.calculate_all_metrics(period_days=30)
    print(f"✓ Calculated {len(metric_ids)} metrics")
    
    metrics = portfolio_store._read_file(portfolio_store.files["agent_metrics"])
    print(f"✓ Agent metrics file contains {len(metrics)} records")
    print()
    
    # Test 7: Cost Controller
    print("Test 7: Testing Cost Controller...")
    cost_controller = CostController(budget_file="data/portfolio_test/budgets.json")
    
    can_call, reason = cost_controller.can_make_call("scout", "scout_test", estimated_tokens=1000)
    print(f"✓ Can make call: {can_call} (reason: {reason})")
    
    if can_call:
        cost_controller.record_call("scout", "scout_test", tokens_used=1000)
        print("✓ Recorded call")
    
    status = cost_controller.get_budget_status("scout")
    print(f"✓ Budget status: {status}")
    print()
    
    # Test 8: Health Monitor
    print("Test 8: Testing Health Monitor...")
    health_monitor = HealthMonitor(portfolio_store)
    health_ids = health_monitor.check_health()
    print(f"✓ Health check completed: {len(health_ids)} issues")
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Startups: {len(portfolio_store.get_all_startups())}")
    print(f"Decisions: {len(portfolio_store.get_all_decisions())}")
    print(f"Portfolio: {len(portfolio_store.get_all_portfolio())}")
    print(f"Watchlist: {len(portfolio_store.get_all_watchlist())}")
    print(f"Signals: {len(portfolio_store._read_file(portfolio_store.files['signals']))}")
    print(f"Metrics: {len(metrics)}")
    print()
    print("All tests passed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_portfolio_layer())


def test_cost_controller_uses_saved_runtime_limits(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "portfolio.cost_control.load_settings",
        lambda user_id=None, use_cache=True: {
            "cost_budget": {
                "enabled": True,
                "max_tokens_per_run": 100,
                "daily_cost_ceiling": 0.0001,
                "cooldown_seconds": 9,
            },
            "agent_config": {"max_agents_per_run": 3},
        },
    )
    monkeypatch.setenv("AETHRIA_TOKEN_COST_PER_1K_USD", "1")

    cost_controller = CostController(
        budget_file=str(tmp_path / "budgets.json"),
        user_id="user_settings",
    )

    allowed, reason = cost_controller.can_make_call("scout", "scout_test", estimated_tokens=101)
    assert allowed is False
    assert "token" in (reason or "").lower()

    cost_controller.record_call("scout", "scout_test", tokens_used=1)
    allowed, reason = cost_controller.can_make_call("scout", "scout_test_2", estimated_tokens=1)
    assert allowed is False
    assert "cost" in (reason or "").lower()

    assert cost_controller.cooldowns["scout"] == 9
    assert cost_controller.get_budget_status("scout")["tokens_limit"] == 100


class _FakeDiscoveryStorage:
    def __init__(self, entries):
        self._entries = entries

    def get_all(self):
        return self._entries


def _portfolio_entry(startup_id, recommendation):
    return {
        "scout_info": {
            "id": startup_id,
            "name": startup_id,
            "one_line": f"{startup_id} summary",
            "sector": "AI",
            "problem": "Manual research is slow",
            "solution": "Automated diligence",
            "target_users": "Seed funds",
            "why_now": "More startup data is online",
            "scout_type": "market_driven",
            "confidence": 0.8,
        },
        "review_info": {
            "key_risks": ["Data quality"],
            "market_score": 8,
            "product_score": 7,
            "technical_score": 7,
            "execution_score": 8,
            "verdict": "STRONG",
        },
        "partner_info": {
            "recommendation": recommendation,
            "confidence": 8,
            "rationale": f"{recommendation} rationale",
        },
    }


@pytest.mark.asyncio
async def test_portfolio_engine_routes_partner_recommendations(monkeypatch, tmp_path):
    monkeypatch.delenv("USE_SUPABASE_STORAGE", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    store = PortfolioStore(data_dir=str(tmp_path / "portfolio"))
    discovery_storage = _FakeDiscoveryStorage(
        [
            _portfolio_entry("invest-startup", "INVEST"),
            _portfolio_entry("monitor-startup", "MONITOR"),
            _portfolio_entry("pass-startup", "PASS"),
        ]
    )
    engine = PortfolioEngine(
        discovery_storage=discovery_storage,
        portfolio_store=store,
        execution_interval=0,
        signal_interval=999999,
        feedback_interval=999999,
        health_interval=999999,
    )

    await engine._run_execution()

    assert [r["startup_id"] for r in store.get_all_portfolio()] == ["invest-startup"]
    assert [r["startup_id"] for r in store.get_all_watchlist()] == ["monitor-startup"]
    assert [r["startup_id"] for r in store.get_all_rejections()] == ["pass-startup"]
