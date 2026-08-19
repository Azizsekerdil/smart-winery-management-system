"""Harici saglayiciya veri gonderme onayi (gizlilik sozlesmesi).

Urunun one cikan gizlilik vaadi sudur: **saraphane verisi, kullanici acikca
onaylamadan sirketin disina cikmaz.** Bu dosya o vaadi uc noktadan dogrular:

  1. Kapi, harici saglayici secildigi ANDA calisir - ekli kayit olsun olmasin.
     (Yalnizca serbest metin sorusu da disari cikan bir veridir.)
  2. Getirilen dokuman parcalari (RAG) kapsam listesinde GORUNUR ve
     onaysiz gonderilmez. "Dokuman icerigi makineden cikmaz" ifadesi ancak
     bu sekilde dogru olur.
  3. Yerel saglayici yanit vermediginde geri donus zinciri sessizce bir bulut
     saglayicisina GECEMEZ. Onay yoksa istek basarisiz olur; veri cikmaz.

Hicbir test gercek bir saglayiciya istek atmaz: harici cagri yapilirsa test
BASARISIZ olur.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.crypto import encrypt_secret
from app.db.session import SessionLocal
from app.models.ai import AIProviderConfig, DocumentChunk
from app.services.ai import registry
from app.services.ai.base import ChatResult, ProviderError


# ------------------------------------------------------------- yardimcilar
@pytest.fixture
async def harici_saglayici_hazir():
    """Anthropic'i 'yapilandirilmis' hale getirir (gercek anahtar DEGIL)."""
    async with SessionLocal() as s:
        config = await s.scalar(
            select(AIProviderConfig).where(AIProviderConfig.provider_key == "anthropic")
        )
        config.api_key_encrypted = encrypt_secret("test-anahtari-gercek-degil")
        config.default_model = "test-model"
        config.enabled = True
        await s.commit()


