"""Yapay zekâ sağlayıcı katmanı testleri.

Bulut sağlayıcılar (Claude / NVIDIA) sahte HTTP taşıyıcısıyla test edilir —
ücret doğuracak gerçek istek atılmaz. LM Studio testi, yerel sunucu kapalıysa
otomatik olarak atlanır.
"""

from __future__ import annotations

import json
import os

import httpx
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services.ai.anthropic import AnthropicProvider
from app.services.ai.base import (
    ChatMessage,
    ProviderAuthError,
    ProviderError,
    ProviderSettings,
    ProviderUnavailable,
    approx_tokens,
)
from app.services.ai.lmstudio import LMStudioProvider
from app.services.ai.nvidia import NvidiaProvider
from app.services.ai.openai_compat import OpenAICompatProvider
from app.services.ai.registry import PROVIDER_CLASSES, TASK_PROVIDER_PREFERENCE


# --------------------------------------------------------------- SAHTE HTTP
def _mock_client_factory(provider, handler):
    """Sağlayıcının httpx istemcisini sahte taşıyıcıyla değiştirir."""
    transport = httpx.MockTransport(handler)

    def _client(*_args, **_kwargs):
        return httpx.AsyncClient(
            base_url=provider._base,
            headers=provider._headers(),
            transport=transport,
            timeout=5.0,
        )

    return _client


OPENAI_YANITI = {
    "id": "chatcmpl-test",
    "model": "test-model",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Fermantasyon normal seyrediyor."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 120, "completion_tokens": 35},
}

ANTHROPIC_YANITI = {
    "id": "msg_test",
    "model": "claude-test",
    "content": [{"type": "text", "text": "Uçucu asitlik sınırda, SO₂ ayarı önerilir."}],
    "usage": {"input_tokens": 210, "output_tokens": 48},
    "stop_reason": "end_turn",
}


def _settings(key="test", api_key="test-anahtar", base="https://ornek.gecersiz/v1"):
    return ProviderSettings(
        key=key,
        display_name=f"Test {key}",
        base_url=base,
        api_key=api_key,
        default_model="test-model",
        timeout_seconds=5,
        max_retries=0,
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
    )


# ------------------------------------------------------- SOYUTLAMA SÖZLEŞMESİ
def test_tum_saglayicilar_ortak_arabirimi_uygular():
    for kind, cls in PROVIDER_CLASSES.items():
        for method in ("chat", "stream_chat", "list_models", "health_check", "estimate_cost"):
            assert hasattr(cls, method), f"{kind} sağlayıcısında {method} eksik"


def test_saglayici_sinirlari_dogru_isaretli():
    assert LMStudioProvider.requires_api_key is False
    assert LMStudioProvider.is_external is False
    assert AnthropicProvider.requires_api_key is True
    assert AnthropicProvider.is_external is True
    assert NvidiaProvider.requires_api_key is True
    assert NvidiaProvider.is_external is True


def test_hassas_gorevler_once_yerel_modele_yonlendirilir():
    for gorev in ("saraphane_danismani", "veri_analisti", "kalite_kontrol"):
        assert TASK_PROVIDER_PREFERENCE[gorev][0] == "lmstudio", (
            f"{gorev} görevi öncelikle yerel modele yönlendirilmeli (gizlilik)"
        )


def test_token_tahmini_makul():
    assert approx_tokens("") >= 1
    assert 10 <= approx_tokens("Bu bir Türkçe cümledir ve yaklaşık on beş token eder.") <= 30


def test_maliyet_hesabi():
    provider = OpenAICompatProvider(_settings())
    assert provider.estimate_cost(1000, 1000) == pytest.approx(0.018)
    assert provider.estimate_cost(0, 0) == 0.0


