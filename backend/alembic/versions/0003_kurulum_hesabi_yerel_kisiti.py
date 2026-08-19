"""kurulum hesabi icin bootstrap_pending sutunu

Ilk kurulumda uretilen yonetici hesabinin, parola degistirilene kadar
yalnizca yerel makineden giris yapabilmesi icin gereken bayrak.

Revision ID: 0003
Revises: 560ad4aebe38
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "560ad4aebe38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "bootstrap_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "bootstrap_pending")
