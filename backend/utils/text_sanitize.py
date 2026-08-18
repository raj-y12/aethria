"""Strip raw markdown scrape artifacts (e.g. a logo carousel's alt text)
that occasionally survive verbatim into LLM free-text output --
"Trusted by teams at ![OpenAI](https://.../openai.png)" instead of prose.
Shared by Scout and Partner: both parse LLM narrative output from the same
scraped-page context and are equally exposed to this artifact.
"""
import re

# Images first so the leading "!" is consumed as part of that match, not
# left dangling for the link pattern to re-match.
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# A field truncated (by a token/length limit upstream) mid-link never gets
# its closing ")" -- e.g. "...teams at ![OpenAI](https://...&q". The two
# patterns above require a closing paren and can't touch this; drop the
# dangling fragment outright rather than leave a raw URL tail.
_DANGLING_MARKDOWN_RE = re.compile(r"!?\[[^\]]*\]\([^)]*$")


def strip_markdown_links(text: str) -> str:
    # Trailing space so adjacent tags with no source whitespace between them
    # ("...)![Figma](...") don't collapse into "OpenAIFigma" -- the final
    # whitespace-collapse below normalizes any doubling.
    text = _MARKDOWN_IMAGE_RE.sub(lambda m: m.group(1) + " ", text)
    text = _MARKDOWN_LINK_RE.sub(lambda m: m.group(1) + " ", text)
    text = _DANGLING_MARKDOWN_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()
