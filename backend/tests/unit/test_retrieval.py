from unittest.mock import MagicMock

import pytest

from app.services import retrieval

pytestmark = pytest.mark.unit


def fake_session(rows=None):
    session = MagicMock()
    result = []
    for r in rows or []:
        row = MagicMock()
        row._mapping = r
        result.append(row)
    session.execute.return_value = result
    return session


def sql_and_params(session):
    sql_clause, params = session.execute.call_args.args
    return str(sql_clause), params


# --- the role filter is inside the SQL, before ranking ----------------------

@pytest.mark.parametrize("search", ["semantic", "fulltext"])
def test_role_filter_is_in_the_query(search):
    session = fake_session()
    if search == "semantic":
        retrieval.semantic_search(session, [0.1] * 384, role="student", top_k=5)
    else:
        retrieval.fulltext_search(session, "late fee", role="student", top_k=5)

    sql, params = sql_and_params(session)
    assert "d.allowed_roles @> ARRAY[:role]" in sql
    assert "d.is_active = true" in sql
    assert params["role"] == "student"
    # the filter must come before ORDER BY, i.e. before ranking
    assert sql.index("allowed_roles") < sql.index("ORDER BY")


def test_top_k_is_passed_as_limit():
    session = fake_session()
    retrieval.semantic_search(session, [0.1] * 384, role="professor", top_k=7)
    sql, params = sql_and_params(session)
    assert "LIMIT :top_k" in sql
    assert params["top_k"] == 7


def test_role_is_a_bound_parameter_not_pasted_into_sql():
    session = fake_session()
    retrieval.semantic_search(session, [0.1] * 384, role="student' OR '1'='1", top_k=5)
    sql, params = sql_and_params(session)
    assert "OR '1'='1" not in sql
    assert params["role"] == "student' OR '1'='1"


# --- RRF fusion logic in hybrid_search --------------------------------------

def hit(chunk_id):
    return {"id": chunk_id, "content": f"text {chunk_id}"}


def test_chunk_found_by_both_methods_ranks_first(monkeypatch):
    monkeypatch.setattr(retrieval, "semantic_search", lambda *a, **k: [hit("A"), hit("B")])
    monkeypatch.setattr(retrieval, "fulltext_search", lambda *a, **k: [hit("C"), hit("B")])

    results = retrieval.hybrid_search(MagicMock(), "q", [0.0], role="student", top_k=3)

    assert results[0]["id"] == "B"
    assert results[0]["retrieval_sources"] == ["fulltext", "semantic"]


def test_rrf_score_formula(monkeypatch):
    monkeypatch.setattr(retrieval, "semantic_search", lambda *a, **k: [hit("A")])
    monkeypatch.setattr(retrieval, "fulltext_search", lambda *a, **k: [hit("A")])

    results = retrieval.hybrid_search(MagicMock(), "q", [0.0], role="student", top_k=5)

    expected = 2 * (1 / (retrieval.RRF_K + 1))
    assert results[0]["rrf_score"] == pytest.approx(expected)


def test_results_are_deduped_and_cut_to_top_k(monkeypatch):
    monkeypatch.setattr(retrieval, "semantic_search", lambda *a, **k: [hit(i) for i in "ABCDE"])
    monkeypatch.setattr(retrieval, "fulltext_search", lambda *a, **k: [hit(i) for i in "EDCBA"])

    results = retrieval.hybrid_search(MagicMock(), "q", [0.0], role="student", top_k=3)

    ids = [r["id"] for r in results]
    assert len(ids) == 3
    assert len(set(ids)) == 3


def test_no_hits_gives_empty_list(monkeypatch):
    monkeypatch.setattr(retrieval, "semantic_search", lambda *a, **k: [])
    monkeypatch.setattr(retrieval, "fulltext_search", lambda *a, **k: [])
    assert retrieval.hybrid_search(MagicMock(), "q", [0.0], role="student", top_k=3) == []