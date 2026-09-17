"""The current, authoritative Reviewer + Partner runtime path (ADR-0016).

Deliberately small public surface — this package's internals (`service.py`,
`grounding.py`, `mandate.py`, `model_gateway.py`, `evidence.py`, ...) are
white-box tested directly by `tests/investment_analysis/` and are not meant
to be imported piecemeal from outside. External callers should need only:

- `analyze`: the one-transaction Reviewer -> validation -> Partner sequence,
  for callers that inject their own evidence/persistence (tests, replay
  tooling) rather than going through the repository.
- `AnalysisBlocked`: the exception every caller must be prepared to catch —
  raised when a dependency (model, budget, evidence) fails closed rather than
  falling back to a stale or guessed result.
- `AnalysisResult`: the shape `analyze()` returns.
- `CompletedAnalysisStage`: the pipeline_runner-facing stage wrapper.

`InvestmentAnalysisRepository` (the live orchestration entrypoint
`pipeline_runner.py`/`api.py` actually construct and call) is deliberately
**not** re-exported here: `repository.py` imports `evaluation_v2.repository`,
which itself imports `investment_analysis.models` for a type hint, and
`evaluation_v2.repository` is commonly the first of the two to load during
normal startup (e.g. via `pipeline_runner`). Re-exporting the repository
eagerly here would make that pre-existing cross-package reference resolve
before this package finishes initializing, breaking `import api` outright.
Import it directly: `from investment_analysis.repository import
InvestmentAnalysisRepository` (as every current caller already does).

See `investment_analysis/README.md` for why Reviewer and Partner are phases
of this one service rather than independent packages.
"""
from __future__ import annotations

from investment_analysis.model_gateway import AnalysisBlocked
from investment_analysis.models import AnalysisResult
from investment_analysis.service import analyze
from investment_analysis.stages import CompletedAnalysisStage

__all__ = [
    "AnalysisBlocked",
    "AnalysisResult",
    "CompletedAnalysisStage",
    "analyze",
]
