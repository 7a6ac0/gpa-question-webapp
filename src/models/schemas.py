from pydantic import BaseModel, Field


class CategoryResponse(BaseModel):
    id: int
    name: str
    source_code: str
    question_count: int

    model_config = {"from_attributes": True}


class QuestionResponse(BaseModel):
    id: int
    category_id: int
    category_name: str
    question_type: str
    question_text: str
    options: list[str] | None = None

    model_config = {"from_attributes": True}


class AnswerRequest(BaseModel):
    session_id: str
    question_id: int
    answer: str


class SessionProgress(BaseModel):
    answered: int
    total: int
    correct: int


class AnswerResponse(BaseModel):
    correct: bool
    correct_answer: str
    regulation_ref: str | None = None
    session_progress: SessionProgress


class CreateSessionRequest(BaseModel):
    category_ids: list[int]
    question_type: str | None = None
    count: int = 20
    anonymous_id: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str
    questions: list[QuestionResponse]


class WeaknessCategoryStats(BaseModel):
    category_id: int
    category_name: str
    total: int
    correct: int
    percentage: float


class WeaknessResponse(BaseModel):
    anonymous_id: str
    sessions_count: int
    total_answered: int
    total_correct: int
    overall_percentage: float
    categories: list[WeaknessCategoryStats]


class CategoryBreakdown(BaseModel):
    category_name: str
    correct: int
    total: int
    percentage: float


class SessionResultsResponse(BaseModel):
    session_id: str
    total: int
    correct: int
    incorrect: int
    percentage: float
    category_breakdown: list[CategoryBreakdown]


class ExplainRequest(BaseModel):
    question_id: int
    selected_answer: str = Field(max_length=10)


class ExplainResponse(BaseModel):
    explanation: str
    cached: bool
