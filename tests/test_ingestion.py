import hashlib
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.base import QuestionRecord, upsert_questions
from src.models.database import Question


class TestQuestionRecord:
    def test_source_hash_deterministic(self):
        r = QuestionRecord(
            category_id=1,
            question_type="tf",
            question_text="測試問題",
            correct_answer="O",
        )
        expected = hashlib.sha256("1|tf|測試問題".encode("utf-8")).hexdigest()
        assert r.source_hash == expected

    def test_source_hash_includes_category_and_type(self):
        r1 = QuestionRecord(category_id=1, question_type="tf", question_text="同一問題", correct_answer="O")
        r2 = QuestionRecord(category_id=2, question_type="tf", question_text="同一問題", correct_answer="O")
        r3 = QuestionRecord(category_id=1, question_type="mc", question_text="同一問題", correct_answer="A")
        assert r1.source_hash != r2.source_hash
        assert r1.source_hash != r3.source_hash


class TestUpsertQuestions:
    def test_insert_new_questions(self, db):
        records = [
            QuestionRecord(
                category_id=1,
                question_type="tf",
                question_text="新問題1",
                correct_answer="O",
            ),
            QuestionRecord(
                category_id=1,
                question_type="tf",
                question_text="新問題2",
                correct_answer="X",
            ),
        ]
        stats = upsert_questions(db, records)
        assert stats["new"] == 2
        assert stats["updated"] == 0
        assert stats["unchanged"] == 0

    def test_unchanged_on_repeat(self, db):
        records = [
            QuestionRecord(
                category_id=1,
                question_type="tf",
                question_text="重複問題",
                correct_answer="O",
            ),
        ]
        upsert_questions(db, records)
        stats = upsert_questions(db, records)
        assert stats["new"] == 0
        assert stats["unchanged"] == 1

    def test_update_changed_answer(self, db):
        r1 = QuestionRecord(category_id=1, question_type="tf", question_text="更新問題", correct_answer="O")
        upsert_questions(db, [r1])

        r2 = QuestionRecord(category_id=1, question_type="tf", question_text="更新問題", correct_answer="X")
        stats = upsert_questions(db, [r2])
        assert stats["updated"] == 1

    def test_soft_delete_removed_questions(self, db):
        r1 = QuestionRecord(category_id=1, question_type="tf", question_text="會被刪除", correct_answer="O")
        r2 = QuestionRecord(category_id=1, question_type="tf", question_text="會保留", correct_answer="X")
        upsert_questions(db, [r1, r2])

        # Second upsert only has r2
        stats = upsert_questions(db, [r2])
        assert stats["soft_deleted"] == 1
        assert stats["unchanged"] == 1

    def test_no_duplicates(self, db):
        records = [
            QuestionRecord(category_id=1, question_type="tf", question_text="唯一問題", correct_answer="O"),
            QuestionRecord(category_id=1, question_type="tf", question_text="唯一問題", correct_answer="O"),
        ]
        # Same hash should only insert once (second is unchanged)
        stats = upsert_questions(db, records)
        assert stats["new"] == 1
        assert stats["unchanged"] == 1


class TestPDFParser:
    def test_split_sections(self):
        from src.ingestion.pdf_parser import _split_sections

        lines = [
            "選擇題",
            "編 答 試題",
            "號 案",
            "1 4 依政府採購法規定？ (1)選項一。 (2)選項二。 (3)選項三。 (4)選項四。",
            "是非題",
            "編 答 試題",
            "號 案",
            "1 O 問題一。",
            "2 X 問題二。",
        ]
        tf, mc = _split_sections(lines)
        # MC: header lines + 1 question line = 3 lines
        assert len(tf) == 4  # header lines + 2 question lines
        assert len(mc) == 3  # header lines + 1 question line

    def test_parse_tf_questions(self):
        from src.ingestion.pdf_parser import _parse_tf_questions

        lines = [
            "編 答 試題",
            "號 案",
            "1 O 機關辦理公告金額以上採購之招標，應依政府採購法第19條規定辦理。",
            "2 X 採購之招標方式，分為公開招標、選擇性招標及限制性招標三種。",
        ]
        records = _parse_tf_questions(lines, category_id=1)
        assert len(records) == 2
        assert records[0].correct_answer == "O"
        assert records[1].correct_answer == "X"
        assert records[0].question_type == "tf"

    def test_parse_tf_multiline(self):
        from src.ingestion.pdf_parser import _parse_tf_questions

        lines = [
            "1 O 因設計與計畫核定有時間差，爰機關編列計畫經費時，除應配合當時物價編",
            "列，亦應針對其後之物價調整編列費用。",
        ]
        records = _parse_tf_questions(lines, category_id=1)
        assert len(records) == 1
        assert "物價調整編列費用" in records[0].question_text

    def test_parse_mc_questions(self):
        from src.ingestion.pdf_parser import _parse_mc_questions

        lines = [
            "1 2 依政府採購法規定，下列何者得採限制性招標？ (1)選項一。 (2)選項二。 (3)選項三。 (4)選項四。",
        ]
        records = _parse_mc_questions(lines, category_id=1)
        assert len(records) == 1
        assert records[0].correct_answer == "B"
        assert records[0].question_type == "mc"
        assert len(records[0].options) == 4
        assert records[0].options[0].startswith("(A)")
        assert records[0].options[1].startswith("(B)")

    def test_parse_mc_multiline(self):
        from src.ingestion.pdf_parser import _parse_mc_questions

        lines = [
            "1 4 依政府公共工程計畫與經費審議作業要點，以下何者不是基本設計階段審議",
            "之重點？ (1)經費合理性。 (2)技術可行性。 (3)期程妥適性。 (4)以上皆",
            "是。",
        ]
        records = _parse_mc_questions(lines, category_id=1)
        assert len(records) == 1
        assert records[0].correct_answer == "D"
        assert records[0].options is not None
        assert len(records[0].options) == 4

    def test_extract_regulation(self):
        from src.ingestion.pdf_parser import _extract_regulation

        text = "依政府採購法第22條第1項第7款規定辦理"
        ref = _extract_regulation(text)
        assert ref is not None
        assert "第22條" in ref
