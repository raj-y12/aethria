from types import SimpleNamespace

import pytest

import pipeline_runner
from models import ScoutInfo
from pipeline_execution import MetaCycleResult, ScoutCycleResult, StageExecutionResult
from utils.storage import Storage


@pytest.mark.asyncio
async def test_periodic_pipeline_prunes_after_scout_and_before_reviewer(monkeypatch):
    order = []

    class StorageStub:
        def remove_startups_without_references(self):
            order.append("prune")
            return 0

        def count_unreviewed(self):
            return 0

        def count_undecided(self):
            return 0

    class Scout:
        scouts = [object()]

        async def run_cycle(self, **kwargs):
            order.append("scout")
            return ScoutCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="scout",
                    code="scout_no_eligible_work",
                    detail="No Scout work.",
                )
            )

    class Reviewer:
        last_cycle_stats = {}

        async def run_cycle(self, **kwargs):
            # Product decision, 2026-08-19: periodic Scout no longer requires
            # canonical identity linkage before Reviewer will consider a
            # startup -- eligible_startup_ids is no longer passed at all.
            assert "eligible_startup_ids" not in kwargs
            order.append("reviewer")
            return StageExecutionResult.skipped_result(
                stage="reviewer",
                code="reviewer_no_eligible_work",
                detail="No Reviewer work.",
            )

    class Partner:
        last_cycle_escalations = 0

        async def run_cycle(self, **kwargs):
            return 0

    class Thesis:
        version_id = "thesis-live"
        embedding = [0.1]

        def as_engine_context(self):
            return {}

    class Portfolio:
        def __init__(self, **kwargs):
            pass

        async def run_cycle(self):
            order.append("portfolio")
            return StageExecutionResult.skipped_result(
                stage="portfolio",
                code="portfolio_no_due_work",
                detail="No Portfolio work.",
            )

    class Meta:
        def __init__(self, **kwargs):
            pass

        async def run_cycle(self):
            order.append("meta")
            return MetaCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="meta",
                    code="meta_not_due",
                    detail="No Meta work.",
                )
            )

    storage = StorageStub()
    engines = pipeline_runner._PipelineEngines(
        scout_engine=Scout(),
        reviewer_engine=Reviewer(),
        partner_engine=Partner(),
        portfolio_store=SimpleNamespace(),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(pipeline_runner.env_config, "use_supabase_storage", lambda: True)
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda *a, **k: {
            "agent_config": {
                "scouts_enabled": True,
                "reviewers_enabled": True,
                "partners_enabled": False,
            }
        },
    )
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda user_id, settings=None: storage)
    monkeypatch.setattr(pipeline_runner, "_load_active_thesis_sync", lambda user_id: Thesis())
    monkeypatch.setattr(pipeline_runner, "_build_pipeline_engines", lambda **kwargs: engines)
    monkeypatch.setattr(pipeline_runner, "_count_startups_sync", lambda user_id: 0)
    monkeypatch.setattr(pipeline_runner, "PortfolioEngine", Portfolio)
    monkeypatch.setattr(pipeline_runner, "MetaAgent", Meta)
    monkeypatch.setattr(pipeline_runner, "get_service_client", lambda: SimpleNamespace())

    class IdentityRepository:
        async def list_linked_legacy_startup_ids(self, *, user_id):
            return []

    class Prerequisites:
        thesis_version_id = "thesis-live"

        def require_tenant(self, user_id, *, context):
            assert user_id == "user-prune-order"
            return user_id

    await pipeline_runner._run_one_pipeline_cycle_inner(
        "user-prune-order",
        identity_repository=IdentityRepository(),
        evaluation_prerequisites=Prerequisites(),
    )

    assert order[:3] == ["scout", "prune", "reviewer"]


