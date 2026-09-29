"""Keep MC options numbered (1)-(4) as in the source PDFs

MC options and answers were converted from the source's (1)-(4) to (A)-(D).
Convert existing rows back and recompute source_hash (which includes the
options) so re-ingestion keeps matching the same rows.

Revision ID: 006
Revises: 005
Create Date: 2026-09-29

"""
import hashlib
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LETTER_TO_NUM = {"A": "1", "B": "2", "C": "3", "D": "4"}
NUM_TO_LETTER = {v: k for k, v in LETTER_TO_NUM.items()}


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


def _relabel_option(option: str, mapping: dict[str, str]) -> str:
    # Options look like "(A) text"; only the leading label changes
    if len(option) >= 3 and option[0] == "(" and option[2] == ")" and option[1] in mapping:
        return f"({mapping[option[1]]}){option[3:]}"
    return option


def _convert(mapping: dict[str, str]) -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, category_id, question_type, question_text, options, correct_answer "
            "FROM questions WHERE question_type = 'mc'"
        )
    ).fetchall()
    update = sa.text(
        "UPDATE questions SET options = :o, correct_answer = :a, source_hash = :h "
        "WHERE id = :id"
    ).bindparams(sa.bindparam("o", type_=sa.JSON()))
    for row in rows:
        options = _load_options(row.options)
        if options:
            options = [_relabel_option(opt, mapping) for opt in options]
        conn.execute(
            update,
            {
                "o": options,
                "a": mapping.get(row.correct_answer, row.correct_answer),
                "h": _hash(row.category_id, row.question_type, row.question_text, options),
                "id": row.id,
            },
        )

    for old, new in mapping.items():
        conn.execute(
            sa.text(
                "UPDATE session_answers SET user_answer = :new "
                "WHERE user_answer = :old AND question_id IN "
                "(SELECT id FROM questions WHERE question_type = 'mc')"
            ),
            {"old": old, "new": new},
        )


def upgrade() -> None:
    _convert(LETTER_TO_NUM)


def downgrade() -> None:
    _convert(NUM_TO_LETTER)
