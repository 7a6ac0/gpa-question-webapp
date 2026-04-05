import os
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID type. Uses CHAR(36) on SQLite, UUID on PostgreSQL."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
        return value


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://gpa:gpa_dev_password@localhost:5432/gpa_questions"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    source_code = Column(String(2), nullable=False, unique=True)
    description = Column(Text)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    questions = relationship("Question", back_populates="category")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    question_type = Column(String(10), nullable=False)  # 'tf' or 'mc'
    question_text = Column(Text, nullable=False)
    options = Column(JSON)  # ["(A) ...", "(B) ...", ...] for mc, null for tf
    correct_answer = Column(String(10), nullable=False)  # 'O'/'X' for tf, 'A'/'B'/'C'/'D' for mc
    regulation_ref = Column(Text)
    source_hash = Column(String(64), unique=True, nullable=False)
    deleted_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    category = relationship("Category", back_populates="questions")

    __table_args__ = (
        Index("idx_questions_category", "category_id"),
        Index("idx_questions_type", "question_type"),
        Index("idx_questions_hash", "source_hash"),
        Index("idx_questions_active", "id", postgresql_where=(deleted_at.is_(None))),
    )


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    anonymous_id = Column(String(64))
    question_type = Column(String(10))  # 'tf', 'mc', or null (all)
    total_questions = Column(Integer, nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime)

    answers = relationship("SessionAnswer", back_populates="session", cascade="all, delete-orphan")
    categories = relationship("SessionCategory", back_populates="session", cascade="all, delete-orphan")


class SessionAnswer(Base):
    __tablename__ = "session_answers"

    id = Column(Integer, primary_key=True)
    session_id = Column(GUID(), ForeignKey("practice_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_answer = Column(String(10), nullable=False)  # 'O'/'X' or 'A'/'B'/'C'/'D'
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime, server_default=func.now())

    session = relationship("PracticeSession", back_populates="answers")
    question = relationship("Question")

    __table_args__ = (
        Index("idx_session_answers_session", "session_id"),
    )


class SessionCategory(Base):
    __tablename__ = "session_categories"

    session_id = Column(GUID(), ForeignKey("practice_sessions.id", ondelete="CASCADE"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)

    session = relationship("PracticeSession", back_populates="categories")
    category = relationship("Category")


class Regulation(Base):
    __tablename__ = "regulations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_number = Column(String(10), unique=True, nullable=False)
    article_text = Column(Text, nullable=False)
    chapter = Column(String(50))
    law_name = Column(String(50), default="政府採購法")
    updated_at = Column(DateTime, server_default=func.now())


class Explanation(Base):
    __tablename__ = "explanations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_answer = Column(String(10), nullable=False)
    explanation_text = Column(Text, nullable=False)
    cache_version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "question_id", "selected_answer", "cache_version",
            name="uq_explanation_cache",
        ),
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


CATEGORY_SEED = [
    {"id": 1, "name": "政府採購全生命週期概論", "source_code": "01"},
    {"id": 2, "name": "政府採購法之總則、招標及決標", "source_code": "02"},
    {"id": 3, "name": "政府採購法之履約管理及驗收", "source_code": "03"},
    {"id": 4, "name": "政府採購法之罰則及附則", "source_code": "04"},
    {"id": 5, "name": "政府採購法之爭議處理", "source_code": "05"},
    {"id": 6, "name": "底價及價格分析", "source_code": "06"},
    {"id": 7, "name": "投標須知及招標文件製作", "source_code": "07"},
    {"id": 8, "name": "採購契約", "source_code": "08"},
    {"id": 9, "name": "最有利標及評選優勝廠商", "source_code": "09"},
    {"id": 10, "name": "電子採購實務", "source_code": "10"},
    {"id": 11, "name": "工程及技術服務採購作業", "source_code": "11"},
    {"id": 12, "name": "財物及勞務採購作業", "source_code": "12"},
    {"id": 13, "name": "道德規範及違法處置", "source_code": "13"},
]


def seed_categories(db):
    """Seed categories if they don't exist."""
    from sqlalchemy import select

    for cat_data in CATEGORY_SEED:
        existing = db.execute(
            select(Category).where(Category.id == cat_data["id"])
        ).scalar_one_or_none()
        if not existing:
            db.add(Category(**cat_data))
    db.commit()
