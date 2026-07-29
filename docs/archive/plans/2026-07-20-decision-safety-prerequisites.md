# Decision Safety Prerequisites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make evidence grounding, missingness, critical-risk precedence, decision vocabulary, and thesis/published-policy gates safe and authoritative before canonical writes can be activated.

**Architecture:** Extend the immutable evaluator with a versioned decision-safety policy and a pure score-eligibility gate over evidence metadata. Keep recommendation calculation deterministic, consolidate compatibility semantics, and use one prerequisite loader for API and durable lookup paths. The still-live legacy scorer and Partner receive matching fail-safe corrections so unsafe behavior does not remain active during the strangler migration.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, asyncpg/PostgreSQL read models, Pytest/pytest-asyncio, React 18, TypeScript, TanStack Query, Vitest.

## Global Constraints

- Every storage read/write and every service entry point receives an explicit non-empty `user_id`; no global or implicit tenant is permitted.
- Existing Supabase migrations are immutable; this slice requires no SQL migration.
- Partner-rule changes are versioned in a new `resources/config/partner_rules/v2.json`; `v1.json` is not edited.
- A complete active thesis and an exact hash-bound published policy are hard gates for evaluation and recommendation.
- A failed or blocked workflow is never represented as PASS or success.
- Missing criteria remain `score=None`; no component, dimension, or overall fallback may manufacture a neutral score.
- Score-bearing claims must satisfy the versioned evidence-eligibility policy.
- Grounded critical risks and hard mandate exclusions take precedence over score bands.
- Recommendation values are `advance | monitor | pass | insufficient_evidence`; human rulings are `advance | monitor | pass | invest`.
- Only human rulings contain `invest`; no compatibility adapter may turn an ADVANCE ruling into legacy `YES`.
- LLM output may explain a policy-permitted outcome but cannot change hard exclusions or critical-risk precedence.
- All behavioral changes follow red-green TDD and each task ends with its focused tests passing.

---

### Task 1: Version the decision-safety policy

**Files:**
- Create: `resources/config/partner_rules/v2.json`
- Modify: `resources/config/active.json`
- Modify: `backend/evaluation_v2/models.py`
- Modify: `backend/evaluation_v2/policy.py`
- Modify: `backend/tests/evaluation_v2/test_evaluation_policy_gate.py`
- Modify: `backend/tests/test_config_registry.py`

**Interfaces:**
- Consumes: the existing exact compiled tenant scoring policy and versioned Partner-rules document.
- Produces: `EvidenceEligibilityPolicy`, `DecisionSafetyPolicy`, and `EvaluationPolicy.decision_safety` for Tasks 3–5.

- [ ] **Step 1: Write the failing policy-contract tests**

Add these assertions to `backend/tests/evaluation_v2/test_evaluation_policy_gate.py`:

```python
def test_compiled_policy_carries_versioned_decision_safety_contract():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules={
            "version": "2.0",
            "score_thresholds": {"min_avg_strong_yes": 8, "min_avg_pass": 5.5},
            "decision_safety": {
                "evidence_eligibility": {
                    "allowed_assertion_classes": ["externally_verified", "operator_asserted"],
                    "allowed_relationships": ["supports", "partially_establishes"],
                    "require_verified_evidence": True,
                    "min_support_strength": 0.5,
                    "min_source_quality": 0.4,
                    "blocked_trust_classes": ["model", "unknown"],
                },
                "critical_risk_claim_types": ["critical_risk"],
                "hard_exclusion_claim_types": ["mandate_exclusion"],
            },
        },
    )

    assert policy.decision_safety.evidence_eligibility.min_support_strength == 0.5
    assert policy.decision_safety.critical_risk_claim_types == ["critical_risk"]
    assert policy.hard_exclusion_claim_types == ["mandate_exclusion"]


def test_missing_decision_safety_config_fails_closed():
    with pytest.raises(ValueError, match="decision_safety"):
        evaluation_policy_from_compiled(
            _compiled_policy(), partner_rules={"version": "2.0"}
        )
```

Extend `backend/tests/test_config_registry.py` to assert that `active.json` selects `v2` and that `v2.json` exists and reports version `2.0`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
cd backend && pytest -q \
  tests/evaluation_v2/test_evaluation_policy_gate.py \
  tests/test_config_registry.py
```

Expected: failures because the decision-safety models and `v2` rules do not exist.

- [ ] **Step 3: Add the exact Pydantic contracts**

Add to `backend/evaluation_v2/models.py`:

```python
class EvidenceEligibilityPolicy(BaseModel):
    allowed_assertion_classes: List[str] = Field(min_length=1)
    allowed_relationships: List[str] = Field(min_length=1)
    require_verified_evidence: bool = True
    min_support_strength: float = Field(default=0.5, ge=0, le=1)
    min_source_quality: float = Field(default=0.4, ge=0, le=1)
    blocked_trust_classes: List[str] = Field(default_factory=lambda: ["model", "unknown"])


class DecisionSafetyPolicy(BaseModel):
    evidence_eligibility: EvidenceEligibilityPolicy
    critical_risk_claim_types: List[str] = Field(default_factory=list)
    hard_exclusion_claim_types: List[str] = Field(default_factory=list)
