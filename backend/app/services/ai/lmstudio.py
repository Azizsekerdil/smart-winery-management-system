"""LM Studio yerel saglayicisi (OpenAI uyumlu, http://localhost:1234/v1).

Farklari:
  * API anahtari gerektirmez
  * Veri makineden CIKMAZ -> gizlilik seviyesi 'yerel_only'
  * Sunucu kapaliyken uygulama COKMEZ; anlasilir Turkce uyari doner
"""

from __future__ import annotations

from app.services.ai.base import ProviderSettings, ProviderUnavailable
from app.services.ai.openai_compat import OpenAICompatProvider


class LMStudioProvider(OpenAICompatProvider):
    kind = "lmstudio"
    requires_api_key = False
    is_external = False

    def __init__(self, settings: ProviderSettings):
        super().__init__(settings)
        self.settings.privacy_level = "yerel_only"

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.base_url)

    def missing_config_message(self) -> str:
        if not self.settings.base_url:
            return (
                "LM Studio sunucu adresi tanımlı değil. Varsayılan: "
                "http://localhost:1234/v1"
            )
        return ""

    async def health_check(self) -> dict:
        result = await super().health_check()
        if not result["ok"]:
            result["message"] = (
                "LM Studio sunucusuna ulaşılamadı. Lütfen LM Studio uygulamasını açıp "
                "'Developer' (Geliştirici) sekmesinden yerel sunucuyu başlatın "
                f"({self.settings.base_url}). Uygulamanın diğer bölümleri normal çalışmaya "
                "devam eder. — " + result["message"]
            )
        return result

    async def ensure_available(self) -> None:
        result = await self.health_check()
        if not result["ok"]:
            raise ProviderUnavailable(result["message"])
