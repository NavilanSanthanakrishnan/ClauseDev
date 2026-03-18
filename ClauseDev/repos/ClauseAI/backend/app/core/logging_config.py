import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Dict, Set

from app.core.config import (
    LOG_LEVEL,
    LOG_MAX_FIELD_LENGTH,
    LOG_REDACT_BODY_KEYS,
    LOG_REDACT_HEADERS,
)

_REQUEST_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})
_BASE_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())
_REDACTION_VALUE = "[REDACTED]"

def _truncate(value: str) -> str:
    if len(value) <= LOG_MAX_FIELD_LENGTH:
        return value
    return f"{value[:LOG_MAX_FIELD_LENGTH]}...[truncated:{len(value) - LOG_MAX_FIELD_LENGTH}]"

def _serialize(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return "[max_depth_exceeded]"
    if isinstance(value, dict):
        return {str(key): _serialize(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item, depth + 1) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return _truncate(value)
        return value
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": str(value)}
    return _truncate(str(value))

def _redact_dict(payload: Dict[str, Any], redact_keys: Set[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        if key_text.lower() in redact_keys:
            result[key_text] = _REDACTION_VALUE
            continue
        if isinstance(value, dict):
            result[key_text] = _redact_dict(value, redact_keys)
            continue
        if isinstance(value, list):
            result[key_text] = [
                _redact_dict(item, redact_keys) if isinstance(item, dict) else _serialize(item)
                for item in value
            ]
            continue
        result[key_text] = _serialize(value)
    return result

def sanitize_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    return _redact_dict(headers, set(LOG_REDACT_HEADERS))

def sanitize_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return _redact_dict(payload, set(LOG_REDACT_BODY_KEYS))
    if isinstance(payload, list):
        return [_redact_dict(item, set(LOG_REDACT_BODY_KEYS)) if isinstance(item, dict) else _serialize(item) for item in payload]
    return _serialize(payload)

def set_request_context(**context: Any) -> Token:
    sanitized = {key: _serialize(value) for key, value in context.items() if value is not None}
    return _REQUEST_CONTEXT.set(sanitized)

def clear_request_context(token: Token) -> None:
    _REQUEST_CONTEXT.reset(token)

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        context = _REQUEST_CONTEXT.get()
        if context:
            payload.update(context)

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _BASE_RECORD_FIELDS and not key.startswith("_")
        }
        for key, value in extras.items():
            payload[key] = _serialize(value)

        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            payload["exception"] = {
                "type": exc_type,
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(payload, ensure_ascii=False)

def configure_logging() -> None:
    if getattr(configure_logging, "_configured", False):
        return

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    for noisy_logger in ("uvicorn.access", "watchfiles.main"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    configure_logging._configured = True