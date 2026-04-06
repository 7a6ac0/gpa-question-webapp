"""LLM client for generating AI explanations via OpenAI-compatible API (LiteLLM)."""
import logging
import os
import re

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.database import Regulation

logger = logging.getLogger(__name__)

CACHE_VERSION = 1


def is_llm_available() -> bool:
    """Return True if LLM_API_KEY is set to a non-empty string."""
    return bool(os.environ.get("LLM_API_KEY", ""))


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", "https://litellm.justmao.com/v1"),
        )
    return _client


SYSTEM_PROMPT = """你是一位專業的政府採購法教師。請用繁體中文回答。
你的任務是解釋為什麼學生的答案是錯的，以及正確答案為什麼是對的。
請引用提供的法條原文。回答限制在 200 字以內。
不要引用任何未在下方提供的法條。"""

SYSTEM_PROMPT_NO_REF = """你是一位專業的政府採購法教師。請用繁體中文回答。
你的任務是根據題目內容解釋為什麼學生的答案是錯的，以及正確答案為什麼是對的。
回答限制在 200 字以內。"""

ARTICLE_NUMBER_RE = re.compile(r"第\s*(\d+)\s*條(?:\s*之\s*(\d+))?")


def extract_article_numbers(regulation_ref: str | None) -> list[str]:
    """Extract article numbers from regulation_ref text.

    Supports patterns like 第22條, 第 22 條, 第22條之1.
    Returns normalized numbers like ["22", "22之1"].
    """
    if not regulation_ref:
        return []
    results = []
    for m in ARTICLE_NUMBER_RE.finditer(regulation_ref):
        num = m.group(1)
        sub = m.group(2)
        results.append(f"{num}之{sub}" if sub else num)
    return results


def get_regulation_texts(db: Session, article_numbers: list[str]) -> str:
    """Look up regulation texts from DB by article numbers."""
    if not article_numbers:
        return ""
    rows = db.execute(
        select(Regulation).where(Regulation.article_number.in_(article_numbers))
    ).scalars().all()
    return "\n\n".join(
        f"第{r.article_number}條：{r.article_text}" for r in rows
    )


def generate_explanation(
    question_text: str,
    selected_answer: str,
    correct_answer: str,
    regulation_ref: str | None,
    regulation_text: str,
) -> str:
    """Call LLM to generate explanation via OpenAI-compatible API (LiteLLM)."""
    client = _get_client()

    if regulation_text:
        system = SYSTEM_PROMPT
        user_prompt = (
            f"題目：{question_text}\n"
            f"學生答案：{selected_answer}\n"
            f"正確答案：{correct_answer}\n"
            f"相關法條：\n{regulation_text}\n\n"
            f"請解釋為什麼學生的答案是錯的。"
        )
    else:
        system = SYSTEM_PROMPT_NO_REF
        ref_line = f"參考：{regulation_ref}\n" if regulation_ref else ""
        user_prompt = (
            f"題目：{question_text}\n"
            f"學生答案：{selected_answer}\n"
            f"正確答案：{correct_answer}\n"
            f"{ref_line}\n"
            f"請根據題目內容解釋為什麼學生的答案是錯的。"
        )

    response = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001"),
        max_tokens=500,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    )

    if not response.choices or not response.choices[0].message.content:
        return "抱歉，暫時無法產生解釋。請稍後再試。"

    return response.choices[0].message.content
