"""
Shared validation helpers for Scout outputs.
Avoids circular imports between storage and scout.
"""

# Placeholder that does NOT prove a company exists; reject discoveries using only this
_GENERIC_REF_PATTERNS = (
    "general domain knowledge",
    "no specific external sources",
    "no specific sources",
)

_MEGACAP_KEYWORDS = (
    "google",
    "alphabet",
    "microsoft",
    "azure",
    "amazon",
    "aws",
    "apple",
    "meta",
    "facebook",
    "ibm",
    "oracle",
    "salesforce",
    "sap",
    "nvidia",
    "tesla",
)


def is_generic_reference(s: str) -> bool:
    """True if reference is the generic placeholder, not a real source (URL, news, etc.)."""
    if not s or not isinstance(s, str):
        return True
    lower = s.strip().lower()
    return any(p in lower for p in _GENERIC_REF_PATTERNS)


def is_megacap_company(name: str) -> bool:
    """
    Heuristic: True if the company name looks like a large public/mega-cap incumbent
    (FAANG / hyperscalers etc.), which we do not consider as VC discovery targets.
    """
    if not isinstance(name, str):
        return False
    lower = name.strip().lower()
    return any(k in lower for k in _MEGACAP_KEYWORDS)
