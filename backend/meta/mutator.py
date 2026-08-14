"""
PromptMutator — decides which prompts to mutate and rewrites them via LLM.
Backed by provider-neutral meta_prompt_library and meta_mutation_log.
"""
import json
import logging
import os
import fcntl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils.timeutil import utcnow
from uuid import uuid4

from utils.prompt_version import hash_prompt
from batch1.store import doc_get, doc_set, list_get_all, list_append_only
from meta.prompt_gating import PROMPT_LIBRARY_DATA_KEY
from meta.schema import (
    PromptMutationBatchResult,
    PromptMutationTargetOutcome,
    PromptMutationTargetState,
)

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROMPT_LIBRARY_PATH = _BACKEND_DIR / "data" / "meta" / "prompt_library.json"
_MUTATION_LOG_PATH = _BACKEND_DIR / "data" / "meta" / "mutation_log.json"
_PROMPT_LIBRARY_TABLE = "meta_prompt_library"
_MUTATION_LOG_TABLE = "meta_mutation_log"
_META_REPORTS_TABLE = "meta_reports"

MUTATOR_SYSTEM_PROMPT = """You are a meta-optimisation agent for an autonomous VC investment pipeline. Your job is to rewrite agent system prompts to improve performance based on observed signal. You must preserve the agent's core cognitive identity and lens. You must not make the agent generic. Mutations should be surgical — one or two targeted adjustments, not a full rewrite.

Return ONLY a JSON object with two fields:
{
  "new_prompt": "the full rewritten system prompt",
  "reasoning": "one paragraph explaining exactly what changed and why"
}"""


