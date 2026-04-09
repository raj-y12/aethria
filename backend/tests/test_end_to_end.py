#!/usr/bin/env python3
"""
Test end-to-end flow: Scout → Storage → Reviewer
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
    load_dotenv()

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import pytest
from utils.storage import Storage
from scout.engine import ScoutEngine
from reviewer.engine import ReviewerEngine


@pytest.mark.skip(reason="Integration test — requires live OPENAI_API_KEY and tenant_user_id (run directly: python tests/test_end_to_end.py)")
async def test_end_to_end():
    """Test the complete flow: Scout discovers → Storage persists → Reviewer evaluates."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    logger = logging.getLogger("test")
    
    # Get API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    # Use a test storage file
    storage_path = "data/test_discoveries.json"
    storage = Storage(file_path=storage_path)
    
    print("=" * 80)
    print("AETHRIA End-to-End Test")
    print("=" * 80)
    print()
    
    # Step 1: Run Scout cycle
    print("Step 1: Running Scout discovery cycle...")
    scout_engine = ScoutEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=60,
        model="gpt-5-nano",
    )
    
    discoveries = await scout_engine.run_cycle()
    print(f"✓ Discovered {len(discoveries)} startup ideas")
    print()
    
    if not discoveries:
        print("ERROR: No discoveries made. Cannot test Reviewer.")
        sys.exit(1)
    
    # Step 2: Verify storage
    print("Step 2: Verifying storage...")
    all_entries = storage.get_all()
    print(f"✓ Storage contains {len(all_entries)} entries")
    
    unreviewed = storage.get_unreviewed()
    print(f"✓ {len(unreviewed)} entries awaiting review")
    print()
    
    # Step 3: Run Reviewer cycle
    print("Step 3: Running Reviewer cycle...")
    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=60,
        model="gpt-5-nano",
        batch_size=len(unreviewed),  # Review all unreviewed
    )
    
    reviewed_count = await reviewer_engine.run_cycle()
    print(f"✓ Reviewed {reviewed_count} entries")
    print()
    
    # Step 4: Display results
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    all_entries = storage.get_all()
    for entry in all_entries:
        scout = entry.get("scout", {})
        review = entry.get("review")
        
        print(f"\nEntry: {scout.get('name', 'Unknown')}")
        print(f"  Scout Type: {scout.get('scout_type', 'Unknown')}")
        print(f"  One-line: {scout.get('one_line', 'N/A')}")
        
        if review:
            verdict = review.get("verdict", "UNKNOWN")
            avg_score = (
                review.get("market_score", 0) +
                review.get("product_score", 0) +
                review.get("technical_score", 0) +
                review.get("execution_score", 0)
            ) / 4.0
            
            print(f"  Review Verdict: {verdict}")
            print(f"  Average Score: {avg_score:.1f}/10")
            print(f"  Summary: {review.get('overall_summary', 'N/A')[:100]}...")
        else:
            print("  Review: Pending")
    
    print()
    print("=" * 80)
    print("Test complete!")
    print(f"Storage file: {storage_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_end_to_end())
