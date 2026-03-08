"""
app/utils/logging.py: Structured JSON logging for Super Tutor backend.

Usage:
  from app.utils.logging import configure_logging
  configure_logging()  # call once at startup

Environment:
  LOG_FORMAT=json   -> each log line is a JSON object
  LOG_FORMAT=text   -> human-readable text (default, same as previous basicConfig)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Standard LogRecord attribute names — skip when harvesting extra fields
# ---------------------------------------------------------------------------

STDLIB_LOG_KEYS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "taskName",
})


# ---------------------------------------------------------------------------
# JsonFormatter
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """
    Formats each LogRecord as a single-line JSON object.

    Standard fields:
      ts      — ISO 8601 UTC timestamp (e.g. "2024-01-15T10:30:00.123456Z")
      level   — log level name (INFO, WARNING, ERROR, ...)
      logger  — logger name
      msg     — formatted log message

    Extra fields from logger.info("...", extra={"session_id": "...", "step": "..."})
    are merged directly into the top-level JSON object.

    exc     — formatted exception traceback (only present when exc_info is set)
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            ) + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Harvest any extra fields the caller passed via extra={}
        for key, value in record.__dict__.items():
            if key not in STDLIB_LOG_KEYS:
                payload[key] = value

        # Attach exception info if present
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------

def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure root logging based on the LOG_FORMAT environment variable.

    LOG_FORMAT=json  -> JsonFormatter (machine-parseable, one JSON object per line)
    LOG_FORMAT=text  -> human-readable text (default; same format as previous basicConfig)

    Also silences noisy third-party loggers to WARNING.
    """
    log_format = os.environ.get("LOG_FORMAT", "text").lower().strip()

    handler = logging.StreamHandler(sys.stdout)

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s \u2014 %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    logging.basicConfig(level=level, handlers=[handler], force=True)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