class PromptMutationTargetError(RuntimeError):
    """One mutation target failed before a durable proposal was produced."""

    def __init__(self, *, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class PromptMutationRejected(RuntimeError):
    """A generated mutation was safely rejected by prompt validation."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _prompt_validation_limits() -> Dict[str, Any]:
    def _i(name: str, default: str) -> int:
        try:
            return int(os.getenv(name, default))
        except ValueError:
            return int(default)

    def _f(name: str, default: str) -> float:
        try:
            return float(os.getenv(name, default))
        except ValueError:
            return float(default)

    return {
        "max_chars": _i("META_AGENT_PROMPT_MAX_CHARS", "32000"),
        "max_lines": _i("META_AGENT_PROMPT_MAX_LINES", "500"),
        "min_ratio": _f("META_AGENT_PROMPT_MIN_LENGTH_RATIO", "0.85"),
        "max_growth": _f("META_AGENT_PROMPT_MAX_GROWTH_RATIO", "2.5"),
    }


def validate_mutated_prompt(
    new_prompt: str,
    current_prompt: str,
    *,
    max_chars: int,
    max_lines: int,
    min_ratio: float,
    max_growth: float,
) -> Optional[str]:
    """
    Return an error reason string if invalid, else None.
    """
    if not new_prompt or not str(new_prompt).strip():
        return "empty_prompt"
    text = str(new_prompt)
    if len(text) > max_chars:
        return f"exceeds_max_chars:{len(text)}>{max_chars}"
    lines = text.count("\n") + (1 if text else 0)
    if lines > max_lines:
        return f"exceeds_max_lines:{lines}>{max_lines}"
    cur = (current_prompt or "").strip()
    if cur:
        if len(text) < len(cur) * min_ratio:
            return f"shorter_than_min_ratio:{len(text)/len(cur):.2f}<{min_ratio}"
        if len(text) > len(cur) * max_growth:
            return f"longer_than_max_growth:{len(text)/len(cur):.2f}>{max_growth}"
    return None


def _read_json_list(path: Path, user_id: str) -> list:
    if path and "meta_reports" in str(path):
        return list_get_all(_META_REPORTS_TABLE, user_id=user_id)
    if path and "mutation_log" in str(path):
        return list_get_all(_MUTATION_LOG_TABLE, user_id=user_id)
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _read_json_dict(path: Path, user_id: str) -> dict:
    if path and "prompt_library" in str(path):
        data = doc_get(_PROMPT_LIBRARY_TABLE, PROMPT_LIBRARY_DATA_KEY, user_id=user_id)
        return data if isinstance(data, dict) else {}
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError):
        return {}


def _atomic_write(path: Path, data: Any, user_id: str) -> None:
    if path and "prompt_library" in str(path):
        doc_set(_PROMPT_LIBRARY_TABLE, data, PROMPT_LIBRARY_DATA_KEY, user_id=user_id)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with open(temp, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def _append_to_json_list(path: Path, entry: dict, user_id: str) -> None:
    if path and "mutation_log" in str(path):
        list_append_only(_MUTATION_LOG_TABLE, entry, user_id=user_id)
        return
    if path and "meta_reports" in str(path):
        list_append_only(_META_REPORTS_TABLE, entry, user_id=user_id)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _read_json_list(path, user_id)
    entries.append(entry)
    _atomic_write(path, entries, user_id)


class PromptMutator:
    """Decides which prompts to mutate and rewrites them via OpenAI."""

    def __init__(self, signal_summary: Dict[str, Any], cycle_number: int, user_id: str):
        self.signal = signal_summary
        self.cycle_number = cycle_number
        self.user_id = user_id
        self.logger = logging.getLogger("meta.mutator")
        self.model = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _get_client(self):
        if self._client is None and self.api_key:
            from utils.openai_client import build_openai_client
            self._client = build_openai_client(self.api_key)
        return self._client

    def close(self) -> None:
        """Release the OpenAI client and worker threads; rebuilt every meta cycle."""
        from utils.resource_cleanup import close_openai_client, shutdown_executor

        shutdown_executor(getattr(self, "_executor", None))
        close_openai_client(getattr(self, "_client", None))
        self._client = None

    def decide(self) -> List[Dict[str, Any]]:
        """Determine which prompts need mutation. Returns list of mutation targets."""
        targets = []
        cooldowns = self.signal.get("mutation_cooldowns", {})
        scout_perf = self.signal.get("scout_performance", {})

        # Scout prompt mutations
        for agent_name, perf in scout_perf.items():
            if cooldowns.get(agent_name, False):
                self.logger.info(f"[Mutator] {agent_name} in cooldown, skipping")
                continue
            if perf.get("current_weight", 0.25) < 0.10:
                self.logger.info(
                    f"[Mutator] {agent_name} weight < 0.10, suppression handling this"
                )
                continue
            if perf.get("acceptance_rate", 1.0) < 0.15:
                targets.append({
                    "agent_target": agent_name,
                    "mutation_type": "scout_prompt",
                    "trigger": f"Low acceptance rate: {perf['acceptance_rate']:.2f}",
                    "signal": perf,
                })
            elif len(perf.get("blind_spots", [])) >= 2:
                targets.append({
                    "agent_target": agent_name,
                    "mutation_type": "scout_prompt",
                    "trigger": f"Blind spots: {perf['blind_spots'][:3]}",
                    "signal": perf,
                })

        # Reviewer prompt mutations
        reviewer_health = self.signal.get("reviewer_health", {})
        vd = reviewer_health.get("verdict_distribution", {})
        total_verdicts = sum(vd.values())
        calibration_warning = reviewer_health.get("calibration_warning")

        if total_verdicts > 0:
            weak_pct = vd.get("WEAK", 0) / total_verdicts
            strong_pct = vd.get("STRONG", 0) / total_verdicts

            if calibration_warning and weak_pct > 0.70:
                if not cooldowns.get("SkepticalReviewer", False):
                    targets.append({
                        "agent_target": "SkepticalReviewer",
                        "mutation_type": "reviewer_prompt",
                        "trigger": f"Calibration warning + {weak_pct:.0%} WEAK verdicts",
                        "signal": reviewer_health,
                    })

            if strong_pct > 0.60:
                if not cooldowns.get("OpportunistReviewer", False):
                    targets.append({
                        "agent_target": "OpportunistReviewer",
                        "mutation_type": "reviewer_prompt",
                        "trigger": f"{strong_pct:.0%} STRONG verdicts — tighten optimism",
                        "signal": reviewer_health,
                    })

        return targets

    def apply(
        self,
        targets: List[Dict],
        scout_engine,
        reviewer_engine,
    ) -> PromptMutationBatchResult:
        """Rewrite targets and return lossless typed terminal accounting."""
        outcomes: List[PromptMutationTargetOutcome] = []
        for target in targets:
            agent_target = str(target.get("agent_target") or "unknown_target")
            try:
                mutation = self._apply_one(target, scout_engine, reviewer_engine)
                if not isinstance(mutation, dict):
                    raise PromptMutationTargetError(
                        code="prompt_proposal_missing",
                        detail="Prompt mutation produced no proposal.",
                    )
                outcomes.append(
                    PromptMutationTargetOutcome(
                        agent_target=agent_target,
                        state=PromptMutationTargetState.PROPOSED,
                        code="prompt_proposal_persisted",
                        detail="Prompt proposal persisted pending operator promotion.",
                        proposal=mutation,
                    )
                )
            except PromptMutationRejected as exc:
                outcomes.append(
                    PromptMutationTargetOutcome(
                        agent_target=agent_target,
                        state=PromptMutationTargetState.REJECTED,
                        code="prompt_proposal_rejected",
                        detail=f"Prompt proposal rejected by validation: {exc.reason}",
                    )
                )
            except PromptMutationTargetError as exc:
                self.logger.error(
                    "[Mutator] Failed to apply %s: %s", agent_target, exc.detail
                )
                outcomes.append(
                    PromptMutationTargetOutcome(
                        agent_target=agent_target,
                        state=PromptMutationTargetState.FAILED,
                        code=exc.code,
                        detail=exc.detail,
                    )
                )
            except Exception as e:
                self.logger.error(
                    "[Mutator] Failed to apply %s: %s", agent_target, e
                )
                outcomes.append(
                    PromptMutationTargetOutcome(
                        agent_target=agent_target,
                        state=PromptMutationTargetState.FAILED,
                        code="prompt_target_failed",
                        detail=f"Prompt mutation target failed: {e}",
                    )
                )
        return PromptMutationBatchResult(outcomes=outcomes)

    def _apply_one(
        self,
        target: Dict,
        scout_engine,
        reviewer_engine,
    ) -> Optional[Dict]:
        agent_name = target["agent_target"]
        current_prompt = self._get_current_prompt(agent_name, scout_engine, reviewer_engine)
        if not current_prompt:
            self.logger.warning(f"[Mutator] Could not get prompt for {agent_name}")
            raise PromptMutationTargetError(
                code="prompt_source_unavailable",
                detail=f"Current prompt is unavailable for {agent_name}.",
            )

        prev_hash = hash_prompt(current_prompt)

        # Build user prompt
        pipeline = self.signal.get("pipeline_health", {})
        rejection_keywords = pipeline.get("top_rejection_keywords", [])
        rejected_sectors = pipeline.get("most_rejected_sectors", [])
        rejection_avoid_block = ""
        if rejection_keywords and target.get("mutation_type") == "scout_prompt":
            rejection_avoid_block = (
                f"- PARTNER REJECT keywords to avoid in future scout prompts: {rejection_keywords[:6]}\n"
                f"- Most rejected sectors (reduce discovery unless contrarian thesis): {rejected_sectors[:3]}\n"
                "When mutating: add one targeted 'AVOID:' bullet per top rejection keyword to the prompt's "
                "negative constraints section. Do not add more than 3 new Avoid bullets per mutation.\n"
            )
        hf = self.signal.get("human_feedback") or {}
        human_block = ""
        if hf.get("recent_count"):
            bo = hf.get("by_outcome") or {}
            human_block = (
                f"- Analyst decisions (Invest/Pass/Monitor) — {hf['recent_count']} recent: "
                f"YES={bo.get('YES', 0)}, NO={bo.get('NO', 0)}, MAYBE={bo.get('MAYBE', 0)}; "
                f"logged disagreements vs AI at resolve time: {hf.get('disagreed_with_ai_count', 0)}.\n"
            )
            samples = hf.get("sample_notes") or []
            if samples:
                snippets = " | ".join(
                    str(s).replace("\n", " ")[:160] for s in samples[:3]
                )
                human_block += (
                    f"- Analyst rationale snippets (mandate alignment, not verbatim copy): {snippets}\n"
                )
            human_block += (
                "- Bias prompt changes toward what analysts actually approve and away from "
                "recurring pass themes implied above.\n"
            )
        user_prompt = (
            f"Agent: {agent_name}\n"
            f"Current prompt:\n{current_prompt}\n\n"
            f"Performance signal:\n"
            f"- Trigger: {target.get('trigger', '')}\n"
            f"- Acceptance rate: {target.get('signal', {}).get('acceptance_rate', 'N/A')}\n"
            f"- Blind spots: {target.get('signal', {}).get('blind_spots', [])}\n"
            f"- Top failed assumptions: {pipeline.get('top_failed_assumptions', [])[:5]}\n"
            f"- Top successful thesis patterns: {pipeline.get('top_successful_thesis_patterns', [])[:5]}\n"
            f"- Oversaturated sectors to avoid: {pipeline.get('most_oversaturated_sector', 'none')}\n"
            f"{human_block}"
            f"{rejection_avoid_block}\n"
            f"Mutate the prompt to address these failure patterns while "
            f"preserving this agent's core cognitive identity."
        )

        try:
            new_prompt, reasoning = self._call_llm(user_prompt)
        except Exception as exc:
            raise PromptMutationTargetError(
                code="prompt_llm_failed",
                detail=f"Prompt mutation LLM failed for {agent_name}.",
            ) from exc
        if not new_prompt:
            self.logger.warning(f"[Mutator] LLM returned no prompt for {agent_name}")
            raise PromptMutationTargetError(
                code="prompt_llm_empty_response",
                detail=f"Prompt mutation LLM returned no prompt for {agent_name}.",
            )

        lim = _prompt_validation_limits()
        reject = validate_mutated_prompt(
            new_prompt,
            current_prompt,
            max_chars=int(lim["max_chars"]),
            max_lines=int(lim["max_lines"]),
            min_ratio=float(lim["min_ratio"]),
            max_growth=float(lim["max_growth"]),
        )
        now = utcnow().isoformat()
        if reject:
            self.logger.warning(
                "[Mutator] Rejected prompt for %s: %s", agent_name, reject
            )
            try:
                _append_to_json_list(
                    _MUTATION_LOG_PATH,
                    {
                        "type": "prompt_proposal_rejected",
                        "agent_target": agent_name,
                        "mutation_type": target["mutation_type"],
                        "reason": reject,
                        "cycle_number": self.cycle_number,
                        "applied_at": now,
                    },
                    self.user_id,
                )
            except Exception as exc:
                raise PromptMutationTargetError(
                    code="prompt_proposal_persistence_failed",
                    detail=f"Prompt rejection audit persistence failed for {agent_name}.",
                ) from exc
            raise PromptMutationRejected(reject)

        new_hash = hash_prompt(new_prompt)
        library_key = f"{agent_name}:{new_hash}"

        mutation = {
            "type": "prompt_proposal",
            "mutation_id": str(uuid4()),
            "mutation_type": target["mutation_type"],
            "agent_target": agent_name,
            "library_key": library_key,
            "previous_prompt_hash": prev_hash,
            "new_prompt_hash": new_hash,
            "reasoning": reasoning,
            "signal_inputs": target.get("signal", {}),
            "applied_at": now,
            "cycle_number": self.cycle_number,
            "promoted": False,
            "activation_status": "pending_operator_promotion",
        }
        try:
            _append_to_json_list(_MUTATION_LOG_PATH, mutation, self.user_id)

            library = _read_json_dict(_PROMPT_LIBRARY_PATH, self.user_id)
            library[library_key] = {
                "prompt": new_prompt,
                "created_at": now,
                "reasoning": reasoning,
                "cycle_number": self.cycle_number,
                "previous_hash": prev_hash,
                "promotion_status": "pending",
            }
            _atomic_write(_PROMPT_LIBRARY_PATH, library, self.user_id)
        except Exception as exc:
            raise PromptMutationTargetError(
                code="prompt_proposal_persistence_failed",
                detail=f"Prompt proposal persistence failed for {agent_name}.",
            ) from exc

        self.logger.info(
            "[Mutator] Saved pending proposal for %s (%s); promote via API to use",
            agent_name,
            library_key,
        )

        return mutation

    def _get_current_prompt(self, agent_name: str, scout_engine, reviewer_engine) -> Optional[str]:
        from meta.analyser import SCOUT_AGENT_NAMES
        # Scout agents
        if agent_name in SCOUT_AGENT_NAMES and scout_engine:
            scout_type = SCOUT_AGENT_NAMES[agent_name]
            for scout in scout_engine.scouts:
                if scout.scout_type == scout_type:
                    return scout.system_prompt
        # Reviewer agents
        if reviewer_engine:
            if agent_name == "DefaultReviewer":
                return reviewer_engine.reviewer.SYSTEM_PROMPT
            elif agent_name == "SkepticalReviewer":
                return reviewer_engine.skeptical_reviewer.SYSTEM_PROMPT
            elif agent_name == "OpportunistReviewer":
                return reviewer_engine.opportunist_reviewer.SYSTEM_PROMPT
        return None

    def _set_agent_prompt(self, agent_name: str, new_prompt: str, scout_engine, reviewer_engine):
        from meta.analyser import SCOUT_AGENT_NAMES
        if agent_name in SCOUT_AGENT_NAMES and scout_engine:
            scout_type = SCOUT_AGENT_NAMES[agent_name]
            for scout in scout_engine.scouts:
                if scout.scout_type == scout_type:
                    scout.set_prompt(new_prompt)
                    return
        if reviewer_engine:
            if agent_name == "DefaultReviewer":
                reviewer_engine.reviewer.set_prompt(new_prompt)
            elif agent_name == "SkepticalReviewer":
                reviewer_engine.skeptical_reviewer.set_prompt(new_prompt)
            elif agent_name == "OpportunistReviewer":
                reviewer_engine.opportunist_reviewer.set_prompt(new_prompt)

    def _call_llm(self, user_prompt: str) -> tuple:
        """Call OpenAI to rewrite a prompt. Dependency errors propagate to the target."""
        client = self._get_client()
        if not client:
            self.logger.warning("[Mutator] No OpenAI client, skipping LLM call")
            return None, None
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": MUTATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=8192,
        )
        content = response.choices[0].message.content
        if not content:
            return None, None
        data = json.loads(content)
        return data.get("new_prompt"), data.get("reasoning", "")