@pytest.mark.asyncio
async def test_periodic_scout_persists_directly_without_identity_admission(monkeypatch):
    """Regression (product decision, 2026-08-19): periodic Scout used to run
    with persist_discoveries=False and require every discovery to clear
    IdentityService.admit() (a verified domain/LinkedIn/Crunchbase match)
    before it ever became a startups row -- Scout's news-article references
    almost never satisfy that, so every discovery opened an
    identity_resolution_case and the same handful of companies kept
    reopening cases every cycle instead of Scout ever finding new ones.
    Scout now persists directly (matching the pre-canonical-identity legacy
    path); _admit_autonomous_discoveries must never be called from the
    periodic cycle. On-demand lookup's own admission path is untouched --
    not exercised by this test."""

    persist_calls = []
    admission_calls = []

    class StorageStub:
        def remove_startups_without_references(self):
            return 0

        def count_unreviewed(self):
            return 0

        def count_undecided(self):
            return 0

    class Scout:
        scouts = [object()]

        async def run_cycle(self, **kwargs):
            persist_calls.append(kwargs.get("persist_discoveries"))
            return ScoutCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="scout",
                    code="scout_no_eligible_work",
                    detail="No Scout work.",
                )
            )

    class Reviewer:
        last_cycle_stats = {}

        async def run_cycle(self, **kwargs):
            assert "eligible_startup_ids" not in kwargs
            return StageExecutionResult.skipped_result(
                stage="reviewer",
                code="reviewer_no_eligible_work",
                detail="No Reviewer work.",
            )

    class Partner:
        last_cycle_escalations = 0

        async def run_cycle(self, **kwargs):
            assert "eligible_startup_ids" not in kwargs
            return StageExecutionResult.skipped_result(
                stage="partner",
                code="partner_no_eligible_work",
                detail="No Partner work.",
            )

    class Thesis:
        version_id = "thesis-live"
        embedding = [0.1]

        def as_engine_context(self):
            return {}

    class Portfolio:
        def __init__(self, **kwargs):
            pass

        async def run_cycle(self):
            return StageExecutionResult.skipped_result(
                stage="portfolio",
                code="portfolio_no_due_work",
                detail="No Portfolio work.",
            )

    class Meta:
        def __init__(self, **kwargs):
            pass

        async def run_cycle(self):
            return MetaCycleResult(
                outcome=StageExecutionResult.skipped_result(
                    stage="meta",
                    code="meta_not_due",
                    detail="No Meta work.",
                )
            )

    async def fake_admit(*args, **kwargs):
        admission_calls.append((args, kwargs))
        return []

    storage = StorageStub()
    engines = pipeline_runner._PipelineEngines(
        scout_engine=Scout(),
        reviewer_engine=Reviewer(),
        partner_engine=Partner(),
        portfolio_store=SimpleNamespace(),
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(pipeline_runner.env_config, "use_supabase_storage", lambda: True)
    monkeypatch.setattr(
        pipeline_runner,
        "load_settings",
        lambda *a, **k: {
            "agent_config": {
                "scouts_enabled": True,
                "reviewers_enabled": True,
                "partners_enabled": True,
            }
        },
    )
    monkeypatch.setattr(pipeline_runner, "_build_storage_sync", lambda user_id, settings=None: storage)
    monkeypatch.setattr(pipeline_runner, "_load_active_thesis_sync", lambda user_id: Thesis())
    monkeypatch.setattr(pipeline_runner, "_build_pipeline_engines", lambda **kwargs: engines)
    monkeypatch.setattr(pipeline_runner, "_count_startups_sync", lambda user_id: 0)
    monkeypatch.setattr(pipeline_runner, "PortfolioEngine", Portfolio)
    monkeypatch.setattr(pipeline_runner, "MetaAgent", Meta)
    monkeypatch.setattr(pipeline_runner, "get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(pipeline_runner, "_admit_autonomous_discoveries", fake_admit)

    class IdentityRepository:
        async def list_linked_legacy_startup_ids(self, *, user_id):
            return []

    class Prerequisites:
        thesis_version_id = "thesis-live"

        def require_tenant(self, user_id, *, context):
            return user_id

    await pipeline_runner._run_one_pipeline_cycle_inner(
        "user-no-identity-gate",
        identity_repository=IdentityRepository(),
        evaluation_prerequisites=Prerequisites(),
    )

    assert persist_calls == [True]
    assert admission_calls == []


def test_reference_prune_keeps_operator_lookup_rows(tmp_path):
    storage = Storage(str(tmp_path / "startups.json"))

    def scout(startup_id, name, origin_type=None):
        return ScoutInfo(
            startup_id=startup_id,
            name=name,
            one_line="one",
            sector="AI",
            problem="problem",
            solution="solution",
            target_users="users",
            why_now="now",
            scout_type="market_driven",
            confidence_score=0.5,
            origin_type=origin_type,
            references=[],
        )

    storage.add_startup(scout("periodic", "Periodic"))
    storage.add_startup(scout("lookup", "Lookup", "on_demand_lookup"))

    assert storage.remove_startups_without_references() == 1
    assert [startup.startup_id for startup in storage.get_all_startups()] == ["lookup"]
