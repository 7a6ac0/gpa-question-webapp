import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.database import Explanation, Question, get_db
from src.models.schemas import ExplainRequest, ExplainResponse
from src.services.llm import (
    CACHE_VERSION,
    extract_article_numbers,
    generate_explanation,
    get_regulation_texts,
    is_llm_available,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest, db: Session = Depends(get_db)):
    """Generate or retrieve cached AI explanation for a wrong answer."""
    if not is_llm_available():
        raise HTTPException(status_code=503, detail="AI 解釋功能目前未啟用")

    question = db.execute(
        select(Question).where(Question.id == req.question_id)
    ).scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if req.selected_answer.upper() == question.correct_answer.upper():
        raise HTTPException(status_code=400, detail="Cannot explain correct answer")

    # Check cache
    try:
        cached = db.execute(
            select(Explanation).where(
                Explanation.question_id == req.question_id,
                Explanation.selected_answer == req.selected_answer.upper(),
                Explanation.cache_version == CACHE_VERSION,
            )
        ).scalar_one_or_none()
    except Exception:
        logger.exception("Cache read failed, falling back to LLM")
        cached = None

    if cached:
        logger.info("Cache hit: question_id=%d, answer=%s", req.question_id, req.selected_answer)
        return ExplainResponse(explanation=cached.explanation_text, cached=True)

    # Cache miss: generate via LLM
    logger.info("Cache miss: question_id=%d, answer=%s", req.question_id, req.selected_answer)

    article_numbers = extract_article_numbers(question.regulation_ref)
    regulation_text = get_regulation_texts(db, article_numbers)

    try:
        explanation_text = generate_explanation(
            question_text=question.question_text,
            selected_answer=req.selected_answer.upper(),
            correct_answer=question.correct_answer,
            regulation_ref=question.regulation_ref,
            regulation_text=regulation_text,
        )
    except Exception:
        logger.exception("LLM call failed for question_id=%d", req.question_id)
        raise HTTPException(
            status_code=503,
            detail="暫時無法生成解釋，請稍後再試",
        )

    # Save to cache (ON CONFLICT DO NOTHING for concurrent writes)
    try:
        new_explanation = Explanation(
            question_id=req.question_id,
            selected_answer=req.selected_answer.upper(),
            explanation_text=explanation_text,
            cache_version=CACHE_VERSION,
        )
        db.add(new_explanation)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Cache write conflict for question_id=%d, answer=%s",
                        req.question_id, req.selected_answer)

    return ExplainResponse(explanation=explanation_text, cached=False)
