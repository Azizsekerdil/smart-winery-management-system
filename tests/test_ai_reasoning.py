"""Akıl yürütme (reasoning) modellerinin bozuk yanıt durumları.

Bu davranışlar gerçek modellerle (LM Studio Gemma 4, NVIDIA Nemotron 3 Ultra)
karşılaşılan sorunlardan türetilmiştir; bkz. docs/AI_MODEL_EVALUATION.md.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.ai.base import ChatMessage, ProviderError, ProviderSettings
from app.services.ai.openai_compat import OpenAICompatProvider


def _ayar() -> ProviderSettings:
    return ProviderSettings(
        key="test",
        display_name="Test Sağlayıcı",
        base_url="https://ornek.gecersiz/v1",
        api_key="test-anahtar",
        default_model="akil-yurutme-modeli",
        timeout_seconds=5,
        max_retries=0,
    )


def _sahte(provider: OpenAICompatProvider, handler):
    transport = httpx.MockTransport(handler)

    def _client(*_a, **_k):
        return httpx.AsyncClient(
            base_url=provider._base,
            headers=provider._headers(),
            transport=transport,
            timeout=5.0,
        )

    return _client


# --------------------------------------------------- a) içerik boş kalıyor
async def test_dusunmede_butce_bitince_acik_hata(monkeypatch):
    """LM Studio davranışı: bütçe düşünmede biter, `content` boş döner."""
    provider = OpenAICompatProvider(_ayar())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "akil-yurutme-modeli",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "reasoning_content": "Kullanıcı şunu istiyor: önce düşün…",
                        },
                        "finish_reason": "length",
                    }
                ],
                "usage": {
                    "prompt_tokens": 41,
                    "completion_tokens": 300,
                    "completion_tokens_details": {"reasoning_tokens": 297},
                },
            },
        )

    monkeypatch.setattr(provider, "_client", _sahte(provider, handler))
    with pytest.raises(ProviderError) as exc:
        await provider.chat([ChatMessage("user", "test")], max_tokens=300)

    assert exc.value.kind == "token_yetersiz"
    assert "akıl yürütme modelidir" in str(exc.value)
    assert "1500" in str(exc.value)


# ------------------------------------------ b) düşünce içeriğe sızıyor
async def test_dusunce_iceriye_sizarsa_kullaniciya_gosterilmez(monkeypatch):
    """NVIDIA davranışı: kesilen düşünce metni `content` alanına da yazılır.

    Bu metin kullanıcıya GÖSTERİLMEMELİDİR — düşünce zinciri ve dolaylı olarak
    sistem yönergesi sızar.
    """
    provider = OpenAICompatProvider(_ayar())
    dusunce = 'The user wants me to respond with only "BAĞLANTI T'

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "akil-yurutme-modeli",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": dusunce,
                            "reasoning_content": dusunce,
                        },
                        "finish_reason": "length",
                    }
                ],
                "usage": {"prompt_tokens": 33, "completion_tokens": 16},
            },
        )

    monkeypatch.setattr(provider, "_client", _sahte(provider, handler))
    with pytest.raises(ProviderError) as exc:
        await provider.chat([ChatMessage("user", "Test")], max_tokens=16)

    assert exc.value.kind == "token_yetersiz"
    # Düşünce zinciri hata mesajına da taşınmamalı
    assert "The user wants me" not in str(exc.value)


# ------------------------------------------ c) yeterli bütçe → temiz yanıt
async def test_yeterli_butcede_temiz_yanit_doner(monkeypatch):
    """Bütçe yeterliyse `content` gerçek yanıttır; düşünce ayrı alanda kalır."""
    provider = OpenAICompatProvider(_ayar())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "akil-yurutme-modeli",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "BAĞLANTI TAMAM",
                            "reasoning_content": "Kullanıcı yalnızca bu ifadeyi istiyor.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 33,
                    "completion_tokens": 42,
                    "completion_tokens_details": {"reasoning_tokens": 30},
                },
            },
        )

    monkeypatch.setattr(provider, "_client", _sahte(provider, handler))
    sonuc = await provider.chat([ChatMessage("user", "Test")], max_tokens=600)

    assert sonuc.content == "BAĞLANTI TAMAM"
    assert "Kullanıcı yalnızca" not in sonuc.content
    assert sonuc.raw["reasoning_tokens"] == 30


# ------------------------------- d) düşünce ile yanıt farklıysa kesme sorun değil
async def test_kesilmis_ama_gercek_yanit_kabul_edilir(monkeypatch):
    """Yanıt kesilmiş olsa bile düşünceden FARKLIYSA gerçek içeriktir; döndürülür."""
    provider = OpenAICompatProvider(_ayar())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "akil-yurutme-modeli",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Uçucu asitlik yüksek; SO₂ ayarı öner",
                            "reasoning_content": "Önce değerleri karşılaştırayım…",
                        },
                        "finish_reason": "length",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    monkeypatch.setattr(provider, "_client", _sahte(provider, handler))
    sonuc = await provider.chat([ChatMessage("user", "test")], max_tokens=50)

    assert sonuc.content.startswith("Uçucu asitlik")
    assert sonuc.finish_reason == "length"


# ------------------------------------------- e) düşünmeyen model etkilenmez
async def test_dusunmeyen_model_etkilenmez(monkeypatch):
    provider = OpenAICompatProvider(_ayar())

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "duz-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "BAĞLANTI TAMAM"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 33, "completion_tokens": 10},
            },
        )

    monkeypatch.setattr(provider, "_client", _sahte(provider, handler))
    sonuc = await provider.chat([ChatMessage("user", "Test")])
    assert sonuc.content == "BAĞLANTI TAMAM"
    assert sonuc.raw["reasoning_tokens"] == 0
