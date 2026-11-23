"""Console + rotating JSON-lines logging with secret scrubbing."""
from __future__ import annotations

import json
import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import SECRET_KEYS

_configured = False


class SecretScrubber(logging.Filter):
    """Replaces any secret value from the environment that leaks into a log line."""

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = [os.environ[k] for k in SECRET_KEYS if os.environ.get(k)]
        if secrets:
            msg = record.getMessage()
            for s in secrets:
                if len(s) >= 6:
                    msg = msg.replace(s, "***REDACTED***")
            msg = re.sub(r"(xi-api-key|Authorization)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+", r"\1\2***", msg)
            record.msg, record.args = msg, None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging(log_dir: Path, level: str = "INFO", json_file: bool = True) -> None:
    global _configured
    root = logging.getLogger()
    if _configured:
        root.setLevel(level)
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    root.setLevel(os.environ.get("FINSTUDIO_LOG_LEVEL", level))
    scrub = SecretScrubber()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
    console.addFilter(scrub)
    root.addHandler(console)

    if json_file:
        fh = RotatingFileHandler(log_dir / "studio.jsonl", maxBytes=5_000_000, backupCount=5)
        fh.setFormatter(JsonFormatter())
        fh.addFilter(scrub)
        root.addHandler(fh)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"finstudio.{name}")
