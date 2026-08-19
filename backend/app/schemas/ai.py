"""Yapay zeka saglayici, sohbet ve ajan semalari."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator

from app.models.ai import AITaskKind, PrivacyLevel, RiskLevel
from app.schemas.common import ORMModel


# --------------------------------------------------------------- SAGLAYICI
class ProviderOut(ORMModel):
    id: int
    provider_key: str
    display_name: str
    kind: str
    enabled: bool
    base_url: str
    default_model: str
    timeout_seconds: int
    max_retries: int
    supports_streaming: bool
    supports_tools: bool
    privacy_level: str
    input_cost_per_1k: float
    output_cost_per_1k: float
    currency: str
    task_model_map: dict = Field(default_factory=dict)
    cached_models: list = Field(default_factory=list)
    models_fetched_at: dt.datetime | None = None
    last_status: str
    last_checked_at: dt.datetime | None = None
    last_error: str | None = None
    last_latency_ms: int | None = None
    priority: int
    notes: str | None = None
    # Guvenlik: anahtarin kendisi ASLA donmez
    has_api_key: bool = False
    api_key_masked: str = ""
    api_key_fingerprint: str = ""
    requires_api_key: bool = True


class ProviderUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    base_url: str | None = Field(default=None, max_length=255)
    default_model: str | None = Field(default=None, max_length=160)
    timeout_seconds: int | None = Field(default=None, ge=5, le=900)
    max_retries: int | None = Field(default=None, ge=0, le=5)
    privacy_level: PrivacyLevel | None = None
    input_cost_per_1k: float | None = Field(default=None, ge=0)
    output_cost_per_1k: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=8)
    task_model_map: dict[str, str] | None = None
    priority: int | None = None
    notes: str | None = None

    @field_validator("base_url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("Adres http:// veya https:// ile başlamalıdır.")
        return v


class ProviderKeyUpdate(BaseModel):
    """Anahtar yalnizca YAZILIR; hicbir uc nokta geri okumaz."""

    api_key: str = Field(min_length=8, max_length=512)


class ProviderTestResult(BaseModel):
    provider_key: str
    ok: bool
    status: str
    latency_ms: int | None = None
    model: str | None = None
    message: str
    sample_response: str | None = None
    models_found: int = 0


class ModelInfo(BaseModel):
    id: str
    label: str | None = None
    owned_by: str | None = None
    context_length: int | None = None


class ProviderModels(BaseModel):
    provider_key: str
    models: list[ModelInfo]
    fetched_at: dt.datetime
    cached: bool = False
    warning: str | None = None


# ------------------------------------------------------------------ SOHBET
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=32_000)
    conversation_id: int | None = None
    provider_key: str | None = None
    model: str | None = None
    task_kind: AITaskKind = AITaskKind.GENEL
    temperature: float = Field(default=0.4, ge=0, le=2)
    max_tokens: int = Field(default=1600, ge=16, le=32_000)
    # Modele eklenecek saraphane verisi
    context_lot_ids: list[int] = Field(default_factory=list, max_length=25)
    context_fermentation_ids: list[int] = Field(default_factory=list, max_length=25)
    include_dashboard: bool = False
    use_rag: bool = False
    # Dis saglayiciya veri gonderme onayi (madde 11)
    confirm_external_share: bool = False


class DataScopePreview(BaseModel):
    """Gonderim oncesi kullaniciya gosterilen veri kapsami."""

    provider_key: str
    provider_name: str
    privacy_level: str
    is_external: bool
    items: list[dict]
    approx_chars: int
    warning_tr: str | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    provider_key: str
    model: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int | None = None
    estimated_cost: float = 0.0
    currency: str = "USD"
    finish_reason: str | None = None
    fallback_used: bool = False
    fallback_note: str | None = None
    disclaimer: str = (
        "Bu yanıt yapay zekâ tarafından üretilmiştir ve yalnızca karar destek "
        "amaçlıdır. Kritik üretim kararlarını uzman onayı olmadan uygulamayın."
    )


class ConversationOut(ORMModel):
    id: int
    title: str
    task_kind: str
    provider_key: str
    model: str
    user_id: int | None = None
    data_scope: list = Field(default_factory=list)
    data_shared_externally: bool = False
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
    is_archived: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    message_count: int = 0


class MessageOut(ORMModel):
    id: int
    role: str
    content: str
    provider_key: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int | None = None
    finish_reason: str | None = None
    error: str | None = None
    created_at: dt.datetime


class UsageSummary(BaseModel):
    provider_key: str
    display_name: str
    requests: int
    success: int
    failed: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    currency: str
    avg_latency_ms: float | None = None


class UsageReport(BaseModel):
    period_start: dt.date
    period_end: dt.date
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    by_provider: list[UsageSummary]
    by_task: list[dict]
    daily: list[dict]


# ---------------------------------------------------- YAPAY ZEKA OZELLIK
class InsightRequest(BaseModel):
    kind: str = Field(
        description=(
            "fermantasyon_tahmin|anomali|lab_yorum|riskli_parti|kalite_puani|"
            "kupaj_karsilastirma|stok_tahmin|bakim_tahmin|rapor"
        )
    )
    lot_id: int | None = None
    fermentation_id: int | None = None
    blend_ids: list[int] = Field(default_factory=list)
    use_llm: bool = Field(
        default=False, description="Sayısal modele ek olarak dil modelinden yorum al"
    )
    provider_key: str | None = None
    # Harici sağlayıcıya veri gönderme onayı. `use_llm=true` ile harici bir
    # sağlayıcı seçildiğinde parti/fermantasyon/analiz değerleri isteme girer;
    # onay verilmezse yalnızca YEREL sağlayıcı kullanılır.
    confirm_external_share: bool = False


class InsightOut(BaseModel):
    kind: str
    title: str
    summary: str
    severity: str = "bilgi"
    confidence: float | None = Field(default=None, ge=0, le=1)
    numeric: dict = Field(default_factory=dict)
    llm_commentary: str | None = None
    provider_key: str | None = None
    model: str | None = None
    generated_at: dt.datetime
    is_advisory: bool = True
    disclaimer: str = (
        "Karar destek amaçlıdır; üretim değerleri kullanıcı onayı olmadan değiştirilmez."
    )


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=25)
    doc_type: str | None = None


class RagHit(BaseModel):
    document_key: str
    title: str
    chunk_index: int
    score: float
    content: str
    source_path: str | None = None


class RagSearchResponse(BaseModel):
    query: str
    hits: list[RagHit]
    embedding_model: str | None = None
    fallback_used: bool = False
    note: str | None = None


class RagIndexRequest(BaseModel):
    paths: list[str] = Field(default_factory=list, description="docs/ altında göreli yollar")
    doc_type: str = "sop"
    rebuild: bool = False


# --------------------------------------------------- AI TERMINAL / AJANI
class AgentPlanRequest(BaseModel):
    request_text: str = Field(min_length=3, max_length=8000)
    title: str | None = Field(default=None, max_length=220)
    provider_key: str | None = None
    model: str | None = None
    proposed_commands: list[str] = Field(default_factory=list, max_length=25)
    affected_paths: list[str] = Field(default_factory=list, max_length=100)
    use_llm: bool = True


class CommandCheck(BaseModel):
    command: str
    allowed: bool
    risk: RiskLevel
    reason: str
    matched_rule: str | None = None


class AgentTaskOut(ORMModel):
    id: int
    code: str
    title: str
    request_text: str
    user_id: int | None = None
    provider_key: str | None = None
    model: str | None = None
    status: str
    risk_level: str
    risk_reasons: list = Field(default_factory=list)
    plan_steps: list = Field(default_factory=list)
    affected_paths: list = Field(default_factory=list)
    proposed_commands: list = Field(default_factory=list)
    approved_by_id: int | None = None
    approved_at: dt.datetime | None = None
    rejection_reason: str | None = None
    git_checkpoint: str | None = None
    git_branch: str | None = None
    diff_text: str | None = None
    test_output: str | None = None
    lint_output: str | None = None
    tests_passed: bool | None = None
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    result_summary: str | None = None
    created_at: dt.datetime
    command_checks: list[CommandCheck] = Field(default_factory=list)


class AgentApproval(BaseModel):
    approve: bool
    reason: str | None = Field(default=None, max_length=1000)
    run_tests: bool = True


class AgentRunOut(ORMModel):
    id: int
    sequence: int
    command: str
    cwd: str
    allowed: bool
    block_reason: str | None = None
    started_at: dt.datetime | None = None
    finished_at: dt.datetime | None = None
    exit_code: int | None = None
    timed_out: bool
    stdout: str | None = None
    stderr: str | None = None
    truncated: bool
    created_at: dt.datetime


class TerminalCommandRequest(BaseModel):
    """Tek komut onizleme/calistirma istegi."""

    command: str = Field(min_length=1, max_length=4000)
    cwd: str | None = Field(default=None, max_length=500)
    task_id: int | None = None


class SandboxStatus(BaseModel):
    workspace: str
    enabled: bool
    require_approval: bool
    timeout_seconds: int
    max_output_bytes: int
    allowed_commands: list[str]
    blocked_patterns: list[str]
    git_available: bool
    git_repo: bool
    current_branch: str | None = None
    dirty: bool = False
