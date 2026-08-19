"""Tests for policy_resolver module."""
import pytest


def test_get_identity_disambiguation_rules_returns_the_active_version():
    from core import policy_resolver

    policy_resolver.reload()
    rules = policy_resolver.get_identity_disambiguation_rules()

    assert rules["auto_correct_confidence_floor"] == 0.85
