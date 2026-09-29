import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.database import Question

logger = logging.getLogger(__name__)


@dataclass
class QuestionRecord:
    category_id: int
    question_type: str  # 'tf' or 'mc'
    question_text: str
    correct_answer: str  # 'O'/'X' for tf, '1'/'2'/'3'/'4' for mc
    options: list[str] | None = None
    regulation_ref: str | None = None

    @property
    def source_hash(self) -> str:
        return compute_source_hash(
            self.category_id, self.question_type, self.question_text, self.options
        )


def compute_source_hash(
    category_id: int,
    question_type: str,
    question_text: str,
    options: list[str] | None = None,
) -> str:
    # MC stems are often generic ("下列敘述何者正確？"), so options must be part
    # of the identity; otherwise distinct questions collapse into one row.
    raw = f"{category_id}|{question_type}|{question_text}"
    if options:
        raw += "|" + "|".join(options)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upsert_questions(db: Session, records: list[QuestionRecord]) -> dict:
    """Upsert questions into the database. Returns summary stats."""
    stats = {"new": 0, "updated": 0, "unchanged": 0, "soft_deleted": 0}

    incoming_hashes = set()

    for record in records:
        h = record.source_hash
        if h in incoming_hashes:
            logger.warning(
                "Duplicate question in source (category %d, %s): %s",
                record.category_id,
                record.question_type,
                record.question_text[:50],
            )
        incoming_hashes.add(h)

        existing = db.execute(
            select(Question).where(Question.source_hash == h)
        ).scalar_one_or_none()

        if existing:
            changed = False
            if existing.correct_answer != record.correct_answer:
                existing.correct_answer = record.correct_answer
                changed = True
            if existing.options != record.options:
                existing.options = record.options
                changed = True
            if existing.regulation_ref != record.regulation_ref:
                existing.regulation_ref = record.regulation_ref
                changed = True
            if existing.deleted_at is not None:
                existing.deleted_at = None
                changed = True

            if changed:
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
        else:
            db.add(
                Question(
                    category_id=record.category_id,
                    question_type=record.question_type,
                    question_text=record.question_text,
                    options=record.options,
                    correct_answer=record.correct_answer,
                    regulation_ref=record.regulation_ref,
                    source_hash=h,
                )
            )
            stats["new"] += 1

    # Soft-delete questions for affected categories that are no longer in source
    affected_category_ids = {r.category_id for r in records}
    if affected_category_ids:
        existing_questions = db.execute(
            select(Question).where(
                Question.category_id.in_(affected_category_ids),
                Question.deleted_at.is_(None),
            )
        ).scalars().all()

        for q in existing_questions:
            if q.source_hash not in incoming_hashes:
                from datetime import datetime, timezone
                q.deleted_at = datetime.now(timezone.utc)
                stats["soft_deleted"] += 1

    db.commit()

    logger.info(
        "Upsert complete: %d new, %d updated, %d unchanged, %d soft-deleted",
        stats["new"],
        stats["updated"],
        stats["unchanged"],
        stats["soft_deleted"],
    )
    return stats
