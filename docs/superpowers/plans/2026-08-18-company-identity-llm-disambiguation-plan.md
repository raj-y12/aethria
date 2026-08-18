# Company Identity LLM Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `resolve_company()`'s threshold-based ambiguity handling with an LLM-grounded disambiguation step that reads competing candidate content and decides, auto-correcting confident mistakes and falling back to `NEEDS_REVIEW` for genuine ambiguity.

**Architecture:** A new standalone module (`backend/resolver/identity_disambiguation.py`) makes one structured-JSON OpenAI call per ambiguous lookup and returns a typed result. `resolve_company()` calls it after picking a candidate the existing way, and applies the design's decision table (agree → proceed, confident disagree → correct, uncertain → review, call failure → review). A new versioned config key holds the auto-correct confidence floor.

**Tech Stack:** Python, Pydantic, OpenAI Python SDK (`utils.openai_client.build_openai_client`), pytest, existing `CostController`/`resources/config/` policy-resolution conventions already used throughout this repo.

## Global Constraints

- Runs on every eligible lookup (not gated behind existing ambiguity heuristics) — per the approved design, correctness takes priority over cost here. Cost is still tracked via `CostController.check_budget`/`record_usage`, never skipped for budget reasons.
- Skipped entirely when `website_hint` was supplied, or when there is only one `official_site`-scored candidate — no LLM call in either case.
- Confidence floor for auto-correction starts at `0.85`, lives in `resources/config/identity_disambiguation_rules/v1.json`, never a bare literal in Python (AGENTS.md invariant #3).
- LLM call failure, timeout, or malformed response fails closed to `NEEDS_REVIEW` — never silently trusts the un-checked heuristic pick (AGENTS.md invariant #5).
- New env var `IDENTITY_DISAMBIGUATION_MODEL` must be registered in `backend/env_config.py` and `.env.example` regenerated (AGENTS.md invariant #6).
- `resolve_company()` is a synchronous function called via `asyncio.to_thread` from `scout/engine.py` — the new LLM call must be synchronous (`OpenAI` client, not `AsyncOpenAI`), matching every other blocking call already inside `resolve_company()`.

---

### Task 1: Confidence-floor config

**Files:**
- Create: `resources/config/identity_disambiguation_rules/v1.json`
- Modify: `resources/config/active.json`
- Modify: `backend/core/policy_resolver.py`
- Test: `backend/tests/test_policy_resolver.py` (create if it does not already exist — check first)

**Interfaces:**
- Consumes: nothing new.
- Produces: `get_identity_disambiguation_rules() -> dict` returning `{"auto_correct_confidence_floor": 0.85}`, callable exactly like `get_triage_rules()`.

- [ ] **Step 1: Check for an existing policy_resolver test file**

Run: `find backend/tests -iname "*policy_resolver*"`

If a file exists, add to it. If not, create `backend/tests/test_policy_resolver.py`.

- [ ] **Step 2: Write the failing test**

```python
def test_get_identity_disambiguation_rules_returns_the_active_version():
    from core import policy_resolver

    policy_resolver.reload()
    rules = policy_resolver.get_identity_disambiguation_rules()

    assert rules["auto_correct_confidence_floor"] == 0.85
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest backend/tests/test_policy_resolver.py::test_get_identity_disambiguation_rules_returns_the_active_version -v -o asyncio_mode=auto`
Expected: FAIL with `AttributeError: module 'core.policy_resolver' has no attribute 'get_identity_disambiguation_rules'`

- [ ] **Step 4: Create the config file**

`resources/config/identity_disambiguation_rules/v1.json`:
```json
{
  "auto_correct_confidence_floor": 0.85
}
```

- [ ] **Step 5: Add the key to active.json**

In `resources/config/active.json`, add `"identity_disambiguation_rules": "v1"` alongside the existing `partner_rules`/`reviewer_rules`/`evaluation_rubric`/`triage_rules` keys.

- [ ] **Step 6: Wire the new key into policy_resolver.py**

In `backend/core/policy_resolver.py`:
- Add `"identity_disambiguation_rules"` to the `_POLICY_KEYS` tuple.
- Add `"identity_disambiguation_rules": "identity_disambiguation_rules"` to the `_POLICY_DIRS` dict.
- Add the accessor function, following the exact shape of `get_triage_rules`:

```python
def get_identity_disambiguation_rules() -> Any:
    _ensure_loaded()
    with _lock:
        return _policy_documents["identity_disambiguation_rules"]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python3 -m pytest backend/tests/test_policy_resolver.py::test_get_identity_disambiguation_rules_returns_the_active_version -v -o asyncio_mode=auto`
Expected: PASS

- [ ] **Step 8: Run the full existing policy_resolver-adjacent suite to confirm no regression**

Run: `python3 -m pytest backend/tests/test_policy_resolver.py backend/tests/test_triage_service.py -v -o asyncio_mode=auto`
Expected: all PASS (adding a required key to `_POLICY_KEYS` must not break existing policy loads — `_load_locked` raises if any key in `_POLICY_KEYS` is missing from `active.json`, so Step 5 is not optional).

- [ ] **Step 9: Commit**

```bash
git add resources/config/identity_disambiguation_rules/v1.json resources/config/active.json backend/core/policy_resolver.py backend/tests/test_policy_resolver.py
git commit -m "feat: add identity_disambiguation_rules versioned config"
```

---

### Task 2: Register the model env var

**Files:**
- Modify: `backend/env_config.py`
- Modify: `.env.example` (regenerated, not hand-edited)

**Interfaces:**
- Consumes: nothing new.
- Produces: `os.environ.get("IDENTITY_DISAMBIGUATION_MODEL", "gpt-5-nano")` becomes a registered, documented env var.

- [ ] **Step 1: Find the exact insertion point**

Run: `grep -n 'PARTNER_MODEL' backend/env_config.py`

Add the new `EnvVar` entry immediately after the `PARTNER_MODEL` line, in the same `"OpenAI / models"` group.

- [ ] **Step 2: Add the EnvVar entry**

```python
EnvVar("IDENTITY_DISAMBIGUATION_MODEL", "str", "gpt-5-nano", "OpenAI / models",
       "Model for LLM-grounded company identity disambiguation."),
```

- [ ] **Step 3: Regenerate .env.example**

Run: `grep -n "env.example\|generate" backend/env_config.py | head -5` to find the existing regeneration mechanism (this repo generates `.env.example` from the `EnvVar` registry per AGENTS.md invariant #6 — do not hand-edit). Run whatever script/command that mechanism specifies.

- [ ] **Step 4: Verify the registry test (if one exists) still passes**

Run: `python3 -m pytest backend/tests/test_config_registry.py -v -o asyncio_mode=auto`
Expected: PASS (this test scans for unregistered bare `os.getenv`/`os.environ.get` calls repo-wide, per the fresh-audit finding from earlier today confirming this test exists and covers the whole repo).

- [ ] **Step 5: Commit**

```bash
git add backend/env_config.py .env.example
git commit -m "feat: register IDENTITY_DISAMBIGUATION_MODEL env var"
```

---

### Task 3: `identity_disambiguation.py` — the disambiguation call, in isolation

**Files:**
- Create: `backend/resolver/identity_disambiguation.py`
- Test: `backend/tests/test_identity_disambiguation.py`

**Interfaces:**
- Consumes: `resources/config/policy_resolver.get_identity_disambiguation_rules()` (Task 1), `utils.openai_client.build_openai_client` (existing), `partner.decision._parse_llm_json_object` (existing, reused as-is — do not duplicate it), `resolver.company_resolver.EvidenceSource` (existing).
- Produces:
  ```python
  class DisambiguationResult(BaseModel):
      picked_url: Optional[str]
      confidence: float
      reasoning: str
      called: bool  # False when skipped or the call itself failed -- distinguishes "the LLM ran and returned this" from "nothing ran, here is the safe default"

  def disambiguate_identity(
      company_name: str,
      candidates: list["EvidenceSource"],
      *,
      user_id: str,
      cost_controller: Any = None,
      api_key: Optional[str] = None,
      model: Optional[str] = None,
  ) -> DisambiguationResult:
      ...
  ```
  Task 4 (`resolve_company()`) calls this directly with the `official_site`-classified candidate list.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_identity_disambiguation.py
from unittest.mock import MagicMock

import pytest

from resolver.company_resolver import EvidenceSource
from resolver.identity_disambiguation import DisambiguationResult, disambiguate_identity


def _candidates():
    return [
        EvidenceSource(
            url="https://notion.com",
            title="Notion — Home",
            snippet="Notion is a workspace for teams.",
            source_type="official_site",
            match_score=1.0,
        ),
        EvidenceSource(
            url="https://notiontechnologies.com/",
            title="Notion Technologies — Home",
            snippet="Notion Technologies builds industrial sensors.",
            source_type="official_site",
            match_score=0.85,
        ),
    ]


def _fake_client(content: str):
    client = MagicMock()
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    response.usage = MagicMock(total_tokens=123)
    client.chat.completions.create.return_value = response
    return client


def test_disambiguate_identity_returns_the_llm_pick(monkeypatch):
    content = '{"picked_url": "https://notion.com", "confidence": 0.95, "reasoning": "Matches the typed name directly."}'
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client",
        lambda *a, **k: _fake_client(content),
    )
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test"
    )
    assert result.called is True
    assert result.picked_url == "https://notion.com"
    assert result.confidence == 0.95


def test_disambiguate_identity_fails_closed_on_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client",
        lambda *a, **k: _fake_client("not json"),
    )
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test"
    )
    assert result.called is False
    assert result.picked_url is None
    assert result.confidence == 0.0