# ---------------------------------------------------------- OpenAI UYUMLU
async def test_openai_uyumlu_sohbet(monkeypatch):
    provider = OpenAICompatProvider(_settings())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert body["messages"][0]["role"] == "system"
        assert request.headers["authorization"] == "Bearer test-anahtar"
        return httpx.Response(200, json=OPENAI_YANITI)

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    result = await provider.chat(
        [ChatMessage("system", "Sen bir enologsun."), ChatMessage("user", "Durum nedir?")]
    )
    assert result.content == "Fermantasyon normal seyrediyor."
    assert result.input_tokens == 120
    assert result.output_tokens == 35
    assert result.finish_reason == "stop"
    assert result.latency_ms >= 0


async def test_openai_uyumlu_model_listesi(monkeypatch):
    provider = OpenAICompatProvider(_settings())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "model-a", "owned_by": "test"}, {"id": "model-b"}]},
        )

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    models = await provider.list_models()
    assert [m.id for m in models] == ["model-a", "model-b"]


@pytest.mark.parametrize(
    ("kod", "beklenen_tur"),
    [(401, "yetkilendirme"), (403, "yetkilendirme"), (404, "bulunamadi"),
     (429, "hiz_siniri"), (500, "ulasilamiyor")],
)
async def test_http_hatalari_turkce_ve_siniflandirilmis(monkeypatch, kod, beklenen_tur):
    provider = OpenAICompatProvider(_settings())

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(kod, json={"error": {"message": "sunucu mesajı"}})

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    with pytest.raises(ProviderError) as exc:
        await provider.chat([ChatMessage("user", "test")])
    assert exc.value.kind == beklenen_tur
    assert "Test test" in str(exc.value) or "Test" in str(exc.value)


async def test_hata_mesajinda_anahtar_sizmaz(monkeypatch):
    gizli = "sk-ant-api03-SIZMAMALI0123456789abcdefgh"
    provider = OpenAICompatProvider(_settings(api_key=gizli))

    def handler(request: httpx.Request) -> httpx.Response:
        # Sunucu hatalı biçimde anahtarı geri yansıtsa bile maskelenmelidir
        return httpx.Response(401, json={"error": {"message": f"Geçersiz anahtar: {gizli}"}})

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    with pytest.raises(ProviderAuthError) as exc:
        await provider.chat([ChatMessage("user", "test")])
    assert gizli not in str(exc.value)
    assert "***GIZLI***" in str(exc.value)


async def test_baglanti_hatasi_anlasilir_mesaj(monkeypatch):
    provider = OpenAICompatProvider(_settings())

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlantı reddedildi")

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    with pytest.raises(ProviderUnavailable) as exc:
        await provider.chat([ChatMessage("user", "test")])
    assert "bağlanılamadı" in str(exc.value)


# ---------------------------------------------------------------- CLAUDE
async def test_claude_istek_bicimi(monkeypatch):
    provider = AnthropicProvider(_settings(key="anthropic", base="https://ornek.gecersiz/v1"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/messages")
        assert request.headers["x-api-key"] == "test-anahtar"
        assert request.headers["anthropic-version"]
        body = json.loads(request.content)
        # system ayrı alanda olmalı, messages içinde değil
        assert body["system"] == "Sen bir enologsun."
        assert all(m["role"] != "system" for m in body["messages"])
        assert body["messages"][0]["role"] == "user"
        return httpx.Response(200, json=ANTHROPIC_YANITI)

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    result = await provider.chat(
        [ChatMessage("system", "Sen bir enologsun."), ChatMessage("user", "Analiz yorumu?")]
    )
    assert "Uçucu asitlik" in result.content
    assert result.input_tokens == 210
    assert result.output_tokens == 48
    assert result.finish_reason == "end_turn"


async def test_claude_anahtarsiz_anlasilir_hata():
    provider = AnthropicProvider(_settings(key="anthropic", api_key=""))
    assert provider.is_configured is False
    with pytest.raises(ProviderAuthError) as exc:
        await provider.chat([ChatMessage("user", "test")])
    assert "API anahtarı tanımlı değil" in str(exc.value)
    assert "şifrelenerek saklanır" in str(exc.value)


async def test_claude_model_listesi(monkeypatch):
    provider = AnthropicProvider(_settings(key="anthropic"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"id": "claude-a", "display_name": "Claude A"}]},
        )

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    models = await provider.list_models()
    assert models[0].id == "claude-a"
    assert models[0].label == "Claude A"


