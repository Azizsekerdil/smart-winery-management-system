"""Egitim modulu ilerleme kayitlari.

Egitim ICERIGI arayuzde tutulur (`frontend/src/lib/egitim.ts`): iki dilli,
surum kontrollu ve paketle birlikte gelir; icerik icin sunucuya gitmek gereksiz
bir bagimliliktir. Burada yalnizca KIMIN NEYI TAMAMLADIGI saklanir.

Neden saklanir: bir isletmede yeni calisanin egitimi tamamlayip tamamlamadigi
takip edilebilir olmalidir; gida guvenligi ve izlenebilirlik denetimlerinde
"personel egitildi mi" sorusu sorulur.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EgitimIlerleme(Base, TimestampMixin):
    """Bir kullanicinin bir egitim modulundeki durumu."""

    __tablename__ = "training_progress"
    __table_args__ = (
        # Kullanici + modul cifti tekildir; tekrar tamamlamada kayit guncellenir.
        UniqueConstraint("user_id", "module_code", name="uq_training_user_module"),
        Index("ix_training_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    module_code: Mapped[str] = mapped_column(String(64), index=True)

    # Sinav sonucu: dogru cevap sayisi / toplam soru
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    question_count: Mapped[int] = mapped_column(Integer, default=0)

    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def score_percent(self) -> float:
        return (
            round(100 * self.correct_count / self.question_count, 1)
            if self.question_count
            else 0.0
        )

    @property
    def passed(self) -> bool:
        """Gecme esigi %70 — ezber degil anlama olcen sorular icin makul."""
        return self.score_percent >= 70.0
