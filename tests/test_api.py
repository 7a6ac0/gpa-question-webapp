import os
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import (
    Base,
    Category,
    Explanation,
    Question,
    PracticeSession,
    Regulation,
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


class TestWeaknessEndpoint:
    def test_weakness_no_data(self, client):
        res = client.get("/api/weakness?anonymous_id=nonexistent")
        assert res.status_code == 200
        data = res.json()
        assert data["sessions_count"] == 0
        assert data["total_answered"] == 0
        assert data["categories"] == []

    def test_weakness_with_sessions(self, client):
        anon_id = "test-weakness-user"

        # Seed questions in 2 categories
        _seed_questions(5, category_id=1, q_type="tf")
        _seed_questions(5, category_id=2, q_type="tf")

        # Session 1: answer cat 1 questions (all correct)
        res1 = client.post("/api/sessions", json={
            "category_ids": [1],
            "count": 3,
            "anonymous_id": anon_id,
        })
        s1 = res1.json()
        for q in s1["questions"]:
            client.post("/api/answer", json={
                "session_id": s1["session_id"],
                "question_id": q["id"],
                "answer": "O",
            })

        # Session 2: answer cat 2 questions (all wrong)
        res2 = client.post("/api/sessions", json={
            "category_ids": [2],
            "count": 3,
            "anonymous_id": anon_id,
        })
        s2 = res2.json()
        for q in s2["questions"]:
            client.post("/api/answer", json={
                "session_id": s2["session_id"],
                "question_id": q["id"],
                "answer": "X",
            })

        res = client.get(f"/api/weakness?anonymous_id={anon_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["sessions_count"] == 2
        assert data["total_answered"] == 6
        assert len(data["categories"]) == 2

    def test_weakness_sorts_worst_first(self, client):
        anon_id = "test-weakness-sort"

        _seed_questions(5, category_id=1, q_type="tf")
        _seed_questions(5, category_id=2, q_type="tf")

        # Cat 1: all correct (100%)
        res1 = client.post("/api/sessions", json={
            "category_ids": [1],
            "count": 2,
            "anonymous_id": anon_id,
        })
        s1 = res1.json()
        for q in s1["questions"]:
            client.post("/api/answer", json={
                "session_id": s1["session_id"],
                "question_id": q["id"],
                "answer": "O",
            })

        # Cat 2: all wrong (0%)
        res2 = client.post("/api/sessions", json={
            "category_ids": [2],
            "count": 2,
            "anonymous_id": anon_id,
        })
        s2 = res2.json()
        for q in s2["questions"]:
            client.post("/api/answer", json={
                "session_id": s2["session_id"],
                "question_id": q["id"],
                "answer": "X",
            })

        res = client.get(f"/api/weakness?anonymous_id={anon_id}")
        data = res.json()
        cats = data["categories"]
        # Worst first: cat 2 (0%) before cat 1 (100%)
        assert cats[0]["percentage"] < cats[1]["percentage"]
        assert cats[0]["category_name"] == "政府採購法之總則、招標及決標"  # cat 2


def _mock_llm_response(text="這是一個測試解釋。"):
    """Create a mock OpenAI chat completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = text
    return mock_response


@patch.dict(os.environ, {"LLM_API_KEY": "test-key"})
class TestExplainEndpoint:
    def _seed_question_with_ref(self, q_type="tf", regulation_ref="依第22條"):
        """Seed a single question and return its ID."""
        import hashlib
        db = TestSession()
        text = f"測試解釋題目-{uuid.uuid4().hex[:8]}"
        h = hashlib.sha256(f"explain|{text}".encode()).hexdigest()
        q = Question(
            category_id=1,
            question_type=q_type,
            question_text=text,
            correct_answer="O" if q_type == "tf" else "B",
            regulation_ref=regulation_ref,
            source_hash=h,
        )
        db.add(q)
        db.commit()
        qid = q.id
        db.close()
        return qid

    def test_explain_question_not_found(self, client):
        res = client.post("/api/explain", json={
            "question_id": 99999,
            "selected_answer": "X",
        })
        assert res.status_code == 404

    def test_explain_correct_answer_rejected(self, client):
        qid = self._seed_question_with_ref()
        res = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "O",  # correct answer
        })
        assert res.status_code == 400
        assert "correct answer" in res.json()["detail"].lower()

    @patch("src.api.routes.explanations.generate_explanation")
    def test_explain_cache_miss_then_hit(self, mock_gen, client):
        mock_gen.return_value = "因為依據第22條規定，正確答案是O。"
        qid = self._seed_question_with_ref()

        # First call: cache miss
        res1 = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "X",
        })
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["cached"] is False
        assert "第22條" in data1["explanation"]
        mock_gen.assert_called_once()

        # Second call: cache hit
        mock_gen.reset_mock()
        res2 = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "X",
        })
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["cached"] is True
        assert data2["explanation"] == data1["explanation"]
        mock_gen.assert_not_called()

    @patch("src.api.routes.explanations.generate_explanation")
    def test_explain_no_regulation_ref(self, mock_gen, client):
        mock_gen.return_value = "這題的正確答案是O，因為題目描述的情況符合規定。"
        qid = self._seed_question_with_ref(regulation_ref=None)

        res = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "X",
        })
        assert res.status_code == 200
        assert res.json()["cached"] is False
        mock_gen.assert_called_once()

    @patch("src.api.routes.explanations.generate_explanation")
    def test_explain_llm_failure(self, mock_gen, client):
        mock_gen.side_effect = Exception("LLM timeout")
        qid = self._seed_question_with_ref()

        res = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "X",
        })
        assert res.status_code == 503

    @patch.dict(os.environ, {"LLM_API_KEY": ""})
    def test_explain_returns_503_when_llm_disabled(self, client):
        """API returns 503 when LLM_API_KEY is empty."""
        qid = self._seed_question_with_ref()
        res = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "X",
        })
        assert res.status_code == 503
        assert "未啟用" in res.json()["detail"]

    def test_explain_cached_entry(self, client):
        """Pre-seed an explanation and verify cache hit without LLM call."""
        qid = self._seed_question_with_ref()
        db = TestSession()
        db.add(Explanation(
            question_id=qid,
            selected_answer="X",
            explanation_text="預先快取的解釋文字",
            cache_version=1,
        ))
        db.commit()
        db.close()

        res = client.post("/api/explain", json={
            "question_id": qid,
            "selected_answer": "X",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["cached"] is True
        assert data["explanation"] == "預先快取的解釋文字"


class TestRegulationRefParsing:
    def test_single_article(self):
        from src.services.llm import extract_article_numbers
        assert extract_article_numbers("依第22條") == ["22"]

    def test_multiple_articles(self):
        from src.services.llm import extract_article_numbers
        result = extract_article_numbers("依第22條及第48條之規定")
        assert "22" in result
        assert "48" in result

    def test_sub_article(self):
        from src.services.llm import extract_article_numbers
        result = extract_article_numbers("第22條之1")
        assert "22之1" in result

    def test_spaced_article(self):
        from src.services.llm import extract_article_numbers
        result = extract_article_numbers("第 22 條")
        assert "22" in result

    def test_none_input(self):
        from src.services.llm import extract_article_numbers
        assert extract_article_numbers(None) == []

    def test_no_match(self):
        from src.services.llm import extract_article_numbers
        assert extract_article_numbers("一般文字沒有條號") == []
