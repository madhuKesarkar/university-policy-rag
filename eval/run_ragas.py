"""Ragas evaluation layer, on top of the custom eval in run_eval.py.

run_eval.py already measures this project's most direct success criteria (abstention
accuracy, citation accuracy — both at 100%/90%+ with zero dependency risk). Ragas's unique
value on top of that is two metrics our custom eval can't compute itself, since they need an
LLM judge to reason about the text rather than just compare IDs/filenames:
  - faithfulness: is the answer actually grounded in the retrieved context, or did the LLM add
    unsupported claims? (an independent hallucination check beyond "did it cite the right doc")
  - context_recall: of what SHOULD have been retrieved to answer the question, how much was
    actually found? (measures retrieval quality directly, complementary to the rerank-score
    analysis from step 3)

Deliberately DROPS context_precision and answer_correctness by default — they're the two
metrics most prone to judge-LLM flakiness in testing, and citation accuracy (which
answer_correctness partly overlaps with) is already fully covered by run_eval.py. Pass
--metrics to add them back if you want the fuller picture and have quota to spare.

Both the judge LLM and judge embeddings are wired to free/local models (Groq via its
OpenAI-compatible endpoint, and the same local bge-small embeddings used everywhere else in
this project) — no OpenAI key needed, keeping this step $0 like the rest of the stack.

Only runs over questions that were EXPECTED to be answerable and WERE answered — these metrics
don't meaningfully apply to "should refuse" cases (run_eval.py's abstention accuracy already
covers those). Reads run_eval.py's raw_results.json rather than re-querying the API.

Quota footprint: each row costs ~1 judge-LLM call per metric (faithfulness costs a bit more —
it first decomposes the answer into individual claims, then checks each one). Two metrics over
a small representative sample (default: up to 2 rows per category, ~10-12 rows total) uses a
small fraction of a free-tier daily token budget — leaving headroom for manual live testing
alongside it, which is the whole point of trimming this down from "all 36 eligible rows x 4
metrics" (144 judge calls) to a deliberately small, representative slice.

Usage (from backend/, with venv active, after running run_eval.py at least once):
    python ../eval/run_ragas.py                          # ~2/category, faithfulness + context_recall
    python ../eval/run_ragas.py --per-category 1          # even smaller: ~1/category
    python ../eval/run_ragas.py --metrics faithfulness context_recall context_precision answer_correctness
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

from datasets import Dataset
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_correctness, context_precision, context_recall, faithfulness
from ragas.run_config import RunConfig

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from app.config import settings  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"

ALL_METRICS = {
    "faithfulness": faithfulness,
    "context_precision": context_precision,
    "context_recall": context_recall,
    "answer_correctness": answer_correctness,
}
DEFAULT_METRICS = ["faithfulness", "context_recall"]


def build_eligible_rows(raw_results: list[dict]) -> list[dict]:
    rows = []
    for row in raw_results:
        tc, resp = row["test_case"], row["response"]
        if not (tc["expected_answerable"] and resp["answered"] and tc.get("ground_truth")):
            continue
        rows.append(
            {
                "category": tc["category"],
                # ragas 0.2.x's schema (SingleTurnSample) renamed these from the older
                # question/answer/contexts/ground_truth field names — this IS the current API,
                # not a mistake to "fix" back.
                "user_input": tc["question"],
                "response": resp["answer"] or "",
                "retrieved_contexts": [p["content"] for p in resp["retrieved_passages"]],
                "reference": tc["ground_truth"],
            }
        )
    return rows


def stratified_sample(rows: list[dict], per_category: int) -> list[dict]:
    """Up to `per_category` rows from EACH category, rather than just the first N overall —
    a flat --limit N would silently only ever sample the early categories in
    test_questions.json (cs4780, stat3000, ...) and never reach rbac_allowed/cross_document."""
    by_category: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_category[row["category"]].append(row)
    sampled = []
    for category in sorted(by_category):
        sampled.extend(by_category[category][:per_category])
    return sampled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--per-category", type=int, default=2, help="max eligible rows to sample per question category (default: 2)"
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        choices=list(ALL_METRICS),
        default=DEFAULT_METRICS,
        help=f"which ragas metrics to compute (default: {' '.join(DEFAULT_METRICS)})",
    )
    args = parser.parse_args()

    raw_results = json.loads((RESULTS_DIR / "raw_results.json").read_text())
    eligible = build_eligible_rows(raw_results)
    sampled = stratified_sample(eligible, args.per_category)
    dataset = Dataset.from_list([{k: v for k, v in r.items() if k != "category"} for r in sampled])

    categories = sorted({r["category"] for r in sampled})
    print(
        f"Evaluating {len(dataset)} rows across {len(categories)} categories {categories} "
        f"with metrics {args.metrics} (of {len(eligible)} eligible)..."
    )

    # Judge LLM: Groq via its OpenAI-compatible endpoint — free, no separate SDK needed for ragas.
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            temperature=0.0,
            timeout=60,
        )
    )
    # Judge embeddings: the same local, free bge-small model used everywhere else in this project.
    judge_embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=settings.embedding_model))

    metrics = [ALL_METRICS[name] for name in args.metrics]

    # Groq's free tier has a per-minute request-rate limit; ragas's default 16 concurrent
    # workers blows straight through it (surfaced as opaque TimeoutErrors — the real 429s were
    # being retried into the ground rather than raised). Low concurrency helps that.
    #
    # BUT: ragas's own default retry policy (max_retries=10, up to 60s backoff each) means one
    # job that keeps soft-failing (e.g. the judge LLM returns something ragas's own parser
    # can't handle — not necessarily a Groq-side error at all) can silently grind for 20+
    # minutes with zero output, indistinguishable from a true hang. Confirmed this directly:
    # process alive, CPU time frozen, no error, no progress, for many minutes straight. Failing
    # fast (few retries, short timeout) trades "eventually maybe succeeds" for "you actually see
    # what broke" — the right tradeoff for a small eval run you're watching, not a background job.
    result = evaluate(
        dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=RunConfig(max_workers=2, timeout=30, max_retries=2, max_wait=10),
        raise_exceptions=False,  # one bad row becomes NaN in that row's score, not a killed run
    )

    df = result.to_pandas()
    df.to_csv(RESULTS_DIR / "ragas_scores.csv", index=False)

    means = df[args.metrics].mean()  # skipna=True by default: a metric that errored on some rows
    counts = df[args.metrics].count()  # is averaged over the rows that DID score, not silently zeroed

    metric_descriptions = {
        "faithfulness": "is the answer grounded in the retrieved passages, no unsupported claims",
        "context_precision": "of what was retrieved, how much was actually relevant",
        "context_recall": "of what should have been retrieved, how much was found",
        "answer_correctness": "does the answer match the expected ground truth",
    }

    summary_lines = [
        "# Ragas Evaluation Results\n",
        f"Evaluated {len(df)} rows (sampled up to {args.per_category}/category across {len(categories)} "
        f"categories, out of {len(eligible)} eligible answered+expected-answerable questions).\n",
        "Some metric computations can individually time out against a free-tier LLM judge under "
        "load (see the `scored` count) — the mean is over the rows that did score, not all of "
        "them; a low `scored` count means take that mean with a grain of salt.\n",
        "| metric | mean score | scored | what it measures |",
        "|---|---|---|---|",
    ]
    for name in args.metrics:
        summary_lines.append(
            f"| {name} | {means[name]:.3f} | {counts[name]}/{len(df)} | {metric_descriptions[name]} |"
        )
    summary_lines.append("")

    question_col = "user_input" if "user_input" in df.columns else "question"
    sort_col = "context_recall" if "context_recall" in args.metrics else args.metrics[0]
    summary_lines.append(f"## Lowest-scoring rows by {sort_col} (worth inspecting)\n")
    worst = df.nsmallest(min(5, len(df)), sort_col)[[question_col] + args.metrics]
    for _, r in worst.iterrows():
        scores = " ".join(f"{m}={r[m]:.2f}" for m in args.metrics)
        summary_lines.append(f"- {scores} — {r[question_col]}")

    summary = "\n".join(summary_lines)
    (RESULTS_DIR / "ragas_summary.md").write_text(summary)
    print("\n" + summary)
    print(f"\nFull per-row scores -> {RESULTS_DIR / 'ragas_scores.csv'}")


if __name__ == "__main__":
    main()
