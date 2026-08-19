"""Yapay zeka saglayici katmani.

Uygulama kodu HICBIR zaman belirli bir saglayiciya dogrudan bagli degildir;
her sey `AIProvider` soyutlamasi uzerinden yurur (bkz. base.py).
"""

from app.services.ai.base import (
    AIProvider,
    ChatMessage,
    ChatResult,
    ModelDescriptor,
    ProviderAuthError,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
)

__all__ = [
    "AIProvider",
    "ChatMessage",
    "ChatResult",
    "ModelDescriptor",
    "ProviderAuthError",
    "ProviderError",
    "ProviderTimeout",
    "ProviderUnavailable",
]
