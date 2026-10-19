import re


def clean_comment(text: str) -> str:
    """Clean a Tamil-English code-mixed social media comment."""

    if not isinstance(text, str):
        return ""

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove URLs
    text = re.sub(
        r"https?://\S+|(?<!\w)www\.\S+",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Normalize repeated whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text

def tokenize_comment(text: str) -> list[str]:
    """Tokenize Tamil-English text while preserving Unicode combining marks."""

    import unicodedata

    if not isinstance(text, str) or not text.strip():
        return []

    tokens = []
    current_token = ""

    for char in text:
        category = unicodedata.category(char)

        # Letters and numbers start or continue a token.
        if char.isalnum():
            current_token += char

        # Combining marks remain attached to the previous character.
        elif category.startswith("M") and current_token:
            current_token += char

        else:
            if current_token:
                tokens.append(current_token)
                current_token = ""

            # Preserve emojis and punctuation, but ignore whitespace.
            if not char.isspace():
                tokens.append(char)

    if current_token:
        tokens.append(current_token)

    return tokens