```

Add `decision_safety: DecisionSafetyPolicy` to `EvaluationPolicy`. Keep the existing `hard_exclusion_claim_types` field temporarily for repository/API compatibility, but populate it from `decision_safety.hard_exclusion_claim_types` in `evaluation_policy_from_compiled()`.

- [ ] **Step 4: Create Partner rules v2 and bind it in policy conversion**

Create `resources/config/partner_rules/v2.json` by preserving every v1 rule and changing only the top-level version to `2.0` plus this top-level block:

```json
"decision_safety": {
  "evidence_eligibility": {
    "allowed_assertion_classes": ["externally_verified", "operator_asserted", "founder_asserted"],
    "allowed_relationships": ["supports", "partially_establishes"],
    "require_verified_evidence": true,
    "min_support_strength": 0.5,
    "min_source_quality": 0.4,
    "blocked_trust_classes": ["model", "unknown"]
  },
  "critical_risk_claim_types": ["critical_risk", "regulatory_blocker", "execution_impossibility"],
  "hard_exclusion_claim_types": ["mandate_exclusion", "excluded_sector", "excluded_geography", "excluded_stage"]
}
```

Change only `"partner_rules": "v2"` in `resources/config/active.json`. In `backend/evaluation_v2/policy.py`, validate the block with `DecisionSafetyPolicy.model_validate()` and pass the exact object and exclusion types into `EvaluationPolicy`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add resources/config/partner_rules/v2.json resources/config/active.json \
  backend/evaluation_v2/models.py backend/evaluation_v2/policy.py \
  backend/tests/evaluation_v2/test_evaluation_policy_gate.py \
  backend/tests/test_config_registry.py
git commit -m "feat: version decision safety policy"
```

---

### Task 2: Make the live legacy scorer fail safe on thin evidence

**Files:**
- Modify: `backend/config/scoring_config.py`
- Modify: `backend/utils/reviewer_structured_signals_clamp.py`
- Modify: `backend/services/scoring/aggregation_layer.py`
- Modify: `backend/tests/test_scoring_thin_evidence_characterization.py`
- Modify: `backend/tests/test_reviewer_structured_signals_clamp.py`

**Interfaces:**
- Consumes: legacy Reviewer structured-signal components during the migration window.
- Produces: confidence-discounted, evidence-capped legacy display scores; the canonical evaluator in Task 3 remains the eventual authority.

- [ ] **Step 1: Flip the characterization test to the safe contract**

Rename the first characterization test to `test_strong_label_without_grounding_cannot_publish_max_score` and replace the bug assertions with:

```python
engine = DeterministicScoringEngine(evidence_calibration=True)
result = engine.score(THIN_EVIDENCE_SCOUT, THIN_EVIDENCE_REVIEW)
network = result["defensibility"]["components"]["network_effects"]

assert network["score"] < 10.0
assert result["defensibility"]["unscored"] is True
assert result["defensibility"]["confidence"] == 0.0
```

Add to `backend/tests/test_reviewer_structured_signals_clamp.py`:

```python
def test_ungrounded_label_is_cleared_by_default(monkeypatch):
    monkeypatch.delenv("REVIEWER_SIGNALS_STRICT_EVIDENCE", raising=False)
    monkeypatch.delenv("REVIEWER_SIGNALS_STRICT_CLEAR", raising=False)
    signals = {"defensibility": {"network_effects": {
        "label": "strong", "confidence": 0.9, "evidence": "speculation"
    }}}
    clamped = clamp_structured_signals_evidence(
        {"references": ["https://example.com/company"]}, signals
    )
    component = clamped["defensibility"]["network_effects"]
    assert component.get("label") is None
    assert component.get("value") is None
    assert component["confidence"] <= 0.2
```

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
cd backend && pytest -q \
  tests/test_scoring_thin_evidence_characterization.py \
  tests/test_reviewer_structured_signals_clamp.py
```

Expected: the default clamp test fails and the current bug test still exposes 10/10.

- [ ] **Step 3: Enable safe defaults and require a grounding signal**

In `backend/config/scoring_config.py`, import `os` and replace the constant with an explicit safe-default environment switch:

```python
EVIDENCE_CALIBRATION_ENABLED = os.getenv(
    "SCORING_EVIDENCE_CALIBRATION_ENABLED", "true"
).strip().lower() in {"1", "true", "yes"}
```

In `clamp_structured_signals_evidence()`, use `"true"` as the default for both `REVIEWER_SIGNALS_STRICT_EVIDENCE` and `REVIEWER_SIGNALS_STRICT_CLEAR`.

In `backend/services/scoring/aggregation_layer.py`, replace `_has_concrete_evidence()` with a grounding-aware check:

```python
def _has_concrete_evidence(comp: Dict[str, Any]) -> bool:
    evidence = str(comp.get("evidence") or "").strip()
    reasoning = str(comp.get("reasoning") or "").strip()
    grounded = bool(evidence) or bool(comp.get("rule"))
    if not grounded and reasoning.lower() in {"", "speculative", "guess", "unknown"}:
        return False
    for key in ("value", "label"):
        raw = comp.get(key)
        if isinstance(raw, str) and raw.strip() and not _MISSING_RE.match(raw.strip()):
            return grounded
        if raw not in (None, "", [], {}):
            return grounded
    return False
```

The strict clamp is the primary source guard; aggregation remains a second fail-safe.

- [ ] **Step 4: Run focused and structured-scoring regressions**

```bash
cd backend && pytest -q \
  tests/test_scoring_thin_evidence_characterization.py \
  tests/test_reviewer_structured_signals_clamp.py \
  tests/test_structured_scoring_engine.py \
  tests/test_scoring_golden_snapshot.py
