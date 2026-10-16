from src.script_identification.script_identifier import identify_script


def test_identifies_tamil_script():
    assert identify_script("நல்ல") == "TAMIL"


def test_identifies_latin_script():
    assert identify_script("friend") == "LATIN"


def test_identifies_mixed_scripts():
    assert identify_script("நல்லfriend") == "MIXED"


def test_ignores_numbers_and_punctuation():
    assert identify_script("123!") == "NO_LETTERS"


def test_handles_empty_string():
    assert identify_script("") == "EMPTY"


def test_identifies_romanised_tamil_as_latin_script():
    assert identify_script("nee") == "LATIN"


def test_identifies_tamil_with_punctuation():
    assert identify_script("நல்ல!") == "TAMIL"


def test_identifies_latin_with_numbers():
    assert identify_script("friend123") == "LATIN"


def test_identifies_emoji_only_token():
    assert identify_script("😂🔥") == "NO_LETTERS"


def test_identifies_other_script():
    assert identify_script("හොඳ") == "OTHER"