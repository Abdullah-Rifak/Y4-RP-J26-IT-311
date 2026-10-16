import unicodedata


def identify_script(token: str) -> str:
    """Identify the script used by a text token."""

    if not isinstance(token, str) or not token:
        return "EMPTY"

    scripts = set()

    for char in token:
        if not char.isalpha():
            continue

        character_name = unicodedata.name(char, "")

        if "TAMIL" in character_name:
            scripts.add("TAMIL")
        elif "LATIN" in character_name:
            scripts.add("LATIN")
        else:
            scripts.add("OTHER")

    if not scripts:
        return "NO_LETTERS"

    if len(scripts) > 1:
        return "MIXED"

    return scripts.pop()