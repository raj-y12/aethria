#!/usr/bin/env python3
"""
Clear data in the data folder by resetting file contents to empty structures.
Does not delete any files.

Usage:
  python scripts/clear_data.py [--data-dir data] [--include-settings] [--dry-run]

Environment:
  DATA_DIR  Optional. Default: data (relative to backend root).
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure backend root is on path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))


def get_default_settings():
    """Default settings structure (same as settings_loader)."""
    from settings_loader import DEFAULT_SETTINGS
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("clear_data")

    parser = argparse.ArgumentParser(
        description="Clear data in the data folder (reset contents; do not delete files)."
    )
    parser.add_argument(
        "--data-dir",
        default=os.getenv("DATA_DIR", "data"),
        help="Data directory relative to backend root (default: data)",
    )
    parser.add_argument(
        "--include-settings",
        action="store_true",
        help="Reset settings.json to defaults (otherwise leave settings unchanged)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be cleared without writing",
    )
    args = parser.parse_args()

    data_dir = BACKEND_ROOT / args.data_dir
    if not data_dir.is_dir():
        logger.error("Data directory does not exist: %s", data_dir)
        return 1

    # Files to clear and the empty value to write (list -> [], settings -> default dict)
    clear_list: list[tuple[Path, str]] = []

    # Pipeline storage (arrays)
    for name in ("startups.json", "discoveries.json"):
        p = data_dir / name
        if p.exists():
            clear_list.append((p, "[]"))

    # Portfolio directory
    portfolio_dir = data_dir / "portfolio"
    if portfolio_dir.is_dir():
        for name in (
            "startups.json",
            "decisions.json",
            "portfolio.json",
            "rejections.json",
            "watchlist.json",
            "signals.json",
            "agent_metrics.json",
        ):
            p = portfolio_dir / name
            if p.exists():
                clear_list.append((p, "[]"))

    # Settings (optional)
    if args.include_settings:
        settings_path = data_dir / "settings.json"
        if settings_path.exists():
            default = json.dumps(get_default_settings(), indent=2)
            clear_list.append((settings_path, default))

    if args.dry_run:
        for path, content_preview in clear_list:
            preview = content_preview[:50] + "..." if len(content_preview) > 50 else content_preview
            logger.info("DRY RUN: would clear %s -> %s", path.relative_to(BACKEND_ROOT), preview)
        logger.info("DRY RUN: %s file(s) would be cleared", len(clear_list))
        return 0

    cleared = 0
    for path, content in clear_list:
        try:
            path.write_text(content, encoding="utf-8")
            logger.info("Cleared %s", path.relative_to(BACKEND_ROOT))
            cleared += 1
        except OSError as e:
            logger.error("Failed to clear %s: %s", path, e)
            return 1

    logger.info("Cleared %s file(s). No files deleted.", cleared)
    return 0


if __name__ == "__main__":
    sys.exit(main())
