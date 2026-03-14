#!/usr/bin/env python3
"""
Safely wipe startups.json and initialize empty storage.

Usage:
  python scripts/wipe_startups.py [--path data/startups.json] [--dry-run]

Environment:
  STORAGE_PATH  Optional. Default: data/startups.json (relative to CWD).
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure backend root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.storage import Storage


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("wipe_startups")

    parser = argparse.ArgumentParser(description="Wipe startups.json and initialize empty storage.")
    parser.add_argument(
        "--path",
        default=os.getenv("STORAGE_PATH", "data/startups.json"),
        help="Path to startups.json (default: STORAGE_PATH or data/startups.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be done without writing.",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = Path.cwd() / path

    logger.info("Storage path: %s", path)
    if args.dry_run:
        logger.info("DRY RUN: would reset storage to empty")
        return 0

    try:
        storage = Storage(file_path=str(path))
        count_before = len(storage.get_all_startups(skip_invalid=True))
        storage.reset_to_empty()
        count_after = len(storage.get_all_startups(skip_invalid=True))
        logger.info("Wipe complete. Entries before: %s, after: %s", count_before, count_after)
        return 0
    except Exception as e:
        logger.error("Wipe failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
