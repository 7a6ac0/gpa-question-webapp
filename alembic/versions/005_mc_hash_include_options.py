"""Include options in MC question source_hash

MC stems are often generic ("下列敘述何者正確？"), so hashing only the stem
merged distinct questions into one row. Recompute existing MC hashes with
options so current rows keep their ids and re-ingestion only adds the
questions that were previously collapsed.

Revision ID: 005
Revises: 004
Create Date: 2026-09-23

"""
import hashlib
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hash(category_id, question_type, question_text, options) -> str:
    # Frozen copy of src.ingestion.base.compute_source_hash at this revision
    raw = f"{category_id}|{question_type}|{question_text}"
    if options:
        raw += "|" + "|".join(options)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_options(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def _rehash(include_options: bool) -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, category_id, question_type, question_text, options "
            "FROM questions WHERE question_type = 'mc'"
        )
    ).fetchall()
    for row in rows:
        options = _load_options(row.options) if include_options else None
        conn.execute(
            sa.text("UPDATE questions SET source_hash = :h WHERE id = :id"),
            {
                "h": _hash(row.category_id, row.question_type, row.question_text, options),
                "id": row.id,
            },
        )


def upgrade() -> None:
    _rehash(include_options=True)


def downgrade() -> None:
    # Fails on the unique constraint if questions sharing a stem were ingested
    # after upgrade; soft-delete or remove the duplicates first.
    _rehash(include_options=False)
