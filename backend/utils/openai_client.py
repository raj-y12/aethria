"""Single governed factory for OpenAI clients.

Every OpenAI client in the codebase must be built here so timeout and retry
policy is centralized. The SDK default timeout is 600s with silent retries —
on a low-concurrency instance one slow call can otherwise stall a pipeline
stage for minutes and double cost invisibly.

Tunable via env:
  OPENAI_TIMEOUT_SECONDS  (default 120)
  OPENAI_MAX_RETRIES      (default 2)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from openai import OpenAI

logger = logging.getLogger("utils.openai_client")

_DEFAULT_TIMEOUT_SECONDS = 120.0
_DEFAULT_MAX_RETRIES = 2


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %.1f", name, raw, default)
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %d", name, raw, default)
        return default


def build_openai_client(
    api_key: str,
    *,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> OpenAI:
    """Construct an OpenAI client with governed timeout + retry policy.

    Explicit arguments win over env; env wins over the built-in defaults.
    """
    eff_timeout = timeout if timeout is not None else _env_float(
        "OPENAI_TIMEOUT_SECONDS", _DEFAULT_TIMEOUT_SECONDS
    )
    eff_retries = max_retries if max_retries is not None else _env_int(
        "OPENAI_MAX_RETRIES", _DEFAULT_MAX_RETRIES
    )
    logger.debug(
        "openai client built timeout=%.1fs max_retries=%d", eff_timeout, eff_retries
    )
    return OpenAI(api_key=api_key, timeout=eff_timeout, max_retries=eff_retries)
