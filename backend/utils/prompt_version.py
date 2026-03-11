"""Prompt versioning utility. SHA-256 hash of prompt string for traceability."""
import hashlib

def hash_prompt(prompt_str: str) -> str:
    """Return first 8 chars of SHA-256 of prompt string."""
    return hashlib.sha256(prompt_str.encode("utf-8")).hexdigest()[:8]
