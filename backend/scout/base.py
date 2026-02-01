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
from openai import OpenAI

from scout.schema import ScoutOutput, validate_scout_output, generate_id


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
    
    @abstractmethod
    async def discover(self) -> Optional[ScoutOutput]:
        """
        Discover one startup idea.
        
        Returns:
            ScoutOutput if discovery succeeds, None if it fails.
            Must emit valid JSON matching the strict schema.
        """
        pass
    
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
                            "Propose one startup idea as a HYPOTHESIS, not a definitive conclusion. "
                            "Output ONLY valid JSON matching the ScoutOutput schema "
                            "(resources/schemas/scout_output_v1.json). Exact shape:\n\n"
                            "{\n"
                            '  "id": "uuid",\n'
                            f'  "scout_type": "{self.scout_type}",\n'
                            '  "name": "string",\n'
                            '  "one_line": "string",\n'
                            '  "sector": "string",\n'
                            '  "problem": "string",\n'
                            '  "solution": "string",\n'
                            '  "target_users": "string",\n'
                            '  "why_now": "string",\n'
                            '  "confidence": number between 0 and 1,\n'
                            '  "primary_thesis": "string (concise: why this idea is investable from your lens)",\n'
                            '  "key_assumptions": ["string", "string", ...],  // exactly 2-4 assumptions the idea depends on\n'
                            '  "biggest_unknown": "string (single largest unresolved risk or uncertainty)",\n'
                            '  "funding_stage": "Pre-Seed" | "Seed" | "Series A" | "Series B" | "Series C+" | "Unknown" | null,\n'
                            '  "est_tam": "string" | null\n'
                            "}\n\n"
                            "REQUIRED: Include primary_thesis, key_assumptions (2-4 items), and biggest_unknown. "
                            "Do NOT make up financial data, team information, or competitors; use null for funding_stage/est_tam if unknown. "
                            "Do not include any text before or after the JSON. Output only the JSON object."
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )
            
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
