#!/usr/bin/env python3
"""Dry-run or apply one restartable canonical identity backfill batch."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from identity.backfill import CanonicalIdentityBackfill
from identity.repository import IdentityRepository
from identity.service import IdentityService
from jobs.postgres import create_pool


async def _run(args):
    pool = await create_pool()
    try:
        repository = IdentityRepository(pool)
        return await CanonicalIdentityBackfill(
            pool,
            repository=repository,
            service=IdentityService(repository),
        ).run_batch(
            user_id=args.user_id,
            apply=args.apply,
            batch_size=args.batch_size,
            after=args.after,
        )
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--after")
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
