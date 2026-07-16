#!/usr/bin/env python3
"""Count-only identity reconciliation; exits nonzero on hard drift."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from identity.reconciliation import reconcile_identity
from jobs.postgres import create_pool


async def _run(args):
    pool = await create_pool()
    try:
        return await reconcile_identity(
            pool, user_id=args.user_id, activated_at=args.activated_at
        )
    finally:
        await pool.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--activated-at")
    args = parser.parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report.model_dump(mode="json"), sort_keys=True))
    return 1 if report.has_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
