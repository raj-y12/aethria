"""Bounded extraction of source-grounded commercial and economic facts.

This module records measurable or explicitly described economics only. It does
not decide whether a business model is attractive, scalable, or defensible.
"""
from __future__ import annotations

import re
from typing import Any


_MONEY = r"(?:[$€£]\s?\d[\d,.]*\s?(?:k|m|mm|b|bn|million|billion)?|\d[\d,.]*\s?(?:k|m|mm|b|bn|million|billion)\s?(?:euros?|dollars?|pounds?)?)"
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
_PAYER = re.compile(r"(?i)\b(?:charges?|billed to|paid by|pays?)\s+(?:its\s+)?([^.;,]+)")
_MODEL = re.compile(
    r"(?i)\b(subscription|SaaS|transaction fee|take[- ]?rate|marketplace|licen[cs]ing|usage[- ]based|per[- ]use|commission)\b"
)
_PRICING = re.compile(rf"(?i)(?:{_MONEY}\s*(?:per|/)\s*[^,.;]+|\d+(?:\.\d+)?%\s*(?:transaction fee|take[- ]?rate|commission))")
_MEASURE = re.compile(
    rf"(?i)(?P<value>{_MONEY}|\d+(?:\.\d+)?%)\s*(?P<metric>ARR|MRR|annual recurring revenue|monthly recurring revenue|revenue|sales|GMV|gross merchandise value|bookings|gross margin|contribution margin|CAC|LTV|payback|net revenue retention|gross revenue retention|churn|customers?)\b"
)
_CONCENTRATION = re.compile(r"(?i)\b(?:top|largest)\s+(?:customer|client)\s+(?:represents?|accounts? for)\s+(?P<percentage>\d+(?:\.\d+)?%)\s+of\s+(?P<basis>revenue|sales|bookings)")
_RETENTION = re.compile(r"(?i)\b(?P<metric>net revenue retention|gross revenue retention|retention|churn)\s*(?:rate|was|is|of)?\s*(?P<value>\d+(?:\.\d+)?%|\d+(?:\.\d+)?\s*(?:months?|years?))")
_REVERSE_MEASURE = re.compile(
    rf"(?i)\b(?P<metric>ARR|MRR|annual recurring revenue|monthly recurring revenue|revenue|sales|GMV|gross merchandise value|bookings|gross margin|contribution margin|CAC|LTV|payback|customers?)\s*(?:was|is|of|at|:|=)\s*(?P<value>{_MONEY}|\d+(?:\.\d+)?%)"
)


def _source_text(source: Any) -> str:
    if not isinstance(source, dict):
        return ""
    return " ".join(
        str(source.get(key) or "").strip()
        for key in ("snippet", "content", "excerpt", "quote", "supports")
        if str(source.get(key) or "").strip()
    )[:4000]


def _period(sentence: str) -> str | None:
    match = re.search(r"\b(?:for|in|during|as of)\s+(20\d{2}|Q[1-4]\s*20\d{2})\b", sentence, re.I)
    return match.group(1) if match else None


def _base(*, claim_type: str, value: dict[str, Any], sentence: str, index: int) -> dict[str, Any]:
    return {
        "claim_type": claim_type,
        "normalized_value": value,
        "display_text": sentence[:700],
        "assertion_class": "externally_verified",
        "confidence": 0.8,
        "support_strength": 0.8,
        "material": True,
        "_supporting_indexes": [index],
    }


