"""Governed two-call model boundary with explicit tenant and budget ownership."""
import asyncio
import json
from openai import LengthFinishReasonError
from pydantic import BaseModel, TypeAdapter
from typing import Any

from security.prompt_safety import isolate_untrusted_text, prompt_safety_instruction
from tenant_context import require_user_id
from utils.openai_client import build_openai_client


class AnalysisBlocked(RuntimeError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(detail)


class ModelGateway:
    def __init__(self, *, user_id: str, api_key: str, reviewer_model: str,
                 partner_model: str, cost_controller, max_completion_tokens: int):
        self.user_id = require_user_id(user_id, context="investment_model_gateway")
        if cost_controller.user_id != self.user_id:
            raise ValueError("model budget tenant mismatch")
        if not api_key:
            raise AnalysisBlocked("analysis_model_unconfigured", "Investment analysis requires a configured model provider.")
        self.models = {"reviewer": reviewer_model, "partner": partner_model}
        self.cost_controller = cost_controller
        self.max_completion_tokens = max_completion_tokens
        self.client = build_openai_client(api_key)

    async def __call__(self, stage: str, prompt: str, payload: dict, schema: type[BaseModel]):
        model = self.models[stage]
        serialized = TypeAdapter(dict[str, Any]).dump_json(payload).decode("utf-8")
        contract = json.dumps(schema.model_json_schema())
        # Includes output allowance; missing/budget-limited models must never
        # silently fall back to an old scoring or decision engine.
        estimated = (len(serialized) + len(prompt) + len(contract)) // 4 + self.max_completion_tokens
        allowed, reason = self.cost_controller.can_make_call(stage, f"investment-{stage}", estimated_tokens=estimated)
        if not allowed:
            raise AnalysisBlocked("analysis_budget_blocked", reason or "Investment analysis budget unavailable.")
        response = None
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.parse,
                model=model, max_completion_tokens=self.max_completion_tokens,
                response_format=schema,
                messages=[
                    {"role": "system", "content": prompt + "\n" + prompt_safety_instruction() + "\nJSON Schema:\n" + contract},
                    {"role": "user", "content": isolate_untrusted_text(serialized, label="investment evidence and fund context")},
                ],
            )
            message = response.choices[0].message
            if message.refusal:
                raise AnalysisBlocked("analysis_model_refused", f"{stage} could not produce the requested structured analysis.")
            if message.parsed is None:
                raise AnalysisBlocked("analysis_model_empty", f"{stage} returned no structured analysis.")
            return schema.model_validate(message.parsed)
        except LengthFinishReasonError as exc:
            response = exc.completion
            raise AnalysisBlocked("analysis_model_truncated", f"{stage} exhausted its output allowance before completing the analysis.") from exc
        finally:
            usage = getattr(response, "usage", None)
            self.cost_controller.record_call(stage, f"investment-{stage}", tokens_used=int(getattr(usage, "total_tokens", 0) or 0))

    def close(self):
        self.client.close()
