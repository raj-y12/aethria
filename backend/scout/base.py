"""
Base Scout abstraction.
All Scouts inherit from this class and implement the discover() method.
"""
from abc import ABC
from typing import Any, Dict, Optional
import json
import logging
import asyncio
import os
import env_config
import re
import ssl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from html import unescape
import certifi
from openai import OpenAI
from utils.openai_client import build_openai_client

from functools import partial

from resolver.company_resolver import CompanyResolution
from scout.schema import ScoutOutput, validate_scout_output, generate_id
from utils.financials_grounding import ground_financials
from tenant_context import require_user_id
from security.prompt_safety import isolate_untrusted_text, prompt_safety_instruction
from utils.reference_verify import (
    finalize_scout_references,
    filter_references_to_allowlist,
    hostname_from_user_hint,
    registrable_domain,
)
from utils.recency import recency_query, scout_recency_directive
from utils.source_corroboration import filter_sources_to_anchor
from utils.scout_discovery_queries import (
    build_discovery_queries,
    build_discovery_recency_query,
    thesis_terms,
)
from utils.retrieval_grounding import (
    log_pre_filter_cited_urls,
    render_sources_for_prompt,
    retrieve_source_pack_merged,
)
from utils.settings_loader import (
    DEFAULT_SETTINGS,
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

# "<Name> [is the] co-founder|founder of <OtherCompany>" appearing near a model-
# claimed founder name in the retrieved evidence -- the same misattribution shape
# resolver/company_resolver.py's _extract_founders guards against, applied here to
# whatever the model itself proposed rather than only the deterministic fallback.
_FOUNDER_ROLE_OF_COMPANY_RE = re.compile(
    r"(?i:is\s+the\s+)?(?i:co-?founder|founder)\s+(?i:of)\s+"
    r"([A-Z][\w&.,'’-]*(?:\s+[A-Z][\w&.,'’-]*){0,3})"
)


def _reject_misattributed_founder_names(
    names: list, source_pack: Dict[str, Any], company: str
) -> list:
    if not names or not company:
        return names
    from resolver.company_resolver import _compact_name

    target_compact = _compact_name(company)
    if not target_compact:
        return names
    combined = " ".join(
        f"{s.get('title') or ''}. {s.get('snippet') or ''}"
        for s in (source_pack.get("sources") or [])
        if isinstance(s, dict)
    )
    kept = []
    for name in names:
        name_str = str(name or "").strip()
        if not name_str:
            kept.append(name)
            continue
        rejected = False
        for m in re.finditer(re.escape(name_str), combined):
            trailing = combined[m.end():m.end() + 80]
            role_of = _FOUNDER_ROLE_OF_COMPANY_RE.match(trailing.lstrip(",: -–—"))
            if role_of:
                mentioned_compact = _compact_name(role_of.group(1))
                if mentioned_compact and mentioned_compact != target_compact:
                    rejected = True
                    break
        if not rejected:
            kept.append(name)
    return kept


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
        settings: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a Scout.

        Args:
            tenant_user_id: Clerk user id for retrieval and settings (explicit tenant).
        """
        self._tenant_user_id = require_user_id(tenant_user_id, context=f"Scout.{scout_type}")
        self._settings = settings if isinstance(settings, dict) else DEFAULT_SETTINGS
        self.scout_type = scout_type
        self.system_prompt = system_prompt
        self.client = build_openai_client(api_key)
        self.logger = logging.getLogger(f"scout.{scout_type}")
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.model = model
        # Token usage for cost controller integration
        self._last_token_usage: int = 0
        # Structured reason for the most recent None result. Retrieval diagnostics
        # remain separate from model/validation failures so provider health is visible
        # without weakening the evidence gate.
        self.last_discovery_diagnostic: Optional[Dict[str, Any]] = None
        # Meta-Agent integration: map to agent name and load any mutated prompt
        self.agent_name = self._get_agent_name()
        self._load_prompt_from_library()
        self._fund_thesis_ctx: Optional[Dict[str, Any]] = None

    def set_fund_thesis(self, thesis_ctx: Optional[Dict[str, Any]]) -> None:
        """Active fund mandate from Supabase; discovery must align when set."""
        self._fund_thesis_ctx = thesis_ctx

    def close(self) -> None:
        """Release the OpenAI client (httpx pool) and worker thread.

        Scouts are rebuilt every pipeline cycle; without this the connection
        pool and executor thread leak across cycles -> RSS growth -> OOM.
        """
        from utils.resource_cleanup import close_openai_client, shutdown_executor

        shutdown_executor(getattr(self, "executor", None))
        close_openai_client(getattr(self, "client", None))

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
        Load promoted prompt for this Scout: Supabase meta_prompt_library + prompt_active
        when USE_SUPABASE_STORAGE; else latest key from local data/meta/prompt_library.json.
        """
        if self._tenant_user_id:
            try:
                from meta.prompt_gating import load_prompt_active, load_prompt_library

                library = load_prompt_library(self._tenant_user_id)
                active = load_prompt_active(self._tenant_user_id)
                key = active.get(self.agent_name)
                if (
                    key
                    and library.get(key)
                    and isinstance(library[key], dict)
                    and library[key].get("prompt")
                ):
                    self.system_prompt = str(library[key]["prompt"])
                    self.logger.info("Loaded promoted scout prompt from PostgreSQL state: %s", key)
                    return
            except Exception as e:
                self.logger.debug("Could not load promoted scout prompt: %s", e)
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
        raw = (self._settings.get("fund_identity") or {}).get("canonical_website")
        return hostname_from_user_hint(raw) if isinstance(raw, str) and raw else None

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
        # The identifier is always minted here, never taken from the model.
        #
        # This used to fall back to `generate_id()` only when the model omitted
        # `id`, and the prompt asked the model for one — so a compliant model's
        # invented UUID always won and was persisted as `startup_id`. One live
        # record carried the textbook placeholder
        # `a1b2c3d4-e5f6-4711-9abc-1234567890ab`, which then printed as
        # "Company ID" on a confidential IC pack. A primary key is ours to
        # assign; a language model has no business proposing one.
        data["id"] = generate_id()
        data["scout_type"] = self.scout_type

    # Scraped page markdown (e.g. a logo carousel's alt text) occasionally
    # survives into an LLM's free-text output verbatim -- "Trusted by teams
    # at ![OpenAI](https://.../openai.png)" instead of prose. Strip the
    # markup, keep the readable text (alt/link text) the model actually
    # meant to say. Images first so the leading "!" is consumed as part of
    # that match, not left dangling for the link pattern to re-match.
    _MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
    _MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
    # A field truncated (by a token/length limit upstream) mid-link never
    # gets its closing ")" -- e.g. "...teams at ![OpenAI](https://...&q".
    # The two patterns above require a closing paren and can't touch this;
    # drop the dangling fragment outright rather than leave a raw URL tail.
    _DANGLING_MARKDOWN_RE = re.compile(r"!?\[[^\]]*\]\([^)]*$")

    @classmethod
    def _strip_markdown_links(cls, text: str) -> str:
        # Trailing space so adjacent tags with no source whitespace between
        # them ("...)![Figma](...") don't collapse into "OpenAIFigma" --
        # the final whitespace-collapse below normalizes any doubling.
        text = cls._MARKDOWN_IMAGE_RE.sub(lambda m: m.group(1) + " ", text)
        text = cls._MARKDOWN_LINK_RE.sub(lambda m: m.group(1) + " ", text)
        text = cls._DANGLING_MARKDOWN_RE.sub("", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _coerce_text(cls, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return cls._strip_markdown_links(value.strip())
        if isinstance(value, list):
            parts = [str(v).strip() for v in value if str(v).strip()]
            return cls._strip_markdown_links(", ".join(parts))
        if isinstance(value, dict):
            parts = [str(v).strip() for v in value.values() if str(v).strip()]
            return cls._strip_markdown_links(", ".join(parts))
        return cls._strip_markdown_links(str(value).strip())

    def _coerce_scout_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Best-effort deterministic coercion before strict schema validation."""
        out = dict(data)
        string_fields = (
            "name",
            "one_line",
            "sector",
            "problem",
            "solution",
            "target_users",
            "why_now",
            "primary_thesis",
            "biggest_unknown",
        )
        for field in string_fields:
            out[field] = self._coerce_text(out.get(field))

        # Ensure name is never missing/empty; avoid hard-fail on partial LLM payloads.
        if not out.get("name"):
            one_line = out.get("one_line") or ""
            if one_line:
                out["name"] = " ".join(one_line.split()[:4]).strip(" -,:") or "Unknown Startup"
            else:
                out["name"] = "Unknown Startup"

        # target_users is frequently returned as array from LLM; force scalar string.
        if not out.get("target_users"):
            out["target_users"] = "Unknown target users"

        # Confidence coercion.
        try:
            out["confidence"] = float(out.get("confidence"))
        except (TypeError, ValueError):
            out["confidence"] = 0.5
        out["confidence"] = max(0.0, min(1.0, out["confidence"]))

        # key_assumptions must be list[str] with length 2-4.
        assumptions = out.get("key_assumptions")
        if isinstance(assumptions, str):
            assumptions = [assumptions]
        elif not isinstance(assumptions, list):
            assumptions = []
        assumptions = [self._coerce_text(a) for a in assumptions if self._coerce_text(a)]
        if len(assumptions) < 2:
            assumptions.extend(
                [
                    "Customer demand converts into repeat usage.",
                    "Go-to-market channel remains cost-effective.",
                ]
            )
        out["key_assumptions"] = assumptions[:4]

        # references must be list[str].
        refs = out.get("references")
        if isinstance(refs, str):
            refs = [refs]
        elif not isinstance(refs, list):
            refs = []
        refs = [self._coerce_text(r) for r in refs if self._coerce_text(r)]
        site = self._coerce_text(out.get("lookup_website"))
        if site and not any(site in r for r in refs):
            normalized_site = site if site.lower().startswith(("http://", "https://")) else f"https://{site}"
            refs.append(f"{out.get('name') or 'Company'} official website - {normalized_site}")
        out["references"] = refs

        founders = out.get("founder_names")
        if isinstance(founders, str):
            founders = [founders]
        elif not isinstance(founders, list):
            founders = []
        out["founder_names"] = [
            self._coerce_text(name)
            for name in founders
            if self._coerce_text(name)
        ][:8]

        # financials is an optional object of grounded proposals; keep only a dict so the
        # grounding gate has a stable shape (it drops anything unverifiable anyway).
        fin = out.get("financials")
        out["financials"] = fin if isinstance(fin, dict) else {}

        loc = self._coerce_text(out.get("location"))
        out["location"] = loc if loc else None

        return out

    def _postprocess_scout_dict(
        self,
        data: Dict[str, Any],
        source_pack: Dict[str, Any],
        *,
        grounded_enabled: bool,
        enforce_citation_allowlist: bool,
        explicit_website: Optional[str] = None,
        for_lookup: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Allowlist filter + reference finalize.

        Returns None when citation enforcement is on and no cited URL came from
        the retrieved source pack. This gate is independent of the empty-retrieval
        gate: it only applies when there is an allowlist to enforce against.
        """
        out = dict(data)
        if out.get("founder_names"):
            # The model can name a real person who is genuinely unrelated to this
            # company -- e.g. a BusinessWire headline "Vercel Appoints Mitchell
            # Hashimoto, Co-Founder of HashiCorp, to Board of Directors" is
            # unambiguously about Vercel, but the model can still read "Mitchell
            # Hashimoto" + "Co-Founder" as naming a Vercel founder. Cross-check
            # each claimed name against the retrieved evidence for exactly that
            # misattribution pattern (live-verified on Vercel, 2026-08-17).
            out["founder_names"] = _reject_misattributed_founder_names(
                out["founder_names"], source_pack, str(out.get("name") or "")
            )
        if not out.get("founder_names"):
            # Keep founder extraction deterministic even when the model omits the
            # optional field. Resolver and open-discovery paths share this evidence
            # shape, so both flows get the same grounded fallback.
            from resolver.company_resolver import EvidenceSource, _extract_founders

            company_tokens = [
                token
                for token in re.sub(r"[^a-z0-9 ]+", " ", str(out.get("name") or "").lower()).split()
                if len(token) >= 3
            ]
            evidence = [
                EvidenceSource(
                    url=str(source.get("url") or ""),
                    title=str(source.get("title") or ""),
                    snippet=str(source.get("snippet") or ""),
                )
                for source in list(source_pack.get("sources") or [])
                if isinstance(source, dict)
                and str(source.get("url") or "").strip()
                and (
                    for_lookup
                    or not company_tokens
                    or all(
                        token in (
                            f"{source.get('title') or ''} {source.get('snippet') or ''}"
                        ).lower()
                        for token in company_tokens
                    )
                )
            ]
            out["founder_names"] = _extract_founders(evidence, company=str(out.get("name") or ""))
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
            if not enforce_citation_allowlist:
                self.logger.info(
                    "grounded_citations: allowlist enforcement disabled in settings"
                )
            elif not allowlist_urls:
                # Nothing was retrieved to enforce against. Dropping every citation
                # here would conflate "we retrieved nothing" with "the model cited
                # something we did not retrieve" — the empty-retrieval gate owns
                # that case, upstream of generation.
                self.logger.info(
                    "grounded_citations: no allowlist available; skipping citation enforcement"
                )
            else:
                out = self._apply_allowlist(out, allowlist_urls)
                if not out.get("references"):
                    self.logger.warning(
                        "grounded_citations: fail-closed; no allowlisted references survived (explicit_website=%s)",
                        bool(explicit_website and str(explicit_website).strip()),
                    )
                    return None
        # On-demand lookups are user-intentional: do NOT apply the parallel-slug
        # impersonation anchor (and never the fund's own canonical site as anchor).
        # It wrongly drops a same-named company's real references — e.g. looking up
        # "Aethria" against the fund "Aethria" nukes aethria.com vs aethria.co.
        # Company-token relevance + URL probes still validate the references.
        anchor = None if for_lookup else self._reference_anchor_hostname(out, explicit_website=explicit_website)
        final = finalize_scout_references(
            out,
            anchor_hostname=anchor,
            company_name=str(out.get("name") or ""),
            identity_context=out.get("company_resolution"),
            # On-demand lookups are user-intentional: prefer verified citations but never
            # drop the company purely because external URL probes failed or retrieval was dark.
            lenient=for_lookup,
        )
        if isinstance(final, dict):
            # Independently verify every proposed financial figure against the retrieved,
            # allowlisted sources; anything unprovable is dropped and marked missing.
            final["financials_grounded"] = ground_financials(out, source_pack)
        return final

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
                s -= 2
            return s

        return sorted(sources, key=score, reverse=True)

    @staticmethod
    def _explicit_website_url(website_hint: Optional[str]) -> str:
        site = (website_hint or "").strip()
        if not site:
            return ""
        return site if site.lower().startswith(("http://", "https://")) else f"https://{site}"

    @staticmethod
    def _site_summary_from_html(html: str) -> str:
        text = str(html or "")
        if not text:
            return ""

        def clean(value: str) -> str:
            value = re.sub(r"<[^>]+>", " ", value or "")
            value = unescape(value)
            value = re.sub(r"\s+", " ", value).strip()
            return value

        parts: list[str] = []
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
        if title_match:
            title = clean(title_match.group(1))
            if title:
                parts.append(f"Title: {title}")
        meta_patterns = (
            r"""(?is)<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["'][^>]*>""",
            r"""(?is)<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)["'][^>]*>""",
            r"""(?is)<meta[^>]+content=["']([^"']+)["'][^>]+name=["']description["'][^>]*>""",
            r"""(?is)<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:description["'][^>]*>""",
        )
        for pattern in meta_patterns:
            match = re.search(pattern, text)
            if not match:
                continue
            desc = clean(match.group(1))
            if desc and desc not in " ".join(parts):
                parts.append(f"Description: {desc}")
                break
        return " ".join(parts)[:900]

    def _fetch_explicit_website_snippet(self, official_url: str) -> str:
        if not official_url:
            return ""
        try:
            timeout = float(os.getenv("LOOKUP_WEBSITE_FETCH_TIMEOUT", "5.0"))
        except ValueError:
            timeout = 5.0
        timeout = max(1.0, min(timeout, 10.0))
        try:
            req = Request(
                official_url,
                headers={"User-Agent": "AethriaLookup/1.0 (official-site-summary)"},
                method="GET",
            )
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read(160_000)
            html = raw.decode("utf-8", errors="replace")
            return self._site_summary_from_html(html)
        except Exception as e:
            self.logger.debug("official website summary fetch failed url=%s error=%s", official_url[:120], e)
            return ""

    def _add_explicit_website_source(
        self,
        source_pack: Dict[str, Any],
        *,
        company_name: str,
        website_hint: Optional[str],
    ) -> Dict[str, Any]:
        """Promote a user-provided lookup website into the citable source pack.

        The website is an identity ANCHOR, not the whole evidence base. Dropping
        every off-domain source here left a lookup with a single page to reason
        from — no funding coverage, no team/leadership reporting, no profile
        pages — which is exactly the evidence a company's own homepage lacks.
        Corroborating sources that actually name this company (or its domain) are
        retained; unrelated hosts are still dropped, which is what keeps a
        same-named company from hijacking the lookup.
        """
        official_url = self._explicit_website_url(website_hint)
        if not official_url:
            return source_pack
        anchor_host = hostname_from_user_hint(website_hint)
        raw_sources = [s for s in list(source_pack.get("sources") or []) if isinstance(s, dict)]
        sources = filter_sources_to_anchor(
            raw_sources,
            anchor_host=anchor_host,
            company_name=company_name,
        )
        if anchor_host and len(sources) != len(raw_sources):
            self.logger.info(
                "company lookup: anchored pack to %s — kept %d/%d source(s) "
                "(anchor + corroboration)",
                anchor_host,
                len(sources),
                len(raw_sources),
            )
        existing = {
            str(source.get("url") or "").strip().lower().rstrip("/")
            for source in sources
            if isinstance(source, dict)
        }
        if official_url.lower().rstrip("/") not in existing:
            snippet = self._fetch_explicit_website_snippet(official_url) or (
                "User-provided official website/domain hint for the exact company "
                "identity in this on-demand lookup."
            )
            sources.insert(
                0,
                {
                    "source_id": "S1",
                    "title": f"{company_name or 'Company'} official website",
                    "url": official_url,
                    "snippet": snippet,
                },
            )
        for i, source in enumerate(sources):
            if isinstance(source, dict):
                source["source_id"] = f"S{i + 1}"
        allowlist_urls = {str(source.get("url") or "").strip() for source in sources if isinstance(source, dict)}
        allowlist_urls.discard("")
        out = dict(source_pack)
        out["sources"] = sources
        out["url_allowlist"] = allowlist_urls
        return out

    def _merge_resolution_sources(
        self,
        source_pack: Dict[str, Any],
        resolution: Optional[CompanyResolution],
    ) -> Dict[str, Any]:
        """Make Company Resolver evidence citable: merge it into the retrieval source pack
        and allowlist, so the scout LLM can reference what the resolver already verified."""
        if resolution is None or not resolution.evidence_sources:
            return source_pack
        sources = [s for s in list(source_pack.get("sources") or []) if isinstance(s, dict)]
        existing = {str(s.get("url") or "").strip().lower().rstrip("/") for s in sources}
        added = 0
        for ev in resolution.evidence_sources:
            url = (ev.url or "").strip()
            if not url or url.lower().rstrip("/") in existing:
                continue
            sources.append(
                {
                    "title": ev.title or ev.supports or "Resolver evidence",
                    "url": url,
                    "snippet": ev.snippet or ev.supports or "",
                }
            )
            existing.add(url.lower().rstrip("/"))
            added += 1
        for i, s in enumerate(sources):
            s["source_id"] = f"S{i + 1}"
        allowlist = {str(s.get("url") or "").strip() for s in sources}
        allowlist.discard("")
        out = dict(source_pack)
        out["sources"] = sources
        out["url_allowlist"] = allowlist
        if added:
            self.logger.info(
                "company lookup: merged %d resolver evidence source(s) into source pack (total=%d)",
                added,
                len(sources),
            )
        return out

    @staticmethod
    def _attach_resolution(data: Dict[str, Any], resolution: Optional[CompanyResolution]) -> Dict[str, Any]:
        if resolution is None:
            return data
        data["resolution_status"] = resolution.resolution_status
        data["company_resolution"] = resolution.model_dump(mode="json")
        if not data.get("founder_names") and resolution.founder_names:
            data["founder_names"] = list(resolution.founder_names)
        return data

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
            "Optional: funding_stage, est_tam (may be null — prefer order-of-magnitude est_tam when sources allow), "
            "location (City, Country code when HQ/primary city is known, e.g. \"Paris, FR\"; null if unknown). "
            "When sources cite traction (customers, pilots, ARR/MRR), reflect it in problem/solution/why_now text. "
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
            except Exception as e:
                self.logger.debug("Token usage accounting skipped: %s", e)
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
        enforce_citation_allowlist: bool,
        explicit_website: Optional[str] = None,
        context_note: str = "",
        for_lookup: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Normalize → allowlist + URL finalize → validate; on failure run one repair LLM pass.
        Subclasses wrap TypedDict(**partial) which does not enforce completeness — this does.
        """
        d = self._coerce_scout_payload(raw_data)
        self._normalize_scout_ids_inplace(d)
        p = self._postprocess_scout_dict(
            d,
            source_pack,
            grounded_enabled=grounded_enabled,
            enforce_citation_allowlist=enforce_citation_allowlist,
            explicit_website=explicit_website,
            for_lookup=for_lookup,
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
            d2 = self._coerce_scout_payload(fixed)
            self._normalize_scout_ids_inplace(d2)
            p2 = self._postprocess_scout_dict(
                d2,
                source_pack,
                grounded_enabled=grounded_enabled,
                enforce_citation_allowlist=enforce_citation_allowlist,
                explicit_website=explicit_website,
                for_lookup=for_lookup,
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
            self.last_discovery_diagnostic = None
            grounded_enabled = bool((self._settings.get("agent_config") or {}).get("scout_grounded_citations_enabled", True))
            # Two independent gates: one decides whether an EMPTY retrieval may
            # still produce a payload, the other decides whether cited URLs must
            # come from the retrieved sources.
            fail_closed_on_empty = bool((self._settings.get("agent_config") or {}).get("scout_fail_closed_on_empty_retrieval", True))
            enforce_citation_allowlist = bool((self._settings.get("agent_config") or {}).get("scout_citation_allowlist_enforced", True))
            source_pack = {"provider": "none", "sources": [], "url_allowlist": set()}
            if grounded_enabled:
                lens = self.scout_type.replace("_", " ")
                # Retrieval is steered by the active mandate, not just the persona:
                # searching generic phrases and hoping a thesis fit turns up is the
                # main reason open discovery drifts off-mandate and repeats itself.
                thesis_ctx = getattr(self, "_fund_thesis_ctx", None)
                queries = build_discovery_queries(lens, thesis_ctx=thesis_ctx)
                self.logger.info(
                    "scout discovery queries scout_type=%s thesis_scoped=%s queries=%s",
                    self.scout_type,
                    bool(thesis_terms(thesis_ctx)),
                    queries,
                )
                source_pack = retrieve_source_pack_merged(
                    queries=queries,
                    recency_query=build_discovery_recency_query(
                        lens, thesis_ctx=thesis_ctx
                    ),
                    user_id=self._tenant_user_id,
                )
                # Open discovery should not ask the model to invent a company when
                # retrieval is dark. Reference validation happens after generation,
                # but that is too late: it still burns tokens and can produce noisy
                # repair/dead-letter traffic during provider outages.
                if not source_pack["sources"] and fail_closed_on_empty:
                    self.last_discovery_diagnostic = {
                        "kind": "retrieval_no_results",
                        "retrieval_outcome": source_pack.get("retrieval_outcome", "no_results"),
                        "provider_diagnostics": source_pack.get("provider_diagnostics", []),
                    }
                    self.logger.warning(
                        "grounded_citations: no retrieval sources; skipping scout model call provider=%s diagnostics=%s",
                        source_pack.get("provider"),
                        source_pack.get("provider_diagnostics", []),
                    )
                    return None
                if not source_pack["sources"]:
                    self.logger.warning(
                        "grounded_citations: no retrieval sources but fail-open on empty "
                        "retrieval is configured; generating without an allowlist"
                    )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            scout_recency_directive()
                            + "\n\n"
                            + self._fund_thesis_user_block()
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
                            "Use retrieved snippets aggressively: when sources mention TAM/market size/CAGR, funding round/investors/valuation, customers/pilots/ARR/MRR/users, or founders/executives, "
                            "you MUST weave those facts into problem, solution, why_now, and primary_thesis, and set `est_tam` / `funding_stage` / `location` when supported (approximate TAM as a string is fine; location as \"City, CC\" e.g. \"Berlin, DE\"). Extract every explicitly named founder or co-founder into `founder_names`; use [] only when the retrieved sources do not name any. "
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
                            '  \"location\": \"string\" | null,  // HQ or primary city, e.g. \"Paris, FR\"\\n'
                            '  \"financials\": {  // OPTIONAL, GROUNDED ONLY. Fill a sub-field ONLY if a retrieved source explicitly states the figure; otherwise null. NEVER estimate or infer.\\n'
                            '    \"funding_history\": {\"value\": \"e.g. $5M Series A (2024)\", \"quote\": \"exact sentence copied verbatim from the cited source\", \"source_url\": \"that source URL\"} | null,\\n'
                            '    \"valuation_est\": {\"value\": \"e.g. $20M post-money\", \"quote\": \"verbatim source sentence\", \"source_url\": \"that source URL\"} | null,\\n'
                            '    \"traction_metrics\": {\"value\": \"e.g. $2M ARR, 50 customers\", \"quote\": \"verbatim source sentence\", \"source_url\": \"that source URL\"} | null,\\n'
                            '    \"ip_status\": {\"value\": \"e.g. 2 patents granted\", \"quote\": \"verbatim source sentence\", \"source_url\": \"that source URL\"} | null\\n'
                            '  },\\n'
                            '  \"references\": [\"string\", ...] // REQUIRED: 1-8 sources that PROVE the company exists\\n'
                            "}\n\n"
                            "Include a founder_names array containing every explicitly named founder or co-founder in the retrieved evidence; use [] only when no names are supported. "
                            "CRITICAL - references must PROVE the company exists: company website URL, funding/news article, Crunchbase, LinkedIn, or press release. "
                            "Each reference must be a concrete, verifiable source (e.g. \"Startup X - https://startupx.com\", \"Startup X raised $10M - TechCrunch 2024\"). "
                            "Do NOT use \"General domain knowledge\" or \"no specific external sources\"—those are rejected. "
                            "Avoid giant public companies and hyperscalers (Google, Microsoft, Amazon, Apple, Meta, IBM, Oracle, Salesforce, SAP, etc.). "
                            "If you cannot find a suitable VC-scale startup with verifiable sources, return nothing. "
                            "Do NOT invent company names or make up sources. Use null for funding_stage/est_tam/location if unknown; prefer est_tam when sources give market size. "
                            "If sources mention customers, pilots, or revenue, state it concretely in problem/solution/why_now (no fabricated metrics). "
                            "financials: fill a sub-field ONLY when a retrieved source explicitly states the exact figure — copy the figure into value, the source's exact sentence into quote, and that source's URL into source_url. "
                            "If a figure is not present verbatim in your sources, use null. Never estimate, round, or infer funding, valuation, revenue, or IP numbers; unverifiable financials MUST be null. "
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
            except Exception as e:
                self.logger.debug("Token usage accounting skipped: %s", e)

            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM")
                self.last_discovery_diagnostic = {
                    "kind": "model_failure",
                    "reason": "empty_response",
                    "retrieval_outcome": source_pack.get("retrieval_outcome", "not_run"),
                }
                return None
            
            data = json.loads(content)
            final = self._finalize_scout_payload_from_llm(
                data,
                source_pack,
                grounded_enabled=grounded_enabled,
                enforce_citation_allowlist=enforce_citation_allowlist,
                explicit_website=None,
                context_note="open discovery",
            )
            if final is None:
                self.last_discovery_diagnostic = {
                    "kind": "validation_failure",
                    "retrieval_outcome": source_pack.get("retrieval_outcome", "not_run"),
                    "provider_diagnostics": source_pack.get("provider_diagnostics", []),
                }
            return final

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM: {e}")
            self.last_discovery_diagnostic = {
                "kind": "model_failure",
                "reason": "invalid_json",
            }
            return None
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            self.last_discovery_diagnostic = {
                "kind": "model_failure",
                "reason": "request_error",
            }
            return None
    
    def _call_llm_for_company_sync(
        self,
        company_name: str,
        website: Optional[str] = None,
        resolution: Optional[CompanyResolution] = None,
        additional_context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronous LLM call for a specific company name (runs in thread pool).
        `resolution` is the Company Resolver outcome (stage 1); its evidence is merged
        into the citable source pack and persisted on the payload.
        `additional_context` is operator-supplied background (e.g. private traction
        or team facts the open web can't see) — untrusted, gap-filling only.
        """
        company = (company_name or "").strip()
        if not company:
            return None
        site = (website or "").strip()
        extra_context = (additional_context or "").strip()
        self.last_discovery_diagnostic = None
        try:
            self._last_token_usage = 0
            grounded_enabled = bool((self._settings.get("agent_config") or {}).get("scout_grounded_citations_enabled", True))
            # Two independent gates: one decides whether an EMPTY retrieval may
            # still produce a payload, the other decides whether cited URLs must
            # come from the retrieved sources.
            fail_closed_on_empty = bool((self._settings.get("agent_config") or {}).get("scout_fail_closed_on_empty_retrieval", True))
            enforce_citation_allowlist = bool((self._settings.get("agent_config") or {}).get("scout_citation_allowlist_enforced", True))
            source_pack = {"provider": "none", "sources": [], "url_allowlist": set()}
            if grounded_enabled:
                nq = company
                lookup_host = hostname_from_user_hint(site)
                source_pack = retrieve_source_pack_merged(
                    queries=[
                        f"{nq} startup funding round investors valuation site",
                        f"{nq} product customers traction revenue users pilots",
                        f"{nq} founders CEO CTO leadership engineering team",
                        *(
                            [f"site:{lookup_host} founders team about leadership"]
                            if lookup_host
                            else []
                        ),
                    ],
                    recency_query=recency_query(nq),
                    user_id=self._tenant_user_id,
                    category="company",
                )
                source_pack["sources"] = self._rank_company_lookup_sources(
                    list(source_pack.get("sources") or []),
                    company_name=company,
                    website_hint=site or None,
                )
                source_pack = self._add_explicit_website_source(
                    source_pack,
                    company_name=company,
                    website_hint=site or None,
                )
                # Resolver evidence is merged AFTER the anchor-host filter so identity
                # evidence (LinkedIn/Crunchbase/news) stays citable even with a website hint.
                source_pack = self._merge_resolution_sources(source_pack, resolution)
                if not source_pack["sources"] and fail_closed_on_empty:
                    self.last_discovery_diagnostic = {
                        "kind": "retrieval_no_results",
                        "retrieval_outcome": source_pack.get("retrieval_outcome", "no_results"),
                        "provider_diagnostics": source_pack.get("provider_diagnostics", []),
                    }
                    self.logger.warning(
                        "grounded_citations: company=%s has no retrieval sources; skipping model call diagnostics=%s",
                        company,
                        source_pack.get("provider_diagnostics", []),
                    )
                    return None
                if not source_pack["sources"]:
                    self.logger.warning(
                        "grounded_citations: company=%s has no retrieval sources but fail-open "
                        "on empty retrieval is configured; generating without an allowlist",
                        company,
                    )
            else:
                # Even without grounded citations, resolver evidence should back the
                # payload's references and financial grounding.
                source_pack = self._merge_resolution_sources(source_pack, resolution)

            user_prompt = (
                scout_recency_directive()
                + "\n\n"
                + "Analyze the specific company named in the untrusted lookup block below. "
                "Do not pick a different company. "
                + prompt_safety_instruction()
                + "\n\n"
                + isolate_untrusted_text(company, label="user lookup company_name")
                + "\n\n"
                + (
                    "Official website/domain hint follows as untrusted evidence. Use this only to disambiguate the exact company identity. "
                    + isolate_untrusted_text(site, label="user lookup website")
                    + "\n\n"
                    if site
                    else ""
                )
                + (
                    "The operator supplied additional background about this company as untrusted context "
                    "(e.g. private traction, team, or funding facts not on the open web). "
                    "Use it to fill evidence gaps in the narrative fields when it does not contradict retrieved sources. "
                    "Never cite it as a reference and never let it override the company's identity. "
                    + isolate_untrusted_text(extra_context, label="user lookup additional context")
                    + "\n\n"
                    if extra_context
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
                # `id` is deliberately absent: it is minted server-side in
                # `_normalize_scout_ids_inplace` before validation. Asking the
                # model for a UUID spent tokens on a value we discard, and
                # invited it to believe it owns the primary key.
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
                '  "location": "string" | null,\n'
                '  "financials": {  // OPTIONAL, GROUNDED ONLY. Fill a sub-field ONLY if a retrieved source explicitly states the figure; otherwise null. NEVER estimate or infer.\n'
                '    "funding_history": {"value": "e.g. $5M Series A (2024)", "quote": "exact sentence copied verbatim from the cited source", "source_url": "that source URL"} | null,\n'
                '    "valuation_est": {"value": "e.g. $20M post-money", "quote": "verbatim source sentence", "source_url": "that source URL"} | null,\n'
                '    "traction_metrics": {"value": "e.g. $2M ARR, 50 customers", "quote": "verbatim source sentence", "source_url": "that source URL"} | null,\n'
                '    "ip_status": {"value": "e.g. 2 patents granted", "quote": "verbatim source sentence", "source_url": "that source URL"} | null\n'
                '  },\n'
                '  "references": ["string", ...]\n'
                "}\n\n"
                "Include a founder_names array containing every explicitly named founder or co-founder in the retrieved evidence; use [] only when no names are supported. "
                "financials: fill a sub-field ONLY when a retrieved source explicitly states the exact figure — copy the figure into value, the source's exact sentence into quote, and that source's URL into source_url. "
                "If a figure is not present verbatim in your sources, use null. Never estimate, round, or infer funding, valuation, revenue, or IP numbers; unverifiable financials MUST be null. "
                "CRITICAL: references must contain verifiable sources proving this company exists. "
                "Prefer primary sources first: official company domain, official docs/blog, product pages, or company-owned GitHub/LinkedIn profile. "
                "Do not rely only on directory/paywalled sources (PitchBook/Crunchbase/Tracxn/CBInsights) if primary sources are available. "
                "Do NOT switch to similarly named companies (for example, different spelling variants). "
                "If the evidence appears to point to a different company identity than requested, return nothing. "
                "If confidence is low or data is incomplete, still return best-effort fields and set unknowns to null. "
                "Mine retrieved snippets for TAM/market sizing language, funding rounds and investors, customer or usage claims, and founder/executive names—reflect them in the narrative fields. "
                "Prefer est_tam as an order-of-magnitude when inferable from sources; put supported traction facts in problem/solution/why_now. "
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
            except Exception as e:
                self.logger.debug("Token usage accounting skipped: %s", e)
            content = response.choices[0].message.content
            if not content:
                self.logger.error("Empty response from LLM (company lookup)")
                self.last_discovery_diagnostic = {
                    "kind": "model_failure",
                    "reason": "empty_response",
                    "retrieval_outcome": source_pack.get("retrieval_outcome", "not_run"),
                }
                return None
            data = json.loads(content)
            if site:
                data["lookup_website"] = site
            # Reference finalization needs the resolver's explicit identity
            # context before it evaluates company relevance. Attach it before
            # the first normalization pass; the later attachment preserves the
            # same persisted contract after finalization.
            data = self._attach_resolution(data, resolution)
            finalized = self._finalize_scout_payload_from_llm(
                data,
                source_pack,
                grounded_enabled=grounded_enabled,
                enforce_citation_allowlist=enforce_citation_allowlist,
                explicit_website=site or None,
                context_note=f'company lookup: "{company}"',
                for_lookup=True,
            )
            if finalized is None:
                self.last_discovery_diagnostic = {
                    "kind": "validation_failure",
                    "retrieval_outcome": source_pack.get("retrieval_outcome", "not_run"),
                    "provider_diagnostics": source_pack.get("provider_diagnostics", []),
                }
                return None
            finalized = self._attach_resolution(finalized, resolution)
            if not self._matches_lookup_identity(
                str(finalized.get("name") or ""),
                expected_company=company,
                website_hint=site or None,
            ):
                # Analyst-style behavior: a possible identity drift is flagged for human
                # review, NOT silently dropped. The user asked for this company; show what
                # was found and why it is uncertain.
                self.logger.warning(
                    "company lookup identity mismatch (kept as NEEDS_REVIEW): expected=%s got=%s website_hint=%s",
                    company,
                    finalized.get("name"),
                    site or "",
                )
                finalized["resolution_status"] = "NEEDS_REVIEW"
                cr = finalized.get("company_resolution")
                note = (
                    f"Identity check: scout returned '{finalized.get('name')}' for lookup "
                    f"'{company}' — confirm this is the intended company."
                )
                if isinstance(cr, dict):
                    notes = list(cr.get("notes") or [])
                    notes.append(note)
                    cr["notes"] = notes
                else:
                    finalized["company_resolution"] = {
                        "query": company,
                        "canonical_name": str(finalized.get("name") or company),
                        "resolution_status": "NEEDS_REVIEW",
                        "confidence": float(finalized.get("confidence") or 0.0),
                        "notes": [note],
                    }
            return finalized
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from LLM (company lookup): {e}")
            self.last_discovery_diagnostic = {
                "kind": "model_failure",
                "reason": "invalid_json",
            }
            return None
        except Exception as e:
            self.logger.error(f"LLM company lookup failed: {e}")
            self.last_discovery_diagnostic = {
                "kind": "model_failure",
                "reason": "request_error",
            }
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

    async def discover_company(
        self,
        company_name: str,
        website: Optional[str] = None,
        resolution: Optional[CompanyResolution] = None,
        additional_context: Optional[str] = None,
    ) -> Optional[ScoutOutput]:
        """
        Discover and validate one specific company by name.
        `resolution` (Company Resolver outcome) seeds the evidence pack and is
        persisted on the resulting payload for UI transparency.
        """
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            self.executor,
            partial(
                self._call_llm_for_company_sync,
                company_name,
                website,
                resolution,
                additional_context,
            ),
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
