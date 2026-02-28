import json
import logging
import sys
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "source_id"):
            log_data["source_id"] = record.source_id
        if hasattr(record, "article_id"):
            log_data["article_id"] = record.article_id
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_format: bool = False):
    """Configure application logging.

    Args:
        level: Log level string.
        json_format: If True, use JSON structured logging.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
