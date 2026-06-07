from types import SimpleNamespace

from pipeline_runner import DEFAULT_REVIEWER_MODEL, DEFAULT_SCOUT_MODEL
from reviewer.base import _chat_completion_content


def test_pipeline_runner_defaults_to_gpt5_nano():
    assert DEFAULT_SCOUT_MODEL == "gpt-5-nano"
    assert DEFAULT_REVIEWER_MODEL == "gpt-5-nano"


def test_reviewer_empty_content_reports_finish_reason_and_usage():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="length",
                message=SimpleNamespace(content=""),
            )
        ],
        usage=SimpleNamespace(
            total_tokens=9211,
            completion_tokens=8192,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=8192),
        ),
    )

    content, diagnostic = _chat_completion_content(response)

    assert content is None
    assert diagnostic["finish_reason"] == "length"
    assert diagnostic["total_tokens"] == 9211
    assert diagnostic["completion_tokens"] == 8192
    assert diagnostic["reasoning_tokens"] == 8192
