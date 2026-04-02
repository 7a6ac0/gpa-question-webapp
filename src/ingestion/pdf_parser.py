import logging
import re
from pathlib import Path

import pdfplumber

from src.ingestion.base import QuestionRecord

logger = logging.getLogger(__name__)

# Regex patterns
QUESTION_BOUNDARY = re.compile(r"^\s*(\d+)\s*[.、]\s*")
TF_PATTERN = re.compile(r"^\s*(\d+)\s*[.、]\s*\(([OX])\)\s*(.+)")
MC_OPTION = re.compile(r"^\s*\(([A-D])\)\s*(.+)")
REGULATION_REF = re.compile(r"(第\s*\d+\s*條[^。，\n]*)")


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

    # Split into sections: true/false (是非題) and multiple-choice (選擇題)
    tf_lines, mc_lines = _split_sections(lines)

    # Parse true/false questions
    records.extend(_parse_tf_questions(tf_lines, category_id))

    # Parse multiple-choice questions
    records.extend(_parse_mc_questions(mc_lines, category_id))

    logger.info("Parsed %d questions from %s", len(records), filepath.name)
    return records


def _split_sections(lines: list[str]) -> tuple[list[str], list[str]]:
    """Split lines into true/false and multiple-choice sections."""
    tf_lines: list[str] = []
    mc_lines: list[str] = []

    current_section = None

    for line in lines:
        stripped = line.strip()
        if "是非題" in stripped:
            current_section = "tf"
            continue
        elif "選擇題" in stripped:
            current_section = "mc"
            continue

        if current_section == "tf":
            tf_lines.append(line)
        elif current_section == "mc":
            mc_lines.append(line)
        else:
            # Before any section header, try to detect by content
            tf_match = TF_PATTERN.match(line)
            if tf_match:
                current_section = "tf"
                tf_lines.append(line)

    return tf_lines, mc_lines


def _parse_tf_questions(lines: list[str], category_id: int) -> list[QuestionRecord]:
    """Parse true/false question lines."""
    records = []
    current_text_parts: list[str] = []
    current_answer: str | None = None

    for line in lines:
        tf_match = TF_PATTERN.match(line)
        if tf_match:
            # Save previous question if exists
            if current_answer and current_text_parts:
                text = " ".join(current_text_parts).strip()
                reg_ref = _extract_regulation(text)
                records.append(
                    QuestionRecord(
                        category_id=category_id,
                        question_type="tf",
                        question_text=text,
                        correct_answer=current_answer,
                        regulation_ref=reg_ref,
                    )
                )

            current_answer = tf_match.group(2)
            current_text_parts = [tf_match.group(3).strip()]
        elif current_answer is not None:
            stripped = line.strip()
            if stripped and not QUESTION_BOUNDARY.match(line):
                current_text_parts.append(stripped)

    # Save last question
    if current_answer and current_text_parts:
        text = " ".join(current_text_parts).strip()
        reg_ref = _extract_regulation(text)
        records.append(
            QuestionRecord(
                category_id=category_id,
                question_type="tf",
                question_text=text,
                correct_answer=current_answer,
                regulation_ref=reg_ref,
            )
        )

    return records


def _parse_mc_questions(lines: list[str], category_id: int) -> list[QuestionRecord]:
    """Parse multiple-choice question lines."""
    records = []

    # Group lines into questions
    questions_raw: list[dict] = []
    current: dict | None = None

    for line in lines:
        q_match = QUESTION_BOUNDARY.match(line)
        option_match = MC_OPTION.match(line.strip())

        if q_match and not option_match:
            if current:
                questions_raw.append(current)
            # Check if answer is embedded like: 1. (B) question text
            answer_embedded = re.match(r"^\s*\d+\s*[.、]\s*\(([A-D])\)\s*(.+)", line)
            if answer_embedded:
                current = {
                    "answer": answer_embedded.group(1),
                    "text_parts": [answer_embedded.group(2).strip()],
                    "options": [],
                }
            else:
                text = QUESTION_BOUNDARY.sub("", line).strip()
                current = {
                    "answer": None,
                    "text_parts": [text] if text else [],
                    "options": [],
                }
        elif option_match and current is not None:
            current["options"].append(f"({option_match.group(1)}) {option_match.group(2).strip()}")
        elif current is not None:
            stripped = line.strip()
            if stripped:
                if current["options"]:
                    # Continuation of last option
                    current["options"][-1] += " " + stripped
                else:
                    current["text_parts"].append(stripped)

    if current:
        questions_raw.append(current)

    # Convert to QuestionRecords
    for q in questions_raw:
        if not q["text_parts"]:
            continue

        text = " ".join(q["text_parts"]).strip()
        options = q["options"] if q["options"] else None
        answer = q.get("answer")

        if not answer:
            logger.warning("MC question without answer detected, skipping: %s...", text[:50])
            continue

        reg_ref = _extract_regulation(text)
        records.append(
            QuestionRecord(
                category_id=category_id,
                question_type="mc",
                question_text=text,
                correct_answer=answer,
                options=options,
                regulation_ref=reg_ref,
            )
        )

    return records


def _extract_regulation(text: str) -> str | None:
    """Extract regulation reference from question text."""
    match = REGULATION_REF.search(text)
    return match.group(1) if match else None
