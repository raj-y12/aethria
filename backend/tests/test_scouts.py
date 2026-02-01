#!/usr/bin/env python3
"""
Test script to demonstrate Scout execution.
Runs a single discovery cycle with all Scouts.
"""
import asyncio
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from parent directory (project root)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Also try loading from current directory
    load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scout.engine import ScoutEngine


async def test_scouts():
    """Run a single discovery cycle to test all Scouts."""
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
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
    discoveries = await engine.run_cycle()
    
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
