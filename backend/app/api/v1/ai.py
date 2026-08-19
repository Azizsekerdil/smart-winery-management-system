"""Yapay Zekâ Çalışma Merkezi uç noktaları."""

from __future__ import annotations

import datetime as dt
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.crud import get_or_404
from app.core.audit import record_audit
from app.core.config import settings
from app.core.crypto import encrypt_secret, mask_secret, secret_fingerprint
from app.core.deps import SessionDep, require_perms
from app.core.permissions import Perm
from app.models.ai import (
    AIConversation,
    AIMessage,
    AIProviderConfig,
    AITaskKind,
    AIUsageLog,
)
from app.models.ops import AuditAction
from app.models.user import User
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    ConversationOut,
    DataScopePreview,
    InsightOut,
    InsightRequest,
    MessageOut,
    ModelInfo,
    ProviderKeyUpdate,
    ProviderModels,
    ProviderOut,
    ProviderTestResult,
    ProviderUpdate,
    RagIndexRequest,
    RagSearchRequest,
    RagSearchResponse,
    UsageReport,
    UsageSummary,
)
from app.schemas.common import Message
from app.services.ai import insights as ai_insights
from app.services.ai import rag as ai_rag
from app.services.ai.base import ChatMessage, ProviderError
from app.services.ai.context import PRIVACY_WARNINGS, build_context
from app.services.ai.prompts import system_prompt
from app.services.ai.registry import (
    TASK_LABELS_TR,
    build_provider,
    chat_with_fallback,
    ensure_default_configs,
    get_config,
    list_configs,
    record_usage,
    resolve,
)

router = APIRouter(prefix="/ai", tags=["Yapay Zekâ"])

UseAI = Annotated[User, Depends(require_perms(Perm.AI_USE))]
ConfigAI = Annotated[User, Depends(require_perms(Perm.AI_CONFIGURE))]


def _provider_out(config: AIProviderConfig) -> ProviderOut:
    provider = build_provider(config)
    out = ProviderOut.model_validate(config)
    out.has_api_key = bool(config.api_key_encrypted)
    # Anahtarin KENDISI asla donmez; yalnizca maskeli gosterim ve parmak izi
    out.api_key_masked = mask_secret("x" * 24 + (config.api_key_fingerprint or "")[:4]) if config.api_key_encrypted else ""
    out.api_key_fingerprint = config.api_key_fingerprint or ""
    out.requires_api_key = provider.requires_api_key
    return out


# ---------------------------------------------------------------- SAGLAYICI
@router.get("/providers", response_model=list[ProviderOut], summary="Sağlayıcı listesi")
async def get_providers(session: SessionDep, _user: UseAI) -> list[ProviderOut]:
    await ensure_default_configs(session)
    return [_provider_out(c) for c in await list_configs(session)]


