import json

import pytest

from app.services import llm

pytestmark = pytest.mark.unit

PASSAGE = {"title": "T", "content": "C", "section_heading": "S", "page_number": 1, "is_stale": False}
USAGE = {"input": 10, "output": 5, "total": 15}


@pytest.fixture
def llm_returns(monkeypatch):
    """Fake the Groq call so no network or API key is needed."""

    def _set(raw_text):
        monkeypatch.setattr(llm.settings, "llm_provider", "groq")
        monkeypatch.setattr(llm, "_call_groq", lambda system, user: (raw_text, USAGE))

    return _set


def test_valid_json_is_parsed(llm_returns):
    llm_returns(json.dumps({"can_answer": True, "answer": "Yes.", "citation_indices": [1]}))
    answer, usage = llm.generate_answer("q?", [PASSAGE])
    assert answer.can_answer is True
    assert answer.answer == "Yes."
    assert answer.citation_indices == [1]
    assert usage == USAGE


def test_optional_fields_get_defaults(llm_returns):
    llm_returns('{"can_answer": false}')
    answer, _ = llm.generate_answer("q?", [PASSAGE])
    assert answer.answer == ""
    assert answer.citation_indices == []


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '{"can_answer": true, "answer": "cut off',      # truncated
        '{"answer": "missing can_answer"}',              # required field missing
        '{"can_answer": "maybe"}',                       # wrong type
        '{"can_answer": true, "citation_indices": "1"}', # wrong type
        "",
    ],
)
def test_malformed_output_fails_safe(llm_returns, raw):
    llm_returns(raw)
    answer, usage = llm.generate_answer("q?", [PASSAGE])
    assert answer.can_answer is False
    assert usage == USAGE  # tokens were still spent, so usage is still reported


def test_json_wrapped_in_extra_text_is_not_recovered(llm_returns):
    # FINDING: a valid answer inside a ```json fence is thrown away as "I don't know".
    llm_returns('```json\n{"can_answer": true, "answer": "Yes."}\n```')
    answer, _ = llm.generate_answer("q?", [PASSAGE])
    assert answer.can_answer is False


def test_no_passages_means_no_llm_call(monkeypatch):
    def must_not_be_called(*args):
        raise AssertionError("LLM was called with nothing to read")

    monkeypatch.setattr(llm, "_call_groq", must_not_be_called)
    answer, usage = llm.generate_answer("q?", [])
    assert answer.can_answer is False
    assert usage == {}


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "openai")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        llm.generate_answer("q?", [PASSAGE])