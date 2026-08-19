"""NVIDIA Build (integrate.api.nvidia.com) saglayicisi.

NVIDIA'nin cikarim uc noktasi OpenAI uyumludur; bu nedenle ortak istemci
kullanilir. Anahtar `nvapi-` onekiyle baslar ve YALNIZCA sifreli olarak
saklanir; loglarda maskelenir.
"""

from __future__ import annotations

from app.services.ai.base import ProviderSettings
from app.services.ai.openai_compat import OpenAICompatProvider


class NvidiaProvider(OpenAICompatProvider):
    kind = "nvidia"
    requires_api_key = True
    is_external = True

    def __init__(self, settings: ProviderSettings):
        if not settings.base_url:
            settings.base_url = "https://integrate.api.nvidia.com/v1"
        super().__init__(settings)

    def missing_config_message(self) -> str:
        if not self.settings.api_key:
            return (
                "NVIDIA Build API anahtarı tanımlı değil. build.nvidia.com adresinden "
                "hesabınıza girip bir model kartındaki 'Get API Key' düğmesiyle anahtar "
                "oluşturun, ardından Ayarlar → Yapay Zekâ Sağlayıcıları ekranından girin. "
                "Anahtar şifrelenerek saklanır ve hiçbir yerde açık gösterilmez."
            )
        return super().missing_config_message()
