"""
Base Scout abstraction.
All Scouts inherit from this class and implement the discover() method.
"""
from abc import ABC
from typing import Any, Dict, Optional
import json
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from openai import OpenAI

from scout.schema import ScoutOutput, validate_scout_output, generate_id
from tenant_context import require_user_id
from utils.reference_verify import (
    finalize_scout_references,
    filter_references_to_allowlist,
    hostname_from_user_hint,
    registrable_domain,
)
from utils.retrieval_grounding import (
    log_pre_filter_cited_urls,
    render_sources_for_prompt,
    retrieve_source_pack,
)
from utils.settings_loader import (
    get_canonical_website_hostname,
    is_scout_fail_closed_on_empty_retrieval,
    is_scout_grounded_citations_enabled,
)


logger = logging.getLogger(__name__)

_LOW_QUALITY_DIRECTORY_DOMAINS = {
    "pitchbook.com",
    "crunchbase.com",
    "tracxn.com",
    "cbinsights.com",
}

_LOOKUP_NAME_STOPWORDS = {
    "inc",
    "llc",
    "ltd",
    "corp",
    "co",
    "company",
    "technologies",
    "technology",
    "intelligence",
    "investment",
    "investments",
    "systems",
}


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

    async def discover(self) -> Optional[ScoutOutput]:
        """
        Run LLM discovery (_call_llm already finalize/repair-validate raw JSON) and
        assert strict schema. Never return partial dicts (TypedDict(**partial) is not safe).
        """
        data = await self._call_llm()
        if data is None:
            return None
        try:
            return validate_scout_output(data)
        except ValueError as e:
            payload_preview = "none"
            if isinstance(data, dict):
                keys = sorted(list(data.keys()))
                preview = {
                    "keys": keys[:16],
                    "has_name": "name" in data,
                    "name_type": type(data.get("name")).__name__ if "name" in data else None,
                    "scout_type_field": data.get("scout_type"),
                }
                payload_preview = json.dumps(preview, ensure_ascii=False)
            self.logger.error(
                "Validation failed: %s | scout_type=%s | payload_preview=%s",
                e,
                self.scout_type,
                payload_preview,
            )
            return None
        except Exception as e:
            self.logger.error("Discovery failed: %s", e)
            return None
    
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

    def _apply_allowlist(self, data: Dict[str, Any], allowlist_urls: set[str]) -> Dict[str, Any]:
        refs = data.get("references")
        if not isinstance(refs, list):
            refs = []
        result = filter_references_to_allowlist(refs, list(allowlist_urls))
        data["references"] = result["kept"]
        self.logger.info(
            "grounded_citations: allowlist kept=%d dropped=%d",
            len(result["kept"]),
            int(result["dropped_count"]),
        )
        return data

    def _normalize_scout_ids_inplace(self, data: Dict[str, Any]) -> None:
        if not data.get("id"):
            data["id"] = generate_id()
        data["scout_type"] = self.scout_type

    def _postprocess_scout_dict(
        self,
        data: Dict[str, Any],
        source_pack: Dict[str, Any],
        *,
        grounded_enabled: bool,
        fail_closed: bool,
        explicit_website: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Allowlist filter + reference finalize. Returns None if fail-closed with no references."""
        out = dict(data)
        allowlist_urls = set(source_pack.get("url_allowlist") or set())
        if explicit_website and str(explicit_website).strip():
            site = str(explicit_website).strip()
            out["lookup_website"] = site
            # On explicit on-demand lookup, always include the user-provided website as a
            # primary reference so valid lookups do not fail due to weak third-party citations.
            refs = out.get("references")
            ref_list = [str(r).strip() for r in refs if isinstance(r, str) and str(r).strip()] if isinstance(refs, list) else []
            normalized_site = site if site.lower().startswith(("http://", "https://")) else f"https://{site}"
            if not any(normalized_site in r for r in ref_list):
                company_name = str(out.get("name") or "").strip() or "Company"
                ref_list.insert(0, f"{company_name} official website - {normalized_site}")
            out["references"] = ref_list
            # Explicit website is a trusted disambiguation hint from the user; include it in
            # the citation allowlist so grounding does not drop the canonical company reference.
            allowlist_urls.add(normalized_site)
        if grounded_enabled:
            log_pre_filter_cited_urls(out.get("references"))
            out = self._apply_allowlist(out, allowlist_urls)
            if fail_closed and not out.get("references"):
                self.logger.warning(
                    "grounded_citations: fail-closed; no allowlisted references survived (explicit_website=%s)",
                    bool(explicit_website and str(explicit_website).strip()),
                )
                return None
        return finalize_scout_references(
            out,
            anchor_hostname=self._reference_anchor_hostname(out, explicit_website=explicit_website),
        )

    def _scout_validates(self, data: Dict[str, Any]) -> bool:
        try:
            validate_scout_output(data)
            return True
        except Exception as e:
            self.logger.warning(f"[_scout_validates] Validation failed: {e}")
            return False

    def _rank_company_lookup_sources(
        self,
        sources: list[Dict[str, str]],
        *,
        company_name: str,
        website_hint: Optional[str],
    ) -> list[Dict[str, str]]:
        """Prefer primary/company-owned sources for named lookups."""
        anchor_host = hostname_from_user_hint(website_hint)
        anchor_reg = registrable_domain(anchor_host) if anchor_host else None
        company_tokens = [t for t in company_name.lower().replace(".", " ").replace("-", " ").split() if len(t) >= 3][:3]

        def score(source: Dict[str, str]) -> int:
            url = str(source.get("url") or "").strip()
            title = str(source.get("title") or "").lower()
            snippet = str(source.get("snippet") or "").lower()
            try:
                host = (urlparse(url).hostname or "").lower().strip(".")
            except Exception:
                host = ""
            host_reg = registrable_domain(host) if host else ""

            s = 0
            token_match = any(tok in host for tok in company_tokens) or any(
                tok in title or tok in snippet for tok in company_tokens
            )
            if anchor_reg and host_reg == anchor_reg:
                s += 8
            if any(tok in host for tok in company_tokens):
                s += 3
            if any(tok in title or tok in snippet for tok in company_tokens):
                s += 2
            if "/blog" in url or "/docs" in url or "/about" in url:
                s += 1
            # Directory/funding DB sources are useful corroboration, but weak as sole identity proof.
            # Keep them neutral when they match the requested company/domain signals.
            if host_reg in _LOW_QUALITY_DIRECTORY_DOMAINS and not (anchor_reg and token_match):
                s -= 6
            return s

        return sorted(sources, key=score, reverse=True)

    @staticmethod
    def _lookup_anchor_tokens(company_name: str) -> list[str]:
        tokens: list[str] = []
        for raw in (company_name or "").lower().replace("/", " ").replace("-", " ").replace(".", " ").split():
            t = "".join(ch for ch in raw if ch.isalnum())
            if len(t) < 3:
                continue
            if t in _LOOKUP_NAME_STOPWORDS:
                continue
            tokens.append(t)
        return tokens[:4]

    def _matches_lookup_identity(
        self,
        candidate_name: str,
        *,
        expected_company: str,
        website_hint: Optional[str],
    ) -> bool:
        cand = (candidate_name or "").lower()
        if not cand:
            return False
        cand_tokens = set(self._lookup_anchor_tokens(cand))
        expected_tokens = self._lookup_anchor_tokens(expected_company)

        if expected_tokens:
            if not any(tok in cand or tok in cand_tokens for tok in expected_tokens):
                return False

        host = hostname_from_user_hint(website_hint)
        if host:
            host_token = registrable_domain(host).split(".")[0].strip().lower()
            if host_token and len(host_token) >= 4 and host_token not in _LOOKUP_NAME_STOPWORDS:
                if host_token not in cand and host_token not in cand_tokens:
                    return False
        return True

    def _repair_scout_json_sync(
        self,
        incomplete: Dict[str, Any],
        source_pack: Dict[str, Any],
        *,
        grounded_enabled: bool,
        context_note: str = "",
    ) -> Optional[Dict[str, Any]]:
        """One completion to fix missing/invalid fields. Keeps retrieval citations honest when grounded."""
        system = (
            "You repair incomplete Scout JSON for a venture scouting system. "
            "Output exactly one JSON object and no other text. "
            "Every required Scout field must be present with correct types: "
            "name, one_line, sector, problem, solution, target_users, why_now, confidence (0-1 number), "
            "primary_thesis, key_assumptions (array of 2-4 strings), biggest_unknown, references (1-8 strings). "
            "Optional: funding_stage, est_tam (may be null). "
            "`name` must be a real operating company's brand or legal name—not a hypothetical venture, not a market theme. "
            "Never return a partial object. Do not use markdown."
        )
        sources_block = (
            render_sources_for_prompt(source_pack["sources"])
            if grounded_enabled and source_pack.get("sources")
            else "No retrieved source pack for this repair; use only facts you can support. "
            "references must still include at least one real http(s) URL proving the company exists."
        )
        note = (context_note or "").strip()
        payload_str = json.dumps(incomplete, ensure_ascii=False)
        payload = payload_str[:14000]
        user = (
            (f"Context: {note}\n\n" if note else "")
            + "The following JSON is INVALID or incomplete — fix it into a single valid Scout payload.\n\n"
            + payload
            + "\n\n"
            + sources_block
            + "\n\nWhen sources are listed above: each references[] string MUST include an http(s) URL copied from those sources. "
            "key_assumptions must have 2-4 items. Avoid mega-cap incumbents (Google, Microsoft, Amazon, Apple, Meta, etc.)."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=4096,
            )
            try:
                if hasattr(response, "usage") and response.usage:
                    add = getattr(response.usage, "total_tokens", None)
                    if isinstance(add, int):
                        self._last_token_usage += add
            except Exception:
                pass
            content = response.choices[0].message.content
            if not content:
                return None
            return json.loads(content)
        except Exception as e:
            self.logger.warning("scout repair LLM failed: %s", e)
            return None

    def _finalize_scout_payload_from_llm(
        self,
        raw_data: Dict[str, Any],
        source_pack: Dict[str, Any],
        *,
        grounded_enabled: bool,
        fail_closed: bool,
        explicit_website: Optional[str] = None,
        context_note: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize → allowlist + URL finalize → validate; on failure run one repair LLM pass.
        Subclasses wrap TypedDict(**partial) which does not enforce completeness — this does.
        """
        d = dict(raw_data)
        self._normalize_scout_ids_inplace(d)
        p = self._postprocess_scout_dict(
            d,
            source_pack,
            grounded_enabled=grounded_enabled,
            fail_closed=fail_closed,
            explicit_website=explicit_website,
        )
        if p is not None and self._scout_validates(p):
            return p
        if p is None:
            self.logger.info(
                "[%s] scout payload postprocess failed or empty refs; attempting repair",
                self.scout_type,
            )
        else:
            self.logger.warning(
                "[%s] scout payload failed validation; attempting repair pass(es)",
                self.scout_type,
            )
        to_repair: Dict[str, Any] = d
        for attempt in range(2):
            fixed = self._repair_scout_json_sync(
                to_repair,
                source_pack,
                grounded_enabled=grounded_enabled,
                context_note=(
                    f"{context_note} | repair_attempt={attempt + 1}"
                    if (context_note or "").strip()
                    else f"repair_attempt={attempt + 1}"
                ),
            )
            if not isinstance(fixed, dict):
                return None
            d2 = dict(fixed)
            self._normalize_scout_ids_inplace(d2)
            p2 = self._postprocess_scout_dict(
                d2,
                source_pack,
                grounded_enabled=grounded_enabled,
                fail_closed=fail_closed,
                explicit_website=explicit_website,
            )
            if p2 is not None and self._scout_validates(p2):
                return p2
            to_repair = d2
        return None

    def _call_llm_sync(self) -> Optional[Dict[str, Any]]:
        """
        Synchronous LLM call (runs in thread pool).
        Uses the model set during initialization.
        
        Returns:
            Parsed JSON dict if successful, None if failed.
        """
        try:
            self._last_token_usage = 0
            grounded_enabled = is_scout_grounded_citations_enabled(self._tenant_user_id)
            fail_closed = is_scout_fail_closed_on_empty_retrieval(self._tenant_user_id)
            source_pack = {"provider": "none", "sources": [], "url_allowlist": set()}
            if grounded_enabled:
                lens_query = (
                    f"{self.scout_type.replace('_', ' ')} early-stage startup funding "
                    f"news company website"
                )
                source_pack = retrieve_source_pack(
                    query=lens_query,
                    user_id=self._tenant_user_id,
                    max_results=6,
                )
                if fail_closed and not source_pack["sources"]:
                    self.logger.warning(
                        "grounded_citations: fail-closed; no retrieval sources provider=%s",
                        source_pack.get("provider"),
                    )
                    return None
                if not source_pack["sources"]:
                    self.logger.warning(
                        "grounded_citations: enabled but retrieval returned no sources provider=%s; continuing without strict citation-source constraints",
                        source_pack.get("provider"),
                    )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            self._fund_thesis_user_block()
                            + (
                                (
                                    "\n\n"
                                    + render_sources_for_prompt(source_pack["sources"])
                                    + "\n\nCITATION RULES:\n"
                                    "1) Only use URLs present in the retrieved sources above.\n"
                                    "2) references entries must include exact source URL.\n"
                                    "3) Format each reference as: [S#] Title - https://...\n"
                                    "4) If no suitable source is available, return nothing.\n\n"
                                )
                                if grounded_enabled and bool(source_pack.get("sources"))
                                else ""
                            )
                            + "Find one REAL VC-BACKABLE STARTUP (Seed to Series C, typically private, technology-driven), "
                            "not a hypothetical idea, not a product category or market theme, and not a mega-cap incumbent like Google, Microsoft, Amazon, Apple, Meta, IBM, Oracle, Salesforce, SAP, or their cloud brands. "
                            "`name` must be that company's actual brand or legal name as used in the wild (not a generic label like \"AI compliance tooling\"). "
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
                            "You MUST include every top-level key from the schema (name through references); never return a partial JSON object with only id/scout_type/references. "
                            "Output only the JSON object, no text before or after."
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )
            
            # Track token usage if available (repair pass may add more)
            try:
                if hasattr(response, "usage") and response.usage:
                    total = getattr(response.usage, "total_tokens", None)
                    if isinstance(total, int):
                        self._last_token_usage += total
            except Exception:
                pass

            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM")
                return None
            
            data = json.loads(content)
            return self._finalize_scout_payload_from_llm(
                data,
                source_pack,
                grounded_enabled=grounded_enabled,
                fail_closed=fail_closed,
                explicit_website=None,
                context_note="open discovery",
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM: {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return None
    
    def _call_llm_for_company_sync(self, company_name: str, website: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Synchronous LLM call for a specific company name (runs in thread pool).
        """
        company = (company_name or "").strip()
        if not company:
            return None
        site = (website or "").strip()
        try:
            self._last_token_usage = 0
            grounded_enabled = is_scout_grounded_citations_enabled(self._tenant_user_id)
            fail_closed = is_scout_fail_closed_on_empty_retrieval(self._tenant_user_id)
            source_pack = {"provider": "none", "sources": [], "url_allowlist": set()}
            if grounded_enabled:
                query = f"{company} startup company profile funding website"
                source_pack = retrieve_source_pack(
                    query=query,
                    user_id=self._tenant_user_id,
                    max_results=6,
                )
                source_pack["sources"] = self._rank_company_lookup_sources(
                    list(source_pack.get("sources") or []),
                    company_name=company,
                    website_hint=site or None,
                )
                if fail_closed and not source_pack["sources"]:
                    self.logger.warning(
                        "grounded_citations: fail-closed company=%s no retrieval sources",
                        company,
                    )
                    return None
                if not source_pack["sources"]:
                    self.logger.warning(
                        "grounded_citations: company lookup enabled but retrieval returned no sources company=%s provider=%s; continuing without strict citation-source constraints",
                        company,
                        source_pack.get("provider"),
                    )

            user_prompt = (
                f'Analyze this specific company: "{company}". '
                "Do not pick a different company. "
                + (
                    f'Official website/domain hint: "{site}". Use this to disambiguate the exact company identity. '
                    if site
                    else ""
                )
                + self._fund_thesis_user_block()
                + (
                    (
                        "\n\n"
                        + render_sources_for_prompt(source_pack["sources"])
                        + "\n\nCITATION RULES:\n"
                        "1) Only cite sources from the retrieved list.\n"
                        "2) references must include exact URL from that list.\n"
                        "3) Format references as [S#] Title - https://...\n"
                        "4) If sources are insufficient, return nothing.\n\n"
                    )
                    if grounded_enabled and bool(source_pack.get("sources"))
                    else ""
                )
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
                "Prefer primary sources first: official company domain, official docs/blog, product pages, or company-owned GitHub/LinkedIn profile. "
                "Do not rely only on directory/paywalled sources (PitchBook/Crunchbase/Tracxn/CBInsights) if primary sources are available. "
                "Do NOT switch to similarly named companies (for example, different spelling variants). "
                "If the evidence appears to point to a different company identity than requested, return nothing. "
                "If confidence is low or data is incomplete, still return best-effort fields and set unknowns to null. "
                "You MUST include every top-level key from the schema (name through references); never return a partial object. "
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
            try:
                if hasattr(response, "usage") and response.usage:
                    total = getattr(response.usage, "total_tokens", None)
                    if isinstance(total, int):
                        self._last_token_usage += total
            except Exception:
                pass
            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM (company lookup)")
                return None
            data = json.loads(content)
            if site:
                data["lookup_website"] = site
            finalized = self._finalize_scout_payload_from_llm(
                data,
                source_pack,
                grounded_enabled=grounded_enabled,
                fail_closed=fail_closed,
                explicit_website=site or None,
                context_note=f'company lookup: "{company}"',
            )
            if finalized is None:
                return None
            if not self._matches_lookup_identity(
                str(finalized.get("name") or ""),
                expected_company=company,
                website_hint=site or None,
            ):
                self.logger.warning(
                    "company lookup identity mismatch: expected=%s got=%s website_hint=%s",
                    company,
                    finalized.get("name"),
                    site or "",
                )
                return None
            return finalized
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM (company lookup): {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM company lookup failed: {e}")
            return None

    async def _call_llm(self) -> Optional[Dict[str, Any]]:
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
        """Pipeline entrypoint; discover() already enforces schema."""
        return await self.discover()
