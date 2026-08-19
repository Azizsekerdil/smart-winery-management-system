"""Veritabaninda saklanan gizli degerlerin (API anahtarlari) sifrelenmesi.

Amac: 15. maddedeki "API anahtarlarini veritabaninda duz metin saklama" kurali.
Yontem: Fernet (AES-128-CBC + HMAC-SHA256), anahtar SECRETS_ENCRYPTION_KEY'den
HKDF ile turetilir; ana anahtar hicbir zaman diske yazilmaz.
"""

from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings

_INFO = b"saraphane-yonetim/secret-store/v1"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_INFO,
    )
    derived = hkdf.derive(settings.SECRETS_ENCRYPTION_KEY.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(plain: str) -> str:
    """Duz metni sifreler; bos deger bos doner."""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    """Sifreli degeri cozer. Cozulemezse bos string doner (sessiz bozulma yok:
    cagirici bos degeri 'anahtar yok' olarak degerlendirir)."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        return ""


def mask_secret(value: str, *, keep: int = 4) -> str:
    """Arayuzde/loglarda gosterim icin maskeler: 'sk-ant-...9f2a' -> '****9f2a'."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * max(8, len(value) - keep) + value[-keep:]


def secret_fingerprint(value: str) -> str:
    """Anahtarin kendisini acmadan 'ayni anahtar mi' karsilastirmasi icin
    kisa parmak izi. Geri donusturulemez."""
    if not value:
        return ""
    digest = hashes.Hash(hashes.SHA256())
    digest.update(_INFO)
    digest.update(value.encode("utf-8"))
    return digest.finalize().hex()[:12]
