from src.preprocessing import clean_comment, tokenize_comment


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
    comment = "à®¨à¯€ à®¨à®²à¯à®² friend"
    assert clean_comment(comment) == comment


def test_handles_empty_input():
    assert clean_comment("") == ""


def test_removes_www_url():
    assert clean_comment("Visit www.google.com now") == "Visit now"


def test_preserves_expressive_www_words():
    comment = "Yowww.. Dawww... wowwwww nice"
    assert clean_comment(comment) == comment


def test_tokenizes_romanized_tamil():
    assert tokenize_comment("avan romba nalla paiyan") == [
        "avan", "romba", "nalla", "paiyan"
    ]


def test_tokenizes_tamil_script():
    assert tokenize_comment("அவன் நல்லவன்") == ["அவன்", "நல்லவன்"]


def test_tokenizes_mixed_tamil_english_and_emoji():
    assert tokenize_comment("அவன் romba நல்லவன் 😂") == [
        "அவன்", "romba", "நல்லவன்", "😂"
    ]


def test_preserves_punctuation_as_separate_tokens():
    assert tokenize_comment("hello!") == ["hello", "!"]


def test_tokenize_empty_or_whitespace_input():
    assert tokenize_comment("") == []
    assert tokenize_comment("   ") == []

