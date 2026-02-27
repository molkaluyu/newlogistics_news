import html
import re
import unicodedata


def clean_text(text: str | None) -> str | None:
    """Clean and normalize text content."""
    if not text:
        return None

    # Strip residual HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    text = html.unescape(text)

    # Unicode normalize (NFKC - compatibility decomposition + canonical composition)
    text = unicodedata.normalize("NFKC", text)

    # Normalize whitespace: collapse multiple spaces/newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text if text else None


def clean_title(title: str | None) -> str | None:
    """Clean article title."""
    if not title:
        return None

    title = clean_text(title)
    if not title:
        return None

    # Remove common title suffixes from source names
    # e.g., " - The Loadstar", " | FreightWaves"
    title = re.sub(r"\s*[\-\|]\s*[A-Z][\w\s]+$", "", title)

    return title.strip() if title.strip() else None
