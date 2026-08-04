#!/usr/bin/env python3
"""
Test script to demonstrate Scout execution.
Runs a single discovery cycle with all Scouts.
"""
import asyncio
import sys
import os
import json

import pytest

from integration_helpers import bootstrap_integration_test, require_openai_api_key

bootstrap_integration_test()

from scout.engine import ScoutEngine


@pytest.mark.skip(reason="Integration test — requires live OPENAI_API_KEY and tenant_user_id (run directly: python tests/test_scouts.py)")
async def test_scouts():
    """Run a single discovery cycle to test all Scouts."""
    api_key = require_openai_api_key()

    # Create engine
    engine = ScoutEngine(
        api_key=api_key,
        interval_seconds=60,  # Not used in test, but required
    )
    
    print("=" * 80)
    print("AETHRIA Scout Layer - Test Run")
    print("=" * 80)
    print(f"Running {len(engine.scouts)} Scouts in parallel...")
    print()
    
    # Run one cycle
    discoveries = (await engine.run_cycle()).discoveries
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Successful discoveries: {len(discoveries)}/{len(engine.scouts)}")
    print()
    
    if discoveries:
        for disc in discoveries:
            print(f"[{disc['scout_type'].upper()}]")
            print(f"  Name: {disc['name']}")
            print(f"  One-line: {disc['one_line']}")
            print(f"  Sector: {disc['sector']}")
            print(f"  Confidence: {disc['confidence']:.2f}")
            print(f"  Problem: {disc['problem'][:100]}...")
            print()
        
        print("=" * 80)
        print("JSON Output (first discovery):")
        print("=" * 80)
        print(json.dumps(discoveries[0], indent=2))
    else:
        print("No discoveries returned. Check logs for errors.")
    
    print()
    print("Test complete.")


if __name__ == "__main__":
    asyncio.run(test_scouts())
