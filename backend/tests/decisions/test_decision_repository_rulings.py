import json
from types import SimpleNamespace

import pytest

from decisions.models import HumanRulingInput, WorkflowActionType
from decisions.repository import DecisionRepository


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows


class _CreateConnection:
    def __init__(self):
        self.fetchrows = [
            {
                "current_ruling_id": None,
                "current_recommendation_id": None,
                "recommended_state": "advance",
                "legacy_startup_id": "6df278f2-679f-4a7f-8dd9-27109904d093",
            },
            {"ruling_id": "ruling-a"},
        ]
        self.calls = []

    def transaction(self):
        return _Acquire(self)

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.pop(0)

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "INSERT 0 1"


@pytest.mark.asyncio
async def test_invest_ruling_creates_canonical_portfolio_position_only_for_explicit_invest():
    connection = _CreateConnection()
    connection.fetchrows[0]["company_id"] = "company-a"
    calls = []

    class Portfolio:
        async def create_position_on_connection(self, conn, **kwargs):
            calls.append(kwargs)
            return {"position_id": "position-a"}

    repository = DecisionRepository(_Pool(connection), portfolio_repository=Portfolio())
    await repository.create_ruling(
        HumanRulingInput(
            user_id="user-a", opportunity_id="opportunity-a", decision="invest",
            rationale="The evidence and mandate support investment.", investor_confidence=0.8,
        ),
        actor_id="operator-a",
    )
    assert len(calls) == 1
    assert calls[0]["user_id"] == "user-a"
    assert calls[0]["opportunity_id"] == "opportunity-a"
    assert calls[0]["company_id"] == "company-a"
    assert calls[0]["rationale"] == "The evidence and mandate support investment."
    assert calls[0]["investor_confidence"] == 0.8
    outbox_events = [
        call[2][4] for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    ]
    assert "portfolio_position.created" in outbox_events


def _workflow_action_row(**overrides):
    row = {
        "workflow_action_id": "4bc2c17a-9943-4d17-8bdf-0a556b6e07c8",
        "user_id": "user-a",
        "opportunity_id": "opportunity-a",
        "action_type": "draft_information_request",
        "trigger_type": "operator",
        "trigger_id": None,
        "status": "pending_approval",
        "generated_content": json.dumps({"draft": "Please share retention data.", "requires_approval": True}),
        "approved_content": None,
        "missing_evidence": json.dumps(["retention"]),
        "requires_approval": True,
        "due_at": None,
        "completed_at": None,
        "external_destination": None,
        "external_reference": None,
        "approved_by": None,
        "approved_at": None,
        "created_at": "2026-07-21T12:00:00Z",
        "updated_at": "2026-07-21T12:00:00Z",
    }
    row.update(overrides)
    return row


class _WorkflowActionConnection:
    def __init__(self, rows):
        self.fetchrows = list(rows)
        self.calls = []

    def transaction(self):
        return _Acquire(self)

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.pop(0)

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "INSERT 0 1"


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_list_rulings_is_tenant_scoped_and_newest_first():
    connection = _Connection([
        {
            "ruling_id": "ruling-2",
            "user_id": "user-a",
            "opportunity_id": "opportunity-1",
            "recommendation_id": "recommendation-1",
            "decision": "monitor",
            "rationale": "Wait for retention evidence.",
            "risk_acknowledgement": None,
            "mandate_exception": None,
            "investor_confidence": 0.7,
            "actor_id": "user-a",
            "prior_ruling_id": "ruling-1",
            "override_type": "timing",
            "override_note": None,
            "created_at": "2026-07-16T12:00:00Z",
        }
    ])
    repository = DecisionRepository(_Pool(connection))

    records = await repository.list_rulings(
        user_id="user-a",
        opportunity_id="opportunity-1",
        limit=20,
    )

    sql, args = connection.calls[0]
    assert "left join public.override_signals" in " ".join(sql.split()).lower()
    assert "where hr.user_id=$1 and hr.opportunity_id=$2" in " ".join(sql.split()).lower()
    assert "order by hr.created_at desc" in " ".join(sql.split()).lower()
    assert args == ("user-a", "opportunity-1", 20)
    assert records[0].ruling_id == "ruling-2"


@pytest.mark.asyncio
async def test_created_ruling_outbox_carries_legacy_startup_and_rationale():
    connection = _CreateConnection()
    repository = DecisionRepository(_Pool(connection))

    await repository.create_ruling(
        HumanRulingInput(
            user_id="user-a",
            opportunity_id="opportunity-a",
            decision="pass",
            rationale="Outside this fund's mandate.",
        ),
        actor_id="operator-a",
    )

    outbox = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    )
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == "6df278f2-679f-4a7f-8dd9-27109904d093"
    assert payload["rationale"] == "Outside this fund's mandate."
    assert payload["compatibility_reason"] == "Outside this fund's mandate."


@pytest.mark.asyncio
async def test_workflow_action_created_emits_linked_legacy_projection_payload():
    from authority.projection import AuthorityProjectionConsumer

    connection = _WorkflowActionConnection([
        {
            "missing_information": json.dumps(["retention"]),
            "legacy_startup_id": "cc52907a-c8ae-4a41-b9e5-259929d26f56",
        },
        _workflow_action_row(),
    ])
    repository = DecisionRepository(_Pool(connection))

    await repository.create_action(
        user_id="user-a",
        opportunity_id="opportunity-a",
        action_type=WorkflowActionType.DRAFT_INFORMATION_REQUEST,
    )

    outbox = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    )
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == "cc52907a-c8ae-4a41-b9e5-259929d26f56"
    assert payload["compatibility_reason"] == "workflow action created: draft_information_request"

    class ProjectionRepository:
        async def get_projection_receipt(self, **_kwargs):
            return None

        async def apply_legacy_projection(self, *, patch, **_kwargs):
            self.patch = patch.patch
            return SimpleNamespace(receipt_id="receipt-a")

    projection_repository = ProjectionRepository()
    receipt = await AuthorityProjectionConsumer(projection_repository).apply(
        user_id="user-a",
        event_id=outbox[2][0],
        aggregate_type=outbox[2][2],
        aggregate_id=outbox[2][3],
        event_type=outbox[2][4],
        payload=payload,
    )
    assert receipt.receipt_id == "receipt-a"
    assert projection_repository.patch["agent_trace"]["authority_projection"]["canonical_workflow_reason"] == (
        "workflow action created: draft_information_request"
    )


@pytest.mark.asyncio
async def test_workflow_action_approval_joins_opportunity_for_projection_payload():
    row = _workflow_action_row(
        status="approved",
        approved_by="operator-a",
        approved_at="2026-07-21T13:00:00Z",
        legacy_startup_id="5d82d549-205e-4cff-a831-316095c6f6e4",
    )
    connection = _WorkflowActionConnection([row])
    repository = DecisionRepository(_Pool(connection))

    await repository.approve_action(
        user_id="user-a",
        workflow_action_id=row["workflow_action_id"],
        approved_by="operator-a",
    )

    update = next(call for call in connection.calls if call[0] == "fetchrow")
    update_sql = " ".join(update[1].split()).lower()
    assert "from public.opportunities as o" in update_sql
    assert "wa.opportunity_id=o.opportunity_id" in update_sql
    outbox = next(
        call for call in connection.calls
        if call[0] == "execute" and "insert into public.domain_outbox" in call[1]
    )
    payload = json.loads(outbox[2][-1])
    assert payload["legacy_startup_id"] == "5d82d549-205e-4cff-a831-316095c6f6e4"
    assert payload["compatibility_reason"] == "workflow action approved: draft_information_request"
