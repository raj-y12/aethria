from pipeline_runner import DEFAULT_REVIEWER_MODEL, DEFAULT_SCOUT_MODEL


def test_pipeline_runner_defaults_to_gpt5_nano():
    assert DEFAULT_SCOUT_MODEL == "gpt-5-nano"
    assert DEFAULT_REVIEWER_MODEL == "gpt-5-nano"
