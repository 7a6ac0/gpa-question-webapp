import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import (
    Base,
    Category,
    Question,
    PracticeSession,
    SessionAnswer,
    SessionCategory,
    CATEGORY_SEED,
    get_db,
)


# Override database for testing
TEST_DB_URL = "sqlite:///test_api.db"
test_engine = create_engine(TEST_DB_URL)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(test_engine)

    from src.api.main import app
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
    import os
    if os.path.exists("test_api.db"):
        os.remove("test_api.db")


@pytest.fixture(autouse=True)
def setup_db():
    """Reset DB before each test."""
    db = TestSession()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()

    for cat in CATEGORY_SEED:
        db.add(Category(**cat))
    db.commit()
    db.close()


def _seed_questions(count=10, category_id=1, q_type="tf"):
    """Helper to seed questions."""
    import hashlib
    db = TestSession()
    questions = []
    for i in range(count):
        text = f"API測試問題-{category_id}-{q_type}-{i}"
        h = hashlib.sha256(f"{category_id}|{q_type}|{text}".encode()).hexdigest()
        q = Question(
            category_id=category_id,
            question_type=q_type,
            question_text=text,
            correct_answer="O" if q_type == "tf" else "B",
            options=[f"(A) A-{i}", f"(B) B-{i}", f"(C) C-{i}", f"(D) D-{i}"] if q_type == "mc" else None,
            regulation_ref=f"第{i+1}條",
            source_hash=h,
        )
        db.add(q)
        questions.append(q)
    db.commit()
    ids = [q.id for q in questions]
    db.close()
    return ids


class TestHealthEndpoint:
    def test_health(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


class TestCategoriesEndpoint:
    def test_list_categories(self, client):
        res = client.get("/api/categories")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 13
        assert data[0]["name"] == "政府採購全生命週期概論"

    def test_categories_with_counts(self, client):
        _seed_questions(5, category_id=1)
        res = client.get("/api/categories")
        data = res.json()
        cat1 = next(c for c in data if c["id"] == 1)
        assert cat1["question_count"] == 5

    def test_empty_category_shows_zero(self, client):
        res = client.get("/api/categories")
        data = res.json()
        cat3 = next(c for c in data if c["id"] == 3)
        assert cat3["question_count"] == 0


class TestQuestionsEndpoint:
    def test_get_questions(self, client):
        _seed_questions(5, category_id=1)
        res = client.get("/api/questions?category_ids=1&count=3")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 3
        # Should NOT contain correct_answer
        assert "correct_answer" not in data[0]

    def test_filter_by_type(self, client):
        _seed_questions(5, category_id=1, q_type="tf")
        _seed_questions(5, category_id=1, q_type="mc")
        res = client.get("/api/questions?category_ids=1&type=mc&count=10")
        data = res.json()
        assert all(q["question_type"] == "mc" for q in data)

    def test_count_exceeds_available(self, client):
        _seed_questions(3, category_id=1)
        res = client.get("/api/questions?category_ids=1&count=100")
        data = res.json()
        assert len(data) == 3  # Returns all available


class TestSessionsEndpoint:
    def test_create_session(self, client):
        _seed_questions(10, category_id=1)
        res = client.post("/api/sessions", json={
            "category_ids": [1],
            "count": 5,
        })
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert len(data["questions"]) == 5

    def test_create_session_invalid_category(self, client):
        res = client.post("/api/sessions", json={
            "category_ids": [999],
            "count": 5,
        })
        assert res.status_code == 400

    def test_create_session_no_questions(self, client):
        res = client.post("/api/sessions", json={
            "category_ids": [1],
            "count": 5,
        })
        assert res.status_code == 404


class TestAnswerEndpoint:
    def _create_session(self, client, category_id=1, count=5):
        _seed_questions(count, category_id=category_id)
        res = client.post("/api/sessions", json={
            "category_ids": [category_id],
            "count": count,
        })
        return res.json()

    def test_submit_answer(self, client):
        session_data = self._create_session(client)
        q = session_data["questions"][0]

        res = client.post("/api/answer", json={
            "session_id": session_data["session_id"],
            "question_id": q["id"],
            "answer": "O",
        })
        assert res.status_code == 200
        data = res.json()
        assert "correct" in data
        assert "correct_answer" in data
        assert data["session_progress"]["answered"] == 1
        assert data["session_progress"]["total"] == 5

    def test_submit_wrong_answer(self, client):
        session_data = self._create_session(client)
        q = session_data["questions"][0]

        res = client.post("/api/answer", json={
            "session_id": session_data["session_id"],
            "question_id": q["id"],
            "answer": "X",
        })
        data = res.json()
        # Could be correct or wrong depending on the question
        assert "correct" in data
        assert "regulation_ref" in data

    def test_duplicate_answer_rejected(self, client):
        session_data = self._create_session(client)
        q = session_data["questions"][0]

        client.post("/api/answer", json={
            "session_id": session_data["session_id"],
            "question_id": q["id"],
            "answer": "O",
        })
        res = client.post("/api/answer", json={
            "session_id": session_data["session_id"],
            "question_id": q["id"],
            "answer": "X",
        })
        assert res.status_code == 409

    def test_invalid_session_id(self, client):
        res = client.post("/api/answer", json={
            "session_id": str(uuid.uuid4()),
            "question_id": 1,
            "answer": "O",
        })
        assert res.status_code == 404

    def test_invalid_question_id(self, client):
        session_data = self._create_session(client)
        res = client.post("/api/answer", json={
            "session_id": session_data["session_id"],
            "question_id": 99999,
            "answer": "O",
        })
        assert res.status_code == 404


class TestResultsEndpoint:
    def test_get_results(self, client):
        _seed_questions(3, category_id=1)
        session_res = client.post("/api/sessions", json={
            "category_ids": [1],
            "count": 3,
        })
        session_data = session_res.json()
        sid = session_data["session_id"]

        # Answer all questions
        for q in session_data["questions"]:
            client.post("/api/answer", json={
                "session_id": sid,
                "question_id": q["id"],
                "answer": "O",
            })

        res = client.get(f"/api/sessions/{sid}/results")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 3
        assert len(data["category_breakdown"]) >= 1

    def test_results_invalid_session(self, client):
        res = client.get(f"/api/sessions/{uuid.uuid4()}/results")
        assert res.status_code == 404
