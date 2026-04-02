import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.database import (
    Category,
    PracticeSession,
    Question,
    SessionAnswer,
    SessionCategory,
    get_db,
)
from src.models.schemas import (
    AnswerRequest,
    AnswerResponse,
    CategoryBreakdown,
    CreateSessionRequest,
    CreateSessionResponse,
    QuestionResponse,
    SessionProgress,
    SessionResultsResponse,
)

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest, db: Session = Depends(get_db)):
    """Create a new practice session and return questions."""
    # Validate category IDs exist
    valid_cats = db.execute(
        select(Category.id).where(Category.id.in_(req.category_ids))
    ).scalars().all()

    if not valid_cats:
        raise HTTPException(status_code=400, detail="No valid category IDs provided")

    # Fetch random questions
    stmt = (
        select(Question, Category.name.label("category_name"))
        .join(Category, Question.category_id == Category.id)
        .where(
            Question.category_id.in_(valid_cats),
            Question.deleted_at.is_(None),
        )
    )

    if req.question_type:
        stmt = stmt.where(Question.question_type == req.question_type)

    stmt = stmt.order_by(func.random()).limit(req.count)
    rows = db.execute(stmt).all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No questions found for selected categories",
        )

    # Create session
    session = PracticeSession(
        id=uuid.uuid4(),
        anonymous_id=req.anonymous_id,
        question_type=req.question_type,
        total_questions=len(rows),
    )
    db.add(session)

    # Create category junction records
    for cat_id in valid_cats:
        db.add(SessionCategory(session_id=session.id, category_id=cat_id))

    db.commit()

    questions = [
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

    return CreateSessionResponse(
        session_id=str(session.id),
        questions=questions,
    )


@router.post("/answer", response_model=AnswerResponse)
def submit_answer(req: AnswerRequest, db: Session = Depends(get_db)):
    """Submit an answer and get feedback."""
    session = db.execute(
        select(PracticeSession).where(
            PracticeSession.id == uuid.UUID(req.session_id)
        )
    ).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    question = db.execute(
        select(Question).where(Question.id == req.question_id)
    ).scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check for duplicate answer
    existing_answer = db.execute(
        select(SessionAnswer).where(
            SessionAnswer.session_id == session.id,
            SessionAnswer.question_id == question.id,
        )
    ).scalar_one_or_none()

    if existing_answer:
        raise HTTPException(status_code=409, detail="Question already answered in this session")

    is_correct = req.answer.upper() == question.correct_answer.upper()

    db.add(
        SessionAnswer(
            session_id=session.id,
            question_id=question.id,
            user_answer=req.answer.upper(),
            is_correct=is_correct,
        )
    )
    db.flush()

    # Count after flush so the new answer is included
    answered_count = db.execute(
        select(func.count(SessionAnswer.id)).where(
            SessionAnswer.session_id == session.id
        )
    ).scalar()

    correct_count = db.execute(
        select(func.count(SessionAnswer.id)).where(
            SessionAnswer.session_id == session.id,
            SessionAnswer.is_correct.is_(True),
        )
    ).scalar()

    if answered_count >= session.total_questions:
        session.finished_at = datetime.now(timezone.utc)

    db.commit()

    return AnswerResponse(
        correct=is_correct,
        correct_answer=question.correct_answer,
        regulation_ref=question.regulation_ref,
        session_progress=SessionProgress(
            answered=answered_count,
            total=session.total_questions,
            correct=correct_count,
        ),
    )


@router.get("/sessions/{session_id}/results", response_model=SessionResultsResponse)
def get_session_results(session_id: str, db: Session = Depends(get_db)):
    """Get session results with category breakdown."""
    session = db.execute(
        select(PracticeSession).where(
            PracticeSession.id == uuid.UUID(session_id)
        )
    ).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all answers with category info
    answers = db.execute(
        select(
            SessionAnswer.is_correct,
            Category.name.label("category_name"),
        )
        .join(Question, SessionAnswer.question_id == Question.id)
        .join(Category, Question.category_id == Category.id)
        .where(SessionAnswer.session_id == session.id)
    ).all()

    total = len(answers)
    correct = sum(1 for a in answers if a.is_correct)

    # Category breakdown
    cat_stats: dict[str, dict] = {}
    for a in answers:
        if a.category_name not in cat_stats:
            cat_stats[a.category_name] = {"correct": 0, "total": 0}
        cat_stats[a.category_name]["total"] += 1
        if a.is_correct:
            cat_stats[a.category_name]["correct"] += 1

    breakdown = [
        CategoryBreakdown(
            category_name=name,
            correct=stats["correct"],
            total=stats["total"],
            percentage=round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
        )
        for name, stats in cat_stats.items()
    ]

    return SessionResultsResponse(
        session_id=session_id,
        total=total,
        correct=correct,
        incorrect=total - correct,
        percentage=round(correct / total * 100, 1) if total > 0 else 0,
        category_breakdown=breakdown,
    )