def derive_commercial_claims(scout_output: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only explicit commercial/economic facts found in source evidence."""
    claims: list[dict[str, Any]] = []
    sources = [item for item in (scout_output.get("source_evidence") or []) if isinstance(item, dict)]
    for index, source in enumerate(sources):
        for sentence_match in _SENTENCE.finditer(_source_text(source)):
            sentence = re.sub(r"\s+", " ", sentence_match.group(0).strip())
            if not sentence:
                continue
            period = _period(sentence)
            payer = _PAYER.search(sentence)
            if payer:
                payer_text = re.split(r"\s+(?:a|an)\s+\d", payer.group(1), maxsplit=1, flags=re.I)[0].strip(" .")
                if payer_text and len(payer_text) <= 100:
                    claims.append(_base(claim_type="payer_type", value={"payer": payer_text, **({"period": period} if period else {})}, sentence=sentence, index=index))
            model = _MODEL.search(sentence)
            if model:
                normalized = model.group(1).casefold().replace("-", " ")
                model_name = {
                    "saas": "subscription", "subscription": "subscription", "transaction fee": "transaction_fee",
                    "take rate": "take_rate", "marketplace": "marketplace", "licensing": "licensing",
                    "license": "licensing", "usage based": "usage_based", "per use": "usage_based",
                    "commission": "commission",
                }.get(normalized, normalized.replace(" ", "_"))
                claims.append(_base(claim_type="revenue_model", value={"model": model_name, **({"period": period} if period else {})}, sentence=sentence, index=index))
            pricing = _PRICING.search(sentence)
            if pricing:
                claims.append(_base(claim_type="pricing", value={"value": pricing.group(0).strip(), **({"period": period} if period else {})}, sentence=sentence, index=index))
            for measurement in _MEASURE.finditer(sentence):
                metric = measurement.group("metric").casefold()
                metric = {
                    "annual recurring revenue": "arr", "monthly recurring revenue": "mrr",
                    "gmv": "gmv", "gross merchandise value": "gmv", "bookings": "bookings",
                    "sales": "revenue", "gross margin": "gross_margin", "contribution margin": "contribution_margin",
                    "cac": "cac", "ltv": "ltv", "payback": "payback_period", "customers": "customer_count",
                }.get(metric, metric)
                claim_type = "revenue_amount" if metric in {"arr", "mrr", "revenue", "gmv", "bookings"} else (
                    metric if metric in {"gross_margin", "contribution_margin"} else (
                        "unit_economics" if metric in {"cac", "ltv", "payback_period"} else "customer_count"
                    )
                )
                value = {"metric": metric, "value": measurement.group("value")}
                if period:
                    value["period"] = period
                claims.append(_base(claim_type=claim_type, value=value, sentence=sentence, index=index))
            for measurement in _REVERSE_MEASURE.finditer(sentence):
                metric = measurement.group("metric").casefold()
                metric = {
                    "annual recurring revenue": "arr", "monthly recurring revenue": "mrr", "gmv": "gmv",
                    "gross merchandise value": "gmv", "sales": "revenue", "gross margin": "gross_margin",
                    "contribution margin": "contribution_margin", "cac": "cac", "ltv": "ltv",
                    "payback": "payback_period", "customers": "customer_count",
                }.get(metric, metric)
                claim_type = "revenue_amount" if metric in {"arr", "mrr", "revenue", "gmv", "bookings"} else (
                    metric if metric in {"gross_margin", "contribution_margin"} else (
                        "unit_economics" if metric in {"cac", "ltv", "payback_period"} else "customer_count"
                    )
                )
                value = {"metric": metric, "value": measurement.group("value")}
                if period:
                    value["period"] = period
                claims.append(_base(claim_type=claim_type, value=value, sentence=sentence, index=index))
            concentration = _CONCENTRATION.search(sentence)
            if concentration:
                value = {"percentage": concentration.group("percentage"), "basis": concentration.group("basis").casefold()}
                if period:
                    value["period"] = period
                claims.append(_base(claim_type="customer_concentration", value=value, sentence=sentence, index=index))
            retention = _RETENTION.search(sentence)
            if retention:
                value = {"metric": retention.group("metric").casefold().replace(" ", "_"), "value": retention.group("value")}
                if period:
                    value["period"] = period
                claims.append(_base(claim_type="retention_churn", value=value, sentence=sentence, index=index))
    return claims
