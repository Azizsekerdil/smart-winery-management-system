"""Yapay zeka saglayici ayarlari, konusmalar, kullanim kaydi, ajan gorevleri ve RAG."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuthorMixin, Base, TimestampMixin


class PrivacyLevel(StrEnum):
    """Saglayiciya gonderilebilecek veri hassasiyeti."""

    YEREL_ONLY = "yerel_only"      # veri makineden cikmaz
    DAHILI = "dahili"              # kurum ici bulut / sozlesmeli
    HERKESE_ACIK = "herkese_acik"  # yalnizca hassas olmayan veri


class AIProviderConfig(Base, TimestampMixin, AuthorMixin):
    """Saglayici ayarlari. API anahtarlari SIFRELI saklanir (app.core.crypto)."""

    __tablename__ = "ai_provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_key: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(24), default="openai_compat")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    base_url: Mapped[str] = mapped_column(String(255), default="")
    default_model: Mapped[str] = mapped_column(String(160), default="")

    # Fernet ile sifrelenmis anahtar; duz metin ASLA saklanmaz.
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    api_key_fingerprint: Mapped[str] = mapped_column(String(24), default="")

    timeout_seconds: Mapped[int] = mapped_column(Integer, default=120)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    privacy_level: Mapped[str] = mapped_column(String(20), default=PrivacyLevel.HERKESE_ACIK)

    # 1000 token basina maliyet (TRY veya USD - `currency` alani belirler)
    input_cost_per_1k: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    output_cost_per_1k: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")

    # Gorev bazli model yonlendirme: {"kod_gelistirici": "model-id", ...}
    task_model_map: Mapped[dict] = mapped_column(JSON, default=dict)
    cached_models: Mapped[list] = mapped_column(JSON, default=list)
    models_fetched_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_status: Mapped[str] = mapped_column(String(16), default="bilinmiyor")
    last_checked_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    priority: Mapped[int] = mapped_column(Integer, default=100)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_encrypted)


class AITaskKind(StrEnum):
    SARAPHANE_DANISMANI = "saraphane_danismani"
    VERI_ANALISTI = "veri_analisti"
    RAPOR_YAZARI = "rapor_yazari"
    KALITE_KONTROL = "kalite_kontrol"
    KOD_GELISTIRICI = "kod_gelistirici"
    HATA_TESHIS = "hata_teshis"
    DOKUMANTASYON = "dokumantasyon"
    GENEL = "genel"


class AIConversation(Base, TimestampMixin, AuthorMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(220), default="Yeni görev")
    task_kind: Mapped[str] = mapped_column(String(32), default=AITaskKind.GENEL, index=True)
    provider_key: Mapped[str] = mapped_column(String(48), index=True)
    model: Mapped[str] = mapped_column(String(160), default="")
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Modele saglanan saraphane veri kapsami (kullaniciya onceden gosterilir)
    data_scope: Mapped[list] = mapped_column(JSON, default=list)
    data_shared_externally: Mapped[bool] = mapped_column(Boolean, default=False)

    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(14, 6), default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list[AIMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.id",
    )


class AIMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # system|user|assistant|tool
    content: Mapped[str] = mapped_column(Text)
    provider_key: Mapped[str | None] = mapped_column(String(48), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachments: Mapped[list] = mapped_column(JSON, default=list)

    conversation: Mapped[AIConversation] = relationship(back_populates="messages")


class AIUsageLog(Base):
    """Saglayici kullanim / maliyet kaydi. Anahtar bilgisi ICERMEZ."""

    __tablename__ = "ai_usage_logs"
    __table_args__ = (Index("ix_ai_usage_provider_time", "provider_key", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: dt.datetime.now(dt.UTC), index=True
    )
    provider_key: Mapped[str] = mapped_column(String(48), index=True)
    model: Mapped[str] = mapped_column(String(160), default="")
    task_kind: Mapped[str] = mapped_column(String(32), default=AITaskKind.GENEL)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Numeric(14, 6), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)  # maskelenmis


# ----------------------------------------------------- AI TERMINAL / AJANI
class AgentTaskStatus(StrEnum):
    TASLAK = "taslak"
    PLAN_HAZIR = "plan_hazir"
    ONAY_BEKLIYOR = "onay_bekliyor"
    ONAYLANDI = "onaylandi"
    CALISIYOR = "calisiyor"
    TEST_EDILIYOR = "test_ediliyor"
    BASARILI = "basarili"
    BASARISIZ = "basarisiz"
    REDDEDILDI = "reddedildi"
    GERI_ALINDI = "geri_alindi"
    IPTAL = "iptal"


class RiskLevel(StrEnum):
    DUSUK = "dusuk"
    ORTA = "orta"
    YUKSEK = "yuksek"
    ENGELLENDI = "engellendi"


class AgentTask(Base, TimestampMixin, AuthorMixin):
    """AI Terminali gorevi: plan -> onay -> git kontrol noktasi -> uygula -> test."""

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(220))
    request_text: Mapped[str] = mapped_column(Text)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider_key: Mapped[str | None] = mapped_column(String(48), nullable=True)
    model: Mapped[str | None] = mapped_column(String(160), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), default=AgentTaskStatus.TASLAK, index=True
    )
    risk_level: Mapped[str] = mapped_column(String(16), default=RiskLevel.DUSUK, index=True)
    risk_reasons: Mapped[list] = mapped_column(JSON, default=list)

    plan_steps: Mapped[list] = mapped_column(JSON, default=list)
    affected_paths: Mapped[list] = mapped_column(JSON, default=list)
    proposed_commands: Mapped[list] = mapped_column(JSON, default=list)

    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    git_checkpoint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    git_branch: Mapped[str | None] = mapped_column(String(160), nullable=True)
    diff_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    lint_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tests_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    runs: Mapped[list[AgentRun]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="AgentRun.id"
    )


class AgentRun(Base, TimestampMixin):
    """Tek bir komut calistirmasi. Cikti kirpilmis ve maskelenmis olarak saklanir."""

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    command: Mapped[str] = mapped_column(Text)
    cwd: Mapped[str] = mapped_column(String(500), default="")
    allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    block_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)

    task: Mapped[AgentTask] = relationship(back_populates="runs")


# ------------------------------------------------------------------- RAG
class DocumentChunk(Base, TimestampMixin, AuthorMixin):
    """Saraphane dokumanlarindan cikarilmis metin parcalari + gomme vektoru.

    Vektorler JSON listesi olarak saklanir; benzerlik hesabi uygulama
    katmaninda yapilir. Buyuk olcekte pgvector'a tasinabilir (bkz. ARCHITECTURE.md).
    """

    __tablename__ = "document_chunks"
    __table_args__ = (Index("ix_doc_chunks_doc", "document_key", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_key: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(32), default="sop")

    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)

    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
