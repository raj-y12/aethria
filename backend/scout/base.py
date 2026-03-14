"""
Base Scout abstraction.
All Scouts inherit from this class and implement the discover() method.
"""
from abc import ABC, abstractmethod
from typing import Optional
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openai import OpenAI

from scout.schema import ScoutOutput, validate_scout_output, generate_id
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
    
    def __init__(self, scout_type: str, system_prompt: str, api_key: str, model: str = "gpt-5-nano"):
        """
        Initialize a Scout.
        
        Args:
            scout_type: Unique identifier for this Scout type (e.g., "market_driven")
            system_prompt: The system prompt that defines this Scout's strategy
            api_key: OpenAI API key
            model: OpenAI model to use (default: gpt-5-nano)
        """
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
                            "Find one REAL VC-BACKABLE STARTUP (Seed to Series C, typically private, technology-driven), "
                            "not a hypothetical idea and not a mega-cap incumbent like Google, Microsoft, Amazon, Apple, Meta, IBM, Oracle, Salesforce, SAP, or their cloud brands. "
                            "Output ONLY valid JSON matching the ScoutOutput schema "
                            "(resources/schemas/scout_output_v1.json). Exact shape:\n\n"
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
            data = maybe_enrich_references(data)
            
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM: {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
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
