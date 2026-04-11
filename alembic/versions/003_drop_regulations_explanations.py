"""Drop regulations and explanations tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("explanations")
    op.drop_table("regulations")


def downgrade() -> None:
    op.create_table(
        "regulations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_number", sa.String(10), nullable=False, unique=True),
        sa.Column("article_text", sa.Text(), nullable=False),
        sa.Column("chapter", sa.String(50)),
        sa.Column("law_name", sa.String(50), server_default="政府採購法"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "explanations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("selected_answer", sa.String(10), nullable=False),
        sa.Column("explanation_text", sa.Text(), nullable=False),
        sa.Column("cache_version", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "question_id", "selected_answer", "cache_version",
            name="uq_explanation_cache",
        ),
    )
