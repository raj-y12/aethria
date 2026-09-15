"""A concise evidence view; immutable source records remain unchanged for audit."""
from copy import deepcopy
import json
import re

from utils.source_corroboration import source_mentions_company, host_of, is_anchor_host
from resolver.founder_resolver import is_non_person_label


_MONEY_RE = re.compile(
    r"(?P<value>\$?\s*(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)\s*"
    r"(?:hundred|thousand|million|billion|m|k|bn)?(?:\s*[-–]\s*\$?\s*\d+(?:\.\d+)?\s*"
    r"(?:million|billion|m|k|bn)?)?)",
    re.IGNORECASE,
)
_FINANCIAL_METRICS = ("arr", "revenue", "funding", "raised", "valuation", "sales")
_ATTRIBUTION_CUES = ("estimate", "estimated", "forecast", "forecasts", "projected", "projection", "third-party", "analyst")


def _money_value(raw: str) -> tuple[float, str | None, str | None] | None:
    compact = re.sub(r"\s+", "", raw).casefold()
    number = re.search(r"\d+(?:\.\d+)?", compact)
    if not number:
        return None
    value = float(number.group())
    unit = ""
    if "billion" in compact or compact.endswith("bn"):
        unit, value = "billion", value * 1000
    elif "million" in compact or compact.endswith("m"):
        unit = "million"
    elif "thousand" in compact or compact.endswith("k"):
        unit, value = "thousand", value / 1000
    currency = "$" if "$" in compact else None
    return value, unit, currency


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _financial_metric(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - 48):min(len(text), end + 48)].casefold()
    for metric in _FINANCIAL_METRICS:
        if metric in window:
            return "revenue" if metric == "sales" else metric
    return None


def financial_assertions_supported(text: str, claims: list[dict]) -> bool:
    """Return whether material money claims preserve metric and value meaning.

    This is deliberately a narrow deterministic guard, not a general entailment
    checker. It prevents a citation about funding or revenue from laundering a
    different financial metric into Reviewer prose.
    """
    assertions: list[tuple[str, re.Match[str], str]] = []
    for sentence in _sentences(text):
        for match in _MONEY_RE.finditer(sentence):
            metric = _financial_metric(sentence, match.start(), match.end())
            parsed = _money_value(match.group(0))
            if metric and parsed and (parsed[1] or parsed[2]):
                assertions.append((sentence, match, metric))
    for phrase in re.finditer(r"\b(?:multi[- ]?hundred[- ]?(?:million|billion)|hundreds of\s+(?:million|billion)|tens of\s+(?:million|billion))\b", text, re.IGNORECASE):
        metric = _financial_metric(text, phrase.start(), phrase.end())
        if metric:
            assertions.append((text, phrase, metric))
    if not assertions:
        return True
    claim_sentences = []
    for claim in claims:
        raw = str(claim.get("display_text") or "") + " " + " ".join(
            str(link.get("display_excerpt") or "") for link in claim.get("evidence_relationships") or []
        )
        claim_sentences.extend(_sentences(raw))
    for assertion, match, metric in assertions:
        assertion_value = _money_value(match.group(0))
        assertion_attributed = any(cue in assertion.casefold() for cue in _ATTRIBUTION_CUES)
        supported = False
        for candidate in claim_sentences:
            candidate_match = None
            for possible in _MONEY_RE.finditer(candidate):
                parsed = _money_value(possible.group(0))
                if (_financial_metric(candidate, possible.start(), possible.end()) == metric
                        and parsed and (parsed[1] or parsed[2])):
                    candidate_match = possible
                    break
            if candidate_match is None:
                continue
            candidate_value = _money_value(candidate_match.group(0)) if candidate_match else None
            if not assertion_value or not candidate_value:
                continue
            if assertion_value[2] and candidate_value[2] and assertion_value[2] != candidate_value[2]:
                continue
            if abs(assertion_value[0] - candidate_value[0]) > max(0.5, candidate_value[0] * 0.015):
                continue
            if any(cue in candidate.casefold() for cue in _ATTRIBUTION_CUES) and not assertion_attributed:
                continue
            years = set(re.findall(r"\b20\d{2}\b", assertion))
            if years and not years.intersection(re.findall(r"\b20\d{2}\b", candidate)):
                continue
            supported = True
            break
        if not supported:
            return False
    return True


def ground_financial_text(text: str, claims: list[dict]) -> str:
    if financial_assertions_supported(text, claims):
        return text
    return text if text.casefold().startswith(("unknown", "unverified", "assumption", "projection")) else "Unverified: " + text


def grounding_company_name(canonical_name: str, website: str | None, observed_name: str | None) -> str:
    """Retain a more specific factual label only when it matches the exact domain brand."""
    compact = lambda value: re.sub(r"[^a-z0-9]", "", str(value or "").lower())
    host = host_of(website if "://" in str(website) else "https://" + str(website or ""))
    slug = host.removeprefix("www.").split(".")[0]
    if (observed_name and compact(observed_name) == compact(slug)
            and compact(observed_name).startswith(compact(canonical_name))):
        return observed_name
    return canonical_name


def relevant_source(source: dict, *, company_name: str, company_website: str | None) -> bool:
    anchor = host_of(company_website if not company_website or "://" in company_website else "https://" + company_website)
    return bool(anchor and is_anchor_host(host_of(source.get("url")), anchor)) or source_mentions_company(
        source, company_name=company_name, anchor_host=anchor)


def reviewer_evidence(snapshot: list[dict], *, company_name: str, company_website: str | None):
    packet, selected, aliases, seen = [], [], {}, set()
    for original in snapshot:
        row = deepcopy(original)
        if str(row.get("claim_type", "")).startswith("founder_") and is_non_person_label(
            str((row.get("normalized_value") or {}).get("name") or "")
        ):
            continue
        links = row.get("evidence_relationships") or []
        retained = [link for link in links if not link.get("prompt_injection_detected") and (
            not link.get("source_uri") or relevant_source(
                {"url": link.get("source_uri"), "snippet": link.get("display_excerpt") or row.get("display_text")},
                company_name=company_name, company_website=company_website))]
        if links and not retained:
            continue
        # Historical person projections can contain role labels or unrelated
        # profiles. They are not factual identity evidence without verification.
        if str(row.get("claim_type", "")).startswith("founder_") and not any(
            link.get("verification_state") == "verified" and float(link.get("source_quality") or 0) > 0
            for link in retained
        ):
            continue
        key = json.dumps([row.get("claim_type"), row.get("normalized_value"), row.get("display_text"),
                          sorted(str(link.get("evidence_item_id")) for link in retained)], sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        row["evidence_relationships"] = retained
        allowed = {link.get("evidence_item_id") for link in retained}
        for field in ("supporting_evidence_ids", "contradicting_evidence_ids"):
            if links:
                row[field] = [key for key in row.get(field, []) if key in allowed]
        handle = f"C{len(packet) + 1}"
        aliases[handle] = str(row["claim_id"])
        selected.append(row)
        packet.append({
            "claim_id": handle, "claim_type": row.get("claim_type"),
            "statement": row.get("display_text"),
            "assertion_class": row.get("assertion_class_at_snapshot"),
            "status": row.get("status_at_snapshot"),
            "sources": [{"url": link.get("source_uri"), "excerpt": link.get("display_excerpt"),
                         "verification": link.get("verification_state"), "quality": link.get("source_quality"),
                         "relationship": link.get("relationship"),
                         "effective_at": link.get("evidence_effective_at") or link.get("artifact_effective_at"),
                         "retrieved_at": link.get("retrieved_at")} for link in retained],
        })
    return packet, selected, aliases
