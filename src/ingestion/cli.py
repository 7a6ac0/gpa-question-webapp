"""CLI for ingesting question bank files into the database.

Usage:
    python -m src.ingestion.cli parse --input ./data/
    python -m src.ingestion.cli parse --input ./data/ --category 2
"""
import argparse
import logging
import sys
from pathlib import Path

from src.ingestion.base import QuestionRecord, upsert_questions
from src.ingestion.doc_parser import parse_docx
from src.ingestion.pdf_parser import parse_pdf
from src.models.database import CATEGORY_SEED, SessionLocal, seed_categories

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def detect_category_id(filepath: Path) -> int | None:
    """Try to detect category ID from filename.

    Expected patterns: '01_xxx.pdf', 'category_01.pdf', etc.
    Falls back to None if not detectable.
    """
    import re

    name = filepath.stem
    # Try to find a leading 2-digit number
    match = re.match(r"(\d{1,2})", name)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 13:
            return num
    return None


def parse_command(args: argparse.Namespace) -> None:
    input_dir = Path(args.input)
    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    files = list(input_dir.glob("*.pdf")) + list(input_dir.glob("*.docx"))
    if not files:
        logger.error("No PDF or DOCX files found in %s", input_dir)
        sys.exit(1)

    logger.info("Found %d files to parse", len(files))

    db = SessionLocal()
    try:
        seed_categories(db)

        all_records: list[QuestionRecord] = []
        for filepath in sorted(files):
            if args.category:
                category_id = args.category
            else:
                category_id = detect_category_id(filepath)
                if category_id is None:
                    logger.warning(
                        "Cannot detect category for %s. Use --category flag. Skipping.",
                        filepath.name,
                    )
                    continue

            logger.info("Parsing %s (category %d)...", filepath.name, category_id)

            if filepath.suffix.lower() == ".pdf":
                records = parse_pdf(filepath, category_id)
            elif filepath.suffix.lower() == ".docx":
                records = parse_docx(filepath, category_id)
            else:
                continue

            all_records.extend(records)

        if all_records:
            stats = upsert_questions(db, all_records)
            logger.info("Summary: %s", stats)
        else:
            logger.warning("No questions parsed from any file.")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="GPA Question Bank Ingestion CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse local PDF/DOCX files")
    parse_parser.add_argument(
        "--input", "-i", required=True, help="Directory containing PDF/DOCX files"
    )
    parse_parser.add_argument(
        "--category", "-c", type=int, help="Force category ID for all files"
    )

    args = parser.parse_args()

    if args.command == "parse":
        parse_command(args)


if __name__ == "__main__":
    main()