```

Expected: all selected tests pass. If a golden snapshot changes, update only score fields whose evidence-capping difference is explicitly asserted by the test; do not blanket-regenerate fixtures.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/config/scoring_config.py \
  backend/utils/reviewer_structured_signals_clamp.py \
  backend/services/scoring/aggregation_layer.py \
  backend/tests/test_scoring_thin_evidence_characterization.py \
  backend/tests/test_reviewer_structured_signals_clamp.py
git commit -m "fix: cap thin evidence scoring"
```

---

### Task 3: Gate canonical scoring on immutable evidence metadata

**Files:**
- Modify: `backend/evaluation_v2/models.py`
- Modify: `backend/evaluation_v2/service.py`
- Modify: `backend/evaluation_v2/repository.py`
- Modify: `backend/tests/evaluation_v2/test_evaluator.py`
- Modify: `backend/tests/evaluation_v2/test_evaluation_repository_projection.py`

**Interfaces:**
- Consumes: `EvaluationPolicy.decision_safety.evidence_eligibility` from Task 1 and immutable claim/link/artifact metadata.
- Produces: `ScoreEligibility` and score-eligible claim subsets used by canonical evaluation.

- [ ] **Step 1: Write failing pure eligibility tests**

Add a helper that builds a link containing `verification_state`, `source_quality`, `trust_class`, `untrusted_input`, and `prompt_injection_detected`. Add these tests to `backend/tests/evaluation_v2/test_evaluator.py`:

```python
def test_ungrounded_external_claim_is_unscored_and_cannot_advance():
    snapshot, _ = snapshot_claims(_claims(), links=[])
    result = evaluate_snapshot(snapshot, _policy())
    assert all(item.score is None for item in result.criteria)
    assert result.recommendation.state is RecommendationState.INSUFFICIENT_EVIDENCE


def test_model_inferred_claim_cannot_establish_decisive_criterion():
    claims = _claims()
    claims[0]["assertion_class"] = "model_inferred"
    links = [_verified_link("claim-market")]
    snapshot, _ = snapshot_claims(claims, links)
    market = next(item for item in evaluate_snapshot(snapshot, _policy()).criteria
                  if item.criterion == "market")
    assert market.score is None
    assert "assertion_class_not_allowed" in market.quality_flags


def test_verified_supported_claim_is_score_eligible():
    links = [_verified_link("claim-market"), _verified_link("claim-execution")]
    snapshot, _ = snapshot_claims(_claims(), links)
    result = evaluate_snapshot(snapshot, _policy())
    assert result.recommendation.state is RecommendationState.ADVANCE
```

Add `test_snapshot_hash_changes_when_grounding_metadata_changes` and a repository test that asserts the link query joins `evidence_items` and `evidence_artifacts` tenant-safely.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
cd backend && pytest -q \
  tests/evaluation_v2/test_evaluator.py \
  tests/evaluation_v2/test_evaluation_repository_projection.py
```

Expected: ungrounded claims still score and the repository query lacks evidence metadata.

- [ ] **Step 3: Add `ScoreEligibility` and the pure gate**

Add to `backend/evaluation_v2/models.py`:

```python
class ScoreEligibility(BaseModel):
    eligible: bool
    reason_codes: List[str] = Field(default_factory=list)
```

Add to `backend/evaluation_v2/service.py`:

```python
def evaluate_claim_score_eligibility(
    claim: Dict[str, Any], *, policy: EvidenceEligibilityPolicy
) -> ScoreEligibility:
    reasons: list[str] = []
    if claim.get("assertion_class_at_snapshot") not in policy.allowed_assertion_classes:
        reasons.append("assertion_class_not_allowed")
    allowed_links = [
        link for link in claim.get("evidence_relationships", [])
        if link.get("relationship") in policy.allowed_relationships
        and float(link.get("support_strength") or 0) >= policy.min_support_strength
        and float(link.get("source_quality") or 0) >= policy.min_source_quality
        and link.get("trust_class") not in policy.blocked_trust_classes
        and not bool(link.get("prompt_injection_detected"))
    ]
    if policy.require_verified_evidence:
        allowed_links = [link for link in allowed_links
                         if link.get("verification_state") == "verified"]
    if not allowed_links:
        reasons.append("no_eligible_supporting_evidence")
    return ScoreEligibility(eligible=not reasons, reason_codes=reasons)
```

For `operator_asserted` claims with a non-empty operator attribution, allow a synthetic attributed support entry only when the policy explicitly includes `operator_asserted`; never synthesize support for `model_inferred` or `unverified`.

- [ ] **Step 4: Snapshot and query the grounding metadata**

Extend each `evidence_relationships` item emitted by `snapshot_claims()` with the exact fields used above. In `EvaluationRepository.evaluate()`, change the link query to join:

```sql
join public.evidence_items ei
  on ei.user_id=l.user_id and ei.evidence_item_id=l.evidence_item_id
join public.evidence_artifacts ea
  on ea.user_id=ei.user_id and ea.artifact_id=ei.artifact_id
```

and select `ei.verification_state`, `ei.source_quality`, `ea.trust_class`, `ea.untrusted_input`, and `ea.prompt_injection_detected`. Keep every join and filter tenant-scoped.

Also snapshot `operator_attribution_at_snapshot` from the claim so the narrowly allowed operator-asserted path is reproducible rather than consulting a live row later.

Filter scored claims through `evaluate_claim_score_eligibility()` and copy rejection reasons into the affected criterion's `quality_flags`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add backend/evaluation_v2/models.py backend/evaluation_v2/service.py \
  backend/evaluation_v2/repository.py \
  backend/tests/evaluation_v2/test_evaluator.py \
  backend/tests/evaluation_v2/test_evaluation_repository_projection.py
git commit -m "feat: ground canonical evaluation scores"
```