def test_disambiguate_identity_fails_closed_when_the_client_raises(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("network down")

    monkeypatch.setattr("resolver.identity_disambiguation.build_openai_client", boom)
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test"
    )
    assert result.called is False
    assert result.picked_url is None


def test_disambiguate_identity_fails_closed_with_no_api_key():
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key=None
    )
    assert result.called is False
    assert result.picked_url is None
    assert "api key" in result.reasoning.lower()


def test_disambiguate_identity_checks_and_records_cost_controller_budget(monkeypatch):
    content = '{"picked_url": "https://notion.com", "confidence": 0.95, "reasoning": "x"}'
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client",
        lambda *a, **k: _fake_client(content),
    )
    cost_controller = MagicMock()
    cost_controller.check_budget.return_value = (True, None)
    disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test",
        cost_controller=cost_controller,
    )
    cost_controller.check_budget.assert_called_once()
    cost_controller.record_usage.assert_called_once()


def test_disambiguate_identity_skips_the_call_when_budget_denies(monkeypatch):
    client = _fake_client('{"picked_url": "https://notion.com", "confidence": 0.95, "reasoning": "x"}')
    monkeypatch.setattr(
        "resolver.identity_disambiguation.build_openai_client", lambda *a, **k: client
    )
    cost_controller = MagicMock()
    cost_controller.check_budget.return_value = (False, "Daily call budget exceeded")
    result = disambiguate_identity(
        "Notion", _candidates(), user_id="user-test", api_key="sk-test",
        cost_controller=cost_controller,
    )
    assert result.called is False
    client.chat.completions.create.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_identity_disambiguation.py -v -o asyncio_mode=auto`
Expected: FAIL (module `resolver.identity_disambiguation` does not exist yet)

- [ ] **Step 3: Write the implementation**

```python
# backend/resolver/identity_disambiguation.py
"""LLM-grounded disambiguation for Company Resolver's identity pick.

The heuristic candidate scoring in company_resolver.py (slug similarity,
name-token overlap) has a ceiling for common/short company names -- several
distinct patches this month (Vercel/Hashimoto, Anthropic/anthropic.io,
General Electric/Motors, Notion) each fixed one text-matching collision.
This reads the actual candidate content and judges instead, per
docs/superpowers/specs/2026-08-18-company-identity-llm-disambiguation-design.md.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from pydantic import BaseModel

from utils.openai_client import build_openai_client
from partner.decision import _parse_llm_json_object

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-5-nano"
_MAX_COMPLETION_TOKENS = 1024  # gpt-5-nano is a reasoning model; too low silently empties content (live-observed, memory 2026-08-17).


class DisambiguationResult(BaseModel):
    picked_url: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    called: bool = False


def _safe_default(reasoning: str) -> DisambiguationResult:
    return DisambiguationResult(picked_url=None, confidence=0.0, reasoning=reasoning, called=False)


def _build_prompt(company_name: str, candidates: List[Any]) -> tuple[str, str]:
    system = (
        "You are disambiguating which of several search-result candidates is the "
        "real company a user typed a name for. Respond with exactly one JSON object: "
        '{"picked_url": "<one of the candidate URLs, or null if none confidently match>", '
        '"confidence": <0.0-1.0>, "reasoning": "<one sentence>"}. '
        "No markdown, no other text."
    )
    lines = [f'Typed company name: "{company_name}"', "", "Candidates:"]
    for c in candidates:
        lines.append(f"- URL: {c.url}\n  Title: {c.title}\n  Snippet: {c.snippet}")
    return system, "\n".join(lines)


def disambiguate_identity(
    company_name: str,
    candidates: List[Any],
    *,
    user_id: str,
    cost_controller: Any = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> DisambiguationResult:
    if not api_key:
        return _safe_default("disambiguation unavailable: no api key configured")
    if len(candidates) < 2:
        return _safe_default("disambiguation skipped: fewer than 2 candidates")

    effective_model = model or _DEFAULT_MODEL

    if cost_controller is not None:
        allowed, reason = cost_controller.check_budget(
            "identity_disambiguation", user_id, estimated_tokens=_MAX_COMPLETION_TOKENS
        )
        if not allowed:
            logger.warning(
                "identity_disambiguation: budget denied user_id=%s reason=%s", user_id, reason
            )
            return _safe_default(f"disambiguation unavailable: {reason}")

    system, user = _build_prompt(company_name, candidates)
    try:
        client = build_openai_client(api_key)
        response = client.chat.completions.create(
            model=effective_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
        )
        content = response.choices[0].message.content
    except Exception as e:
        logger.warning("identity_disambiguation: call failed user_id=%s: %s", user_id, e)
        return _safe_default(f"disambiguation unavailable: {e}")

    if cost_controller is not None:
        tokens_used = getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
        cost_controller.record_usage(
            "identity_disambiguation", user_id, tokens_used, model=effective_model
        )

    parsed = _parse_llm_json_object(content or "")
    if not parsed:
        return _safe_default("disambiguation unavailable: malformed model response")

    picked_url = parsed.get("picked_url")
    if picked_url is not None and not isinstance(picked_url, str):
        picked_url = None
    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    reasoning = str(parsed.get("reasoning") or "").strip()

    return DisambiguationResult(
        picked_url=picked_url, confidence=confidence, reasoning=reasoning, called=True
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_identity_disambiguation.py -v -o asyncio_mode=auto`
Expected: PASS, all 6 tests

- [ ] **Step 5: Commit**

```bash
git add backend/resolver/identity_disambiguation.py backend/tests/test_identity_disambiguation.py
git commit -m "feat: add LLM-grounded identity disambiguation module"
```

---

### Task 4: Wire into `resolve_company()`

**Files:**
- Modify: `backend/resolver/company_resolver.py`
- Modify: `backend/scout/engine.py:557-562` (the `resolve_company` call site — thread `cost_controller` and `api_key` through)
- Test: `backend/tests/test_company_resolver.py`

**Interfaces:**
- Consumes: `resolver.identity_disambiguation.disambiguate_identity` (Task 3), `core.policy_resolver.get_identity_disambiguation_rules` (Task 1).
- Produces: `resolve_company(..., cost_controller=None, api_key=None)` — two new optional keyword params, default `None` so every existing call site and test keeps working unchanged unless it opts in.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_company_resolver.py` (uses the existing `_pack`/`resolve_company`/`monkeypatch.setattr(cr, "retrieve_source_pack_merged", ...)` fixtures already in that file):

```python
def test_disambiguation_is_skipped_when_website_hint_given(monkeypatch):
    called = {"n": 0}

    def fake_disambiguate(*a, **k):
        called["n"] += 1
        return object()  # would blow up if actually used -- proves it wasn't

    monkeypatch.setattr(cr, "disambiguate_identity", fake_disambiguate)
    sources = [
        {"title": "Aethria — Home", "url": "https://aethria.co", "snippet": "Aethria."},
        {"title": "Aethria Labs", "url": "https://aethrialabs.com", "snippet": "Aethria Labs."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    resolve_company("Aethria", user_id=USER, website_hint="aethria.co")
    assert called["n"] == 0


def test_disambiguation_is_skipped_with_a_single_candidate(monkeypatch):
    called = {"n": 0}

    def fake_disambiguate(*a, **k):
        called["n"] += 1
        return object()

    monkeypatch.setattr(cr, "disambiguate_identity", fake_disambiguate)
    sources = [
        {"title": "Acme Robotics — Home", "url": "https://acmerobotics.com", "snippet": "Acme Robotics."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    resolve_company("Acme Robotics", user_id=USER)
    assert called["n"] == 0


def test_disambiguation_confidently_overriding_corrects_the_website(monkeypatch):
    from resolver.identity_disambiguation import DisambiguationResult

    sources = [
        {"title": "Notion — Home", "url": "https://notion.com", "snippet": "A workspace."},
        {"title": "Notion Technologies", "url": "https://notiontechnologies.com/", "snippet": "Industrial sensors."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    monkeypatch.setattr(
        cr,
        "disambiguate_identity",
        lambda *a, **k: DisambiguationResult(
            picked_url="https://notiontechnologies.com/", confidence=0.9, reasoning="x", called=True
        ),
    )
    res = resolve_company("Notion", user_id=USER)
    assert res.website == "https://notiontechnologies.com/"
    assert any(a.website == "https://notion.com" for a in res.alternative_matches)
    assert res.resolution_status != "NEEDS_REVIEW"


def test_disambiguation_low_confidence_disagreement_forces_review(monkeypatch):
    from resolver.identity_disambiguation import DisambiguationResult

    sources = [
        {"title": "Notion — Home", "url": "https://notion.com", "snippet": "A workspace."},
        {"title": "Notion Technologies", "url": "https://notiontechnologies.com/", "snippet": "Industrial sensors."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    monkeypatch.setattr(
        cr,
        "disambiguate_identity",
        lambda *a, **k: DisambiguationResult(
            picked_url="https://notiontechnologies.com/", confidence=0.4, reasoning="unsure", called=True
        ),
    )
    res = resolve_company("Notion", user_id=USER)
    assert res.website == "https://notion.com"  # heuristic pick stands, not silently swapped
    assert res.resolution_status == "NEEDS_REVIEW"


def test_disambiguation_call_failure_forces_review_not_silent_trust(monkeypatch):
    from resolver.identity_disambiguation import DisambiguationResult

    sources = [
        {"title": "Notion — Home", "url": "https://notion.com", "snippet": "A workspace."},
        {"title": "Notion Technologies", "url": "https://notiontechnologies.com/", "snippet": "Industrial sensors."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    monkeypatch.setattr(
        cr,
        "disambiguate_identity",
        lambda *a, **k: DisambiguationResult(called=False, reasoning="no api key"),
    )
    res = resolve_company("Notion", user_id=USER)
    assert res.resolution_status == "NEEDS_REVIEW"


def test_disambiguation_agreeing_with_heuristic_proceeds_normally(monkeypatch):
    from resolver.identity_disambiguation import DisambiguationResult

    sources = [
        {"title": "Notion — Home", "url": "https://notion.com", "snippet": "A workspace."},
        {"title": "Notion Technologies", "url": "https://notiontechnologies.com/", "snippet": "Industrial sensors."},
    ]
    monkeypatch.setattr(cr, "retrieve_source_pack_merged", lambda **kw: _pack(sources))
    monkeypatch.setattr(
        cr,
        "disambiguate_identity",
        lambda *a, **k: DisambiguationResult(
            picked_url="https://notion.com", confidence=0.95, reasoning="matches", called=True
        ),
    )
    res = resolve_company("Notion", user_id=USER)
    assert res.website == "https://notion.com"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest backend/tests/test_company_resolver.py -k disambiguation -v -o asyncio_mode=auto`
Expected: FAIL (no `disambiguate_identity` import in `company_resolver.py`, no such behavior wired yet)

- [ ] **Step 3: Import and wire the call**

At the top of `backend/resolver/company_resolver.py`, add:
```python
from resolver.identity_disambiguation import disambiguate_identity
```
and
```python
from core.policy_resolver import get_identity_disambiguation_rules
```

Verified exact insertion point (`backend/resolver/company_resolver.py:1018-1034` as of this plan being written): `resolve_company()` computes `resolution.confidence` (line 1007), `resolution.missing_fields` (1008), `resolution.resolution_status` via `_assign_status()` (1009), appends a `NEEDS_REVIEW` note (1012-1017) and a `PARTIAL`/`LOW_CONFIDENCE` note (1018-1022), then calls `_log_stage(...)` (1024-1033) and returns. Insert the new block **after line 1022 and before the `_log_stage(...)` call at line 1024** — not immediately after `_assign_identity_fields` (line 978-984). Inserting earlier would have this block's `resolution.resolution_status = "NEEDS_REVIEW"` overwritten by `_assign_status()` at line 1009, which runs after. Inserting after line 1022 (but before `_log_stage`) means: all of today's existing status/confidence/notes computation finishes untouched first, this block gets the final say on the status, and `_log_stage` logs the true final state including any correction.

```python
    if not website_hint:
        official_candidates = [
            s for s in resolution.evidence_sources
            if s.source_type == "official_site" and s.match_score >= 0.5
        ]
        if len(official_candidates) >= 2:
            rules = get_identity_disambiguation_rules()
            floor = float(rules.get("auto_correct_confidence_floor", 0.85))
            heuristic_pick = resolution.website
            result = disambiguate_identity(
                company, official_candidates, user_id=uid,
                cost_controller=cost_controller, api_key=api_key,
            )
            if result.called and result.picked_url and result.picked_url != heuristic_pick:
                if result.confidence >= floor:
                    if heuristic_pick and all(
                        a.website != heuristic_pick for a in resolution.alternative_matches
                    ):
                        resolution.alternative_matches.append(
                            AlternativeMatch(
                                name=registrable_domain(_host_of(heuristic_pick)).split(".", 1)[0],
                                website=heuristic_pick,
                                reason="Superseded by LLM identity disambiguation.",
                                match_score=1.0,
                            )
                        )
                    resolution.website = result.picked_url
                    resolution.notes.append(
                        f"Identity corrected by LLM disambiguation: was {heuristic_pick}, "
                        f"now {result.picked_url}. {result.reasoning}"
                    )
                else:
                    resolution.notes.append(
                        f"LLM disambiguation uncertain (confidence={result.confidence:.2f}): {result.reasoning}"
                    )
                    resolution.resolution_status = "NEEDS_REVIEW"
            elif not result.called:
                resolution.notes.append(f"LLM disambiguation unavailable: {result.reasoning}")
                resolution.resolution_status = "NEEDS_REVIEW"
```

Add `cost_controller: Any = None, api_key: Optional[str] = None` to `resolve_company()`'s signature.

- [ ] **Step 4: Thread `cost_controller`/`api_key` through the call site**

In `backend/scout/engine.py`, the existing call at (originally) lines 557-562:
```python
resolution = await asyncio.to_thread(
    resolve_company,
    company,
    user_id=self.tenant_user_id,
    website_hint=website,
)
```
becomes:
```python
resolution = await asyncio.to_thread(
    resolve_company,
    company,
    user_id=self.tenant_user_id,
    website_hint=website,
    cost_controller=self.cost_controller,
    api_key=self.api_key,
)
```
Verified: `ScoutEngine.__init__` (`backend/scout/engine.py:53,74`) takes `api_key: str` and stores it as `self.api_key` — same attribute name used above.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest backend/tests/test_company_resolver.py -v -o asyncio_mode=auto`
Expected: PASS, all tests including the 6 new disambiguation tests and every pre-existing test in the file (the pre-existing ambiguous-identity tests, e.g. `test_ambiguous_same_slug_domains_need_review`, do not mock `disambiguate_identity` — they will exercise the real fail-closed path since no `api_key` is passed in those tests, and should still land on `NEEDS_REVIEW`, their existing expected outcome).

- [ ] **Step 6: Run the full resolver/scout/founder test suite**

Run: `python3 -m pytest backend/tests/test_company_resolver.py backend/tests/test_founder_resolver.py backend/tests/test_scout_payload_coercion.py backend/tests/test_merge_resolution_sources_anchor_filter.py backend/tests/test_founder_evidence.py -v -o asyncio_mode=auto`
Expected: PASS, zero regressions.

- [ ] **Step 7: Run the full backend suite**

Run: `python3 -m pytest -o asyncio_mode=auto -q`
Expected: same 39 pre-existing Postgres-container failures (no live Postgres in this environment) as the baseline recorded in `docs/archive/plans/2026-08-18-full-codebase-audit.md`'s most recent update; no new failures.

- [ ] **Step 8: Commit**

```bash
git add backend/resolver/company_resolver.py backend/scout/engine.py backend/tests/test_company_resolver.py
git commit -m "feat: wire LLM identity disambiguation into resolve_company"
```

---

### Task 5: Live-dispatch validation

Not automatable — requires a real `OPENAI_API_KEY` and a live dispatch, matching the verification standard used for every other fix in this session's history.

- [ ] **Step 1:** Run a live on-demand lookup for "Notion" through the app (same path used to diagnose the original bug: `POST` a company lookup, or trigger via the dispatch UI).
- [ ] **Step 2:** Inspect the resulting `scout_info.company_resolution` row in the database — confirm `notion.com` is picked (not overridden incorrectly), and that `notes` either shows no disambiguation note (if the LLM simply agreed) or a clear correction/uncertainty note if it didn't.
- [ ] **Step 3:** Run a live lookup for a name known to collide (e.g. "Perplexity" — cited in the design doc's motivating bug list) and confirm the LLM either correctly disambiguates or produces a `NEEDS_REVIEW` with a legible reason, not a silent wrong pick.
- [ ] **Step 4:** Check `CostController`'s recorded usage for the `identity_disambiguation` agent_type to confirm cost tracking is actually recording (not just structurally present but never called end-to-end).
- [ ] **Step 5:** Report results back — do not report this task complete without having actually run it, per this session's standing verification convention.
