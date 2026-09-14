"""POST /ask — the core student-facing endpoint.

Role comes from the verified JWT (app.deps.get_current_user), never from the request body,
so a student cannot simply claim to be a professor to see restricted documents. search()
applies the allowed_roles filter inside the SQL itself (see app/services/retrieval.py), before
any ranking happens.

The LLM (app/services/llm.py) is the real "I do not know" arbiter, not the retrieval score.
Step 4 testing showed a wrong top match scoring HIGHER (0.723) on a deliberately out-of-corpus
question than some genuinely correct in-corpus answers scored (0.503-0.726) — a fixed
threshold on retrieval confidence alone cannot reliably separate the two. The retrieval score
is still logged (useful for the eval/dashboard in steps 6-7) but the final answered/not-answered
decision comes from the LLM's own can_answer judgment, made after reading the actual passages.
"""
import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.deps import get_current_user
from app.models import QueryLog, User
from app.schemas import AskRequest, AskResponse, Citation, RetrievedChunk
from app.services.llm import generate_answer
from app.services.search import search
from app.services.tracing import trace_ask

router = APIRouter(tags=["ask"])

NO_ANSWER_MESSAGE = (
    "I do not know. I couldn't find a passage in the indexed documents that confidently "
    "answers this question — please check with your department or the registrar directly."
)


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> AskResponse:
    start = time.perf_counter()

    with trace_ask(payload.question, user_id=str(current_user.id), role=current_user.role) as tracer:
        results = search(session, payload.question, role=current_user.role)
        retrieval_top_score = results[0]["rerank_score"] if results else 0.0
        tracer.span(
            name="hybrid_retrieval_and_rerank",
            input={"question": payload.question, "role": current_user.role},
            output=[
                {"source": r["source_filename"], "section": r["section_heading"], "rerank_score": r["rerank_score"]}
                for r in results
            ],
            metadata={"top_score": retrieval_top_score},
        )

        llm_answer, usage = generate_answer(payload.question, results)
        answered = llm_answer.can_answer and bool(llm_answer.answer.strip())
        tracer.generation(
            name="answer_generation",
            model=settings.groq_model if settings.llm_provider == "groq" else settings.gemini_model,
            input=payload.question,
            output=llm_answer.model_dump(),
            usage=usage or None,
        )
        tracer.score(name="answered", value=answered)
        tracer.score(name="retrieval_top_score", value=retrieval_top_score)

        latency_ms = int((time.perf_counter() - start) * 1000)
        tracer.update(output={"answered": answered, "answer": llm_answer.answer}, metadata={"latency_ms": latency_ms})

    def to_citation(r: dict) -> Citation:
        return Citation(
            document_title=r["title"],
            course_code=r["course_code"],
            department=r["department"],
            section_heading=r["section_heading"],
            page_number=r["page_number"],
            source_filename=r["source_filename"],
            is_stale=r["is_stale"],
        )

    citations = [
        to_citation(results[idx - 1])
        for idx in llm_answer.citation_indices
        if 1 <= idx <= len(results)
    ]

    retrieved_passages = [
        RetrievedChunk(
            content=r["content"],
            citation=to_citation(r),
            rerank_score=r["rerank_score"],
            retrieval_sources=r["retrieval_sources"],
        )
        for r in results
    ]

    session.add(
        QueryLog(
            user_id=current_user.id,
            question=payload.question,
            answer=llm_answer.answer if answered else None,
            answered=answered,
            top_chunk_ids=[r["id"] for r in results] or None,
            top_score=retrieval_top_score,
            latency_ms=latency_ms,
            model=settings.groq_model if settings.llm_provider == "groq" else settings.gemini_model,
            prompt_tokens=usage.get("input"),
            completion_tokens=usage.get("output"),
        )
    )
    session.commit()

    return AskResponse(
        answered=answered,
        answer=llm_answer.answer if answered else None,
        message=None if answered else NO_ANSWER_MESSAGE,
        citations=citations,
        retrieved_passages=retrieved_passages,
        latency_ms=latency_ms,
    )