---

### Task 4: Preserve required missingness as insufficient evidence

**Files:**
- Modify: `backend/evaluation_v2/service.py`
- Modify: `backend/tests/evaluation_v2/test_evaluator.py`
- Modify: `backend/tests/evaluation_v2/test_evaluation_repository_projection.py`

**Interfaces:**
- Consumes: score-eligible claims from Task 3 and existing `CriterionRule.required`.
- Produces: deterministic `INSUFFICIENT_EVIDENCE` whenever a required criterion is unscored.

- [ ] **Step 1: Write failing missingness tests**

```python
def test_required_unscored_criterion_forces_insufficient_evidence_despite_high_average():
    claims = [_claims()[0]]
    links = [_verified_link("claim-market")]
    snapshot, _ = snapshot_claims(claims, links)
    result = evaluate_snapshot(snapshot, _policy())
    assert result.criteria[0].score == 8.0
    assert next(c for c in result.criteria if c.criterion == "execution").score is None
    assert result.recommendation.state is RecommendationState.INSUFFICIENT_EVIDENCE
    assert "execution" in result.recommendation.missing_information


def test_optional_unscored_criterion_never_receives_numeric_placeholder():
    policy = _policy().model_copy(deep=True)
    policy.criteria[1].required = False
    snapshot, _ = snapshot_claims([_claims()[0]], [_verified_link("claim-market")])
    result = evaluate_snapshot(snapshot, policy)
    execution = next(c for c in result.criteria if c.criterion == "execution")
    assert execution.score is None
```

Also add an all-unscored test expecting zero confidence and `INSUFFICIENT_EVIDENCE`.

- [ ] **Step 2: Run tests and verify RED**

```bash
cd backend && pytest -q tests/evaluation_v2/test_evaluator.py
```

Expected: the high partial average can still ADVANCE under coverage alone.

- [ ] **Step 3: Make `required` authoritative**

In `evaluate_snapshot()`, collect `required_missing` separately and select outcomes in this order after decisive risks are handled:

```python
if required_missing or coverage < policy.minimum_scored_weight:
    state = RecommendationState.INSUFFICIENT_EVIDENCE
elif average >= policy.advance_threshold:
    state = RecommendationState.ADVANCE
elif average <= policy.pass_threshold:
    state = RecommendationState.PASS
else:
    state = RecommendationState.MONITOR
```

Keep `CriterionResult.score=None`; do not insert `DEFAULT_SCORE`. Include required missing criteria in `missing_information`, `change_conditions`, and `human_review_required`.

- [ ] **Step 4: Run focused projection regressions**

```bash
cd backend && pytest -q \
  tests/evaluation_v2/test_evaluator.py \
  tests/evaluation_v2/test_evaluation_repository_projection.py
```

Expected: all selected tests pass and serialized criterion scores remain null.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/evaluation_v2/service.py \
  backend/tests/evaluation_v2/test_evaluator.py \
  backend/tests/evaluation_v2/test_evaluation_repository_projection.py
git commit -m "fix: preserve required evaluation missingness"
```

---

### Task 5: Apply grounded critical-risk precedence in canonical and legacy Partner paths

**Files:**
- Modify: `backend/evaluation_v2/service.py`
- Modify: `backend/partner/decision.py`
- Modify: `backend/tests/evaluation_v2/test_evaluator.py`
- Modify: `backend/tests/test_partner_decision_fallback.py`
- Modify: `backend/tests/test_partner_mandate_gate.py`

**Interfaces:**
- Consumes: versioned critical-risk/exclusion claim types and Task 3 eligibility.
- Produces: deterministic PASS with mandatory human review before any score-band decision.

- [ ] **Step 1: Write the two high-score critical-risk regressions**

For the canonical evaluator, create high supported score claims plus a supported `critical_risk` claim whose `normalized_value` contains `{"value": True}`. Assert PASS, `human_review_required=True`, and the risk in `principal_risks`.

Replace the current legacy test expectation with:

```python
def test_critical_risk_forces_pass_even_with_invest_scores():
    engine = PartnerDecisionEngine(use_llm_fallback=False, api_key=None)
    review = _base_review()
    review.update({
        "verdict": "STRONG",
        "market_score": 9,
        "product_score": 9,
        "technical_score": 9,
        "execution_score": 9,
        "defensibility_score": 9,
        "key_risks": ["Regulatory ban risk in primary market"],
    })
    out = engine.decide(_base_scout(), review)
    assert out["recommendation"] == "PASS"
    assert out["decision"] == "NO"
    assert out["human_review_required"] is True
    assert "critical" in out["next_action"].lower()
```

Add a canonical test proving an ungrounded critical-risk claim cannot auto-PASS; it must be reported as ineligible/missing uncertainty.

- [ ] **Step 2: Run tests and verify RED**

```bash
cd backend && pytest -q \
  tests/evaluation_v2/test_evaluator.py \
  tests/test_partner_decision_fallback.py \
  tests/test_partner_mandate_gate.py
