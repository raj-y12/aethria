"""
PromptMutator — decides which prompts to mutate and rewrites them via LLM.
Decision logic is deterministic. Only the rewriting uses LLM.
"""
import json
import logging
import os
import fcntl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from utils.prompt_version import hash_prompt

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROMPT_LIBRARY_PATH = _BACKEND_DIR / "data" / "meta" / "prompt_library.json"
_MUTATION_LOG_PATH = _BACKEND_DIR / "data" / "meta" / "mutation_log.json"

MUTATOR_SYSTEM_PROMPT = """You are a meta-optimisation agent for an autonomous VC investment pipeline. Your job is to rewrite agent system prompts to improve performance based on observed signal. You must preserve the agent's core cognitive identity and lens. You must not make the agent generic. Mutations should be surgical — one or two targeted adjustments, not a full rewrite.

Return ONLY a JSON object with two fields:
{
  "new_prompt": "the full rewritten system prompt",
  "reasoning": "one paragraph explaining exactly what changed and why"
}"""


def _read_json_list(path: Path) -> list:
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


def _read_json_dict(path: Path) -> dict:
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


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with open(temp, "w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def _append_to_json_list(path: Path, entry: dict) -> None:
    """Append to a JSON list file (append-only pattern)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _read_json_list(path)
    entries.append(entry)
    _atomic_write(path, entries)


class PromptMutator:
    """Decides which prompts to mutate and rewrites them via OpenAI."""

    def __init__(self, signal_summary: Dict[str, Any], cycle_number: int):
        self.signal = signal_summary
        self.cycle_number = cycle_number
        self.logger = logging.getLogger("meta.mutator")
        self.model = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=2)

    def _get_client(self):
        if self._client is None and self.api_key:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

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
    ) -> List[Dict]:
        """Rewrite prompts via LLM and apply to live agents. Returns PromptMutation records."""
        mutations = []
        for target in targets:
            try:
                mutation = self._apply_one(target, scout_engine, reviewer_engine)
                if mutation:
                    mutations.append(mutation)
            except Exception as e:
                self.logger.error(f"[Mutator] Failed to apply {target['agent_target']}: {e}")
        return mutations

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
            return None

        prev_hash = hash_prompt(current_prompt)

        # Build user prompt
        pipeline = self.signal.get("pipeline_health", {})
        user_prompt = (
            f"Agent: {agent_name}\n"
            f"Current prompt:\n{current_prompt}\n\n"
            f"Performance signal:\n"
            f"- Trigger: {target.get('trigger', '')}\n"
            f"- Acceptance rate: {target.get('signal', {}).get('acceptance_rate', 'N/A')}\n"
            f"- Blind spots: {target.get('signal', {}).get('blind_spots', [])}\n"
            f"- Top failed assumptions: {pipeline.get('top_failed_assumptions', [])[:5]}\n"
            f"- Top successful thesis patterns: {pipeline.get('top_successful_thesis_patterns', [])[:5]}\n"
            f"- Oversaturated sectors to avoid: {pipeline.get('most_oversaturated_sector', 'none')}\n\n"
            f"Mutate the prompt to address these failure patterns while "
            f"preserving this agent's core cognitive identity."
        )

        new_prompt, reasoning = self._call_llm(user_prompt)
        if not new_prompt:
            self.logger.warning(f"[Mutator] LLM returned no prompt for {agent_name}")
            return None

        new_hash = hash_prompt(new_prompt)
        now = datetime.now().isoformat()

        # Log mutation BEFORE applying (safety constraint)
        mutation = {
            "mutation_id": str(uuid4()),
            "mutation_type": target["mutation_type"],
            "agent_target": agent_name,
            "previous_prompt_hash": prev_hash,
            "new_prompt_hash": new_hash,
            "reasoning": reasoning,
            "signal_inputs": target.get("signal", {}),
            "applied_at": now,
            "cycle_number": self.cycle_number,
        }
        _append_to_json_list(_MUTATION_LOG_PATH, mutation)

        # Write to prompt library
        library = _read_json_dict(_PROMPT_LIBRARY_PATH)
        library[f"{agent_name}:{new_hash}"] = {
            "prompt": new_prompt,
            "created_at": now,
            "reasoning": reasoning,
            "cycle_number": self.cycle_number,
            "previous_hash": prev_hash,
        }
        _atomic_write(_PROMPT_LIBRARY_PATH, library)

        # Apply to live agent
        self._set_agent_prompt(agent_name, new_prompt, scout_engine, reviewer_engine)
        self.logger.info(f"[Mutator] Applied mutation to {agent_name}: {prev_hash} -> {new_hash}")

        return mutation

    def _get_current_prompt(self, agent_name: str, scout_engine, reviewer_engine) -> Optional[str]:
        from meta_agent.analyser import SCOUT_AGENT_NAMES
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
        from meta_agent.analyser import SCOUT_AGENT_NAMES
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
        """Call OpenAI to rewrite a prompt. Returns (new_prompt, reasoning) or (None, None)."""
        client = self._get_client()
        if not client:
            self.logger.warning("[Mutator] No OpenAI client, skipping LLM call")
            return None, None
        try:
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
        except Exception as e:
            self.logger.error(f"[Mutator] LLM call failed: {e}")
            return None, None
