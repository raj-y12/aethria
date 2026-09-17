#!/usr/bin/env python3
"""Dry-run or explicitly apply the approved 4B.5C startup alias artifact."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from jobs.postgres import create_pool
from startups import load_reconciliation_artifact, repository_rows
from startups import StartupIdAliasRepository


async def _run(apply: bool) -> dict[str, int | str]:
    rows = repository_rows(load_reconciliation_artifact())
    if not apply:
        return {"status": "dry_run", "mapping_count": len(rows)}
    pool = await create_pool()
    try:
        inserted = await StartupIdAliasRepository(pool).insert_approved_aliases(rows)
        return {"status": "applied", "mapping_count": len(inserted)}
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write to DATABASE_URL explicitly")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(_run(args.apply)), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
