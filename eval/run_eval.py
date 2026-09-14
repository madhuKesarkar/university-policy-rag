"""Runs the 50 test questions against the LIVE /ask API (not a unit test of internals — this
exercises auth, RBAC, retrieval, rerank, and LLM generation exactly as a real student would hit
them) and scores against this project's actual stated success criteria:
  - abstention accuracy: did the system answer exactly when it should have (and refuse when it
    shouldn't), i.e. does it say "I do not know" instead of hallucinating?
  - citation accuracy: when it did answer, did it cite the right source document?
  - staleness accuracy: does it correctly flag/not-flag the two staleness test cases?

Requires the API server running at BASE_URL (see README) and student/professor accounts
already registered (backend/ingestion/sample_docs or the step-5 test accounts).

Usage (from backend/, with venv active):
    python ../eval/run_eval.py
"""
import json
import statistics
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
QUESTIONS_PATH = Path(__file__).parent / "test_questions.json"
RESULTS_DIR = Path(__file__).parent / "results"

TEST_ACCOUNTS = {
    "student": {"email": "alice@uni.edu", "password": "password123"},
    "professor": {"email": "prof.rossi@uni.edu", "password": "password123"},
}


def get_token(client: httpx.Client, role: str) -> str:
    creds = TEST_ACCOUNTS[role]
    resp = client.post(
        "/auth/login",
        data={"username": creds["email"], "password": creds["password"]},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def run_question(client: httpx.Client, token: str, question: str) -> dict:
    start = time.perf_counter()
    resp = client.post(
        "/ask",
        json={"question": question},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60.0,
    )
    wall_ms = int((time.perf_counter() - start) * 1000)
    resp.raise_for_status()
    data = resp.json()
    data["_wall_ms"] = wall_ms
    return data


def main() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text())
    RESULTS_DIR.mkdir(exist_ok=True)

    with httpx.Client(base_url=BASE_URL) as client:
        tokens = {role: get_token(client, role) for role in TEST_ACCOUNTS}

        raw_results = []
        for q in questions:
            print(f"[{q['id']:2}/{len(questions)}] ({q['role']:>9}) {q['question'][:70]}")
            response = run_question(client, tokens[q["role"]], q["question"])
            raw_results.append({"test_case": q, "response": response})

    (RESULTS_DIR / "raw_results.json").write_text(json.dumps(raw_results, indent=2, default=str))
    print(f"\nSaved raw results -> {RESULTS_DIR / 'raw_results.json'}")

    score(raw_results)


def score(raw_results: list[dict]) -> None:
    total = len(raw_results)
    abstention_correct = 0
    citation_correct = 0
    citation_checkable = 0
    staleness_correct = 0
    staleness_checkable = 0
    false_positives = []  # answered when it shouldn't have (hallucination risk)
    false_negatives = []  # refused when it should have answered (over-cautious)
    wrong_citations = []
    by_category: dict[str, dict[str, int]] = {}
    latencies = []

    for row in raw_results:
        tc, resp = row["test_case"], row["response"]
        cat = tc["category"]
        by_category.setdefault(cat, {"total": 0, "abstention_correct": 0})
        by_category[cat]["total"] += 1

        latencies.append(resp["_wall_ms"])

        abstention_ok = resp["answered"] == tc["expected_answerable"]
        if abstention_ok:
            abstention_correct += 1
            by_category[cat]["abstention_correct"] += 1
        elif resp["answered"] and not tc["expected_answerable"]:
            false_positives.append((tc["id"], tc["question"]))
        elif not resp["answered"] and tc["expected_answerable"]:
            false_negatives.append((tc["id"], tc["question"]))

        if tc["expected_answerable"] and tc["expected_sources"] and resp["answered"]:
            citation_checkable += 1
            actual_sources = {c["source_filename"] for c in resp["citations"]}
            if actual_sources & set(tc["expected_sources"]):
                citation_correct += 1
            else:
                wrong_citations.append((tc["id"], tc["question"], sorted(actual_sources)))

        if "expected_stale" in tc and resp["answered"] and resp["citations"]:
            staleness_checkable += 1
            if resp["citations"][0]["is_stale"] == tc["expected_stale"]:
                staleness_correct += 1

    lines = []
    lines.append("# Eval Results\n")
    lines.append(f"**{total} questions** run against the live API.\n")
    lines.append("## Headline metrics\n")
    lines.append(f"- **Abstention accuracy**: {abstention_correct}/{total} ({100*abstention_correct/total:.1f}%) "
                  f"— answered exactly when it should have, refused exactly when it shouldn't")
    if citation_checkable:
        lines.append(f"- **Citation accuracy**: {citation_correct}/{citation_checkable} "
                      f"({100*citation_correct/citation_checkable:.1f}%) of answered, checkable questions cited a correct source doc")
    if staleness_checkable:
        lines.append(f"- **Staleness-flag accuracy**: {staleness_correct}/{staleness_checkable} "
                      f"({100*staleness_correct/staleness_checkable:.1f}%)")
    lines.append(f"- **Latency**: mean {statistics.mean(latencies):.0f}ms | "
                  f"p50 {statistics.median(latencies):.0f}ms | "
                  f"p95 {sorted(latencies)[int(0.95*len(latencies))-1]:.0f}ms\n")

    lines.append("## By category\n")
    lines.append("| category | abstention accuracy |")
    lines.append("|---|---|")
    for cat, stats in sorted(by_category.items()):
        lines.append(f"| {cat} | {stats['abstention_correct']}/{stats['total']} |")
    lines.append("")

    if false_positives:
        lines.append(f"## ⚠️ False positives ({len(false_positives)}) — answered when it should have said \"I don't know\"\n")
        lines.append("**This is the dangerous failure mode (hallucination risk).**\n")
        for qid, q in false_positives:
            lines.append(f"- [{qid}] {q}")
        lines.append("")

    if false_negatives:
        lines.append(f"## False negatives ({len(false_negatives)}) — refused when it should have answered\n")
        for qid, q in false_negatives:
            lines.append(f"- [{qid}] {q}")
        lines.append("")

    if wrong_citations:
        lines.append(f"## Wrong citations ({len(wrong_citations)})\n")
        for qid, q, actual in wrong_citations:
            lines.append(f"- [{qid}] {q} -> cited {actual}")
        lines.append("")

    summary = "\n".join(lines)
    (RESULTS_DIR / "summary.md").write_text(summary)
    print("\n" + summary)


if __name__ == "__main__":
    main()
