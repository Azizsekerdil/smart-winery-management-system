"""Saglayici kayit defteri, gorev bazli yonlendirme ve guvenli geri donus.

Sorumluluklar:
  * Veritabanindaki `AIProviderConfig` kayitlarindan saglayici nesneleri kurmak
  * Ilk calistirmada .env ayarlarindan varsayilan kayitlari olusturmak
  * Gorev turune gore model/saglayici secmek
  * Bir saglayici kapaliysa oncelik sirasina gore GUVENLI geri donus yapmak
  * Kullanim/maliyet kaydini tutmak
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret, secret_fingerprint
from app.core.logging import get_logger, scrub
from app.models.ai import AIProviderConfig, AITaskKind, AIUsageLog, PrivacyLevel
from app.services.ai.anthropic import AnthropicProvider
from app.services.ai.base import (
    AIProvider,
    ChatMessage,
    ChatResult,
    ProviderError,
    ProviderSettings,
)
from app.services.ai.lmstudio import LMStudioProvider
from app.services.ai.nvidia import NvidiaProvider
from app.services.ai.openai_compat import OpenAICompatProvider

log = get_logger("ai.registry")

PROVIDER_CLASSES: dict[str, type[AIProvider]] = {
    "lmstudio": LMStudioProvider,
    "anthropic": AnthropicProvider,
    "nvidia": NvidiaProvider,
    "openai_compat": OpenAICompatProvider,
}

# Gorev -> tercih edilen saglayici sirasi.
# Hassas veri iceren gorevler once YEREL saglayiciya yonlendirilir (madde 11).
TASK_PROVIDER_PREFERENCE: dict[str, list[str]] = {
    AITaskKind.SARAPHANE_DANISMANI: ["lmstudio", "anthropic", "nvidia"],
    AITaskKind.VERI_ANALISTI: ["lmstudio", "anthropic", "nvidia"],
    AITaskKind.KALITE_KONTROL: ["lmstudio", "anthropic", "nvidia"],
    AITaskKind.RAPOR_YAZARI: ["lmstudio", "anthropic", "nvidia"],
    AITaskKind.KOD_GELISTIRICI: ["anthropic", "nvidia", "lmstudio"],
    AITaskKind.HATA_TESHIS: ["anthropic", "nvidia", "lmstudio"],
    AITaskKind.DOKUMANTASYON: ["lmstudio", "anthropic", "nvidia"],
    AITaskKind.GENEL: ["lmstudio", "anthropic", "nvidia"],
}

TASK_LABELS_TR: dict[str, str] = {
    AITaskKind.SARAPHANE_DANISMANI: "Şaraphane danışmanı",
    AITaskKind.VERI_ANALISTI: "Veri analisti",
    AITaskKind.RAPOR_YAZARI: "Rapor yazarı",
    AITaskKind.KALITE_KONTROL: "Kalite kontrol yardımcısı",
    AITaskKind.KOD_GELISTIRICI: "Kod geliştirici",
    AITaskKind.HATA_TESHIS: "Hata teşhis uzmanı",
    AITaskKind.DOKUMANTASYON: "Dokümantasyon yazarı",
    AITaskKind.GENEL: "Genel",
}

DEFAULT_PROVIDERS: list[dict[str, Any]] = [
    {
        "provider_key": "lmstudio",
        "display_name": "LM Studio (Yerel)",
        "kind": "lmstudio",
        "base_url": settings.LMSTUDIO_BASE_URL,
        "default_model": settings.LMSTUDIO_MODEL,
        "privacy_level": PrivacyLevel.YEREL_ONLY,
        "priority": 10,
        "enabled": settings.LMSTUDIO_ENABLED,
        "supports_streaming": True,
        "notes": "Veriler bilgisayardan çıkmaz. Hassas şaraphane verisi için tercih edilir.",
    },
    {
        "provider_key": "anthropic",
        "display_name": "Claude (Anthropic)",
        "kind": "anthropic",
        "base_url": settings.ANTHROPIC_BASE_URL,
        "default_model": settings.ANTHROPIC_MODEL,
        "privacy_level": PrivacyLevel.HERKESE_ACIK,
        "priority": 20,
        "enabled": settings.ANTHROPIC_ENABLED,
        "supports_streaming": True,
        "supports_tools": True,
        "notes": "Bulut sağlayıcı. Gönderilecek veri kapsamı işlem öncesi gösterilir.",
    },
    {
        "provider_key": "nvidia",
        "display_name": "NVIDIA Build",
        "kind": "nvidia",
        "base_url": settings.NVIDIA_BASE_URL,
        "default_model": settings.NVIDIA_MODEL,
        "privacy_level": PrivacyLevel.HERKESE_ACIK,
        "priority": 30,
        "enabled": settings.NVIDIA_ENABLED,
        "supports_streaming": True,
        "notes": "OpenAI uyumlu bulut çıkarım servisi (build.nvidia.com).",
    },
]


@dataclass(slots=True)
class ResolvedProvider:
    provider: AIProvider
    config: AIProviderConfig
    model: str
    fallback_used: bool = False
    fallback_note: str | None = None


async def ensure_default_configs(session: AsyncSession) -> None:
    """Ilk calistirmada varsayilan saglayici kayitlarini olusturur."""
    existing = {
        c.provider_key
        for c in (await session.execute(select(AIProviderConfig))).scalars().all()
    }
    env_keys = {
        "anthropic": settings.ANTHROPIC_API_KEY,
        "nvidia": settings.NVIDIA_API_KEY,
        "openai_compat": settings.OPENAI_COMPAT_API_KEY,
    }
    created = False
    for spec in DEFAULT_PROVIDERS:
        if spec["provider_key"] in existing:
            continue
        raw_key = env_keys.get(spec["provider_key"], "")
        config = AIProviderConfig(
            **spec,
            timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
            api_key_encrypted=encrypt_secret(raw_key) if raw_key else "",
            api_key_fingerprint=secret_fingerprint(raw_key) if raw_key else "",
        )
        session.add(config)
        created = True

    if settings.OPENAI_COMPAT_ENABLED and "openai_compat" not in existing:
        session.add(
            AIProviderConfig(
                provider_key="openai_compat",
                display_name=settings.OPENAI_COMPAT_NAME,
                kind="openai_compat",
                base_url=settings.OPENAI_COMPAT_BASE_URL,
                default_model=settings.OPENAI_COMPAT_MODEL,
                privacy_level=PrivacyLevel.HERKESE_ACIK,
                priority=40,
                enabled=True,
                api_key_encrypted=encrypt_secret(settings.OPENAI_COMPAT_API_KEY)
                if settings.OPENAI_COMPAT_API_KEY
                else "",
                api_key_fingerprint=secret_fingerprint(settings.OPENAI_COMPAT_API_KEY),
            )
        )
        created = True

    if created:
        await session.commit()


def build_provider(config: AIProviderConfig) -> AIProvider:
    """Veritabani kaydindan saglayici nesnesi olusturur."""
    cls = PROVIDER_CLASSES.get(config.kind, OpenAICompatProvider)
    api_key = decrypt_secret(config.api_key_encrypted or "")
    return cls(
        ProviderSettings(
            key=config.provider_key,
            display_name=config.display_name,
            base_url=config.base_url,
            api_key=api_key,
            default_model=config.default_model,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.max_retries,
            privacy_level=config.privacy_level,
            input_cost_per_1k=float(config.input_cost_per_1k or 0),
            output_cost_per_1k=float(config.output_cost_per_1k or 0),
            currency=config.currency,
        )
    )


async def get_config(session: AsyncSession, provider_key: str) -> AIProviderConfig | None:
    return (
        await session.execute(
            select(AIProviderConfig).where(AIProviderConfig.provider_key == provider_key)
        )
    ).scalar_one_or_none()


async def list_configs(session: AsyncSession) -> list[AIProviderConfig]:
    return list(
        (
            await session.execute(
                select(AIProviderConfig).order_by(AIProviderConfig.priority, AIProviderConfig.id)
            )
        )
        .scalars()
        .all()
    )


def model_for_task(config: AIProviderConfig, task_kind: str) -> str:
    """Gorev bazli model esleme tablosundan model secer; yoksa varsayilani kullanir."""
    mapping = config.task_model_map or {}
    return mapping.get(task_kind) or config.default_model


async def resolve(
    session: AsyncSession,
    *,
    provider_key: str | None = None,
    model: str | None = None,
    task_kind: str = AITaskKind.GENEL,
    allow_fallback: bool = True,
    allow_external: bool = True,
    exclude: set[str] | None = None,
) -> ResolvedProvider:
    """Istenen saglayiciyi cozer; kapaliysa oncelik sirasina gore geri doner.

    `allow_external=False` verildiginde saraphane disina veri gonderen
    saglayicilar HIC denenmez. Bu, kullanicinin harici paylasimi onaylamadigi
    durumlarda sessiz bir yerel -> bulut gecisini kod duzeyinde engeller
    (yalnizca arayuz uyarisi degil).
    """
    configs = {c.provider_key: c for c in await list_configs(session)}
    if not configs:
        await ensure_default_configs(session)
        configs = {c.provider_key: c for c in await list_configs(session)}

    order: list[str] = []
    if provider_key:
        order.append(provider_key)
    order.extend(TASK_PROVIDER_PREFERENCE.get(task_kind, []))
    if settings.AI_DEFAULT_PROVIDER not in order:
        order.append(settings.AI_DEFAULT_PROVIDER)
    for key in configs:
        if key not in order:
            order.append(key)

    tried: list[str] = []
    first_error: str | None = None
    exclude = exclude or set()

    for index, key in enumerate(order):
        config = configs.get(key)
        if config is None or not config.enabled:
            continue
        # Zaten denenip basarisiz olmus saglayici tekrar secilmez. Bu satir
        # olmadan geri donus zinciri ilk saglayiciyi yeniden secip donguyu
        # kirdigi icin IKINCI saglayici hicbir zaman denenmiyordu.
        if key in exclude:
            continue
        provider = build_provider(config)
        if provider.is_external and not allow_external:
            tried.append(
                f"{config.display_name}: harici saglayici, kullanici onayi yok "
                "(confirm_external_share=false)"
            )
            continue
        if not provider.is_configured:
            tried.append(f"{config.display_name}: {provider.missing_config_message()}")
            first_error = first_error or provider.missing_config_message()
            if not allow_fallback and index == 0:
                raise ProviderError(provider.missing_config_message(), kind="yapilandirma")
            continue

        chosen_model = model if (model and (index == 0 and provider_key)) else model_for_task(
            config, task_kind
        )
        if not chosen_model:
            chosen_model = model or ""
        if not chosen_model:
            tried.append(f"{config.display_name}: model seçilmemiş")
            continue

        fallback = bool(provider_key) and key != provider_key
        note = None
        if fallback:
            note = (
                f"İstenen sağlayıcı ({provider_key}) kullanılamadı; "
                f"{config.display_name} sağlayıcısına geçildi. "
                + (tried[0] if tried else "")
            )
        return ResolvedProvider(
            provider=provider,
            config=config,
            model=chosen_model,
            fallback_used=fallback,
            fallback_note=note,
        )

    detail = " | ".join(tried) if tried else "Etkin sağlayıcı bulunamadı."
    if not allow_external:
        raise ProviderError(
            "Kullanılabilir YEREL yapay zekâ sağlayıcısı yok ve harici sağlayıcıya "
            "veri gönderimi onaylanmadı. Yerel modeli (LM Studio) çalıştırın veya "
            "veri kapsamını onaylayın. " + detail,
            kind="onay_gerekli",
        )
    raise ProviderError(
        "Kullanılabilir yapay zekâ sağlayıcısı yok. " + detail,
        kind="saglayici_yok",
    )


async def record_usage(
    session: AsyncSession,
    *,
    provider_key: str,
    model: str,
    task_kind: str,
    user_id: int | None,
    conversation_id: int | None,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float,
    currency: str,
    latency_ms: int | None,
    success: bool,
    error_type: str | None = None,
    error_message: str | None = None,
) -> AIUsageLog:
    entry = AIUsageLog(
        provider_key=provider_key,
        model=model,
        task_kind=task_kind,
        user_id=user_id,
        conversation_id=conversation_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        currency=currency,
        latency_ms=latency_ms,
        success=success,
        error_type=error_type,
        error_message=scrub(error_message) if error_message else None,
    )
    session.add(entry)
    return entry


async def chat_with_fallback(
    session: AsyncSession,
    messages: list[ChatMessage],
    *,
    provider_key: str | None = None,
    model: str | None = None,
    task_kind: str = AITaskKind.GENEL,
    temperature: float = 0.4,
    max_tokens: int = 1600,
    user_id: int | None = None,
    conversation_id: int | None = None,
    allow_fallback: bool = True,
    allow_external: bool = True,
    **kwargs: Any,
) -> tuple[ChatResult, ResolvedProvider]:
    """Cozumleme + cagri + kullanim kaydi. Hata halinde siradaki saglayiciya gecer.

    GUVENLIK: `allow_external=False` ise geri donus zinciri HICBIR asamada
    saraphane disina veri gonderen bir saglayiciya gecemez. Aksi halde
    kullanicinin "yerel model" secimi, yerel model yanit vermedigi anda
    sessizce bir bulut saglayicisina donusurdu ve onaylanmamis veri disari
    cikardi.
    """
    attempted: list[str] = []
    current_key = provider_key
    last_error: ProviderError | None = None

    for _ in range(3):  # en fazla 3 saglayici denenir
        try:
            resolved = await resolve(
                session,
                provider_key=current_key,
                model=model,
                task_kind=task_kind,
                allow_fallback=allow_fallback,
                allow_external=allow_external,
                exclude=set(attempted),
            )
        except ProviderError:
            # Denenmemis baska saglayici kalmadi; ilk gercek hatayi bildir.
            if last_error is not None:
                raise last_error from None
            raise
        attempted.append(resolved.config.provider_key)

        try:
            result = await resolved.provider.chat(
                messages,
                model=resolved.model,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except ProviderError as exc:
            last_error = exc
            await record_usage(
                session,
                provider_key=resolved.config.provider_key,
                model=resolved.model,
                task_kind=task_kind,
                user_id=user_id,
                conversation_id=conversation_id,
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.0,
                currency=resolved.config.currency,
                latency_ms=None,
                success=False,
                error_type=exc.kind,
                error_message=exc.safe_message,
            )
            resolved.config.last_status = "hata"
            resolved.config.last_error = exc.safe_message
            resolved.config.last_checked_at = dt.datetime.now(dt.UTC)
            await session.flush()

            if not allow_fallback:
                raise
            current_key = None  # sonraki tercih sirasindan devam et
            continue

        cost = resolved.provider.estimate_cost(result.input_tokens, result.output_tokens)
        await record_usage(
            session,
            provider_key=resolved.config.provider_key,
            model=result.model,
            task_kind=task_kind,
            user_id=user_id,
            conversation_id=conversation_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=cost,
            currency=resolved.config.currency,
            latency_ms=result.latency_ms,
            success=True,
        )
        resolved.config.last_status = "cevrimici"
        resolved.config.last_error = None
        resolved.config.last_latency_ms = result.latency_ms
        resolved.config.last_checked_at = dt.datetime.now(dt.UTC)

        if len(attempted) > 1:
            resolved.fallback_used = True
            resolved.fallback_note = (
                f"İlk tercih edilen sağlayıcı yanıt vermedi; "
                f"{resolved.config.display_name} kullanıldı."
                + (f" ({last_error.safe_message})" if last_error else "")
            )
        await session.flush()
        return result, resolved

    raise last_error or ProviderError(
        "Hiçbir yapay zekâ sağlayıcısı yanıt vermedi.", kind="saglayici_yok"
    )
