"""OpenAI uyumlu HTTP saglayicisi.

LM Studio, NVIDIA Build ve OpenAI uyumlu diger tum servisler bu sinifi kullanir.
SDK bagimliligi yoktur; yalnizca httpx (BSD-3-Clause).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

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


class OpenAICompatProvider(AIProvider):
    kind = "openai_compat"
    requires_api_key = True
    is_external = True

    def __init__(self, settings: ProviderSettings):
        super().__init__(settings)
        self._base = settings.base_url.rstrip("/")

    # ------------------------------------------------------------ dahili
    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self.settings.extra_headers,
        }
        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"
        return headers

    def _client(self, *, stream: bool = False) -> httpx.AsyncClient:
        timeout = httpx.Timeout(
            connect=10.0,
            read=float(self.settings.timeout_seconds),
            write=30.0,
            pool=10.0,
        )
        return httpx.AsyncClient(base_url=self._base, headers=self._headers(), timeout=timeout)

    def _raise_for(self, response: httpx.Response) -> None:
        code = response.status_code
        if code < 400:
            return
        try:
            body = response.json()
            detail = (
                body.get("error", {}).get("message")
                if isinstance(body.get("error"), dict)
                else body.get("error") or body.get("detail") or response.text
            )
        except (ValueError, AttributeError):
            detail = response.text[:400]

        detail = str(detail)[:400]
        if code in (401, 403):
            raise ProviderAuthError(
                f"{self.display_name}: yetkilendirme hatası ({code}). "
                f"API anahtarını kontrol edin. Ayrıntı: {detail}",
                status_code=code,
            )
        if code == 404:
            raise ProviderError(
                f"{self.display_name}: model veya uç nokta bulunamadı ({code}). {detail}",
                kind="bulunamadi",
                status_code=code,
            )
        if code == 429:
            raise ProviderError(
                f"{self.display_name}: istek sınırı aşıldı (429). Biraz bekleyip tekrar deneyin.",
                kind="hiz_siniri",
                status_code=code,
            )
        if code >= 500:
            raise ProviderUnavailable(
                f"{self.display_name}: sunucu hatası ({code}). {detail}", status_code=code
            )
        raise ProviderError(
            f"{self.display_name}: istek reddedildi ({code}). {detail}",
            kind="istek_hatasi",
            status_code=code,
        )

    @staticmethod
    def _sistem_rolu_desteklenmiyor(exc: ProviderError) -> bool:
        """Bazi yerel modellerin sohbet sablonu `system` rolunu kabul etmez.

        Ornek (LM Studio / BioMistral): "Only user and assistant roles are supported!"
        Bu durumda sistem yonergesi ilk kullanici mesajina katlanarak tekrar denenir.
        """
        metin = str(exc).lower()
        return exc.status_code == 400 and (
            "only user and assistant roles" in metin
            or "system role" in metin
            or "does not support system" in metin
        )

    @staticmethod
    def _sistemi_katla(messages: list[ChatMessage]) -> list[ChatMessage]:
        sistem = "\n\n".join(m.content for m in messages if m.role == "system")
        kalan = [m for m in messages if m.role != "system"]
        if not sistem:
            return kalan or messages
        if kalan and kalan[0].role == "user":
            birlesik = f"{sistem}\n\n---\n\n{kalan[0].content}"
            return [ChatMessage("user", birlesik), *kalan[1:]]
        return [ChatMessage("user", sistem), *kalan]

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = self.settings.max_retries + 1
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                async with self._client() as client:
                    response = await client.post(path, json=payload)
                    self._raise_for(response)
                    return response.json()
            except httpx.TimeoutException:
                # Zaman asiminda YENIDEN DENEMEYIZ: model zaten yavas calisiyorsa
                # tekrar denemek toplam bekleme suresini katlar (2 deneme = 2x sure)
                # ve kullaniciyi cok daha uzun bekletir. Bunun yerine ne yapilmasi
                # gerektigini soyleyen acik bir hata doneriz.
                raise ProviderTimeout(
                    f"{self.display_name}: yanıt {self.settings.timeout_seconds} saniyede "
                    "gelmedi. Yerel modeller ilk çağrıda belleğe yüklenirken yavaş olabilir; "
                    "Ayarlar ekranından zaman aşımı süresini artırın, daha küçük bir model "
                    "seçin veya yanıt uzunluğu sınırını düşürün."
                ) from None
            except httpx.ConnectError as exc:
                last = ProviderUnavailable(
                    f"{self.display_name} sunucusuna bağlanılamadı ({self._base}). "
                    f"Servisin çalıştığından emin olun. Ayrıntı: {type(exc).__name__}"
                )
            except httpx.HTTPError as exc:
                last = ProviderUnavailable(f"{self.display_name}: ağ hatası — {type(exc).__name__}")
            except ProviderError as exc:
                # Yetkilendirme/istek hatalarinda tekrar denemek anlamsizdir
                if exc.kind in ("yetkilendirme", "istek_hatasi", "bulunamadi"):
                    raise
                last = exc
            if attempt < attempts - 1:
                await asyncio.sleep(min(2 ** attempt * 0.75, 5.0))
        raise last if last else ProviderError(f"{self.display_name}: bilinmeyen hata.")

    # ------------------------------------------------------------- API
    async def list_models(self) -> list[ModelDescriptor]:
        if not self.is_configured:
            raise ProviderAuthError(self.missing_config_message())
        try:
            async with self._client() as client:
                response = await client.get("/models")
                self._raise_for(response)
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.display_name}: model listesi zaman aşımına uğradı.") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailable(
                f"{self.display_name} sunucusuna bağlanılamadı ({self._base}). "
                "Servis kapalı olabilir."
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"{self.display_name}: ağ hatası — {type(exc).__name__}") from exc

        items = body.get("data") if isinstance(body, dict) else body
        out: list[ModelDescriptor] = []
        for item in items or []:
            if isinstance(item, str):
                out.append(ModelDescriptor(id=item))
                continue
            mid = item.get("id") or item.get("name")
            if not mid:
                continue
            out.append(
                ModelDescriptor(
                    id=mid,
                    label=item.get("display_name") or mid,
                    owned_by=item.get("owned_by") or item.get("publisher"),
                    context_length=item.get("context_length")
                    or item.get("max_context_length")
                    or (item.get("loaded_context_length") if isinstance(item, dict) else None),
                )
            )
        return out

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
                f"{self.display_name}: model seçilmedi. Ayarlardan varsayılan model belirleyin.",
                kind="yapilandirma",
            )

        payload: dict[str, Any] = {
            "model": use_model,
            "messages": [m.as_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if kwargs.get("json_mode"):
            payload["response_format"] = {"type": "json_object"}
        if kwargs.get("top_p") is not None:
            payload["top_p"] = kwargs["top_p"]
        if kwargs.get("stop"):
            payload["stop"] = kwargs["stop"]

        started = time.perf_counter()
        try:
            body = await self._post("/chat/completions", payload)
        except ProviderError as exc:
            # Sohbet sablonu `system` rolunu kabul etmiyorsa katlayip BIR KEZ daha dene
            if self._sistem_rolu_desteklenmiyor(exc) and any(
                m.role == "system" for m in messages
            ):
                payload["messages"] = [m.as_dict() for m in self._sistemi_katla(messages)]
                body = await self._post("/chat/completions", payload)
            else:
                self._log_call(
                    False, use_model, int((time.perf_counter() - started) * 1000), str(exc)
                )
                raise

        latency = int((time.perf_counter() - started) * 1000)
        choices = body.get("choices") or []
        if not choices:
            raise ProviderError(f"{self.display_name}: yanıt boş döndü.", kind="bos_yanit")

        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):  # bazi saglayicilar parca listesi doner
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )

        usage = body.get("usage") or {}
        ayrinti = usage.get("completion_tokens_details") or {}
        reasoning_tok = int(ayrinti.get("reasoning_tokens") or 0)
        reasoning_metin = (message.get("reasoning_content") or "").strip()
        finish = choices[0].get("finish_reason")

        # --- Akil yurutme (reasoning) modelleri -----------------------------
        # Bu modeller once "dusunur", sonra gorunur yaniti uretir. Token butcesi
        # dusunme asamasinda tukenirse iki farkli bozuk durum olusur:
        #   a) LM Studio  : `content` BOS kalir
        #   b) NVIDIA NIM : kesilen dusunce metni `content` alanina da YAZILIR
        # (b) durumunda kullaniciya modelin dusunce zinciri (ve dolayli olarak
        # sistem yonergesi) gosterilmis olur. Ikisi de sessizce gecilmemelidir.
        butce_bitti = finish == "length"
        dusunce_sizdi = bool(
            butce_bitti
            and reasoning_metin
            and content.strip()
            and (
                content.strip() == reasoning_metin
                or reasoning_metin.startswith(content.strip())
                or content.strip().startswith(reasoning_metin)
            )
        )

        if not content.strip() or dusunce_sizdi:
            if (reasoning_tok > 0 or reasoning_metin) and butce_bitti:
                raise ProviderError(
                    f"{self.display_name}: '{use_model}' bir akıl yürütme modelidir ve "
                    "token bütçesi düşünme aşamasında tükendi; görünür yanıt "
                    "üretilemedi. Yanıt uzunluğu sınırını artırın "
                    "(akıl yürütme modelleri için en az 1500 önerilir) veya "
                    "düşünme yapmayan daha küçük bir model seçin.",
                    kind="token_yetersiz",
                )
            if not content.strip():
                raise ProviderError(
                    f"{self.display_name}: model boş yanıt döndürdü "
                    f"(bitiş nedeni: {finish or 'bilinmiyor'}).",
                    kind="bos_yanit",
                )

        in_tok = int(usage.get("prompt_tokens") or 0) or sum(
            approx_tokens(m.content) for m in messages
        )
        out_tok = int(usage.get("completion_tokens") or 0) or approx_tokens(content)

        self._log_call(True, use_model, latency)
        return ChatResult(
            content=content.strip(),
            model=body.get("model") or use_model,
            provider_key=self.key,
            input_tokens=in_tok,
            output_tokens=out_tok,
            latency_ms=latency,
            finish_reason=finish,
            raw={"usage": usage, "reasoning_tokens": reasoning_tok},
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
        payload = {
            "model": use_model,
            "messages": [m.as_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with (
                self._client(stream=True) as client,
                client.stream("POST", "/chat/completions", json=payload) as response,
            ):
                if response.status_code >= 400:
                    await response.aread()
                    self._raise_for(response)
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in chunk.get("choices", []):
                        piece = (choice.get("delta") or {}).get("content")
                        if piece:
                            yield piece
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.display_name}: akış zaman aşımına uğradı.") from exc
        except httpx.ConnectError as exc:
            raise ProviderUnavailable(
                f"{self.display_name} sunucusuna bağlanılamadı ({self._base})."
            ) from exc

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        use_model = model or ""
        if not use_model:
            raise ProviderError(
                f"{self.display_name}: gömme modeli belirtilmedi.", kind="yapilandirma"
            )
        body = await self._post("/embeddings", {"model": use_model, "input": texts})
        data = body.get("data") or []
        return [item.get("embedding", []) for item in data]
