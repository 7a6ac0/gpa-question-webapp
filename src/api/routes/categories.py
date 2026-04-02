from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.database import Category, Question, get_db
from src.models.schemas import CategoryResponse

router = APIRouter()


@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(db: Session = Depends(get_db)):
    """List all categories with question counts."""
    stmt = (
        select(
            Category.id,
            Category.name,
            Category.source_code,
            func.count(Question.id).label("question_count"),
        )
        .outerjoin(
            Question,
            (Question.category_id == Category.id) & (Question.deleted_at.is_(None)),
        )
        .group_by(Category.id)
        .order_by(Category.id)
    )

    rows = db.execute(stmt).all()
    return [
        CategoryResponse(
            id=row.id,
            name=row.name,
            source_code=row.source_code,
            question_count=row.question_count,
        )
        for row in rows
    ]
