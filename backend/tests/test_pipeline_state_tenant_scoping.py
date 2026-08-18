"""Regression coverage (fresh audit, MEDIUM): get_pipeline_state_row accepted
and validated a user_id param but never checked it against the ambient
Batch4AState it actually reads from -- a caller/context mismatch would
silently return another tenant's pipeline status with no error."""

import pytest

import pipeline_state
from batch4a.context import reset_state, set_state
from batch4a.repository import Batch4AState


@pytest.fixture()
def _set_batch4a_state():
    tokens = []

    def _set(state):
        tokens.append(set_state(state))
        return state

    yield _set
    for token in reversed(tokens):
        reset_state(token)


def test_returns_state_when_user_id_matches_ambient_context(_set_batch4a_state):
    state = Batch4AState(user_id="user-a", pipeline_states={"startup-1": {"status": "ready"}})
    _set_batch4a_state(state)

    row = pipeline_state.get_pipeline_state_row(None, user_id="user-a", startup_id="startup-1")

    assert row == {"status": "ready"}


def test_returns_none_instead_of_leaking_another_tenants_state_on_mismatch(_set_batch4a_state):
    state = Batch4AState(user_id="user-a", pipeline_states={"startup-1": {"status": "ready"}})
    _set_batch4a_state(state)

    row = pipeline_state.get_pipeline_state_row(None, user_id="user-b", startup_id="startup-1")

    assert row is None
