"""Ragas evaluation layer, on top of the custom eval in run_eval.py.

run_eval.py already measures this project's most direct success criteria (abstention
accuracy, citation accuracy) with zero dependency risk. Ragas adds standard RAG metrics that
require an LLM judge to compute:
  - faithfulness: is the answer actually grounded in the retrieved context, or did the LLM add
    unsupported claims? (a second, independent hallucination check beyond "did it cite a doc")
  - context_precision / context_recall: of what was retrieved, how much was relevant, and of
    what SHOULD have been retrieved, how much was found? (measures retrieval quality directly,
    which is what step 3's hybrid search + rerank is supposed to deliver)
  - answer_correctness: does the answer match the expected ground truth?

Both the judge LLM and judge embeddings are wired to free/local models (Groq via its
OpenAI-compatible endpoint, and the same local bge-small embeddings used everywhere else in
this project) — no OpenAI key needed, keeping this step $0 like the rest of the stack.

Only runs over questions that were EXPECTED to be answerable and WERE answered — these metrics
don't meaningfully apply to "should refuse" cases (run_eval.py's abstention accuracy already
covers those). Reads run_eval.py's raw_results.json rather than re-querying the API.

Usage (from backend/, with venv active, after running run_eval.py at least once):
    python ../eval/run_ragas.py [--limit N]
"""
import argparse
import json
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


def build_dataset(raw_results: list[dict], limit: int | None) -> Dataset:
    rows = []
    for row in raw_results:
        tc, resp = row["test_case"], row["response"]
        if not (tc["expected_answerable"] and resp["answered"] and tc.get("ground_truth")):
            continue
        rows.append(
            {
                # ragas 0.2.x's schema (SingleTurnSample) renamed these from the older
                # question/answer/contexts/ground_truth field names — this IS the current API,
                # not a mistake to "fix" back.
                "user_input": tc["question"],
                "response": resp["answer"] or "",
                "retrieved_contexts": [p["content"] for p in resp["retrieved_passages"]],
                "reference": tc["ground_truth"],
            }
        )
    if limit:
        rows = rows[:limit]
    return Dataset.from_list(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only evaluate the first N eligible rows (smoke test)")
    args = parser.parse_args()

    raw_results = json.loads((RESULTS_DIR / "raw_results.json").read_text())
    dataset = build_dataset(raw_results, args.limit)
    print(f"Evaluating {len(dataset)} answered, expected-answerable questions with Ragas...")

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

    # Groq's free tier has a per-minute request-rate limit; ragas's default 16 concurrent
    # workers blows straight through it, which surfaced as opaque TimeoutErrors (the real 429s
    # were being retried into the ground rather than raised). Low concurrency + a longer
    # per-job timeout trades eval speed for actually completing on a free-tier key.
    result = evaluate(
        dataset,
        metrics=[faithfulness, context_precision, context_recall, answer_correctness],
        llm=judge_llm,
        embeddings=judge_embeddings,
        run_config=RunConfig(max_workers=2, timeout=120),
    )

    df = result.to_pandas()
    df.to_csv(RESULTS_DIR / "ragas_scores.csv", index=False)

    metric_cols = ["faithfulness", "context_precision", "context_recall", "answer_correctness"]
    means = df[metric_cols].mean()  # skipna=True by default: a metric that errored on some rows
    counts = df[metric_cols].count()  # (see below) is averaged over the rows that DID score, not silently zeroed
    summary_lines = [
        "# Ragas Evaluation Results\n",
        f"Evaluated {len(df)} answered, expected-answerable questions.\n",
        "Some metric computations can individually time out against a free-tier LLM judge under "
        "load (see the `scored` count) — the mean is over the rows that did score, not all of "
        "them; a low `scored` count means take that mean with a grain of salt.\n",
        "| metric | mean score | scored | what it measures |",
        "|---|---|---|---|",
        f"| faithfulness | {means['faithfulness']:.3f} | {counts['faithfulness']}/{len(df)} | is the answer grounded in the retrieved passages, no unsupported claims |",
        f"| context_precision | {means['context_precision']:.3f} | {counts['context_precision']}/{len(df)} | of what was retrieved, how much was actually relevant |",
        f"| context_recall | {means['context_recall']:.3f} | {counts['context_recall']}/{len(df)} | of what should have been retrieved, how much was found |",
        f"| answer_correctness | {means['answer_correctness']:.3f} | {counts['answer_correctness']}/{len(df)} | does the answer match the expected ground truth |",
        "",
        "## Lowest-scoring rows (worth inspecting)\n",
    ]
    question_col = "user_input" if "user_input" in df.columns else "question"
    worst = df.nsmallest(5, "context_recall")[[question_col, "context_recall", "faithfulness", "answer_correctness"]]
    for _, r in worst.iterrows():
        summary_lines.append(
            f"- context_recall={r['context_recall']:.2f} faithfulness={r['faithfulness']:.2f} "
            f"answer_correctness={r['answer_correctness']:.2f} — {r[question_col]}"
        )

    summary = "\n".join(summary_lines)
    (RESULTS_DIR / "ragas_summary.md").write_text(summary)
    print("\n" + summary)
    print(f"\nFull per-row scores -> {RESULTS_DIR / 'ragas_scores.csv'}")


if __name__ == "__main__":
    main()
