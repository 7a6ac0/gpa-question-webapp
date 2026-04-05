"""Seed regulations table from JSON data file."""
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.database import Regulation

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "regulations.json"


def seed_regulations(db: Session, data_path: Path | None = None) -> int:
    """Seed or update regulations from JSON file. Returns count of upserted rows."""
    path = data_path or DATA_FILE
    if not path.exists():
        logger.error("Regulation data file not found: %s", path)
        return 0

    with open(path, encoding="utf-8") as f:
        articles = json.load(f)

    count = 0
    for art in articles:
        existing = db.execute(
            select(Regulation).where(
                Regulation.article_number == art["article_number"]
            )
        ).scalar_one_or_none()

        if existing:
            existing.article_text = art["article_text"]
            existing.chapter = art.get("chapter")
        else:
            db.add(Regulation(
                article_number=art["article_number"],
                article_text=art["article_text"],
                chapter=art.get("chapter"),
                law_name=art.get("law_name", "政府採購法"),
            ))
        count += 1

    db.commit()
    logger.info("Seeded %d regulations", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.models.database import SessionLocal
    db = SessionLocal()
    try:
        n = seed_regulations(db)
        print(f"Done: {n} regulations seeded.")
    finally:
        db.close()