@pytest.fixture
def cagri_kaydi(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Saglayiciya giden her cagriyi kaydeder; GERCEK istek atilmaz."""
    kayitlar: list[dict] = []

    async def sahte_chat(self, messages, *, model="", **kwargs):
        kayitlar.append(
            {
                "provider": self.key,
                "is_external": self.is_external,
                "text": "\n".join(m.content for m in messages),
            }
        )
        return ChatResult(
            content="test yaniti", model=model or "test-model",
            provider_key=self.key, input_tokens=1, output_tokens=1, latency_ms=1,
        )

    for cls in registry.PROVIDER_CLASSES.values():
        monkeypatch.setattr(cls, "chat", sahte_chat, raising=False)
    return kayitlar


def _harici_cagri(kayitlar: list[dict]) -> list[dict]:
    return [k for k in kayitlar if k["is_external"]]


# ============================================================ 1. KOSULSUZ KAPI
async def test_ekli_kayit_olmadan_da_onay_istenir(
    client: AsyncClient, admin_headers, harici_saglayici_hazir, cagri_kaydi
) -> None:
    """WIN-H3: kapi eskiden YALNIZCA ekli kayit varken calisiyordu.

    Kullanici sadece soru yazdiginda kapi tamamen atlaniyordu ve serbest metin
    onaysiz olarak buluta gidiyordu. Bu, urunun one cikan gizlilik vaadini
    gecersiz kilan asil durumdur.
    """
    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={
            "message": "2019 rekoltesi icin mayalama sicakligi ne olmali?",
            "provider_key": "anthropic",
            # ekli kayit YOK, RAG YOK, onay YOK
        },
    )

    assert yanit.status_code == 412, (
        f"Onay istenmeden gonderildi (durum {yanit.status_code}). "
        "Serbest metin sorusu da saraphane disina cikan bir veridir."
    )
    assert _harici_cagri(cagri_kaydi) == [], "Onay alinmadan harici cagri yapildi"


async def test_onay_verilince_gonderilir(
    client: AsyncClient, admin_headers, harici_saglayici_hazir, cagri_kaydi
) -> None:
    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={
            "message": "Merhaba",
            "provider_key": "anthropic",
            "confirm_external_share": True,
        },
    )
    assert yanit.status_code == 200, yanit.text
    assert len(_harici_cagri(cagri_kaydi)) == 1


async def test_yerel_saglayici_onay_istemez(
    client: AsyncClient, admin_headers, cagri_kaydi
) -> None:
    """Yerel model icin onay sorulmaz; veri zaten makineden cikmaz."""
    async with SessionLocal() as s:
        config = await s.scalar(
            select(AIProviderConfig).where(AIProviderConfig.provider_key == "lmstudio")
        )
        config.default_model = "yerel-test-model"
        await s.commit()

    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={"message": "Merhaba", "provider_key": "lmstudio"},
    )
    assert yanit.status_code == 200, yanit.text
    assert _harici_cagri(cagri_kaydi) == []


# ======================================================= 2. DOKUMANLAR (RAG)
@pytest.fixture
async def dokuman_indeksi():
    """Aranabilir tek bir dokuman parcasi ekler."""
    async with SessionLocal() as s:
        s.add(
            DocumentChunk(
                document_key="sop/fermantasyon.md",
                title="Fermantasyon SOP",
                source_path="/sunucu/ic/yol/docs/sop/fermantasyon.md",
                doc_type="sop",
                chunk_index=0,
                content=(
                    "Fermantasyon sicakligi kirmizi sarapta 24-28 santigrat "
                    "derece araliginda tutulur ve gunluk Brix olcumu alinir."
                ),
                token_estimate=30,
            )
        )
        await s.commit()


async def test_dokuman_parcalari_kapsam_listesinde_gorunur(
    client: AsyncClient, admin_headers, harici_saglayici_hazir, dokuman_indeksi,
    cagri_kaydi,
) -> None:
    """WIN-H4: getirilen parcalar ne sayiliyor ne de listeleniyordu."""
    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={
            "message": "fermantasyon sicakligi nedir",
            "provider_key": "anthropic",
            "use_rag": True,
        },
    )
    assert yanit.status_code == 412, (
        "Dokuman icerigi onaysiz gonderildi; 'icerik makineden cikmaz' "
        "ifadesi bu haliyle dogru degil."
    )
    assert _harici_cagri(cagri_kaydi) == []


async def test_onayli_rag_isteginde_dokuman_kapsamda_kayitlidir(
    client: AsyncClient, admin_headers, harici_saglayici_hazir, dokuman_indeksi,
    cagri_kaydi,
) -> None:
    """Onay verildiginde dokuman parcasi konusma kaydinin kapsamina yazilir."""
    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={
            "message": "fermantasyon sicakligi nedir",
            "provider_key": "anthropic",
            "use_rag": True,
            "confirm_external_share": True,
        },
    )
    assert yanit.status_code == 200, yanit.text

    detay = await client.get("/api/v1/ai/conversations", headers=admin_headers)
    assert detay.status_code == 200, detay.text
    konusma = next(
        k for k in detay.json() if k["id"] == yanit.json()["conversation_id"]
    )
    kapsam = konusma.get("data_scope") or []
    assert any("Doküman" in (k.get("tur") or "") for k in kapsam), (
        f"Dokuman parcasi kapsam listesine yazilmadi: {kapsam}"
    )


async def test_rag_yaniti_sunucu_ic_yolunu_sizdirmaz(
    client: AsyncClient, admin_headers, dokuman_indeksi
) -> None:
    """Mutlak sunucu yolu istemciye donmemeli (ic dizin yapisi ifsasi)."""
    yanit = await client.post(
        "/api/v1/ai/rag/search",
        headers=admin_headers,
        json={"query": "fermantasyon sicakligi"},
    )
    assert yanit.status_code == 200, yanit.text
    assert "/sunucu/ic/yol" not in yanit.text, "Sunucu ic yolu istemciye dondu"


# ================================================ 3. SESSIZ GERI DONUS YOK
async def test_yerel_saglayici_coktugunde_buluta_gecilmez(
    client: AsyncClient, admin_headers, harici_saglayici_hazir,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En kritik senaryo.

    Kullanici bilincli olarak YEREL modeli secer ve harici paylasimi
    onaylamaz. Yerel model o anda kapalidir. Eski davranista geri donus
    zinciri sessizce Anthropic'e geciyordu: kullanici "veri makinemden
    cikmiyor" sanirken tum baglami buluta gidiyordu.
    """
    cagrilar: list[str] = []

    async def yerel_coktu(self, messages, *, model="", **kwargs):
        cagrilar.append(self.key)
        if not self.is_external:
            raise ProviderError("LM Studio yanit vermiyor.", kind="baglanti")
        return ChatResult(
            content="bulut yaniti", model=model or "test-model",
            provider_key=self.key, input_tokens=1, output_tokens=1, latency_ms=1,
        )

    for cls in registry.PROVIDER_CLASSES.values():
        monkeypatch.setattr(cls, "chat", yerel_coktu, raising=False)

    async with SessionLocal() as s:
        config = await s.scalar(
            select(AIProviderConfig).where(AIProviderConfig.provider_key == "lmstudio")
        )
        config.default_model = "yerel-test-model"
        await s.commit()

    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={
            "message": "Gizli uretim verimizi yorumla",
            "provider_key": "lmstudio",
            "include_dashboard": True,
            # onay YOK - kullanici yerel model istedi
        },
    )

    assert yanit.status_code == 503, (
        f"Beklenen 503 (saglayici yok), gelen {yanit.status_code}. "
        "Yerel model coktugunde istek basarisiz olmali, buluta kaymamali."
    )
    assert "anthropic" not in cagrilar, (
        "Yerel model coktugunde veri sessizce Anthropic'e gonderildi."
    )
    assert "nvidia" not in cagrilar


