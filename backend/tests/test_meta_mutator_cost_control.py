"""Regression coverage (audit HIGH-H4): PromptMutator._call_llm used to fire
one prompt-rewrite completion per mutation target with no budget gate at
all -- direct violation of AGENTS.md invariant #8. It now checks/records
against CostController's "meta" budget, mirroring the pattern already used
by scout/reviewer/partner."""

from meta.mutator import PromptMutator


class _FakeUsage:
    def __init__(self, total_tokens):
        self.total_tokens = total_tokens


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content, total_tokens=123):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(total_tokens)


class _FakeCompletions:
    def __init__(self, content='{"new_prompt": "x", "reasoning": "y"}'):
        self.content = content
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        return _FakeResponse(self.content)


class _FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": _FakeCompletions()})()


class _FakeCostController:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.check_calls = []
        self.record_calls = []

    def check_budget(self, agent_type, agent_id, estimated_tokens=0):
        self.check_calls.append((agent_type, agent_id, estimated_tokens))
        return (self.allowed, None if self.allowed else "Daily call budget exceeded")

    def record_usage(self, agent_type, agent_id, tokens_used, *, model="unknown", provider="openai"):
        self.record_calls.append((agent_type, agent_id, tokens_used))


def _mutator(cost_controller):
    m = PromptMutator({}, cycle_number=1, user_id="test-user", cost_controller=cost_controller)
    m._client = _FakeClient()
    m.api_key = "sk-test"
    return m


def test_call_llm_checks_meta_budget_before_calling():
    cc = _FakeCostController(allowed=True)
    mutator = _mutator(cc)

    new_prompt, reasoning = mutator._call_llm("rewrite this")

    assert new_prompt == "x"
    assert cc.check_calls == [("meta", "test-user", 8192)]
    assert cc.record_calls == [("meta", "test-user", 123)]


def test_call_llm_skips_the_call_when_budget_denies():
    cc = _FakeCostController(allowed=False)
    mutator = _mutator(cc)

    new_prompt, reasoning = mutator._call_llm("rewrite this")

    assert (new_prompt, reasoning) == (None, None)
    # The actual completions.create was never reached.
    assert mutator._client.chat.completions.call_count == 0
    assert cc.record_calls == []


def test_call_llm_still_works_with_no_cost_controller_configured():
    mutator = _mutator(cost_controller=None)
    new_prompt, reasoning = mutator._call_llm("rewrite this")
    assert new_prompt == "x"


def test_call_llm_uses_the_per_target_agent_id_not_a_shared_one():
    """Self-audit catch on H4: CostController's cooldown (60s for "meta")
    keys on agent_id, and apply() calls _call_llm once per mutation target,
    synchronously, within the same cycle. An early version of this fix used
    a single shared agent_id (self.user_id) for every target -- meaning the
    FIRST target's call would set the cooldown and silently deny every
    other target rewritten in the same cycle. agent_id must be per-target."""
    cc = _FakeCostController(allowed=True)
    mutator = _mutator(cc)

    mutator._call_llm("rewrite scout prompt", agent_id="MarketDrivenScout")
    mutator._client.chat.completions.call_count = 0
    mutator._call_llm("rewrite reviewer prompt", agent_id="DefaultReviewer")

    assert cc.check_calls == [
        ("meta", "MarketDrivenScout", 8192),
        ("meta", "DefaultReviewer", 8192),
    ]