# ---------------------------------------------------------------- NVIDIA
async def test_nvidia_openai_uyumlu_calisir(monkeypatch):
    provider = NvidiaProvider(_settings(key="nvidia", base="https://ornek.gecersiz/v1"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-anahtar"
        return httpx.Response(200, json=OPENAI_YANITI)

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    result = await provider.chat([ChatMessage("user", "test")])
    assert result.content


async def test_nvidia_anahtarsiz_yonlendirici_mesaj():
    provider = NvidiaProvider(_settings(key="nvidia", api_key=""))
    mesaj = provider.missing_config_message()
    assert "build.nvidia.com" in mesaj
    assert "Get API Key" in mesaj


def test_nvidia_varsayilan_adres():
    provider = NvidiaProvider(_settings(key="nvidia", base=""))
    assert provider.settings.base_url == "https://integrate.api.nvidia.com/v1"


# -------------------------------------------------------------- LM STUDIO
def test_lmstudio_anahtar_gerektirmez():
    provider = LMStudioProvider(_settings(key="lmstudio", api_key="", base="http://localhost:1234/v1"))
    assert provider.is_configured is True
    assert provider.settings.privacy_level == "yerel_only"


async def test_lmstudio_kapaliyken_uygulama_cokmez(monkeypatch):
    """LM Studio kapalıysa anlaşılır Türkçe uyarı dönmeli, istisna fırlamamalı."""
    provider = LMStudioProvider(
        _settings(key="lmstudio", api_key="", base="http://localhost:59999/v1")
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("bağlantı yok")

    monkeypatch.setattr(provider, "_client", _mock_client_factory(provider, handler))
    health = await provider.health_check()
    assert health["ok"] is False
    assert "LM Studio uygulamasını açıp" in health["message"]
    assert "normal çalışmaya devam eder" in health["message"]


@pytest.mark.canli_ai
async def test_lmstudio_gercek_baglanti():
    """Yerel LM Studio sunucusuna gerçek bağlantı (kapalıysa atlanır)."""
    provider = LMStudioProvider(
        ProviderSettings(
            key="lmstudio",
            display_name="LM Studio",
            base_url=os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1"),
            timeout_seconds=15,
            max_retries=0,
        )
    )
    health = await provider.health_check()
    if not health["ok"]:
        pytest.skip(f"LM Studio çalışmıyor: {health['message'][:80]}")
    assert health["models_found"] > 0
    models = await provider.list_models()
    assert all(m.id for m in models)


# --------------------------------------------------------------- API KATMANI
async def test_saglayici_listesi_uc_noktasi(client: AsyncClient, admin_headers):
    response = await client.get("/api/v1/ai/providers", headers=admin_headers)
    assert response.status_code == 200
    keys = {p["provider_key"] for p in response.json()}
    assert {"lmstudio", "anthropic", "nvidia"} <= keys

    lmstudio = next(p for p in response.json() if p["provider_key"] == "lmstudio")
    assert lmstudio["privacy_level"] == "yerel_only"
    assert lmstudio["requires_api_key"] is False


async def test_saglayici_ayari_guncellenebilir(client: AsyncClient, admin_headers):
    response = await client.patch(
        "/api/v1/ai/providers/lmstudio",
        json={"default_model": "google/gemma-4-12b-qat", "timeout_seconds": 90},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["default_model"] == "google/gemma-4-12b-qat"
    assert response.json()["timeout_seconds"] == 90


async def test_gorev_bazli_model_esleme(client: AsyncClient, admin_headers):
    response = await client.patch(
        "/api/v1/ai/providers/lmstudio",
        json={
            "task_model_map": {
                "kod_gelistirici": "qwen/qwen3-vl-8b",
                "veri_analisti": "google/gemma-4-12b-qat",
            }
        },
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["task_model_map"]["kod_gelistirici"] == "qwen/qwen3-vl-8b"


async def test_saglayici_kapaliyken_sohbet_anlasilir_hata(client: AsyncClient, admin_headers):
    """Tüm sağlayıcılar kullanılamazken 503 + Türkçe açıklama dönmeli (çökme yok)."""
    for key in ("lmstudio", "anthropic", "nvidia"):
        await client.patch(
            f"/api/v1/ai/providers/{key}", json={"enabled": False}, headers=admin_headers
        )
    response = await client.post(
        "/api/v1/ai/chat",
        json={"message": "Merhaba", "task_kind": "genel"},
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert "sağlayıcı" in response.json()["detail"].lower()


async def test_gorev_turleri_listelenir(client: AsyncClient, admin_headers):
    response = await client.get("/api/v1/ai/task-kinds", headers=admin_headers)
    assert response.status_code == 200
    kodlar = {t["kod"] for t in response.json()}
    assert {"saraphane_danismani", "veri_analisti", "kod_gelistirici", "hata_teshis"} <= kodlar


async def test_kullanim_raporu_bos_donemde_calisir(client: AsyncClient, admin_headers):
    response = await client.get("/api/v1/ai/usage", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["total_requests"] == 0


async def test_veri_kapsami_onizlemesi(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/ai/data-scope-preview",
        json={"message": "Analiz et", "provider_key": "anthropic", "include_dashboard": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_external"] is True
    assert "harici bir bulut" in (body["warning_tr"] or "")
    assert any(i["tur"] == "Pano özeti" for i in body["items"])


async def test_yerel_saglayici_gizlilik_uyarisi(client: AsyncClient, admin_headers):
    response = await client.post(
        "/api/v1/ai/data-scope-preview",
        json={"message": "Analiz et", "provider_key": "lmstudio", "include_dashboard": True},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_external"] is False
    assert "makineden çıkmaz" in response.json()["warning_tr"]


async def test_ai_yetkisi_olmayan_kullanici_reddedilir(client: AsyncClient, auth_headers):
    headers = await auth_headers(["denetci"], "denetci_ai")
    response = await client.post(
        "/api/v1/ai/chat", json={"message": "test"}, headers=headers
    )
    assert response.status_code == 403


# ------------------------------------------------- SAYISAL ÖZELLİKLER (LLM'siz)
async def test_kalite_puani_llm_olmadan_calisir(client: AsyncClient, admin_headers):
    variety = await client.post(
        "/api/v1/varieties", json={"name": "Test Çeşit", "color": "kirmizi"},
        headers=admin_headers,
    )
    intake = await client.post(
        "/api/v1/harvest-intakes",
        json={
            "variety_id": variety.json()["id"],
            "harvest_date": "2026-09-01",
            "net_weight_kg": 5000,
            "brix": 23.5,
            "ph": 3.5,
        },
        headers=admin_headers,
    )
    lot = await client.post(
        "/api/v1/lots/with-sources",
        json={
            "name": "Puan Testi",
            "volume_l": 3000,
            "sources": [{"intake_id": intake.json()["id"], "weight_kg": 5000}],
        },
        headers=admin_headers,
    )
    response = await client.post(
        "/api/v1/ai/insights",
        json={"kind": "kalite_puani", "lot_id": lot.json()["id"], "use_llm": False},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "kalite_puani"
    assert 0 <= body["numeric"]["puan"] <= 100
    assert body["is_advisory"] is True
    assert "karar destek" in body["disclaimer"].lower()


async def test_stok_ve_bakim_tahmini_saglayicisiz_calisir(client: AsyncClient, admin_headers):
    for kind in ("stok_tahmin", "bakim_tahmin"):
        response = await client.post(
            "/api/v1/ai/insights", json={"kind": kind, "use_llm": False}, headers=admin_headers
        )
        assert response.status_code == 200, f"{kind}: {response.text}"
        assert response.json()["kind"] == kind


def test_ai_varsayilan_saglayici_ayarli():
    assert settings.AI_DEFAULT_PROVIDER in PROVIDER_CLASSES
