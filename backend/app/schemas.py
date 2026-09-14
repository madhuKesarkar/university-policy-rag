"""Pydantic request/response models — the API's public contract."""
import uuid

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    # DEMO SHORTCUT: a real university system would never let self-registration pick its own
    # role — role/department would come from institutional SSO (student/professor/staff feed)
    # or an admin-only provisioning endpoint. Left open here so RBAC is easy to test end-to-end;
    # flagged again in ask.py's docstring and in the final write-up.
    role: str = "student"
    department: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    department: str | None
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Citation(BaseModel):
    document_title: str
    course_code: str | None
    department: str | None
    section_heading: str | None
    page_number: int | None
    source_filename: str
    is_stale: bool


class RetrievedChunk(BaseModel):
    content: str
    citation: Citation
    rerank_score: float
    retrieval_sources: list[str]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class DailyPoint(BaseModel):
    date: str
    total: int
    answered: int
    unanswered: int
    avg_latency_ms: float


class AnalyticsSummary(BaseModel):
    total_queries: int
    answered_count: int
    unanswered_count: int  # "failed searches" / "unsupported answers" — the system said "I don't know"
    unanswered_rate: float
    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    estimated_cost_usd: float  # what usage WOULD cost on a paid tier; $0 in practice on free tier
    priced_models: list[str]
    unpriced_models: list[str]  # models used that aren't in our pricing table (cost not counted for these)
    recent_unanswered_questions: list[str]
    daily: list[DailyPoint]


class AskResponse(BaseModel):
    answered: bool
    answer: str | None = None  # the LLM's prose answer, only set when answered=True
    message: str | None = None  # set to the "I do not know" explanation when answered=False
    citations: list[Citation] = []  # only the passages the LLM actually cited
    retrieved_passages: list[RetrievedChunk] = []  # everything retrieval considered, for transparency/debugging
    latency_ms: int
