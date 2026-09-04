"""구조화 로깅 + 시크릿 마스킹.

★ 의존성 없음
   structlog 이 설치되어 있으면 그것을 쓰고, 없으면 표준 logging 으로
   같은 인터페이스를 제공합니다.

★ 시크릿 마스킹
   API 키가 실수로 로그에 들어가도 출력에는 *** 로만 남습니다.
   이건 선택 사항이 아닙니다 (§53).
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

# ------------------------------------------------------------------ 마스킹

_SK_RE = re.compile(r"(sk-[A-Za-z0-9_\-]{6,})")
_BEARER_RE = re.compile(r"(Bearer\s+[A-Za-z0-9._\-]{6,})", re.IGNORECASE)
_KV_RE = re.compile(
    r"((?:api[_-]?key|apikey|token|secret|password|passwd)\s*[=:]\s*)"
    r"([^\s,'\"]{3,})",
    re.IGNORECASE,
)

_SECRET_KEYS = {
    "api_key", "apikey", "anthropic_api_key", "openai_api_key", "google_api_key",
    "token", "secret", "password", "passwd", "authorization",
    "postgres_password", "database_url", "redis_url",
}


def mask_text(text: str) -> str:
    out = _SK_RE.sub("***", text)
    out = _BEARER_RE.sub("Bearer ***", out)
    out = _KV_RE.sub(r"\1***", out)
    return out


def mask_event(event_dict: dict) -> dict:
    for key, value in list(event_dict.items()):
        if key.lower() in _SECRET_KEYS:
            event_dict[key] = "***"
        elif isinstance(value, str):
            event_dict[key] = mask_text(value)
    return event_dict


def _structlog_processor(_logger: Any, _method: str, event_dict: dict) -> dict:
    return mask_event(event_dict)


# ------------------------------------------------------------------ 폴백 로거


class _FallbackLogger:
    """structlog 이 없을 때 쓰는 최소 구현. 인터페이스는 동일합니다."""

    def __init__(self, name: str, level: int):
        self._log = logging.getLogger(name)
        self._log.setLevel(level)

    @staticmethod
    def _render(event: str, kwargs: dict) -> str:
        masked = mask_event(dict(kwargs))
        masked_event = mask_text(str(event))
        if not masked:
            return masked_event
        pairs = " ".join(f"{k}={v}" for k, v in masked.items())
        return f"{masked_event} {pairs}"

    def debug(self, event: str, **kw): self._log.debug(self._render(event, kw))
    def info(self, event: str, **kw): self._log.info(self._render(event, kw))
    def warning(self, event: str, **kw): self._log.warning(self._render(event, kw))
    def warn(self, event: str, **kw): self.warning(event, **kw)
    def error(self, event: str, **kw): self._log.error(self._render(event, kw))
    def exception(self, event: str, **kw): self._log.exception(self._render(event, kw))
    def critical(self, event: str, **kw): self._log.critical(self._render(event, kw))


_configured = False
_using_structlog = False


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    global _configured, _using_structlog
    if _configured:
        return

    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s",
                        stream=sys.stdout, level=lvl)

    try:
        import structlog

        renderer = (
            structlog.processors.JSONRenderer()
            if json_output
            else structlog.dev.ConsoleRenderer(colors=False)
        )
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                _structlog_processor,          # ★ 렌더러 앞에 있어야 함
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(lvl),
            cache_logger_on_first_use=True,
        )
        _using_structlog = True
    except ImportError:
        _using_structlog = False

    _configured = True


def get_logger(name: str = "airo"):
    configure_logging()
    if _using_structlog:
        import structlog

        return structlog.get_logger(name)
    return _FallbackLogger(name, logging.getLogger().level)


def logging_backend() -> str:
    configure_logging()
    return "structlog" if _using_structlog else "stdlib"
