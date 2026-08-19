"""AIProvider soyutlamasi - tum saglayicilarin uydugu ortak sozlesme."""

from __future__ import annotations

import abc
import datetime as dt
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger, scrub

log = get_logger("ai.provider")


class ProviderError(Exception):
    """Saglayici hatasi. Mesaj HER ZAMAN maskelenmis olarak saklanir."""

    def __init__(self, message: str, *, kind: str = "hata", status_code: int | None = None):
        super().__init__(scrub(message))
        self.kind = kind
        self.status_code = status_code

    @property
    def safe_message(self) -> str:
        return str(self)


class ProviderUnavailable(ProviderError):
    """Saglayiciya ulasilamiyor (kapali, ag hatasi)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, kind="ulasilamiyor", status_code=status_code)


class ProviderAuthError(ProviderError):
    """Anahtar yok / gecersiz."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, kind="yetkilendirme", status_code=status_code)


class ProviderTimeout(ProviderError):
    def __init__(self, message: str):
        super().__init__(message, kind="zaman_asimi")


@dataclass(slots=True)
class ChatMessage:
    role: str  # system | user | assistant
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class ModelDescriptor:
    id: str
    label: str | None = None
    owned_by: str | None = None
    context_length: int | None = None


@dataclass(slots=True)
class ChatResult:
    content: str
    model: str
    provider_key: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(slots=True)
class ProviderSettings:
    """Saglayici ornegi olusturmak icin gereken tum ayarlar."""

    key: str
    display_name: str
    base_url: str
    api_key: str = ""
    default_model: str = ""
    timeout_seconds: int = 120
    max_retries: int = 2
    privacy_level: str = "herkese_acik"
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    currency: str = "USD"
    extra_headers: dict[str, str] = field(default_factory=dict)


class AIProvider(abc.ABC):
    """Butun saglayicilarin ortak arayuzu.

    Somut siniflar yalnizca `chat`, `stream_chat` ve `list_models` uygular;
    yeniden deneme, sure olcumu ve maliyet hesabi burada ortaktir.
    """

    #: Bu saglayicinin API anahtari gerektirip gerektirmedigi
    requires_api_key: bool = True
    #: Verinin makineden cikip cikmadigi
    is_external: bool = True
    kind: str = "generic"

    def __init__(self, settings: ProviderSettings):
        self.settings = settings

    # ------------------------------------------------------------ ozellikler
    @property
    def key(self) -> str:
        return self.settings.key

    @property
    def display_name(self) -> str:
        return self.settings.display_name

    @property
    def is_configured(self) -> bool:
        if self.requires_api_key and not self.settings.api_key:
            return False
        return bool(self.settings.base_url)

    def missing_config_message(self) -> str:
        if self.requires_api_key and not self.settings.api_key:
            return (
                f"{self.display_name} için API anahtarı tanımlı değil. "
                "Ayarlar → Yapay Zekâ Sağlayıcıları ekranından ekleyin "
                "(anahtar şifrelenerek saklanır)."
            )
        if not self.settings.base_url:
            return f"{self.display_name} için sunucu adresi tanımlı değil."
        return ""

    # ------------------------------------------------------ soyut arabirim
    @abc.abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1600,
        **kwargs: Any,
    ) -> ChatResult:
        """Tek seferlik yanit uretir."""

    @abc.abstractmethod
    def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1600,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Yaniti parca parca uretir (SSE)."""

    @abc.abstractmethod
    async def list_models(self) -> list[ModelDescriptor]:
        """Saglayicidan guncel model listesini alir."""

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Gomme vektoru uretir. Destegi olmayan saglayici NotImplementedError verir."""
        raise NotImplementedError(f"{self.display_name} gömme (embedding) desteklemiyor.")

    # ---------------------------------------------------------- yardimcilar
    async def health_check(self) -> dict[str, Any]:
        """Kucuk, dusuk maliyetli baglanti testi.

        Once model listesi denenir (cogu saglayicida ucretsizdir); basarisiz
        olursa cok kisa bir sohbet istegi yapilir.
        """
        started = time.perf_counter()
        try:
            models = await self.list_models()
            return {
                "ok": True,
                "status": "cevrimici",
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "models_found": len(models),
                "model": self.settings.default_model or (models[0].id if models else None),
                "message": f"{self.display_name} bağlantısı başarılı "
                f"({len(models)} model bulundu).",
            }
        except ProviderError as exc:
            return {
                "ok": False,
                "status": exc.kind,
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "models_found": 0,
                "model": None,
                "message": exc.safe_message,
            }

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return round(
            input_tokens / 1000 * self.settings.input_cost_per_1k
            + output_tokens / 1000 * self.settings.output_cost_per_1k,
            6,
        )

    def _log_call(self, ok: bool, model: str, latency_ms: int, error: str | None = None) -> None:
        log.info(
            "ai_cagri",
            provider=self.key,
            model=model,
            ok=ok,
            latency_ms=latency_ms,
            error=scrub(error) if error else None,
            at=dt.datetime.now(dt.UTC).isoformat(),
        )


def approx_tokens(text: str) -> int:
    """Kaba token tahmini (saglayici sayim dondurmediginde kullanilir).

    Turkce metinde ortalama ~3.2 karakter/token gozlenmistir; guvenli tarafta
    kalmak icin 3.5 kullanilir.
    """
    return max(1, int(len(text) / 3.5))
