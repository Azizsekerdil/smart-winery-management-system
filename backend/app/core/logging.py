"""Yapilandirilmis kayit (logging) ve gizli deger maskeleme.

`scrub()` fonksiyonu API anahtari benzeri tum degerleri metin icinden temizler.
Hem log kayitlarinda hem de AI saglayici hata mesajlarinda kullanilir.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings

MASK = "***GIZLI***"

# Bilinen anahtar bicimleri + genel "uzun rastgele dizge" kaliplari.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),          # Anthropic
    re.compile(r"nvapi-[A-Za-z0-9_\-]{10,}"),           # NVIDIA Build
    re.compile(r"sk-[A-Za-z0-9]{20,}"),                 # OpenAI uyumlu
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),          # GitHub
    re.compile(r"swm_[A-Za-z0-9_\-]{20,}"),             # kendi belirtecimiz
    re.compile(r"\bey[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"),  # JWT
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                # AWS
)

# `anahtar = deger` bicimindeki hassas alanlar
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|apikey|secret|password|passwd|parola|token|authorization|"
    r"bearer|access[_-]?key|private[_-]?key|encryption[_-]?key|"
    r"anthropic_api_key|nvidia_api_key|openai_api_key|secret_key"
    r")\b\s*[:=]\s*[\"']?([^\s\"',;]{4,})"
)

# Sozluklerde tamamen maskelenecek alan adlari
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "password",
        "parola",
        "new_password",
        "old_password",
        "password_hash",
        "api_key",
        "apikey",
        "api_key_encrypted",
        "secret",
        "secret_key",
        "secrets_encryption_key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "anthropic_api_key",
        "nvidia_api_key",
        "openai_compat_api_key",
        "private_key",
    }
)


def scrub(value: Any, *, _depth: int = 0) -> Any:
    """Metin/sozluk/liste icindeki gizli degerleri maskeler.

    Ic ice yapilarda 6 seviyeye kadar iner; daha derini oldugu gibi birakilir
    (log yazarken sonsuz dongu riskini engeller).
    """
    if _depth > 6:
        return value

    if isinstance(value, str):
        out = value
        for pat in _SECRET_PATTERNS:
            out = pat.sub(MASK, out)
        out = _SENSITIVE_KEY_RE.sub(lambda m: f"{m.group(1)}={MASK}", out)
        return out

    if isinstance(value, dict):
        return {
            k: (
                MASK
                if isinstance(k, str) and k.lower() in SENSITIVE_FIELD_NAMES
                else scrub(v, _depth=_depth + 1)
            )
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        cleaned = [scrub(v, _depth=_depth + 1) for v in value]
        return type(value)(cleaned) if not isinstance(value, set) else set(cleaned)

    return value


class ScrubbingFilter(logging.Filter):
    """Standart logging kayitlarini structlog disinda da temizler."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = scrub(record.msg)
            if record.args:
                record.args = scrub(record.args)  # type: ignore[assignment]
        except Exception:  # noqa: S110 - pragma: no cover
            # Loglama HICBIR kosulda is akisini kesmemelidir; maskeleme
            # basarisiz olsa bile kayit yazilmaya devam eder.
            pass
        return True


def _structlog_scrubber(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """structlog islemci zinciri: her kayit yazilmadan once maskelenir."""
    return scrub(dict(event_dict))


_configured = False


def configure_logging() -> None:
    """Uygulama genelinde loglamayi kurar (idempotent)."""
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handlers: list[logging.Handler] = []

    stream = logging.StreamHandler(sys.stdout)
    stream.addFilter(ScrubbingFilter())
    handlers.append(stream)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.addFilter(ScrubbingFilter())
    handlers.append(file_handler)

    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=handlers,
        force=True,
    )

    # Gurultulu kutuphaneler
    for noisy in ("httpx", "httpcore", "multipart", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    renderer: Any = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if settings.LOG_JSON
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _structlog_scrubber,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str = "saraphane") -> Any:
    configure_logging()
    return structlog.get_logger(name)
