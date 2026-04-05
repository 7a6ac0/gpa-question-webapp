import logging
from pathlib import Path

from docx import Document

from src.ingestion.base import QuestionRecord
from src.ingestion.pdf_parser import (
    _split_sections,
    _parse_tf_questions,
    _parse_mc_questions,
)

logger = logging.getLogger(__name__)


def parse_docx(filepath: Path, category_id: int) -> list[QuestionRecord]:
    """Parse a DOCX question bank file into QuestionRecords."""
    try:
        doc = Document(str(filepath))
    except Exception:
        logger.exception("Failed to open DOCX: %s", filepath)
        return []

    lines = [para.text for para in doc.paragraphs if para.text.strip()]

    tf_lines, mc_lines = _split_sections(lines)

    records: list[QuestionRecord] = []
    records.extend(_parse_tf_questions(tf_lines, category_id))
    records.extend(_parse_mc_questions(mc_lines, category_id))

    logger.info("Parsed %d questions from %s", len(records), filepath.name)
    return records
