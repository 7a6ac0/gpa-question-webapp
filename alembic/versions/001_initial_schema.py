"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("source_code", sa.String(2), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("question_type", sa.String(10), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON()),
        sa.Column("correct_answer", sa.String(10), nullable=False),
        sa.Column("regulation_ref", sa.Text()),
        sa.Column("source_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_questions_category", "questions", ["category_id"])
    op.create_index("idx_questions_type", "questions", ["question_type"])
    op.create_index("idx_questions_hash", "questions", ["source_hash"])
    op.create_index(
        "idx_questions_active",
        "questions",
        ["id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "practice_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("anonymous_id", sa.String(64)),
        sa.Column("question_type", sa.String(10)),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime()),
    )

    op.create_table(
        "session_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("user_answer", sa.String(10), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("idx_session_answers_session", "session_answers", ["session_id"])

    op.create_table(
        "session_categories",
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("practice_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), primary_key=True),
    )

    # Seed categories
    categories_table = sa.table(
        "categories",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("source_code", sa.String),
    )
    op.bulk_insert(
        categories_table,
        [
            {"id": 1, "name": "政府採購全生命週期概論", "source_code": "01"},
            {"id": 2, "name": "政府採購法之總則、招標及決標", "source_code": "02"},
            {"id": 3, "name": "政府採購法之履約管理及驗收", "source_code": "03"},
            {"id": 4, "name": "政府採購法之罰則及附則", "source_code": "04"},
            {"id": 5, "name": "政府採購法之爭議處理", "source_code": "05"},
            {"id": 6, "name": "底價及價格分析", "source_code": "06"},
            {"id": 7, "name": "投標須知及招標文件製作", "source_code": "07"},
            {"id": 8, "name": "採購契約", "source_code": "08"},
            {"id": 9, "name": "最有利標及評選優勝廠商", "source_code": "09"},
            {"id": 10, "name": "電子採購實務", "source_code": "10"},
            {"id": 11, "name": "工程及技術服務採購作業", "source_code": "11"},
            {"id": 12, "name": "財物及勞務採購作業", "source_code": "12"},
            {"id": 13, "name": "道德規範及違法處置", "source_code": "13"},
        ],
    )


def downgrade() -> None:
    op.drop_table("session_categories")
    op.drop_table("session_answers")
    op.drop_table("practice_sessions")
    op.drop_index("idx_questions_active", table_name="questions")
    op.drop_index("idx_questions_hash", table_name="questions")
    op.drop_index("idx_questions_type", table_name="questions")
    op.drop_index("idx_questions_category", table_name="questions")
    op.drop_table("questions")
    op.drop_table("categories")
