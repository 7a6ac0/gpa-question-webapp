"""Add category 14 (錯誤採購態樣)

Revision ID: 004
Revises: 003
Create Date: 2026-09-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO categories (id, name, source_code) "
            "SELECT 14, '錯誤採購態樣', '14' "
            "WHERE NOT EXISTS (SELECT 1 FROM categories WHERE id = 14)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM categories WHERE id = 14"))