async def test_onay_varken_geri_donus_calismaya_devam_eder(
    client: AsyncClient, admin_headers, harici_saglayici_hazir,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Onay verilmisse guvenli geri donus ozelligi korunur."""
    cagrilar: list[str] = []

    async def yerel_coktu(self, messages, *, model="", **kwargs):
        cagrilar.append(self.key)
        if not self.is_external:
            raise ProviderError("LM Studio yanit vermiyor.", kind="baglanti")
        return ChatResult(
            content="bulut yaniti", model=model or "test-model",
            provider_key=self.key, input_tokens=1, output_tokens=1, latency_ms=1,
        )

    for cls in registry.PROVIDER_CLASSES.values():
        monkeypatch.setattr(cls, "chat", yerel_coktu, raising=False)

    async with SessionLocal() as s:
        config = await s.scalar(
            select(AIProviderConfig).where(AIProviderConfig.provider_key == "lmstudio")
        )
        config.default_model = "yerel-test-model"
        await s.commit()

    yanit = await client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={
            "message": "Merhaba",
            "provider_key": "lmstudio",
            "confirm_external_share": True,
        },
    )
    assert yanit.status_code == 200, yanit.text
    assert "anthropic" in cagrilar


# ========================================== 4. ANALIZ (INSIGHTS) YOLU
async def test_analiz_yorumu_onaysiz_buluta_gitmez(
    client: AsyncClient, admin_headers, harici_saglayici_hazir, cagri_kaydi
) -> None:
    """`/insights` yolunda hicbir onay kapisi YOKTU.

    `use_llm=true` ile parti/lab degerleri dogrudan buluta gonderiliyordu.
    Sayisal cekirdek onaysiz da calismaya devam etmelidir.
    """
    yanit = await client.post(
        "/api/v1/ai/insights",
        headers=admin_headers,
        json={"kind": "rapor", "use_llm": True, "provider_key": "anthropic"},
    )
    assert yanit.status_code == 200, yanit.text
    assert _harici_cagri(cagri_kaydi) == [], (
        "Analiz yorumu onay alinmadan harici saglayiciya gonderildi."
    )
    # Ozellik calismaya devam eder: sayisal sonuc uretilir
    assert yanit.json()["summary"]


async def test_analiz_yorumu_onayla_gonderilir(
    client: AsyncClient, admin_headers, harici_saglayici_hazir, cagri_kaydi
) -> None:
    yanit = await client.post(
        "/api/v1/ai/insights",
        headers=admin_headers,
        json={
            "kind": "rapor",
            "use_llm": True,
            "provider_key": "anthropic",
            "confirm_external_share": True,
        },
    )
    assert yanit.status_code == 200, yanit.text
    assert len(_harici_cagri(cagri_kaydi)) == 1
