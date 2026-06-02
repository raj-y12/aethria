"""Shared bootstrap for optional live integration scripts under tests/."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def bootstrap_integration_test() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
    backend_dir = Path(__file__).resolve().parent.parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def require_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    return api_key
