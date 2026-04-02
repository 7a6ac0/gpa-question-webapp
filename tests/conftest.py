import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite for tests (no PostgreSQL dependency)
TEST_DB_URL = "sqlite:///test.db"

os.environ["DATABASE_URL"] = TEST_DB_URL

from src.models.database import Base, Category, Question, CATEGORY_SEED


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    # Clean up test db file
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture
def db(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    # Clear all tables before each test
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()

    # Seed categories
    for cat_data in CATEGORY_SEED:
        session.add(Category(**cat_data))
    session.commit()

    yield session
    session.close()


@pytest.fixture
def sample_questions(db):
    """Insert sample questions for testing."""
    import hashlib

    questions = []
    for i in range(5):
        text = f"是非題測試問題 {i+1}"
        h = hashlib.sha256(f"1|tf|{text}".encode()).hexdigest()
        q = Question(
            category_id=1,
            question_type="tf",
            question_text=text,
            correct_answer="O" if i % 2 == 0 else "X",
            regulation_ref=f"政府採購法第{i+1}條",
            source_hash=h,
        )
        db.add(q)
        questions.append(q)

    for i in range(5):
        text = f"選擇題測試問題 {i+1}"
        h = hashlib.sha256(f"2|mc|{text}".encode()).hexdigest()
        q = Question(
            category_id=2,
            question_type="mc",
            question_text=text,
            options=[
                f"(A) 選項A-{i}",
                f"(B) 選項B-{i}",
                f"(C) 選項C-{i}",
                f"(D) 選項D-{i}",
            ],
            correct_answer="B",
            regulation_ref=f"政府採購法第{10+i}條",
            source_hash=h,
        )
        db.add(q)
        questions.append(q)

    db.commit()
    return questions
