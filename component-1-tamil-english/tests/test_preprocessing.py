from src.preprocessing import clean_comment


def test_removes_url():
    result = clean_comment("Vanakkam https://example.com friends")
    assert result == "Vanakkam friends"


def test_removes_html_tags():
    result = clean_comment("<b>Vanakkam</b> nanba")
    assert result == "Vanakkam nanba"


def test_normalizes_whitespace():
    result = clean_comment("Vanakkam    nanba")
    assert result == "Vanakkam nanba"


def test_preserves_tamil_and_english():
    comment = "நீ நல்ல friend"
    assert clean_comment(comment) == comment


def test_handles_empty_input():
    assert clean_comment("") == ""