```

Expected: the legacy reproduction returns INVEST and the canonical critical-risk type is not applied.

- [ ] **Step 3: Implement one canonical precedence helper**

Add to `backend/evaluation_v2/service.py`:

```python
def decisive_policy_outcome(
    snapshot: Sequence[Dict[str, Any]], policy: EvaluationPolicy
) -> tuple[RecommendationState | None, list[str], list[str]]:
    risks: list[str] = []
    conflicts: list[str] = []
    for claim in snapshot:
        if claim.get("status_at_snapshot") != "current":
            continue
        eligibility = evaluate_claim_score_eligibility(
            claim, policy=policy.decision_safety.evidence_eligibility
        )
        if not eligibility.eligible or not bool((claim.get("normalized_value") or {}).get("value")):
            continue
        claim_type = claim.get("claim_type")
        if claim_type in policy.decision_safety.hard_exclusion_claim_types:
            conflicts.append(str(claim_type))
        if claim_type in policy.decision_safety.critical_risk_claim_types:
            risks.append(str(claim.get("display_text") or claim_type))
    if conflicts or risks:
        return RecommendationState.PASS, risks, conflicts
    return None, risks, conflicts
```

Call this before required-missing and score-band logic. Merge returned values into `principal_risks` and `mandate_conflicts`.

- [ ] **Step 4: Correct the still-live legacy Partner branch**

In `backend/partner/decision.py`, calculate score-band recommendation first, then override it before tags/rationale:

```python
final_recommendation = self._canonical_recommendation(avg_score)
if has_critical_risk:
    final_recommendation = "PASS"
```

Change the critical-risk branch to `_emit_deterministic(8 + conviction_adjust, True)` and ensure its next action comes from `next_actions["critical_risks"]`. Do not let the LLM branch alter this outcome.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 5**

```bash
git add backend/evaluation_v2/service.py backend/partner/decision.py \
  backend/tests/evaluation_v2/test_evaluator.py \
  backend/tests/test_partner_decision_fallback.py \
  backend/tests/test_partner_mandate_gate.py
git commit -m "fix: enforce critical risk precedence"
```

---

### Task 6: Consolidate recommendation/ruling semantics and expose ADVANCE in the ruling UI

**Files:**
- Modify: `backend/utils/partner_codes.py`
- Modify: `backend/evaluation_v2/compatibility.py`
- Modify: `backend/decisions/service.py`
- Modify: `backend/tests/test_decision_codes.py`
- Modify: `backend/tests/decisions/test_decision_service.py`
- Modify: `app-front-end/src/components/institutional/HumanRulingComposer.tsx`
- Create: `app-front-end/src/components/institutional/__tests__/HumanRulingComposer.test.tsx`

**Interfaces:**
- Consumes: canonical recommendation and human-ruling enums.
- Produces: one compatibility mapping owner plus correct override attribution and all four human ruling controls.

- [ ] **Step 1: Write failing backend semantics tests**

Add:

```python
def test_no_recommendation_cannot_be_overridden():
    assert classify_override(
        recommendation=None, ruling=HumanRulingDecision.INVEST, requested=None
    ) is None


def test_advance_to_invest_is_lifecycle_progression_not_override():
    assert classify_override(
        recommendation="advance", ruling=HumanRulingDecision.INVEST, requested=None
    ) is None


def test_advance_ruling_never_projects_to_legacy_yes():
    projection = legacy_ruling_from_institutional("advance")
    assert projection.value == "MAYBE"
    assert projection.compatibility_reason == "advance"
```

Add a source-level assertion that `evaluation_v2.compatibility.recommendation_to_legacy()` delegates to `legacy_partner_from_institutional_recommendation()` rather than owning another table.

- [ ] **Step 2: Write the failing frontend control test**

In the existing composer test, assert buttons `Advance`, `Monitor`, `Pass`, and `Invest` are present and that choosing Advance submits `decision: "advance"`. Assert a recommended ADVANCE preselects Advance instead of appearing as no recommendation.

- [ ] **Step 3: Run backend and frontend tests and verify RED**

```bash
cd backend && pytest -q tests/test_decision_codes.py tests/decisions/test_decision_service.py
cd app-front-end && npm test -- src/components/institutional/__tests__/HumanRulingComposer.test.tsx
```

- [ ] **Step 4: Implement one mapping owner and alignment helper**

Add to `backend/utils/partner_codes.py`:

```python
def ruling_aligns_with_recommendation(
    recommendation: Optional[str], ruling: str
) -> bool:
    if recommendation is None or not str(recommendation).strip():
        return True
    rec = RecommendationCode(_required_code(recommendation, label="recommendation"))
    human = HumanRulingCode(_required_code(ruling, label="human ruling"))
    if rec is RecommendationCode.ADVANCE:
        return human in {HumanRulingCode.ADVANCE, HumanRulingCode.INVEST}
    if rec is RecommendationCode.MONITOR:
        return human is HumanRulingCode.MONITOR
    if rec is RecommendationCode.PASS:
        return human is HumanRulingCode.PASS
    return False
```

Make `decisions.service.classify_override()` call this helper. Replace `evaluation_v2/compatibility.py` with a thin delegating wrapper that converts the returned `LegacyProjection` to the existing response shape and sets `human_review_required=True` only for insufficient evidence.

- [ ] **Step 5: Expose the full human-ruling vocabulary**

In `HumanRulingComposer.tsx`, remove `VisibleDecision = Exclude<HumanRulingDecision, 'advance'>`; use `HumanRulingDecision` directly. Define options in lifecycle order:

```typescript
const DECISION_OPTIONS = [
  { value: 'advance', label: 'Advance' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'pass', label: 'Pass' },
  { value: 'invest', label: 'Invest' },
] satisfies Array<{ value: HumanRulingDecision; label: string }>;
```

Compare `decision` directly to `recommendedDecision`; do not hide ADVANCE before override attribution.

- [ ] **Step 6: Run backend/frontend tests and verify GREEN**

Run the Step 3 commands. Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 6**

```bash
git add backend/utils/partner_codes.py backend/evaluation_v2/compatibility.py \
  backend/decisions/service.py backend/tests/test_decision_codes.py \
  backend/tests/decisions/test_decision_service.py \
  app-front-end/src/components/institutional/HumanRulingComposer.tsx \
  app-front-end/src/components/institutional/__tests__/HumanRulingComposer.test.tsx
