"""Anthropic Claude saglayicisi (Messages API).

Anthropic'in bicimi OpenAI'dan farklidir:
  * `system` ayri bir alandir, mesaj listesinde yer almaz
  * kimlik dogrulama `x-api-key` basligi ile yapilir
  * `anthropic-version` basligi zorunludur
  * yanit `content` bloklari listesi olarak doner

Model kimlikleri SABIT VARSAYILMAZ; `/models` uc noktasindan okunur ve
ayarlardan yapilandirilir.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings as app_settings
from app.services.ai.base import (
    AIProvider,
    ChatMessage,
    ChatResult,
    ModelDescriptor,
    ProviderAuthError,
    ProviderError,
    ProviderSettings,
    ProviderTimeout,
    ProviderUnavailable,
    approx_tokens,
)


class AnthropicProvider(AIProvider):
    kind = "anthropic"
    requires_api_key = True
    is_external = True

    def __init__(self, settings: ProviderSettings):
        if not settings.base_url:
            settings.base_url = "https://api.anthropic.com/v1"
        super().__init__(settings)
        self._base = settings.base_url.rstrip("/")

    def missing_config_message(self) -> str:
        if not self.settings.api_key:
            return (
                "Claude (Anthropic) API anahtarı tanımlı değil. Ayarlar → Yapay Zekâ "
                "Sağlayıcıları ekranından ekleyin veya .env dosyasına "
                "ANTHROPIC_API_KEY olarak yazın. Anahtar şifrelenerek saklanır."
            )
        return ""

    def _headers(self) -> dict[str, str]:
        return {
            "content-type": "application/json",
            "accept": "application/json",
            "x-api-key": self.settings.api_key,
            "anthropic-version": app_settings.ANTHROPIC_VERSION,
            **self.settings.extra_headers,
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base,
            headers=self._headers(),
            timeout=httpx.Timeout(
                connect=10.0, read=float(self.settings.timeout_seconds), write=30.0, pool=10.0
            ),
        )

    def _raise_for(self, response: httpx.Response) -> None:
        code = response.status_code
        if code < 400:
            return
        try:
            body = response.json()
            detail = body.get("error", {}).get("message", response.text)
        except (ValueError, AttributeError):
            detail = response.text[:400]
        detail = str(detail)[:400]

        if code in (401, 403):
            raise ProviderAuthError(
                f"Claude: API anahtarı geçersiz veya yetkisiz ({code}). {detail}",
                status_code=code,
            )
        if code == 429:
            raise ProviderError(
                "Claude: istek/kota sınırı aşıldı (429). Biraz bekleyip tekrar deneyin.",
                kind="hiz_siniri",
                status_code=code,
            )
        if code == 404:
            raise ProviderError(
                f"Claude: model bulunamadı ({code}). Ayarlardaki model kimliğini "
                f"güncel model listesinden seçin. {detail}",
                kind="bulunamadi",
                status_code=code,
            )
        if code >= 500:
            raise ProviderUnavailable(f"Claude: sunucu hatası ({code}). {detail}", status_code=code)
        raise ProviderError(
            f"Claude: istek reddedildi ({code}). {detail}", kind="istek_hatasi", status_code=code
        )

    @staticmethod
    def _split(messages: list[ChatMessage]) -> tuple[str, list[dict[str, str]]]:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [
            {"role": ("assistant" if m.role == "assistant" else "user"), "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        if not chat:
            chat = [{"role": "user", "content": "Merhaba."}]
        # Anthropic ardisik ayni rolu kabul eder ama ilk mesaj 'user' olmalidir
        if chat[0]["role"] != "user":
            chat.insert(0, {"role": "user", "content": "(bağlam)"})
        return "\n\n".join(system_parts), chat

    async def list_models(self) -> list[ModelDescriptor]:
        if not self.is_configured:
            raise ProviderAuthError(self.missing_config_message())
        try:
            async with self._client() as client:
                response = await client.get("/models", params={"limit": 100})
                self._raise_for(response)
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("Claude: model listesi zaman aşımına uğradı.") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailable(
                "Claude API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Claude: ağ hatası — {type(exc).__name__}") from exc

        return [
            ModelDescriptor(
                id=item["id"],
                label=item.get("display_name") or item["id"],
                owned_by="anthropic",
            )
            for item in body.get("data", [])
            if item.get("id")
        ]

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1600,
        **kwargs: Any,
    ) -> ChatResult:
        if not self.is_configured:
            raise ProviderAuthError(self.missing_config_message())

        use_model = model or self.settings.default_model
        if not use_model:
            raise ProviderError(
                "Claude: model seçilmedi. Ayarlar ekranından güncel model listesinden "
                "bir model seçin.",
                kind="yapilandirma",
            )

        system_text, chat_messages = self._split(messages)
        payload: dict[str, Any] = {
            "model": use_model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": min(max(temperature, 0.0), 1.0),
        }
        if system_text:
            payload["system"] = system_text

        started = time.perf_counter()
        attempts = self.settings.max_retries + 1
        last: Exception | None = None

        for attempt in range(attempts):
            try:
                async with self._client() as client:
                    response = await client.post("/messages", json=payload)
                    self._raise_for(response)
                    body = response.json()
                    break
            except httpx.TimeoutException:
                # Zaman asiminda yeniden deneme yapilmaz (bkz. openai_compat.py):
                # bekleme suresini katlar ve bulut saglayicida ucreti ikiye katlayabilir.
                self._log_call(False, use_model, int((time.perf_counter() - started) * 1000))
                raise ProviderTimeout(
                    f"Claude: yanıt {self.settings.timeout_seconds} saniyede gelmedi. "
                    "Ayarlar ekranından zaman aşımı süresini artırabilir veya yanıt "
                    "uzunluğu sınırını düşürebilirsiniz."
                ) from None
            except httpx.ConnectError:
                last = ProviderUnavailable("Claude API'ye bağlanılamadı.")
            except httpx.HTTPError as exc:
                last = ProviderUnavailable(f"Claude: ağ hatası — {type(exc).__name__}")
            except ProviderError as exc:
                if exc.kind in ("yetkilendirme", "istek_hatasi", "bulunamadi", "yapilandirma"):
                    self._log_call(
                        False, use_model, int((time.perf_counter() - started) * 1000), str(exc)
                    )
                    raise
                last = exc
            if attempt < attempts - 1:
                await asyncio.sleep(min(2 ** attempt * 0.75, 5.0))
        else:
            self._log_call(
                False, use_model, int((time.perf_counter() - started) * 1000), str(last)
            )
            raise last if last else ProviderError("Claude: bilinmeyen hata.")

        latency = int((time.perf_counter() - started) * 1000)
        blocks = body.get("content") or []
        text = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        )
        usage = body.get("usage") or {}

        self._log_call(True, use_model, latency)
        return ChatResult(
            content=text.strip(),
            model=body.get("model") or use_model,
            provider_key=self.key,
            input_tokens=int(usage.get("input_tokens") or 0)
            or sum(approx_tokens(m.content) for m in messages),
            output_tokens=int(usage.get("output_tokens") or 0) or approx_tokens(text),
            latency_ms=latency,
            finish_reason=body.get("stop_reason"),
            raw={"usage": usage},
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 1600,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        if not self.is_configured:
            raise ProviderAuthError(self.missing_config_message())

        use_model = model or self.settings.default_model
        system_text, chat_messages = self._split(messages)
        payload: dict[str, Any] = {
            "model": use_model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": min(max(temperature, 0.0), 1.0),
            "stream": True,
        }
        if system_text:
            payload["system"] = system_text

        try:
            async with (
                self._client() as client,
                client.stream("POST", "/messages", json=payload) as response,
            ):
                if response.status_code >= 400:
                    await response.aread()
                    self._raise_for(response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        piece = (event.get("delta") or {}).get("text")
                        if piece:
                            yield piece
                    elif event.get("type") == "message_stop":
                        break
        except httpx.TimeoutException as exc:
            raise ProviderTimeout("Claude: akış zaman aşımına uğradı.") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailable("Claude API'ye bağlanılamadı.") from exc
