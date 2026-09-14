"""LLM answer generation. Per step 4's finding, the LLM — not the retrieval-score threshold
— is the real "I don't know" arbiter: it sees ONLY the retrieved passages and must explicitly
say so when none of them actually answer the question, rather than a numeric score trying (and
failing) to make that call on its own.
"""
import json

from pydantic import BaseModel, Field

from app.config import settings

SYSTEM_PROMPT = """You are a university academic-policy assistant. Answer using ONLY the \
passages provided below — never your own outside knowledge of how universities, courses, or \
policies typically work, since this university's actual rules may differ.

Rules:
1. If, and only if, the passages actually contain the information needed to answer the \
question, set can_answer=true and write a direct, concise answer grounded in them.
2. If the passages do not answer the question — even if they are topically related — set \
can_answer=false and leave answer empty. Being topically related is NOT the same as answering \
the question. Do not guess, infer, or fill gaps with general knowledge.
3. Every factual claim in your answer must be traceable to a specific passage. Track which \
passages you actually used by their [N] index.
4. If a passage is marked as a draft, unpublished, or flagged as possibly outdated, say so \
explicitly rather than presenting it as settled policy.

Respond with ONLY a JSON object, no other text:
{"can_answer": bool, "answer": string, "citation_indices": [int]}
citation_indices lists the [N] index of every passage you actually used (empty if can_answer \
is false)."""


class LLMAnswer(BaseModel):
    can_answer: bool
    answer: str = ""
    citation_indices: list[int] = Field(default_factory=list)


def _build_user_prompt(question: str, passages: list[dict]) -> str:
    blocks = []
    for i, p in enumerate(passages, start=1):
        stale_note = " [FLAGGED: not recently reviewed, may be outdated]" if p.get("is_stale") else ""
        scope = p.get("course_code") or p.get("department") or "university-wide"
        blocks.append(
            f'[{i}] Source: "{p["title"]}" ({scope}), section "{p.get("section_heading") or "n/a"}", '
            f'page {p.get("page_number") or "n/a"}{stale_note}\n{p["content"]}'
        )
    return f"Question: {question}\n\nPassages:\n\n" + "\n\n".join(blocks)


def _call_groq(system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    from groq import Groq

    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys and add "
            "it to backend/.env (or the repo-root .env), then restart the server."
        )
    client = Groq(api_key=settings.groq_api_key)
    completion = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    usage = completion.usage
    usage_dict = {
        "input": getattr(usage, "prompt_tokens", None),
        "output": getattr(usage, "completion_tokens", None),
        "total": getattr(usage, "total_tokens", None),
    }
    return completion.choices[0].message.content, usage_dict


def _call_gemini(system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    import google.generativeai as genai

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey and "
            "add it to backend/.env (or the repo-root .env), then restart the server."
        )
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model, system_instruction=system_prompt)
    response = model.generate_content(
        user_prompt, generation_config={"temperature": 0.0, "response_mime_type": "application/json"}
    )
    usage = getattr(response, "usage_metadata", None)
    usage_dict = {
        "input": getattr(usage, "prompt_token_count", None),
        "output": getattr(usage, "candidates_token_count", None),
        "total": getattr(usage, "total_token_count", None),
    }
    return response.text, usage_dict


def generate_answer(question: str, passages: list[dict]) -> tuple[LLMAnswer, dict]:
    """Returns (parsed answer, token usage dict) — usage is {} when there was nothing to send
    to the LLM at all (no retrieved passages), so no API call was made."""
    if not passages:
        return LLMAnswer(can_answer=False), {}

    user_prompt = _build_user_prompt(question, passages)

    if settings.llm_provider == "groq":
        raw, usage = _call_groq(SYSTEM_PROMPT, user_prompt)
    elif settings.llm_provider == "gemini":
        raw, usage = _call_gemini(SYSTEM_PROMPT, user_prompt)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")

    try:
        return LLMAnswer(**json.loads(raw)), usage
    except Exception:
        # malformed LLM output: fail safe to "I don't know" rather than guess at broken JSON
        return LLMAnswer(can_answer=False), usage
