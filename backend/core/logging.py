"""Structured logging helpers for RAID Nexus."""

from __future__ import annotations

import logging
import re

PII_PATTERN = re.compile(
    r"(?i)\b(name|phone|mobile|address)\b\s*[:=]\s*['\"]?[^,'\"\}\]\s]+"
)


def _redact_message(value: object) -> object:
    if not isinstance(value, str):
        return value
    return PII_PATTERN.sub(lambda match: f"{match.group(1)}=<redacted>", value)


class RedactingFilter(logging.Filter):
    """Best-effort guard against patient PII leaking through application logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact_message(record.msg)
        if isinstance(record.args, dict):
            record.args = {key: _redact_message(value) for key, value in record.args.items()}
        elif isinstance(record.args, tuple):
            record.args = tuple(_redact_message(value) for value in record.args)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Configure consistent application logging."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    redactor = RedactingFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(redactor)
    for handler in root_logger.handlers:
        handler.addFilter(redactor)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger."""

    return logging.getLogger(name)
