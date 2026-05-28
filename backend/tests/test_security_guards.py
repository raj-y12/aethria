from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def test_require_authenticated_user_returns_request_user_id():
    from security.request_guards import require_authenticated_user

    request = SimpleNamespace(state=SimpleNamespace(user_id="user_123"))

    assert require_authenticated_user(request) == "user_123"


def test_require_authenticated_user_rejects_missing_user_id():
    from security.request_guards import require_authenticated_user

    request = SimpleNamespace(state=SimpleNamespace())

    with pytest.raises(HTTPException) as exc:
        require_authenticated_user(request)

    assert exc.value.status_code == 401


@pytest.mark.parametrize("value", ["startup_123", "abc-DEF_123", "550e8400-e29b-41d4-a716-446655440000"])
def test_validate_route_id_accepts_expected_identifiers(value):
    from security.request_guards import validate_route_id

    assert validate_route_id(value, field_name="startup_id") == value


@pytest.mark.parametrize("value", ["", "../other", "a/b", "x y", "x<script>"])
def test_validate_route_id_rejects_unsafe_identifiers(value):
    from security.request_guards import validate_route_id

    with pytest.raises(HTTPException) as exc:
        validate_route_id(value, field_name="startup_id")

    assert exc.value.status_code == 422
