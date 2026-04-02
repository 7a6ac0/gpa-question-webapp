from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from src.models.database import Category, Question, get_db
from src.models.schemas import QuestionResponse

router = APIRouter()


@router.get("/questions", response_model=list[QuestionResponse])
def get_questions(
    category_ids: str = Query(default="", description="Comma-separated category IDs"),
    type: str | None = Query(default=None, description="'tf' or 'mc'"),
    count: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get random questions. Returns questions WITHOUT correct answers."""
    stmt = (
        select(Question, Category.name.label("category_name"))
        .join(Category, Question.category_id == Category.id)
        .where(Question.deleted_at.is_(None))
    )

    if category_ids:
        ids = [int(x.strip()) for x in category_ids.split(",") if x.strip()]
        if ids:
            stmt = stmt.where(Question.category_id.in_(ids))

    if type:
        stmt = stmt.where(Question.question_type == type)

    stmt = stmt.order_by(func.random()).limit(count)

    rows = db.execute(stmt).all()
    return [
        QuestionResponse(
            id=row.Question.id,
            category_id=row.Question.category_id,
            category_name=row.category_name,
            question_type=row.Question.question_type,
            question_text=row.Question.question_text,
            options=row.Question.options,
        )
        for row in rows
    ]