git commit -m "fix: align recommendation and ruling semantics"
```

---

### Task 7: Centralize evaluation prerequisites and block thesis-blind lookup

**Files:**
- Create: `backend/evaluation_v2/prerequisites.py`
- Create: `backend/tests/evaluation_v2/test_evaluation_prerequisites.py`
- Modify: `backend/routers/evaluations.py`
- Modify: `backend/jobs/handlers.py`
- Modify: `backend/pipeline_runner.py`
- Modify: `backend/tests/evaluation_v2/test_evaluation_policy_gate.py`
- Modify: `backend/tests/jobs/test_job_handlers.py`
- Modify: `backend/tests/test_on_demand_lookup_independent.py`

**Interfaces:**
- Consumes: tenant ID, active thesis, governed or legacy published policy, versioned Partner rules.
- Produces: `EvaluationPrerequisites(thesis_version_id, policy)` or an attributed fail-closed error shared by API and job paths.

- [ ] **Step 1: Write failing prerequisite service tests**

Create tests for exact active thesis/policy resolution plus missing thesis, missing published policy, governed-policy hash mismatch, and transient thesis-store failure. Use dependency callables so the pure orchestration is testable without Supabase.

```python
@pytest.mark.asyncio
async def test_missing_thesis_has_operator_recovery():
    with pytest.raises(EvaluationPrerequisiteError) as exc:
        await load_evaluation_prerequisites(
            user_id="user-a",
            fund_intelligence_repository=None,
            load_thesis=lambda _: None,
            load_policy=lambda _: _compiled_policy(),
            load_partner_rules=lambda: _partner_rules(),
        )
    assert exc.value.code == "thesis_required"
    assert "Settings" in exc.value.recovery_action
```

Add handler tests asserting `run_on_demand_lookup` is never called when thesis or policy is missing and the job blocks after preserving identity admission.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend && pytest -q \
  tests/evaluation_v2/test_evaluation_prerequisites.py \
  tests/evaluation_v2/test_evaluation_policy_gate.py \
  tests/jobs/test_job_handlers.py \
  tests/test_on_demand_lookup_independent.py
```

- [ ] **Step 3: Implement the shared prerequisite loader**

Create `backend/evaluation_v2/prerequisites.py`:

```python
@dataclass(frozen=True)
class EvaluationPrerequisites:
    thesis_version_id: str
    policy: EvaluationPolicy


class EvaluationPrerequisiteError(RuntimeError):
    def __init__(self, *, code: str, detail: str, recovery_action: str):
        self.code = code
        self.detail = detail
        self.recovery_action = recovery_action
        super().__init__(f"{code}: {detail}")


async def load_evaluation_prerequisites(
    *,
    user_id: str,
    fund_intelligence_repository: Any | None,
    load_thesis: Callable[[str], Any] | None = None,
    load_policy: Callable[[str], Dict[str, Any]] | None = None,
    load_partner_rules: Callable[[], Dict[str, Any]] | None = None,
) -> EvaluationPrerequisites:
    uid = require_user_id(user_id, context="load_evaluation_prerequisites")

    async def resolve_thesis() -> Any:
        if load_thesis is not None:
            value = load_thesis(uid)
            return await value if inspect.isawaitable(value) else value
        return await asyncio.to_thread(
            get_active_thesis, get_service_client(), uid
        )

    async def resolve_policy() -> Dict[str, Any]:
        if load_policy is not None:
            value = load_policy(uid)
            return await value if inspect.isawaitable(value) else value
        return await asyncio.to_thread(load_published_policy, uid)

    async def resolve_rules() -> Dict[str, Any]:
        if load_partner_rules is not None:
            value = load_partner_rules()
            return await value if inspect.isawaitable(value) else value
        return await asyncio.to_thread(get_partner_rules)

    try:
        thesis = await resolve_thesis()
    except FundThesisIncompleteError as exc:
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="The active fund thesis is incomplete.",
            recovery_action="Complete and publish the fund thesis in Settings.",
        ) from exc
    except FundThesisError as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The active fund thesis could not be loaded.",
            recovery_action="Retry after the thesis store is available.",
        ) from exc
    except Exception as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The active fund thesis could not be loaded.",
            recovery_action="Retry after the thesis store is available.",
        ) from exc
    if thesis is None:
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active fund thesis is required before evaluation.",
            recovery_action="Create and publish the fund thesis in Settings.",
        )

    compiled: Dict[str, Any] | None = None
    if fund_intelligence_repository is not None:
        try:
            governed = await fund_intelligence_repository.get_active_published_policy(
                user_id=uid
            )
        except LookupError:
            governed = None
        except Exception as exc:
            raise EvaluationPrerequisiteError(
                code="prerequisite_unavailable",
                detail="The governed policy could not be loaded.",
                recovery_action="Retry after the policy store is available.",
            ) from exc
        if governed is not None:
            compiled = await asyncio.to_thread(
                compile_policy_from_fund_config,
                governed["policy_patch"],
                require_publish_ready=True,
            )
            if compiled["policy_hash"] != governed["policy_hash"]:
                raise EvaluationPrerequisiteError(
                    code="prerequisite_unavailable",
                    detail="The governed policy hash is inconsistent.",
                    recovery_action="Republish the governed policy before retrying.",
                )
            compiled["policy_version_id"] = governed[
                "governed_policy_version_id"
            ]
    if compiled is None:
        try:
            compiled = await resolve_policy()
        except PolicyNotPublishedError as exc:
            raise EvaluationPrerequisiteError(
                code="published_policy_required",
                detail="An active published scoring policy is required before evaluation.",
                recovery_action="Publish the fund scoring policy in Settings.",
            ) from exc
        except Exception as exc:
            raise EvaluationPrerequisiteError(
                code="prerequisite_unavailable",
                detail="The published policy could not be loaded.",
                recovery_action="Retry after the policy store is available.",
            ) from exc

    try:
        rules = await resolve_rules()
        policy = evaluation_policy_from_compiled(compiled, partner_rules=rules)
    except EvaluationPrerequisiteError:
        raise
    except Exception as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The versioned evaluation policy could not be compiled.",
            recovery_action="Republish the scoring policy before retrying.",
        ) from exc
    return EvaluationPrerequisites(
        thesis_version_id=str(thesis.version_id), policy=policy
    )
```

