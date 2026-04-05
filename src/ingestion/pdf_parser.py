import logging
import re
from pathlib import Path

import pdfplumber

from src.ingestion.base import QuestionRecord

logger = logging.getLogger(__name__)

# Regex patterns for PCC question bank PDF format
# MC: "number answer(1-4) question_text (1)opt1 (2)opt2 (3)opt3 (4)opt4"
# TF: "number answer(O/X) question_text"
MC_QUESTION_START = re.compile(r"^\s*(\d+)\s+([1-4])\s+(.+)")
TF_QUESTION_START = re.compile(r"^\s*(\d+)\s+([OX])\s+(.+)")
HEADER_LINE = re.compile(r"^\s*(編\s+答\s+試題|號\s+案|資料產生日期)")
REGULATION_REF = re.compile(r"(第\s*\d+\s*條[^。，\n]*)")

ANSWER_NUM_TO_LETTER = {"1": "A", "2": "B", "3": "C", "4": "D"}


def parse_pdf(filepath: Path, category_id: int) -> list[QuestionRecord]:
    """Parse a PCC question bank PDF into QuestionRecords."""
    records: list[QuestionRecord] = []

    try:
        with pdfplumber.open(filepath) as pdf:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    except Exception:
        logger.exception("Failed to open PDF: %s", filepath)
        return records

    lines = full_text.split("\n")
    tf_lines, mc_lines = _split_sections(lines)

    records.extend(_parse_tf_questions(tf_lines, category_id))
    records.extend(_parse_mc_questions(mc_lines, category_id))

    logger.info("Parsed %d questions from %s", len(records), filepath.name)
    return records


def _is_skip_line(line: str) -> bool:
    """Check if a line is a header/metadata line that should be skipped."""
    stripped = line.strip()
    if not stripped:
        return True
    if HEADER_LINE.match(stripped):
        return True
    if stripped in ("選擇題", "是非題"):
        return True
    return False


def _split_sections(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split lines into true/false and multiple-choice sections."""
    tf_lines: list[str] = []
    mc_lines: list[str] = []
    current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped == "是非題":
            current_section = "tf"
            continue
        elif stripped == "選擇題":
            current_section = "mc"
            continue

        if current_section == "tf":
            tf_lines.append(line)
        elif current_section == "mc":
            mc_lines.append(line)
        else:
            # Before any section header, detect by content
            if TF_QUESTION_START.match(line):
                current_section = "tf"
                tf_lines.append(line)
            elif MC_QUESTION_START.match(line):
                current_section = "mc"
                mc_lines.append(line)

    return tf_lines, mc_lines


def _parse_tf_questions(lines: list[str], category_id: int) -> list[QuestionRecord]:
    """Parse true/false question lines."""
    records: list[QuestionRecord] = []
    current_text_parts: list[str] = []
    current_answer: str | None = None

    def _save():
        if current_answer and current_text_parts:
            text = " ".join(current_text_parts).strip()
            records.append(
                QuestionRecord(
                    category_id=category_id,
                    question_type="tf",
                    question_text=text,
                    correct_answer=current_answer,
                    regulation_ref=_extract_regulation(text),
                )
            )

    for line in lines:
        if _is_skip_line(line):
            continue

        tf_match = TF_QUESTION_START.match(line)
        if tf_match:
            _save()
            current_answer = tf_match.group(2)
            current_text_parts = [tf_match.group(3).strip()]
        elif current_answer is not None:
            stripped = line.strip()
            if stripped:
                current_text_parts.append(stripped)

    _save()
    return records


def _parse_mc_questions(lines: list[str], category_id: int) -> list[QuestionRecord]:
    """Parse multiple-choice question lines."""
    records: list[QuestionRecord] = []
    current_text_parts: list[str] = []
    current_answer_num: str | None = None

    def _save():
        if current_answer_num and current_text_parts:
            full_text = " ".join(current_text_parts).strip()
            question_text, options = _extract_mc_options(full_text)
            answer_letter = ANSWER_NUM_TO_LETTER.get(
                current_answer_num, current_answer_num
            )
            records.append(
                QuestionRecord(
                    category_id=category_id,
                    question_type="mc",
                    question_text=question_text,
                    correct_answer=answer_letter,
                    options=options,
                    regulation_ref=_extract_regulation(full_text),
                )
            )

    for line in lines:
        if _is_skip_line(line):
            continue

        mc_match = MC_QUESTION_START.match(line)
        if mc_match:
            _save()
            current_answer_num = mc_match.group(2)
            current_text_parts = [mc_match.group(3).strip()]
        elif current_answer_num is not None:
            stripped = line.strip()
            if stripped:
                current_text_parts.append(stripped)

    _save()
    return records


def _extract_mc_options(full_text: str) -> tuple[str, list[str] | None]:
    """Extract question stem and options from MC question text.

    Options are inline as (1)...(2)...(3)...(4)...
    Converts to (A)...(B)...(C)...(D)... for frontend compatibility.
    """
    match = re.search(
        r"\(1\)(.+?)\(2\)(.+?)\(3\)(.+?)\(4\)(.+)", full_text, re.DOTALL
    )
    if not match:
        return full_text, None

    question_stem = full_text[: match.start()].strip()
    options = [
        f"(A) {match.group(1).strip()}",
        f"(B) {match.group(2).strip()}",
        f"(C) {match.group(3).strip()}",
        f"(D) {match.group(4).strip()}",
    ]

    return question_stem, options


def _extract_regulation(text: str) -> str | None:
    """Extract regulation reference from question text."""
    match = REGULATION_REF.search(text)
    return match.group(1) if match else None
