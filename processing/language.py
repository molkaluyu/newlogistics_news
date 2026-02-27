import logging

from langdetect import detect
from langdetect.lang_detect_exception import LangDetectException

logger = logging.getLogger(__name__)

# Minimum text length to attempt language detection
MIN_TEXT_LENGTH = 20


def detect_language(text: str) -> str:
    """Detect the language of the given text.

    Uses langdetect to return an ISO 639-1 code (e.g., "en", "zh", "ja").
    Falls back to "en" if detection fails or text is too short.
    """
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        return "en"

    try:
        lang = detect(text)
        return lang
    except LangDetectException:
        logger.debug("Language detection failed, falling back to 'en'")
        return "en"
    except Exception as e:
        logger.warning(f"Unexpected error during language detection: {e}")
        return "en"