Production defaults use `asyncio.to_thread()` for blocking thesis/policy/rules calls. If a governed policy exists, compile and hash-check its exact patch; otherwise call `load_published_policy()`. Missing thesis maps to `thesis_required`; `PolicyNotPublishedError` maps to `published_policy_required`; transient storage errors remain `prerequisite_unavailable` and are not mislabeled as missing.

- [ ] **Step 4: Replace duplicate route logic and gate durable lookup**

Make `routers/evaluations.evaluate_opportunity()` call the shared loader and translate missing requirements to HTTP 409 and transient prerequisite errors to HTTP 503.

In `company_lookup_handler`, call the loader immediately after resolved identity and before `run_on_demand_lookup()`. Apply the same gate in `pipeline_cycle_handler` before the legacy Reviewer/Partner cycle. Translate any `EvaluationPrerequisiteError` to:

```python
raise JobExecutionBlocked(
    code=exc.code,
    detail=exc.detail,
    recovery_action=exc.recovery_action,
)
```

Pass the returned `EvaluationPrerequisites` into `run_on_demand_lookup()` and include its policy/thesis IDs in `institutional_context` so the next vertical-slice plan can consume them. Add this optional keyword to the legacy helper:

```python
evaluation_prerequisites: EvaluationPrerequisites | None = None
```

When direct callers omit it, `run_on_demand_lookup()` must call the shared loader before constructing Scout/Reviewer/Partner engines. Delete the thesis-blind branch; missing prerequisites return/raise the typed prerequisite error rather than continuing. The durable handler passes its already-loaded instance so the production path does not load twice.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run the Step 2 command. Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 7**

```bash
git add backend/evaluation_v2/prerequisites.py \
  backend/tests/evaluation_v2/test_evaluation_prerequisites.py \
  backend/routers/evaluations.py backend/jobs/handlers.py backend/pipeline_runner.py \
  backend/tests/evaluation_v2/test_evaluation_policy_gate.py \
  backend/tests/jobs/test_job_handlers.py \
  backend/tests/test_on_demand_lookup_independent.py
git commit -m "feat: fail closed on evaluation prerequisites"
```

---

### Task 8: Add the executable decision-safety certification gate

**Files:**
- Create: `backend/tests/evaluation_v2/test_decision_safety_certification.py`
- Modify: `docs/institutional-foundation/phase-3-8-readiness.md`

**Interfaces:**
- Consumes: the exact evaluator and prerequisite contracts delivered by Tasks 1–7.
- Produces: an executable, non-snapshot certification suite for promotion into the authority-control slice.

- [ ] **Step 1: Create eight exact executable cases**

Define a frozen case model and the exact case names/outcomes in the test file:

```python
@dataclass(frozen=True)
class SafetyCase:
    name: str
    kind: Literal["evaluation", "override", "projection"]
    expected_state: str | None = None
    expected_override: str | None = None
    expected_projection: dict[str, str | None] | None = None


CASES = [
    SafetyCase("ungrounded_high_score", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("model_inferred_high_score", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("required_dimension_missing", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("grounded_critical_risk_with_high_scores", "evaluation", expected_state="pass"),
    SafetyCase("grounded_hard_exclusion_with_high_scores", "evaluation", expected_state="pass"),
    SafetyCase("grounded_complete_high_scores", "evaluation", expected_state="advance"),
    SafetyCase("advance_then_invest", "override", expected_override=None),
    SafetyCase(
        "advance_ruling_projection",
        "projection",
        expected_projection={"value": "MAYBE", "compatibility_reason": "advance"},
    ),
]
```

Use these local builders so the certification test does not import another test module:

