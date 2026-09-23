"""Backfill Sub-project 4's evidence-plan -> retrieval -> extraction -> re-evaluate
pipeline against opportunities dispatched before that pipeline existed.

Reuses exactly the functions a live dispatch calls inline (pipeline_runner.py) --
no new production code path, just the existing one run against opportunities that
never went through it. Each opportunity gets a real, bounded (max 3 queries)
retrieval pass, retains factual source statements without extraction model calls,
then runs the shared Reviewer/validation/Partner analysis. Retrieval and analysis
cost real API spend -- run with --limit first.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import env_config
from evaluation_v2.prerequisites import (
    EvaluationPrerequisiteError,
    load_evaluation_prerequisites,
)
from investment_analysis.repository import InvestmentAnalysisRepository
from evidence.factual import retain_verified_source_statements
from evidence.planning import compute_missing_evidence
from evidence.repository import EvidenceRepository
from evidence.retrieval import execute_evidence_plan
from fund_intelligence.repository import FundIntelligenceRepository


async def _backfill_opportunity(
    pool: asyncpg.Pool,
    *,
    user_id: str,
    opportunity_id: str,
    company_id: str,
    company_name: str,
    company_website: str | None,
    api_key: str,
) -> dict:
    try:
        evaluation_prerequisites = await load_evaluation_prerequisites(
            user_id=user_id,
            fund_intelligence_repository=FundIntelligenceRepository(pool),
        )
    except EvaluationPrerequisiteError as exc:
        return {"opportunity_id": str(opportunity_id), "skipped": exc.code}

    evidence_repository = EvidenceRepository(pool)
    current_claim_types = await evidence_repository.list_current_claim_types(
        user_id=user_id, opportunity_id=opportunity_id,
        min_confidence=evaluation_prerequisites.policy.decision_safety.claim_confidence.minimum_eligible,
    )
    missing_evidence, search_questions = compute_missing_evidence(
        evaluation_prerequisites.policy, current_claim_types,
    )
    if not missing_evidence:
        return {"opportunity_id": str(opportunity_id), "skipped": "no_missing_evidence"}

    plan = await evidence_repository.create_plan(
        user_id=user_id,
        opportunity_id=opportunity_id,
        trigger_type="backfill",
        missing_evidence=missing_evidence,
        search_questions=search_questions,
    )
    retrieval_result = await execute_evidence_plan(
        user_id=user_id,
        company_id=company_id,
        opportunity_id=opportunity_id,
        plan=plan,
        evidence_repository=evidence_repository,
        company_name=company_name,
        company_website=company_website,
    )
    verified_items = retrieval_result.get("verified_items") or []
    if not verified_items:
        return {"opportunity_id": str(opportunity_id), "skipped": "no_verified_evidence", **retrieval_result}

    extraction_result = await retain_verified_source_statements(
        user_id=user_id,
        company_id=company_id,
        opportunity_id=opportunity_id,
        evidence_item_ids=[str(item["evidence_item_id"]) for item in verified_items],
        evidence_repository=evidence_repository,
    )
    if not extraction_result.get("claims_created"):
        return {
            "opportunity_id": str(opportunity_id),
            "skipped": "no_claims_extracted",
            **retrieval_result,
            **extraction_result,
        }

    await InvestmentAnalysisRepository(pool).evaluate(
        user_id=user_id,
        opportunity_id=opportunity_id,
        actor_id=user_id,
        trigger_type="backfill",
        policy=evaluation_prerequisites.policy,
        thesis_version_id=evaluation_prerequisites.thesis_version_id,
    )
    return {"opportunity_id": str(opportunity_id), "ok": True, **retrieval_result, **extraction_result}


async def _run(database_url: str, *, limit: int | None) -> list[dict]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=4)
    try:
        query = "select opportunity_id, user_id, company_id from public.opportunities order by created_at"
        if limit:
            query += f" limit {int(limit)}"
        rows = await pool.fetch(query)
        results: list[dict] = []
        for row in rows:
            company = await pool.fetchrow(
                "select canonical_name, canonical_domain from public.companies "
                "where company_id = $1 and user_id = $2",
                row["company_id"], row["user_id"],
            )
            if company is None or not company["canonical_name"]:
                results.append({"opportunity_id": str(row["opportunity_id"]), "skipped": "no_company_name"})
                continue
            result = await _backfill_opportunity(
                pool,
                user_id=str(row["user_id"]),
                opportunity_id=str(row["opportunity_id"]),
                company_id=str(row["company_id"]),
                company_name=company["canonical_name"],
                company_website=company["canonical_domain"],
                api_key=api_key,
            )
            print(result)
            results.append(result)
        return results
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--limit", type=int, default=None, help="Backfill only the first N opportunities.")
    args = parser.parse_args()
    if not args.database_url.strip():
        parser.error("--database-url or DATABASE_URL is required")
    results = asyncio.run(_run(args.database_url.strip(), limit=args.limit))
    ok = sum(1 for r in results if r.get("ok"))
    print(f"\n{ok}/{len(results)} opportunities gained new extraction coverage.")


if __name__ == "__main__":
    main()
