"""Hiz sinirlama kapsamlandirmasi testleri.

Kritik gerileme: `/auth/me` her sayfa yuklemesinde cagrilan bir OKUMA ucudur.
Kaba kuvvet korumasi icin ayrilan kati `RATE_LIMIT_AUTH_PER_MINUTE` sinirina
dahil edilirse, sayfayi birkac kez yenileyen normal bir kullanici API'den
kilitlenir. Kati sinir yalnizca kimlik bilgisi dogrulayan uclara uygulanmali.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.ratelimit import SlidingWindowLimiter, _client_key, _limit_for

ONEK = settings.API_V1_PREFIX


@pytest.mark.parametrize(
    "yol",
    [f"{ONEK}/auth/login", f"{ONEK}/auth/refresh", f"{ONEK}/auth/change-password"],
)
def test_kimlik_uclari_kati_sinira_tabi(yol: str) -> None:
    assert _limit_for(yol) == settings.RATE_LIMIT_AUTH_PER_MINUTE


@pytest.mark.parametrize("yol", [f"{ONEK}/auth/me", f"{ONEK}/auth/logout"])
def test_auth_okuma_uclari_kati_sinira_tabi_degil(yol: str) -> None:
    """Sayfa yenilemede cagrilan uclar varsayilan (genis) siniri kullanir."""
    assert _limit_for(yol) == settings.RATE_LIMIT_DEFAULT_PER_MINUTE
    assert settings.RATE_LIMIT_DEFAULT_PER_MINUTE > settings.RATE_LIMIT_AUTH_PER_MINUTE


@pytest.mark.parametrize("yol", [f"{ONEK}/ai/chat", f"{ONEK}/terminal/run"])
def test_ai_uclari_ai_sinirini_kullanir(yol: str) -> None:
    assert _limit_for(yol) == settings.RATE_LIMIT_AI_PER_MINUTE


def test_varsayilan_sinir_diger_modullerde() -> None:
    assert _limit_for(f"{ONEK}/tanks") == settings.RATE_LIMIT_DEFAULT_PER_MINUTE


class _SahteIstemci:
    def __init__(self, host: str) -> None:
        self.host = host


class _SahteURL:
    def __init__(self, path: str) -> None:
        self.path = path


class _SahteIstek:
    """Sayac anahtari icin gereken en kucuk Request yuzeyi."""

    def __init__(self, yol: str, ip: str = "10.0.0.1", iletilen: str | None = None) -> None:
        self.url = _SahteURL(yol)
        self.client = _SahteIstemci(ip)
        self.headers = {"x-forwarded-for": iletilen} if iletilen else {}


def test_farkli_moduller_ayri_sayac_kullanir() -> None:
    """Tanklarda yogun kullanim, laboratuvar isteklerini engellememeli."""
    assert _client_key(_SahteIstek(f"{ONEK}/tanks")) != _client_key(
        _SahteIstek(f"{ONEK}/lab-samples")
    )


def test_ayni_modulun_alt_yollari_ayni_sayaci_paylasir() -> None:
    assert _client_key(_SahteIstek(f"{ONEK}/tanks")) == _client_key(
        _SahteIstek(f"{ONEK}/tanks/5/transfer")
    )


def test_login_ve_me_ayri_sayaclarda() -> None:
    """Ayni /auth grubunda olsalar da sinirlari farkli oldugu icin ayrilirlar."""
    assert _client_key(_SahteIstek(f"{ONEK}/auth/login")) != _client_key(
        _SahteIstek(f"{ONEK}/auth/me")
    )


def test_farkli_ip_farkli_sayac() -> None:
    a = _client_key(_SahteIstek(f"{ONEK}/tanks", ip="10.0.0.1"))
    b = _client_key(_SahteIstek(f"{ONEK}/tanks", ip="10.0.0.2"))
    assert a != b


def test_x_forwarded_for_ilk_adresi_kullanilir() -> None:
    anahtar = _client_key(_SahteIstek(f"{ONEK}/tanks", iletilen="203.0.113.5, 10.0.0.9"))
    assert "203.0.113.5" in anahtar
    assert "10.0.0.9" not in anahtar


def test_sayfa_yenileme_senaryosu_engellenmez() -> None:
    """20 kez sayfa yenileme (her biri /auth/me) sinira takilmamali."""
    limiter = SlidingWindowLimiter()
    yol = f"{ONEK}/auth/me"
    anahtar = _client_key(_SahteIstek(yol))
    for _ in range(20):
        izin, _kalan, _sifir = limiter.check(anahtar, _limit_for(yol))
        assert izin, "Sayfa yenilemesi hiz sinirina takildi"


def test_kaba_kuvvet_giris_denemesi_engellenir() -> None:
    """Ard arda giris denemeleri kati sinira takilmali."""
    limiter = SlidingWindowLimiter()
    yol = f"{ONEK}/auth/login"
    anahtar = _client_key(_SahteIstek(yol))
    sinir = _limit_for(yol)
    for _ in range(sinir):
        assert limiter.check(anahtar, sinir)[0]
    izin, kalan, sifirlanma = limiter.check(anahtar, sinir)
    assert not izin
    assert kalan == 0
    assert 0 < sifirlanma <= 60