@router.get("/providers/{provider_key}", response_model=ProviderOut, summary="Sağlayıcı detayı")
async def get_provider(provider_key: str, session: SessionDep, _user: UseAI) -> ProviderOut:
    config = await get_config(session, provider_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {provider_key}")
    return _provider_out(config)


@router.patch("/providers/{provider_key}", response_model=ProviderOut, summary="Sağlayıcı ayarla")
async def update_provider(
    provider_key: str,
    payload: ProviderUpdate,
    request: Request,
    session: SessionDep,
    user: ConfigAI,
) -> ProviderOut:
    config = await get_config(session, provider_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {provider_key}")

    before = config.to_dict(exclude={"api_key_encrypted"})
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(config, k, v)

    await record_audit(
        session,
        action=AuditAction.AYAR_DEGISIKLIGI,
        entity_type="ai_provider_configs",
        entity_id=config.id,
        entity_code=provider_key,
        summary=f"Yapay zekâ sağlayıcı ayarı güncellendi: {provider_key}",
        before=before,
        after=config.to_dict(exclude={"api_key_encrypted"}),
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    await session.refresh(config)
    return _provider_out(config)


@router.put(
    "/providers/{provider_key}/api-key",
    response_model=Message,
    summary="API anahtarını kaydet (yalnızca yazılır, hiçbir uçtan okunamaz)",
)
async def set_api_key(
    provider_key: str,
    payload: ProviderKeyUpdate,
    request: Request,
    session: SessionDep,
    user: ConfigAI,
) -> Message:
    config = await get_config(session, provider_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {provider_key}")

    raw = payload.api_key.strip()
    config.api_key_encrypted = encrypt_secret(raw)
    config.api_key_fingerprint = secret_fingerprint(raw)
    config.last_status = "bilinmiyor"
    config.last_error = None

    await record_audit(
        session,
        action=AuditAction.AYAR_DEGISIKLIGI,
        entity_type="ai_provider_configs",
        entity_id=config.id,
        entity_code=provider_key,
        summary=f"{provider_key} için API anahtarı güncellendi "
        f"(parmak izi {config.api_key_fingerprint})",
        after={"api_key": "***GIZLI***", "fingerprint": config.api_key_fingerprint},
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(
        detail=(
            f"{config.display_name} API anahtarı şifrelenerek kaydedildi. "
            "Anahtar hiçbir ekranda veya günlükte açık gösterilmez."
        )
    )


@router.delete(
    "/providers/{provider_key}/api-key", response_model=Message, summary="API anahtarını sil"
)
async def delete_api_key(
    provider_key: str, request: Request, session: SessionDep, user: ConfigAI
) -> Message:
    config = await get_config(session, provider_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {provider_key}")
    config.api_key_encrypted = ""
    config.api_key_fingerprint = ""
    config.last_status = "bilinmiyor"
    await record_audit(
        session,
        action=AuditAction.AYAR_DEGISIKLIGI,
        entity_type="ai_provider_configs",
        entity_id=config.id,
        entity_code=provider_key,
        summary=f"{provider_key} API anahtarı silindi",
        user=user,
        request=request,
        severity="uyari",
    )
    await session.commit()
    return Message(detail="API anahtarı silindi.")


@router.post(
    "/providers/{provider_key}/test",
    response_model=ProviderTestResult,
    summary="Bağlantı testi (küçük, düşük maliyetli)",
)
async def test_provider(
    provider_key: str,
    request: Request,
    session: SessionDep,
    user: UseAI,
    with_chat: bool = Query(
        False,
        description="Model listesine ek olarak çok kısa bir sohbet isteği de gönder "
        "(bulut sağlayıcılarda küçük bir ücret doğurabilir)",
    ),
) -> ProviderTestResult:
    config = await get_config(session, provider_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {provider_key}")

    provider = build_provider(config)
    health = await provider.health_check()

    sample: str | None = None
    if health["ok"] and with_chat:
        try:
            result = await provider.chat(
                [
                    ChatMessage("system", "Yalnızca 'BAĞLANTI TAMAM' yaz."),
                    ChatMessage("user", "Test"),
                ],
                model=config.default_model or health.get("model"),
                temperature=0.0,
                # Akıl yürütme modelleri görünür yanıttan ÖNCE düşünce üretir;
                # çok düşük bir sınır testin "başarısız" görünmesine yol açar.
                # 512 belirteç hem bu modeller için yeterli hem de maliyeti ihmal
                # edilebilir düzeydedir.
                max_tokens=512,
            )
            sample = result.content[:200]
            await record_usage(
                session,
                provider_key=provider_key,
                model=result.model,
                task_kind=AITaskKind.GENEL,
                user_id=user.id,
                conversation_id=None,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                estimated_cost=provider.estimate_cost(result.input_tokens, result.output_tokens),
                currency=config.currency,
                latency_ms=result.latency_ms,
                success=True,
            )
        except ProviderError as exc:
            health["ok"] = False
            health["status"] = exc.kind
            health["message"] = exc.safe_message

    config.last_status = "cevrimici" if health["ok"] else health["status"]
    config.last_checked_at = dt.datetime.now(dt.UTC)
    config.last_latency_ms = health.get("latency_ms")
    config.last_error = None if health["ok"] else health["message"]

    await record_audit(
        session,
        action=AuditAction.AI_ISTEK,
        entity_type="ai_provider_configs",
        entity_id=config.id,
        entity_code=provider_key,
        summary=f"Bağlantı testi: {provider_key} → {'başarılı' if health['ok'] else 'başarısız'}",
        user=user,
        request=request,
        ai_provider=provider_key,
    )
    await session.commit()

    return ProviderTestResult(
        provider_key=provider_key,
        ok=health["ok"],
        status=health["status"],
        latency_ms=health.get("latency_ms"),
        model=health.get("model"),
        message=health["message"],
        sample_response=sample,
        models_found=health.get("models_found", 0),
    )


@router.get(
    "/providers/{provider_key}/models", response_model=ProviderModels, summary="Model listesi"
)
async def provider_models(
    provider_key: str,
    session: SessionDep,
    _user: UseAI,
    refresh: bool = Query(False, description="Önbelleği yok say, sağlayıcıdan yeniden çek"),
) -> ProviderModels:
    config = await get_config(session, provider_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {provider_key}")

    if not refresh and config.cached_models and config.models_fetched_at:
        age = dt.datetime.now(dt.UTC) - (
            config.models_fetched_at
            if config.models_fetched_at.tzinfo
            else config.models_fetched_at.replace(tzinfo=dt.UTC)
        )
        if age < dt.timedelta(hours=6):
            return ProviderModels(
                provider_key=provider_key,
                models=[ModelInfo(**m) for m in config.cached_models],
                fetched_at=config.models_fetched_at,
                cached=True,
            )

    provider = build_provider(config)
    try:
        models = await provider.list_models()
    except ProviderError as exc:
        config.last_status = exc.kind
        config.last_error = exc.safe_message
        config.last_checked_at = dt.datetime.now(dt.UTC)
        await session.commit()
        return ProviderModels(
            provider_key=provider_key,
            models=[ModelInfo(**m) for m in (config.cached_models or [])],
            fetched_at=config.models_fetched_at or dt.datetime.now(dt.UTC),
            cached=True,
            warning=exc.safe_message,
        )

    infos = [
        ModelInfo(
            id=m.id,
            label=m.label or m.id,
            owned_by=m.owned_by,
            context_length=m.context_length,
        )
        for m in models
    ]
    config.cached_models = [m.model_dump() for m in infos]
    config.models_fetched_at = dt.datetime.now(dt.UTC)
    config.last_status = "cevrimici"
    config.last_error = None
    await session.commit()

    return ProviderModels(
        provider_key=provider_key,
        models=infos,
        fetched_at=config.models_fetched_at,
        cached=False,
    )


@router.get("/task-kinds", summary="Görev türleri")
async def task_kinds(_user: UseAI) -> list[dict]:
    return [{"kod": k, "ad": v} for k, v in TASK_LABELS_TR.items()]


# ------------------------------------------------------------ VERI KAPSAMI
@router.post(
    "/data-scope-preview",
    response_model=DataScopePreview,
    summary="Gönderilecek veri kapsamını önizle (dış sağlayıcı öncesi zorunlu adım)",
)
async def data_scope_preview(
    payload: ChatRequest, session: SessionDep, _user: UseAI
) -> DataScopePreview:
    """Onizleme, saglayici HENUZ yapilandirilmamis olsa da calisir.

    Amaci "hangi saglayiciya hangi veri gidecek" sorusunu yanitlamaktir; model
    veya anahtar eksikligi bu bilgiyi gostermeye engel olmamalidir.
    """
    key = payload.provider_key or settings.AI_DEFAULT_PROVIDER
    config = await get_config(session, key)
    if config is None:
        await ensure_default_configs(session)
        config = await get_config(session, key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Sağlayıcı bulunamadı: {key}")

    provider = build_provider(config)
    ctx = await build_context(
        session,
        lot_ids=payload.context_lot_ids,
        fermentation_ids=payload.context_fermentation_ids,
        include_dashboard=payload.include_dashboard,
    )

    warning = PRIVACY_WARNINGS.get(config.privacy_level)
    if not provider.is_configured:
        warning = (
            f"{provider.missing_config_message()} "
            f"(Veri kapsamı bilgilendirme amaçlı gösterilmektedir.) "
            + (warning or "")
        ).strip()

    return DataScopePreview(
        provider_key=config.provider_key,
        provider_name=config.display_name,
        privacy_level=config.privacy_level,
        is_external=provider.is_external,
        items=ctx.items,
        approx_chars=ctx.approx_chars + len(payload.message),
        warning_tr=warning,
    )


# ------------------------------------------------------------------ SOHBET
async def _prepare_chat(session, payload: ChatRequest, user: User):
    resolved = await resolve(
        session,
        provider_key=payload.provider_key,
        model=payload.model,
        task_kind=payload.task_kind,
    )
    ctx = await build_context(
        session,
        lot_ids=payload.context_lot_ids,
        fermentation_ids=payload.context_fermentation_ids,
        include_dashboard=payload.include_dashboard,
    )
    # --------------------------------------------------------------- RAG
    # Doküman araması onay kapısından ÖNCE çalıştırılır. Getirilen parçaların
    # METNİ giden isteme eklendiği için bunlar da "gönderilecek veri"dir ve
    # kapsam listesinde görünmek ZORUNDADIR. Aksi hâlde harici sağlayıcı
    # seçiliyken doküman içeriği listelenmeden ve onaylanmadan dışarı çıkardı.
    rag_text = ""
    if payload.use_rag:
        hits = await ai_rag.search(session, payload.message, top_k=4)
        if hits.hits:
            rag_text = "\n\n## İLGİLİ DOKÜMANLAR\n" + "\n\n".join(
                f"### {h.title} (parça {h.chunk_index})\n{h.content}" for h in hits.hits
            )
            for h in hits.hits:
                ctx.items.append(
                    {
                        "tur": "Doküman parçası",
                        "kod": f"{h.document_key}#{h.chunk_index}",
                        "ad": h.title,
                        "alanlar": "doküman metni (tam parça içeriği isteme eklenir)",
                    }
                )

    # ------------------------------------------------ HARİCİ PAYLAŞIM KAPISI
    # Kapı, harici sağlayıcı seçildiği ANDA çalışır; ekli kayıt olup olmaması
    # fark etmez. Kullanıcının serbest metin sorusu da şaraphane dışına çıkan
    # bir veridir ve onaysız gönderilemez.
    if resolved.provider.is_external and not payload.confirm_external_share:
        kapsam = (
            f"{len(ctx.items)} kayıt/doküman parçası ve mesaj metniniz"
            if ctx.items
            else "mesaj metniniz"
        )
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            (
                f"{resolved.config.display_name} harici bir sağlayıcıdır; {kapsam} "
                "şaraphane dışına gönderilecektir. Devam etmek için veri kapsamını "
                "onaylayın (confirm_external_share=true) veya yerel modeli "
                "(LM Studio) seçin."
            ),
        )

    conversation = None
    if payload.conversation_id:
        conversation = await session.get(AIConversation, payload.conversation_id)
        if conversation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Konuşma bulunamadı.")
    if conversation is None:
        conversation = AIConversation(
            title=payload.message[:200],
            task_kind=payload.task_kind,
            provider_key=resolved.config.provider_key,
            model=resolved.model,
            user_id=user.id,
            data_scope=ctx.items,
            data_shared_externally=resolved.provider.is_external,
            created_by_id=user.id,
        )
        session.add(conversation)
        await session.flush()

    history = list(
        (
            await session.execute(
                select(AIMessage)
                .where(AIMessage.conversation_id == conversation.id)
                .order_by(AIMessage.id)
            )
        )
        .scalars()
        .all()
    )[-14:]

    # Önceki mesajlar da giden isteme eklenir. Yerel sağlayıcıyla başlamış bir
    # konuşma harici sağlayıcıya çevrildiğinde geçmiş TAMAMEN dışarı çıkar; bu
    # yüzden geçmiş de kapsam listesine yazılır (kapı zaten yukarıda her harici
    # sağlayıcı için çalıştı).
    if history and resolved.provider.is_external:
        ctx.items.append(
            {
                "tur": "Konuşma geçmişi",
                "kod": f"konusma-{conversation.id}",
                "ad": "Önceki mesajlar",
                "alanlar": f"{len(history)} önceki mesajın tam metni",
            }
        )

    messages = [ChatMessage("system", system_prompt(payload.task_kind))]
    if ctx.text or rag_text:
        messages.append(ChatMessage("system", ctx.text + rag_text))
    for h in history:
        if h.role in ("user", "assistant") and h.content:
            messages.append(ChatMessage(h.role, h.content))
    messages.append(ChatMessage("user", payload.message))

    session.add(
        AIMessage(
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
            provider_key=resolved.config.provider_key,
            model=resolved.model,
        )
    )
    await session.flush()
    return resolved, conversation, messages, ctx


@router.post("/chat", response_model=ChatResponse, summary="Yapay zekâya görev ver")
async def chat(
    payload: ChatRequest, request: Request, session: SessionDep, user: UseAI
) -> ChatResponse:
    try:
        resolved, conversation, messages, ctx = await _prepare_chat(session, payload, user)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    try:
        result, used = await chat_with_fallback(
            session,
            messages,
            provider_key=resolved.config.provider_key,
            model=resolved.model,
            task_kind=payload.task_kind,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            user_id=user.id,
            conversation_id=conversation.id,
            # Yerel sağlayıcı yanıt vermezse geri dönüş zinciri bir bulut
            # sağlayıcısına geçebilirdi; onay yoksa bu kod düzeyinde engellenir.
            allow_external=payload.confirm_external_share,
        )
    except ProviderError as exc:
        session.add(
            AIMessage(
                conversation_id=conversation.id,
                role="assistant",
                content="",
                error=exc.safe_message,
                provider_key=resolved.config.provider_key,
            )
        )
        await session.commit()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc

    cost = used.provider.estimate_cost(result.input_tokens, result.output_tokens)
    msg = AIMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result.content,
        provider_key=used.config.provider_key,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        finish_reason=result.finish_reason,
    )
    session.add(msg)
    conversation.total_input_tokens += result.input_tokens
    conversation.total_output_tokens += result.output_tokens
    conversation.total_cost = float(conversation.total_cost or 0) + cost
    conversation.provider_key = used.config.provider_key
    conversation.model = result.model
    await session.flush()

    await record_audit(
        session,
        action=AuditAction.AI_ISTEK,
        entity_type="ai_conversations",
        entity_id=conversation.id,
        summary=(
            f"AI görevi ({payload.task_kind}): {len(ctx.items)} veri kaydı, "
            f"{result.input_tokens + result.output_tokens} token"
        ),
        after={
            "provider": used.config.provider_key,
            "model": result.model,
            "veri_kapsami": ctx.items,
            "harici_paylasim": used.provider.is_external and bool(ctx.items),
        },
        user=user,
        request=request,
        ai_provider=used.config.provider_key,
        ai_model=result.model,
    )
    await session.commit()

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=msg.id,
        provider_key=used.config.provider_key,
        model=result.model,
        content=result.content,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=result.latency_ms,
        estimated_cost=cost,
        currency=used.config.currency,
        finish_reason=result.finish_reason,
        fallback_used=used.fallback_used,
        fallback_note=used.fallback_note,
    )


@router.post("/chat/stream", summary="Akışlı yanıt (SSE)")
async def chat_stream(
    payload: ChatRequest, session: SessionDep, user: UseAI
) -> StreamingResponse:
    try:
        resolved, conversation, messages, _ctx = await _prepare_chat(session, payload, user)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, exc.safe_message) from exc
    await session.commit()

    async def generate():
        collected: list[str] = []
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation.id, 'provider': resolved.config.provider_key, 'model': resolved.model}, ensure_ascii=False)}\n\n"
        try:
            async for piece in resolved.provider.stream_chat(
                messages,
                model=resolved.model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
            ):
                collected.append(piece)
                yield f"data: {json.dumps({'type': 'delta', 'content': piece}, ensure_ascii=False)}\n\n"
        except ProviderError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': exc.safe_message}, ensure_ascii=False)}\n\n"

        text = "".join(collected)
        if text:
            async with session.begin_nested():
                session.add(
                    AIMessage(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=text,
                        provider_key=resolved.config.provider_key,
                        model=resolved.model,
                    )
                )
            await session.commit()
        yield f"data: {json.dumps({'type': 'done', 'length': len(text)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------- KONUSMALAR
@router.get("/conversations", response_model=list[ConversationOut], summary="Görev geçmişi")
async def list_conversations(
    session: SessionDep,
    user: UseAI,
    mine_only: bool = True,
    limit: int = Query(50, le=200),
) -> list[ConversationOut]:
    stmt = select(AIConversation).order_by(AIConversation.updated_at.desc()).limit(limit)
    if mine_only:
        stmt = stmt.where(AIConversation.user_id == user.id)
    rows = (await session.execute(stmt)).scalars().all()
    out = []
    for c in rows:
        item = ConversationOut.model_validate(c)
        item.message_count = (
            await session.execute(
                select(func.count())
                .select_from(AIMessage)
                .where(AIMessage.conversation_id == c.id)
            )
        ).scalar_one()
        out.append(item)
    return out


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
    summary="Konuşma mesajları",
)
async def conversation_messages(
    conversation_id: int, session: SessionDep, _user: UseAI
) -> list[MessageOut]:
    await get_or_404(session, AIConversation, conversation_id, "Konuşma")
    rows = (
        (
            await session.execute(
                select(AIMessage)
                .where(AIMessage.conversation_id == conversation_id)
                .order_by(AIMessage.id)
            )
        )
        .scalars()
        .all()
    )
    return [MessageOut.model_validate(r) for r in rows]


@router.delete("/conversations/{conversation_id}", response_model=Message, summary="Konuşmayı arşivle")
async def archive_conversation(
    conversation_id: int, session: SessionDep, user: UseAI
) -> Message:
    conv = await get_or_404(session, AIConversation, conversation_id, "Konuşma")
    if conv.user_id not in (None, user.id) and not user.has(Perm.AI_CONFIGURE):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu konuşmayı arşivleme yetkiniz yok.")
    conv.is_archived = True
    await session.commit()
    return Message(detail="Konuşma arşivlendi.")


# ------------------------------------------------------------ KULLANIM/MALIYET
@router.get("/usage", response_model=UsageReport, summary="Token ve maliyet raporu")
async def usage_report(
    session: SessionDep,
    _user: UseAI,
    start: dt.date | None = None,
    end: dt.date | None = None,
) -> UsageReport:
    end = end or dt.date.today()
    start = start or (end - dt.timedelta(days=30))
    start_dt = dt.datetime.combine(start, dt.time.min, dt.UTC)
    end_dt = dt.datetime.combine(end, dt.time.max, dt.UTC)

    rows = (
        (
            await session.execute(
                select(AIUsageLog).where(
                    AIUsageLog.created_at >= start_dt, AIUsageLog.created_at <= end_dt
                )
            )
        )
        .scalars()
        .all()
    )
    configs = {c.provider_key: c for c in await list_configs(session)}

    by_provider: dict[str, dict] = {}
    by_task: dict[str, dict] = {}
    daily: dict[str, dict] = {}

    for r in rows:
        p = by_provider.setdefault(
            r.provider_key,
            {
                "requests": 0, "success": 0, "failed": 0, "input": 0, "output": 0,
                "cost": 0.0, "latency": [], "currency": r.currency,
            },
        )
        p["requests"] += 1
        p["success" if r.success else "failed"] += 1
        p["input"] += r.input_tokens
        p["output"] += r.output_tokens
        p["cost"] += float(r.estimated_cost or 0)
        if r.latency_ms:
            p["latency"].append(r.latency_ms)

        t = by_task.setdefault(r.task_kind, {"requests": 0, "tokens": 0, "cost": 0.0})
        t["requests"] += 1
        t["tokens"] += r.input_tokens + r.output_tokens
        t["cost"] += float(r.estimated_cost or 0)

        day = r.created_at.date().isoformat()
        d = daily.setdefault(day, {"requests": 0, "tokens": 0, "cost": 0.0})
        d["requests"] += 1
        d["tokens"] += r.input_tokens + r.output_tokens
        d["cost"] += float(r.estimated_cost or 0)

    return UsageReport(
        period_start=start,
        period_end=end,
        total_requests=len(rows),
        total_input_tokens=sum(r.input_tokens for r in rows),
        total_output_tokens=sum(r.output_tokens for r in rows),
        total_cost_usd=round(sum(float(r.estimated_cost or 0) for r in rows), 6),
        by_provider=[
            UsageSummary(
                provider_key=key,
                display_name=configs[key].display_name if key in configs else key,
                requests=v["requests"],
                success=v["success"],
                failed=v["failed"],
                input_tokens=v["input"],
                output_tokens=v["output"],
                estimated_cost=round(v["cost"], 6),
                currency=v["currency"],
                avg_latency_ms=round(sum(v["latency"]) / len(v["latency"]), 1)
                if v["latency"]
                else None,
            )
            for key, v in by_provider.items()
        ],
        by_task=[
            {"task_kind": k, "ad": TASK_LABELS_TR.get(k, k), **v} for k, v in by_task.items()
        ],
        daily=[{"tarih": k, **v} for k, v in sorted(daily.items())],
    )


# ------------------------------------------------------------------ OZELLIK
@router.post("/insights", response_model=InsightOut, summary="Yapay zekâ destekli analiz")
async def get_insight(
    payload: InsightRequest, request: Request, session: SessionDep, user: UseAI
) -> InsightOut:
    kind = payload.kind
    try:
        if kind == "fermantasyon_tahmin":
            if not payload.fermentation_id:
                raise ValueError("fermentation_id gereklidir.")
            result = await ai_insights.fermentation_forecast(
                session, payload.fermentation_id, use_llm=payload.use_llm,
                provider_key=payload.provider_key, user_id=user.id,
                confirm_external_share=payload.confirm_external_share,
            )
        elif kind == "anomali":
            if not payload.fermentation_id:
                raise ValueError("fermentation_id gereklidir.")
            result = await ai_insights.fermentation_anomalies(
                session, payload.fermentation_id, use_llm=payload.use_llm,
                provider_key=payload.provider_key, user_id=user.id,
                confirm_external_share=payload.confirm_external_share,
            )
        elif kind == "lab_yorum":
            if not payload.lot_id:
                raise ValueError("lot_id (analiz sonucu kimliği) gereklidir.")
            result = await ai_insights.explain_lab_result(
                session, payload.lot_id, use_llm=payload.use_llm,
                provider_key=payload.provider_key, user_id=user.id,
                confirm_external_share=payload.confirm_external_share,
            )
        elif kind == "riskli_parti":
            if not payload.lot_id:
                raise ValueError("lot_id gereklidir.")
            result = await ai_insights.lot_risk(
                session, payload.lot_id, use_llm=payload.use_llm,
                provider_key=payload.provider_key, user_id=user.id,
                confirm_external_share=payload.confirm_external_share,
            )
        elif kind == "kalite_puani":
            if not payload.lot_id:
                raise ValueError("lot_id gereklidir.")
            result = await ai_insights.quality_score(session, payload.lot_id)
        elif kind == "kupaj_karsilastirma":
            result = await ai_insights.compare_blends(
                session, payload.blend_ids, use_llm=payload.use_llm,
                provider_key=payload.provider_key, user_id=user.id,
                confirm_external_share=payload.confirm_external_share,
            )
        elif kind == "stok_tahmin":
            result = await ai_insights.stock_forecast(session)
        elif kind == "bakim_tahmin":
            result = await ai_insights.maintenance_forecast(session)
        elif kind == "rapor":
            result = await ai_insights.natural_language_report(
                session, lot_id=payload.lot_id, provider_key=payload.provider_key,
                user_id=user.id,
                confirm_external_share=payload.confirm_external_share,
            )
        else:
            raise ValueError(f"Bilinmeyen analiz türü: {kind}")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    await record_audit(
        session,
        action=AuditAction.AI_ONERI,
        entity_type="ai_insights",
        summary=f"AI analizi: {kind} — {result.title}",
        after={"kind": kind, "severity": result.severity, "llm": payload.use_llm},
        user=user,
        request=request,
        ai_provider=result.provider_key,
        ai_model=result.model,
    )
    await session.commit()
    return result


# --------------------------------------------------------------------- RAG
@router.post("/rag/search", response_model=RagSearchResponse, summary="Doküman araması")
async def rag_search(
    payload: RagSearchRequest, session: SessionDep, _user: UseAI
) -> RagSearchResponse:
    return await ai_rag.search(
        session, payload.query, top_k=payload.top_k, doc_type=payload.doc_type
    )


@router.post("/rag/index", summary="Dokümanları indeksle")
async def rag_index(
    payload: RagIndexRequest, request: Request, session: SessionDep, user: ConfigAI
) -> dict:
    result = await ai_rag.index_documents(
        session, paths=payload.paths, doc_type=payload.doc_type, rebuild=payload.rebuild
    )
    await record_audit(
        session,
        action=AuditAction.AI_ISTEK,
        entity_type="document_chunks",
        summary=f"Doküman indeksleme: {result['parca_sayisi']} parça, "
        f"{result['gomme_sayisi']} gömme",
        after=result,
        user=user,
        request=request,
        commit=True,
    )
    return result
