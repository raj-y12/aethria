from api import _parse_lookup_input


def test_parse_lookup_input_strips_common_command_prefix():
    parsed = _parse_lookup_input("find Perplexity AI")

    assert parsed["company_name"] == "Perplexity AI"
    assert parsed["lookup_query"] == "find Perplexity AI"
    assert parsed["lookup_input_type"] == "company_name"


def test_parse_lookup_input_strips_generic_trailing_qualifier():
    parsed = _parse_lookup_input("Perplexity AI company")

    assert parsed["company_name"] == "Perplexity AI"
    assert parsed["lookup_query"] == "Perplexity AI company"


def test_parse_lookup_input_keeps_the_browser_company_brand():
    parsed = _parse_lookup_input("The Browser Company")

    assert parsed["company_name"] == "The Browser Company"


def test_parse_lookup_input_keeps_embedded_website_disambiguation():
    parsed = _parse_lookup_input("Aethria aethria.ai")

    assert parsed["company_name"] == "Aethria"
    assert parsed["website"] == "aethria.ai"
    assert parsed["lookup_input_type"] == "company_name"


def test_parse_lookup_input_normalizes_command_prefix_before_embedded_website():
    parsed = _parse_lookup_input("look up Aethria https://aethria.co")

    assert parsed["company_name"] == "Aethria"
    assert parsed["website"] == "aethria.co"
    assert parsed["lookup_input_type"] == "company_name"


def test_parse_lookup_input_command_plus_only_website_uses_domain_label():
    parsed = _parse_lookup_input("find https://aethria.co")

    assert parsed["company_name"] == "Aethria"
    assert parsed["website"] == "aethria.co"
    assert parsed["lookup_input_type"] == "website"
