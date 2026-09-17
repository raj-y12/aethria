"""
AETHRIA Scout Layer

The Scout layer discovers real, verifiable startup companies (not hypothetical
ideas) using multiple LLM-powered agents with distinct cognitive strategies.

Unlike Reviewer/Partner, there is no legacy/current split here: this is the
one and only Scout implementation. `ScoutEngine` is the orchestration
entrypoint; `scout/tools/` holds Scout-private tools not reusable elsewhere.
"""
from scout.base import Scout
from scout.schema import ScoutOutput, validate_scout_output, generate_id
from scout.scouts import (
    MarketDrivenScout,
    BuilderTechnicalScout,
    PainPointScout,
    ContrarianScout,
)
from scout.engine import ScoutEngine

__all__ = [
    "Scout",
    "ScoutOutput",
    "validate_scout_output",
    "generate_id",
    "MarketDrivenScout",
    "BuilderTechnicalScout",
    "PainPointScout",
    "ContrarianScout",
    "ScoutEngine",
]
