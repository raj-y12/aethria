"""
Base Scout abstraction.
All Scouts inherit from this class and implement the discover() method.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openai import OpenAI

from scout.schema import ScoutOutput, validate_scout_output, generate_id
from tenant_context import require_user_id
from utils.reference_verify import finalize_scout_references, hostname_from_user_hint
from utils.settings_loader import get_canonical_website_hostname
from utils.serp_client import maybe_enrich_references


logger = logging.getLogger(__name__)


class Scout(ABC):
    """
    Base class for all Scout agents.
    
    Each Scout:
    - Has a unique type identifier
    - Uses a system prompt to guide discovery
    - Makes one LLM call per discovery cycle
    - Emits validated JSON output
    """
    
    def __init__(
        self,
        scout_type: str,
        system_prompt: str,
        api_key: str,
        model: str = "gpt-5-nano",
        tenant_user_id: str = "",
    ):
        """
        Initialize a Scout.

        Args:
            tenant_user_id: Clerk user id for SERP usage and settings (explicit tenant).
        """
        self._tenant_user_id = require_user_id(tenant_user_id, context=f"Scout.{scout_type}")
        self.scout_type = scout_type
        self.system_prompt = system_prompt
        self.client = OpenAI(api_key=api_key)
        self.logger = logging.getLogger(f"scout.{scout_type}")
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.model = model
        # Token usage for cost controller integration
        self._last_token_usage: int = 0
        # Meta-Agent integration: map to agent name and load any mutated prompt
        self.agent_name = self._get_agent_name()
        self._load_prompt_from_library()
        self._fund_thesis_ctx: Optional[Dict[str, Any]] = None

    def set_fund_thesis(self, thesis_ctx: Optional[Dict[str, Any]]) -> None:
        """Active fund mandate from Supabase; discovery must align when set."""
        self._fund_thesis_ctx = thesis_ctx

    def _fund_thesis_user_block(self) -> str:
        ctx = getattr(self, "_fund_thesis_ctx", None)
        if not ctx:
            return ""
        pj = ctx.get("parsed_json") or {}
        raw = str(ctx.get("raw_text") or "").strip()
        summary = raw[:4000] if len(raw) > 4000 else raw
        lines = [
            "\n\nEvaluate this startup relative to the following investment mandate:\n",
            (summary + "\n\n") if summary else "",
            "FUND THESIS (discover a company that fits this mandate; avoid exclusions):\n",
            f"thesis_version_id: {ctx.get('version_id', '')}\n",
            f"mandate_json: {json.dumps(pj, ensure_ascii=False)[:10000]}\n",
        ]
        emb = ctx.get("embedding") or []
        if isinstance(emb, list) and emb:
            lines.append(
                f"thesis_embedding_dim: {len(emb)}; preview: "
                f"{json.dumps([round(float(x), 6) for x in emb[:16]])}\n"
            )
        return "".join(lines)

    @abstractmethod
    async def discover(self) -> Optional[ScoutOutput]:
        """
        Discover one startup idea.
        
        Returns:
            ScoutOutput if discovery succeeds, None if it fails.
            Must emit valid JSON matching the strict schema.
        """
        pass
    
    def _get_agent_name(self) -> str:
        """
        Map scout_type to Meta-Agent agent name for prompt library lookup.
        """
        mapping = {
            "market_driven": "MarketDrivenScout",
            "builder_technical": "BuilderTechnicalScout",
            "pain_point": "PainPointScout",
            "contrarian": "ContrarianScout",
        }
        return mapping.get(self.scout_type, self.scout_type)

    def _load_prompt_from_library(self) -> None:
        """
        Load latest prompt for this Scout from data/meta/prompt_library.json if available.
        """
        try:
            lib_path = Path(__file__).resolve().parent.parent / "data" / "meta" / "prompt_library.json"
            if not lib_path.exists():
                return
            with open(lib_path, "r", encoding="utf-8") as f:
                library = json.load(f)
            if not isinstance(library, dict):
                return
            latest_key = None
            latest_time = ""
            for key, entry in library.items():
                if key.startswith(self.agent_name + ":"):
                    created = entry.get("created_at", "")
                    if created > latest_time:
                        latest_time = created
                        latest_key = key
            if latest_key and library[latest_key].get("prompt"):
                self.system_prompt = library[latest_key]["prompt"]
                self.logger.info(f"Loaded prompt from library: {latest_key}")
        except Exception as e:
            # Library is optional; log at debug level to avoid noise.
            self.logger.debug(f"Could not load prompt from library: {e}")

    def set_prompt(self, new_prompt: str) -> None:
        """
        Set a new system prompt (called by Meta-Agent).
        """
        self.system_prompt = new_prompt
        self.logger.info(f"Prompt updated for {self.agent_name}")

    def set_dynamic_context(self, context: dict | None) -> None:
        """
        Attach dynamic context from DealMemory before discovery cycles.

        Engines may pass in a dict of aggregate signals (e.g. oversaturated
        sectors, failed assumptions). The base implementation just stores it
        so subclasses or the prompt can consult it when building requests.
        """
        self.dynamic_context = context or {}

    def _reference_anchor_hostname(self, data: Dict[str, Any], explicit_website: Optional[str] = None) -> Optional[str]:
        """Hostname hint for citation filtering: lookup website, then fund canonical site."""
        for cand in (explicit_website, data.get("lookup_website")):
            h = hostname_from_user_hint(cand if isinstance(cand, str) else None)
            if h:
                return h
        return get_canonical_website_hostname(self._tenant_user_id)

    def _call_llm_sync(self) -> Optional[dict]:
        """
        Synchronous LLM call (runs in thread pool).
        Uses the model set during initialization.
        
        Returns:
            Parsed JSON dict if successful, None if failed.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            self._fund_thesis_user_block()
                            + "Find one REAL VC-BACKABLE STARTUP (Seed to Series C, typically private, technology-driven), "
                            "not a hypothetical idea and not a mega-cap incumbent like Google, Microsoft, Amazon, Apple, Meta, IBM, Oracle, Salesforce, SAP, or their cloud brands. "
                            "Output ONLY valid JSON matching the ScoutOutput schema "
                            "(resources/contracts/schemas/scout_output_v1.json). Exact shape:\n\n"
                            "{\n"
                            '  \"id\": \"uuid\",\\n'
                            f'  \"scout_type\": \"{self.scout_type}\",\\n'
                            '  \"name\": \"string (actual startup/company name)\",\\n'
                            '  \"one_line\": \"string\",\\n'
                            '  \"sector\": \"string\",\\n'
                            '  \"problem\": \"string\",\\n'
                            '  \"solution\": \"string\",\\n'
                            '  \"target_users\": \"string\",\\n'
                            '  \"why_now\": \"string\",\\n'
                            '  \"confidence\": number between 0 and 1,\\n'
                            '  \"primary_thesis\": \"string (concise: why investable from your lens)\",\\n'
                            '  \"key_assumptions\": [\"string\", \"string\", ...],  // exactly 2-4 assumptions\\n'
                            '  \"biggest_unknown\": \"string (single largest risk or uncertainty)\",\\n'
                            '  \"funding_stage\": \"Pre-Seed\" | \"Seed\" | \"Series A\" | \"Series B\" | \"Series C+\" | \"Unknown\" | null,\\n'
                            '  \"est_tam\": \"string\" | null,\\n'
                            '  \"references\": [\"string\", ...] // REQUIRED: 1-8 sources that PROVE the company exists\\n'
                            "}\n\n"
                            "CRITICAL - references must PROVE the company exists: company website URL, funding/news article, Crunchbase, LinkedIn, or press release. "
                            "Each reference must be a concrete, verifiable source (e.g. \"Startup X - https://startupx.com\", \"Startup X raised $10M - TechCrunch 2024\"). "
                            "Do NOT use \"General domain knowledge\" or \"no specific external sources\"—those are rejected. "
                            "Avoid giant public companies and hyperscalers (Google, Microsoft, Amazon, Apple, Meta, IBM, Oracle, Salesforce, SAP, etc.). "
                            "If you cannot find a suitable VC-scale startup with verifiable sources, return nothing. "
                            "Do NOT invent company names or make up sources. Use null for funding_stage/est_tam if unknown. "
                            "Output only the JSON object, no text before or after."
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )
            
            # Track token usage if available
            try:
                if hasattr(response, "usage") and response.usage:
                    total = getattr(response.usage, "total_tokens", None)
                    if isinstance(total, int):
                        self._last_token_usage = total
            except Exception:
                # Non-fatal; cost accounting is best-effort
                self._last_token_usage = 0

            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM")
                return None
            
            # Parse JSON
            data = json.loads(content)
            
            # Ensure ID is set
            if "id" not in data or not data["id"]:
                data["id"] = generate_id()
            
            # Ensure scout_type matches
            data["scout_type"] = self.scout_type
            # Optionally enrich references using SERP (guarded + rate-limited)
            data = maybe_enrich_references(data, user_id=self._tenant_user_id)
            data = finalize_scout_references(
                data,
                anchor_hostname=self._reference_anchor_hostname(data),
            )

            return data

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM: {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return None
    
    def _call_llm_for_company_sync(self, company_name: str, website: Optional[str] = None) -> Optional[dict]:
        """
        Synchronous LLM call for a specific company name (runs in thread pool).
        """
        company = (company_name or "").strip()
        if not company:
            return None
        site = (website or "").strip()
        try:
            user_prompt = (
                f'Analyze this specific company: "{company}". '
                "Do not pick a different company. "
                + (
                    f'Official website/domain hint: "{site}". Use this to disambiguate the exact company identity. '
                    if site
                    else ""
                )
                + self._fund_thesis_user_block()
                + "Output ONLY valid JSON matching the ScoutOutput schema "
                "(resources/contracts/schemas/scout_output_v1.json). Exact shape:\n\n"
                "{\n"
                '  "id": "uuid",\n'
                f'  "scout_type": "{self.scout_type}",\n'
                '  "name": "string (canonical legal/brand company name, not the full query sentence)",\n'
                '  "one_line": "string",\n'
                '  "sector": "string",\n'
                '  "problem": "string",\n'
                '  "solution": "string",\n'
                '  "target_users": "string",\n'
                '  "why_now": "string",\n'
                '  "confidence": number between 0 and 1,\n'
                '  "primary_thesis": "string",\n'
                '  "key_assumptions": ["string", "string"],\n'
                '  "biggest_unknown": "string",\n'
                '  "funding_stage": "Pre-Seed" | "Seed" | "Series A" | "Series B" | "Series C+" | "Unknown" | null,\n'
                '  "est_tam": "string" | null,\n'
                '  "references": ["string", ...]\n'
                "}\n\n"
                "CRITICAL: references must contain verifiable sources proving this company exists. "
                "If confidence is low or data is incomplete, still return best-effort fields and set unknowns to null. "
                "Do not invent references. Output only JSON."
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM (company lookup)")
                return None
            data = json.loads(content)
            if "id" not in data or not data["id"]:
                data["id"] = generate_id()
            data["scout_type"] = self.scout_type
            if site:
                data["lookup_website"] = site
            data = maybe_enrich_references(data, user_id=self._tenant_user_id)
            data = finalize_scout_references(
                data,
                anchor_hostname=self._reference_anchor_hostname(data, explicit_website=site or None),
            )
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM (company lookup): {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM company lookup failed: {e}")
            return None

    async def _call_llm(self) -> Optional[dict]:
        """
        Async wrapper for LLM call (runs sync call in thread pool).
        Uses the model set during initialization.
        
        Returns:
            Parsed JSON dict if successful, None if failed.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._call_llm_sync,
        )

    async def discover_company(self, company_name: str, website: Optional[str] = None) -> Optional[ScoutOutput]:
        """
        Discover and validate one specific company by name.
        """
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            self.executor,
            self._call_llm_for_company_sync,
            company_name,
            website,
        )
        if data is None:
            return None
        try:
            return validate_scout_output(data)
        except Exception as e:
            self.logger.error(f"Company lookup validation failed: {e}")
            return None
    
    async def _discover_with_validation(self) -> Optional[ScoutOutput]:
        """
        Internal method that calls discover() and validates output.
        """
        try:
            data = await self.discover()
            if data is None:
                return None
            
            # Validate against schema
            validated = validate_scout_output(data)
            return validated
            
        except ValueError as e:
            self.logger.error(f"Validation failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Discovery failed: {e}")
            return None