```python
def _support(evidence_id: str) -> dict[str, object]:
    return {
        "evidence_item_id": evidence_id,
        "relationship": "supports",
        "support_strength": 0.9,
        "verification_state": "verified",
        "source_quality": 0.9,
        "trust_class": "independent",
        "untrusted_input": True,
        "prompt_injection_detected": False,
    }


def _claim(
    claim_id: str,
    claim_type: str,
    *,
    score: float | None = None,
    assertion_class: str = "externally_verified",
    grounded: bool = True,
    value: bool | None = None,
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    if score is not None:
        normalized["criterion_score"] = score
    if value is not None:
        normalized["value"] = value
    relationships = [_support(f"evidence-{claim_id}")] if grounded else []
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "normalized_value": normalized,
        "unit": None,
        "period": None,
        "display_text": claim_type.replace("_", " "),
        "status_at_snapshot": "current",
        "assertion_class_at_snapshot": assertion_class,
        "operator_attribution_at_snapshot": None,
        "confidence_at_snapshot": 0.9,
        "supporting_evidence_ids": [
            link["evidence_item_id"] for link in relationships
        ],
        "contradicting_evidence_ids": [],
        "evidence_relationships": relationships,
    }


def _snapshot_for(name: str) -> list[dict[str, object]]:
    market = _claim("market", "market", score=9)
    execution = _claim("execution", "execution", score=9)
    if name == "ungrounded_high_score":
        return [_claim("market", "market", score=9, grounded=False),
                _claim("execution", "execution", score=9, grounded=False)]
    if name == "model_inferred_high_score":
        return [_claim("market", "market", score=9, assertion_class="model_inferred"),
                _claim("execution", "execution", score=9, assertion_class="model_inferred")]
    if name == "required_dimension_missing":
        return [market]
    if name == "grounded_critical_risk_with_high_scores":
        return [market, execution,
                _claim("risk", "critical_risk", value=True)]
    if name == "grounded_hard_exclusion_with_high_scores":
        return [market, execution,
                _claim("exclusion", "mandate_exclusion", value=True)]
    if name == "grounded_complete_high_scores":
        return [market, execution]
    raise AssertionError(f"No evaluation snapshot for {name}")


def _safety_policy() -> EvaluationPolicy:
    eligibility = EvidenceEligibilityPolicy(
        allowed_assertion_classes=["externally_verified", "operator_asserted"],
        allowed_relationships=["supports", "partially_establishes"],
        require_verified_evidence=True,
        min_support_strength=0.5,
        min_source_quality=0.4,
        blocked_trust_classes=["model", "unknown"],
    )
    safety = DecisionSafetyPolicy(
        evidence_eligibility=eligibility,
        critical_risk_claim_types=["critical_risk"],
        hard_exclusion_claim_types=["mandate_exclusion"],
    )
    return EvaluationPolicy(
        policy_version_id="policy-safety-v1",
        policy_hash="policy-safety-hash",
        rubric_version="rubric-safety-v1",
        partner_rules_version="2.0",
        partner_rules_hash="partner-rules-v2-hash",
        criteria=[
            CriterionRule(criterion="market", claim_types=["market"], weight=0.6),
            CriterionRule(criterion="execution", claim_types=["execution"], weight=0.4),
        ],
        advance_threshold=7.5,
        pass_threshold=4.0,
        minimum_scored_weight=0.5,
        hard_exclusion_claim_types=["mandate_exclusion"],
        decision_safety=safety,
    )
```

Each evaluator case includes complete immutable claim and relationship metadata; do not reuse the legacy startup golden-set format.

- [ ] **Step 2: Write the parameterized certification test**

```python
@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_decision_safety_case(case):
    if case.kind == "evaluation":
        result = evaluate_snapshot(_snapshot_for(case.name), _safety_policy())
        assert result.recommendation.state.value == case.expected_state
    elif case.kind == "override":
        assert classify_override(
            recommendation="advance",
            ruling=HumanRulingDecision.INVEST,
            requested=None,
        ) == case.expected_override
    else:
        projection = legacy_ruling_from_institutional("advance")
        assert projection.model_dump() == case.expected_projection
```

- [ ] **Step 3: Run the complete focused backend gate**

```bash
cd backend && pytest -q \
  tests/evidence \
  tests/evaluation_v2 \
  tests/decisions \
  tests/jobs/test_job_handlers.py \
  tests/jobs/test_job_worker.py \
  tests/test_decision_codes.py \
  tests/test_partner_decision_fallback.py \
  tests/test_partner_mandate_gate.py \
  tests/test_policy_compiler.py \
  tests/test_policy_store.py \
  tests/test_reviewer_structured_signals_clamp.py \
  tests/test_scoring_thin_evidence_characterization.py \
  tests/test_structured_scoring_engine.py \
  tests/test_on_demand_lookup_independent.py
```

Expected: zero failures. Skips must be inspected and must not include the new decision-safety certification file.

- [ ] **Step 4: Run frontend verification**

```bash
cd app-front-end && npm test -- \
  src/components/institutional/__tests__/HumanRulingComposer.test.tsx
cd app-front-end && npm run lint
cd app-front-end && npm run build
```

Expected: all selected tests pass; lint and build exit 0.

- [ ] **Step 5: Update readiness evidence and commit**

Document the exact commands and observed counts in `docs/institutional-foundation/phase-3-8-readiness.md`. Do not claim target-PostgreSQL certification because this slice has no schema change and does not yet prove the authority-control migration.

```bash
git add backend/tests/evaluation_v2/test_decision_safety_certification.py \
  docs/institutional-foundation/phase-3-8-readiness.md
git commit -m "test: certify decision safety prerequisites"
```

## Plan completion evidence

This plan is complete only when:

1. The focused backend gate and frontend test/lint/build commands above pass from a clean working tree.
2. The high-score regulatory-ban reproduction returns PASS with human review.
3. An unsupported or model-inferred high score cannot ADVANCE.
4. Missing required criteria produce `INSUFFICIENT_EVIDENCE` with null criterion scores.
5. Durable lookup blocks before legacy Scout/Reviewer/Partner work when thesis or published policy is unavailable.
6. Recommendation/ruling compatibility has one mapping owner and ADVANCE is available as a human ruling without projecting to legacy YES.
7. The executable decision-safety fixture suite passes without skips.
8. The next authority-control plan can depend on these contracts without reintroducing a parallel safety path.
