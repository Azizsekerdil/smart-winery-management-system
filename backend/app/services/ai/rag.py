"""Saraphane dokumanlarinda RAG (getirmeli uretim) aramasi.

Gomme (embedding) LM Studio'nun yerel modeliyle uretilir; boylece dokuman
icerigi makineden CIKMAZ. Gomme alinamazsa anahtar kelime tabanli yedek arama
devreye girer - ozellik hicbir kosulda tamamen devre disi kalmaz.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DOCS_DIR, settings
from app.core.logging import get_logger
from app.models.ai import DocumentChunk
from app.schemas.ai import RagHit, RagSearchResponse
from app.services.ai.base import ProviderError
from app.services.ai.registry import build_provider, get_config

log = get_logger("ai.rag")

CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150


def split_text(text: str, *, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Metni paragraf sinirlarini gozeterek parcalara boler."""
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if len(text) <= size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            # en yakin paragraf/cumle sinirina cek
            for sep in ("\n\n", "\n", ". ", " "):
                idx = text.rfind(sep, start + size // 2, end)
                if idx != -1:
                    end = idx + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def _embedder(session: AsyncSession):
    """LM Studio gomme saglayicisini dondurur (yoksa None)."""
    config = await get_config(session, "lmstudio")
    if config is None or not config.enabled:
        return None, None
    provider = build_provider(config)
    if not provider.is_configured:
        return None, None
    return provider, settings.LMSTUDIO_EMBEDDING_MODEL


async def index_documents(
    session: AsyncSession, *, paths: list[str] | None = None, doc_type: str = "sop",
    rebuild: bool = False,
) -> dict:
    """docs/ altindaki markdown/metin dosyalarini parcalayip indeksler."""
    targets: list[Path] = []
    if paths:
        for rel in paths:
            candidate = (DOCS_DIR / rel).resolve()
            # Dizin disina cikisi engelle
            if DOCS_DIR.resolve() not in candidate.parents and candidate != DOCS_DIR.resolve():
                continue
            if candidate.is_file():
                targets.append(candidate)
    else:
        targets = sorted(
            p for p in DOCS_DIR.rglob("*") if p.suffix.lower() in {".md", ".txt"} and p.is_file()
        )

    if rebuild:
        await session.execute(delete(DocumentChunk).where(DocumentChunk.doc_type == doc_type))

    provider, embed_model = await _embedder(session)
    indexed = 0
    embedded = 0
    warnings: list[str] = []

    for path in targets:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            warnings.append(f"{path.name}: okunamadı ({exc.__class__.__name__})")
            continue

        key = str(path.relative_to(DOCS_DIR)).replace("\\", "/")
        await session.execute(delete(DocumentChunk).where(DocumentChunk.document_key == key))

        pieces = split_text(text)
        vectors: list[list[float]] = []
        if provider is not None and pieces:
            try:
                vectors = await provider.embed(pieces, model=embed_model)
                embedded += len(vectors)
            except (ProviderError, NotImplementedError) as exc:
                warnings.append(
                    f"Gömme üretilemedi ({type(exc).__name__}); anahtar kelime araması kullanılacak."
                )
                vectors = []

        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()), key)
        for i, piece in enumerate(pieces):
            vector = vectors[i] if i < len(vectors) else None
            session.add(
                DocumentChunk(
                    document_key=key,
                    title=title[:255],
                    source_path=str(path),
                    doc_type=doc_type,
                    chunk_index=i,
                    content=piece,
                    token_estimate=len(piece) // 4,
                    embedding=vector,
                    embedding_model=embed_model if vector else None,
                    embedding_dim=len(vector) if vector else None,
                )
            )
            indexed += 1

    await session.commit()
    return {
        "dosya_sayisi": len(targets),
        "parca_sayisi": indexed,
        "gomme_sayisi": embedded,
        "uyarilar": sorted(set(warnings)),
    }


def _keyword_score(query: str, content: str) -> float:
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
    if not terms:
        return 0.0
    low = content.lower()
    hits = sum(low.count(t) for t in terms)
    return min(1.0, hits / (len(terms) * 3))


async def search(
    session: AsyncSession, query: str, *, top_k: int = 5, doc_type: str | None = None
) -> RagSearchResponse:
    stmt = select(DocumentChunk)
    if doc_type:
        stmt = stmt.where(DocumentChunk.doc_type == doc_type)
    chunks = list((await session.execute(stmt)).scalars().all())

    if not chunks:
        return RagSearchResponse(
            query=query,
            hits=[],
            fallback_used=True,
            note="Doküman indeksi boş. Önce 'Dokümanları indeksle' işlemini çalıştırın.",
        )

    provider, embed_model = await _embedder(session)
    query_vector: list[float] | None = None
    fallback = True
    note: str | None = None

    if provider is not None and any(c.embedding for c in chunks):
        try:
            vectors = await provider.embed([query], model=embed_model)
            query_vector = vectors[0] if vectors else None
            fallback = query_vector is None
        except (ProviderError, NotImplementedError) as exc:
            note = (
                "Gömme modeli kullanılamadı, anahtar kelime araması yapıldı. "
                f"({type(exc).__name__})"
            )

    scored: list[tuple[float, DocumentChunk]] = []
    for chunk in chunks:
        if query_vector and chunk.embedding:
            score = cosine(query_vector, chunk.embedding)
        else:
            score = _keyword_score(query, chunk.content)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    hits = [
        RagHit(
            document_key=c.document_key,
            title=c.title,
            chunk_index=c.chunk_index,
            score=round(s, 4),
            content=c.content[:1500],
            # Mutlak sunucu yolu istemciye DONMEZ (ic dizin yapisi ifsasi);
            # `document_key` zaten docs/ altindaki goreli yoldur.
            source_path=None,
        )
        for s, c in scored[:top_k]
    ]
    if not hits:
        note = note or "Sorguyla eşleşen içerik bulunamadı."

    return RagSearchResponse(
        query=query,
        hits=hits,
        embedding_model=embed_model if query_vector else None,
        fallback_used=fallback,
        note=note,
    )
