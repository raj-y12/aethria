#!/usr/bin/env python3
"""
Test complete flow: Scout → Review → Partner
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
from utils.storage import Storage
from scout.engine import ScoutEngine
from reviewer.engine import ReviewerEngine
from partner.engine import PartnerEngine


async def test_complete_flow():
    """Test the complete flow: Scout discovers → Reviewer evaluates → Partner decides."""
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
    storage_path = "data/test_partner_flow.json"
    storage = Storage(file_path=storage_path)
    
    print("=" * 80)
    print("AETHRIA Complete Flow Test: Scout → Review → Partner")
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
        print("ERROR: No discoveries made. Cannot test Reviewer/Partner.")
        sys.exit(1)
    
    # Step 2: Run Reviewer cycle
    print("Step 2: Running Reviewer cycle...")
    reviewer_engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        interval_seconds=60,
        model="gpt-5-nano",
        batch_size=len(discoveries),  # Review all
    )
    
    reviewed_count = await reviewer_engine.run_cycle()
    print(f"✓ Reviewed {reviewed_count} entries")
    print()
    
    if reviewed_count == 0:
        print("ERROR: No reviews completed. Cannot test Partner.")
        sys.exit(1)
    
    # Step 3: Run Partner cycle
    print("Step 3: Running Partner decision cycle...")
    partner_engine = PartnerEngine(
        storage=storage,
        interval_seconds=30,
        use_llm_fallback=False,  # Test rule-based only
    )
    
    decided_count = await partner_engine.run_cycle()
    print(f"✓ Made {decided_count} decisions")
    print()
    
    # Step 4: Display results
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    
    all_entries = storage.get_all()
    # Canonical Partner decisions: YES / NO / MAYBE
    decisions_summary = {"YES": 0, "MAYBE": 0, "NO": 0}
    
    for entry in all_entries:
        scout = entry.get("scout", {})
        review = entry.get("review")
        partner = entry.get("partner")
        
        print(f"\n{'='*80}")
        print(f"Company: {scout.get('name', 'Unknown')}")
        print(f"  Scout Type: {scout.get('scout_type', 'Unknown')}")
        print(f"  One-line: {scout.get('one_line', 'N/A')[:80]}...")
        
        if review:
            verdict = review.get("verdict", "UNKNOWN")
            avg_score = (
                review.get("market_score", 0) +
                review.get("product_score", 0) +
                review.get("technical_score", 0) +
                review.get("execution_score", 0)
            ) / 4.0
            print(f"  Review: {verdict} (avg: {avg_score:.1f}/10)")
        
        if partner:
            decision = partner.get("decision", "UNKNOWN")
            confidence = partner.get("confidence", 0)
            rationale = partner.get("rationale", "N/A")
            next_action = partner.get("next_action", "N/A")
            human_review = partner.get("human_review_required", False)
            
            decisions_summary[decision] = decisions_summary.get(decision, 0) + 1
            
            print(f"  Partner Decision: {decision}")
            print(f"    Confidence: {confidence}/10")
            print(f"    Rationale: {rationale[:100]}...")
            print(f"    Next Action: {next_action}")
            print(f"    Human Review Required: {human_review}")
        else:
            print("  Partner Decision: Pending")
    
    print()
    print("=" * 80)
    print("DECISION SUMMARY")
    print("=" * 80)
    print(f"YES: {decisions_summary.get('YES', 0)}")
    print(f"MAYBE: {decisions_summary.get('MAYBE', 0)}")
    print(f"NO: {decisions_summary.get('NO', 0)}")
    print()
    print("=" * 80)
    print("Test complete!")
    print(f"Storage file: {storage_path}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_complete_flow())
