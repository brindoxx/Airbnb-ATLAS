"""Airbnb ATLAS - RAGAS Automated Golden Set Evaluation Suite.

Evaluates the ATLAS RAG pipeline across the curated Golden Evaluation Set using Ragas metrics:
- Faithfulness: Factual grounding of generated itinerary claims against retrieved chunks.
- Context Precision: Signal-to-noise ratio and rank-ordering of relevant context chunks.
- Context Recall: Proportion of ground-truth destination facts captured in retrieved evidence.

Supports both:
1. Fast, deterministic corpus mode (default): Evaluates Two-Tier retrieval + Generation + Verification
   against snapshotted travel sources with distractor chunks in ChromaDB.
2. Live LangGraph mode (--mode live): Runs end-to-end live DuckDuckGo web search + BeautifulSoup scraping.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import types
import warnings
from typing import Any

# ──────────────────────────────────────────────────
# 1. Harmless Warning Suppression & Environment Setup
# ──────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Ensure the parent directory is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ──────────────────────────────────────────────────
# 2. Patch for Ragas 0.4.x VertexAI Bug
# ──────────────────────────────────────────────────
dummy_chat = types.ModuleType("langchain_community.chat_models.vertexai")
dummy_chat.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = dummy_chat

from datasets import Dataset
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate
from ragas.metrics import context_precision, context_recall, faithfulness
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.run_config import RunConfig

from app.graph import (
    app_graph,
    generator_evaluator,
    verifier_evaluator,
)
from app.rag_engine import (
    chroma_client,
    cross_encoder,
    embeddings,
    format_retrieved_context,
    text_splitter,
)

load_dotenv()

DEFAULT_DATASET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "golden_eval_set.json",
)
DEFAULT_OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "ragas_eval_results.json",
)


# =====================================================================
# Helper: Format Itinerary Cards to Clean Markdown Text
# =====================================================================

def format_cards_to_markdown(cards: list[Any] | str) -> str:
    """Converts structured itinerary cards into a clean, markdown-formatted text response."""
    if isinstance(cards, str):
        return cards.strip()

    if not isinstance(cards, list):
        return str(cards).strip()

    sections = []
    for card in cards:
        if isinstance(card, dict):
            title = card.get("title", "Section")
            details = card.get("details", [])
        else:
            title = getattr(card, "title", "Section")
            details = getattr(card, "details", [])

        bullets = "\n".join([f"- {d}" for d in details])
        sections.append(f"### {title}\n{bullets}")

    return "\n\n".join(sections).strip()


# =====================================================================
# Shared Corpus Indexer for Deterministic Evaluation
# =====================================================================

def index_eval_corpus(items: list[dict[str, Any]], collection_name: str = "ragas_shared_golden_corpus"):
    """Indexes all snapshotted sources from the evaluation set into a shared ephemeral ChromaDB collection.
    This creates an authentic IR testbed where queries must retrieve target destination facts while
    discriminating against distractor chunks from other travel locations.
    """
    collection = chroma_client.get_or_create_collection(collection_name)
    if collection.count() > 0:
        collection.delete(ids=collection.get()["ids"])

    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metas: list[dict[str, Any]] = []

    for item in items:
        qid = item["query_id"]
        sources = item.get("snapshotted_sources", [])
        for s_idx, source in enumerate(sources):
            source_id = source.get("source_id", f"Src-{s_idx+1}")
            text = source.get("text", "")
            split_chunks = text_splitter.split_text(text)
            if not split_chunks:
                split_chunks = [text]

            for c_idx, c_text in enumerate(split_chunks):
                cid = f"{qid}_{source_id}_{c_idx}"
                all_chunks.append(c_text)
                all_ids.append(cid)
                all_metas.append({
                    "query_id": qid,
                    "source_id": source_id,
                    "title": source.get("title", ""),
                    "domain": source.get("domain", ""),
                    "url": f"https://{source.get('domain', 'travel-guide.org')}",
                    "chunk_id": cid,
                })

    print(f"[INDEX] Indexing {len(all_chunks)} chunks across {len(items)} scenarios into shared evaluation corpus...")
    chunk_embeddings = embeddings.embed_documents(all_chunks)
    collection.add(
        documents=all_chunks,
        ids=all_ids,
        metadatas=all_metas,
        embeddings=chunk_embeddings,
    )
    return collection


# =====================================================================
# Scenario Pipeline Execution
# =====================================================================

def run_corpus_scenario(item: dict[str, Any], collection: Any, top_k_candidates: int = 15, final_top_k: int = 5) -> dict[str, Any]:
    """Executes ATLAS Two-Tier retrieval (Bi-Encoder + Cross-Encoder), Citation Generator,
    and Claim Verification Agent over the shared corpus.
    """
    query = item["query"]
    total_docs = collection.count()

    # Contextualize query for revisions if destination is implied from chat history
    constraints = item.get("expected_constraints", {})
    dest = constraints.get("destination") or constraints.get("current_location", "")
    vibe = constraints.get("vibe_or_interests", "")
    budget = constraints.get("budget", "")

    retrieval_query = query
    if dest and dest.lower() not in query.lower():
        retrieval_query = f"{dest} {vibe} {budget} {query}".strip()

    # Tier 1: Bi-Encoder Candidate Retrieval
    query_vector = embeddings.embed_query(retrieval_query)
    cand_res = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k_candidates, total_docs),
        include=["documents", "metadatas"],
    )
    cand_docs = cand_res["documents"][0]
    cand_metas = cand_res["metadatas"][0]

    # Tier 2: Cross-Encoder Reranking
    pairs = [[retrieval_query, d] for d in cand_docs]
    cross_scores = cross_encoder.predict(pairs)
    ranked = sorted(zip(cand_docs, cand_metas, cross_scores), key=lambda x: x[2], reverse=True)[:final_top_k]

    reranked_chunks = []
    for doc, meta, score in ranked:
        reranked_chunks.append({
            "source_id": meta.get("source_id", "Src-1"),
            "chunk_id": meta.get("chunk_id", ""),
            "title": meta.get("title", ""),
            "domain": meta.get("domain", ""),
            "url": meta.get("url", ""),
            "text": doc,
            "rerank_score": float(score),
        })

    formatted_context = format_retrieved_context(reranked_chunks)

    # Stage 4: Citation-Aware Generator
    gen_prompt = f"""
    You are the Airbnb Atlas Itinerary Synthesizer.
    Synthesize an itinerary for the user's travel request based STRICTLY and ONLY on the retrieved context below.

    USER REQUEST: "{query}"

    RETRIEVED LIVE CONTEXT (With source tags):
    {formatted_context}

    CRITICAL RULES FOR FACTUAL FAITHFULNESS:
    1. Every single sentence MUST state only facts directly found in the retrieved context chunks.
    2. Every bullet point MUST cite its source tag, e.g. [Src-1].
    3. DO NOT extrapolate, fabricate, or add generic day-by-day filler (e.g. "wake up and have breakfast", "pack your bags") unless explicitly mentioned in the context.
    4. Confine the itinerary strictly to the verified hotels, prices, permits, and activities present in the context.
    """
    gen_response = generator_evaluator.invoke(gen_prompt)
    draft_cards = gen_response.itinerary_cards

    # Stage 5: Claim Verification Agent (Critic)
    cards_text = ""
    for card in draft_cards:
        cards_text += f"\n### {card.title}\n"
        for detail in card.details:
            cards_text += f"- {detail}\n"

    verif_prompt = f"""
    You are the Airbnb Atlas Claim Verification Judge (Critic).
    Review the draft itinerary below and audit every single sentence against the retrieved evidence chunks.

    RETRIEVED EVIDENCE CHUNKS:
    {formatted_context}

    DRAFT ITINERARY TO AUDIT:
    {cards_text}

    AUDIT INSTRUCTIONS:
    1. Check every bullet point sentence against the retrieved evidence chunks.
    2. Completely REMOVE any generic filler sentences, ungrounded activities, or unverified estimates.
    3. Return verified_cards containing ONLY factual claims that are 100% supported by the retrieved evidence chunks.
    """
    verif_response = verifier_evaluator.invoke(verif_prompt)
    final_cards = verif_response.verified_cards if verif_response.verified_cards else draft_cards

    formatted_answer = format_cards_to_markdown(final_cards)
    retrieved_contexts = [c["text"] for c in reranked_chunks]

    return {
        "question": query,
        "answer": formatted_answer,
        "contexts": retrieved_contexts,
        "ground_truth": "\n".join(item["ground_truth_facts"]),
        "query_id": item["query_id"],
        "category": item.get("category", "travel"),
    }


def run_live_scenario(item: dict[str, Any]) -> dict[str, Any]:
    """Executes the full live LangGraph workflow with real DuckDuckGo web scraping."""
    query = item["query"]
    session_id = f"eval_live_{hashlib.md5(query.encode()).hexdigest()[:8]}"
    state = {
        "messages": [query],
        "session_id": session_id,
    }
    config = {"configurable": {"thread_id": session_id}}

    res = app_graph.invoke(state, config=config)

    final_itinerary = res.get("final_itinerary", res.get("messages", [""])[-1])
    formatted_answer = format_cards_to_markdown(final_itinerary)

    raw_context = res.get("retrieved_context", "")
    context_chunks = [c.strip() for c in re.split(r"\n---\n|\n\n", raw_context) if len(c.strip()) > 30]
    if not context_chunks:
        context_chunks = [raw_context] if raw_context else ["No context retrieved."]

    return {
        "question": query,
        "answer": formatted_answer,
        "contexts": context_chunks,
        "ground_truth": "\n".join(item["ground_truth_facts"]),
        "query_id": item["query_id"],
        "category": item.get("category", "travel"),
    }


# =====================================================================
# Main RAGAS Evaluation Runner
# =====================================================================

def run_evaluation(
    dataset_path: str = DEFAULT_DATASET_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    limit: int | None = None,
    mode: str = "corpus",
    judge: str = "gemini",
    groq_model: str | None = None,
    query_id: str | None = None,
    delay: float = 1.0,
):
    print("=" * 80)
    print("         AIRBNB ATLAS — RAGAS AUTOMATED GOLDEN SET EVALUATION SUITE        ")
    print("=" * 80)

    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Golden evaluation set not found at: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        golden_set: list[dict[str, Any]] = json.load(f)

    if query_id:
        golden_set = [item for item in golden_set if item.get("query_id") == query_id]
        if not golden_set:
            raise ValueError(f"Query ID '{query_id}' not found in dataset!")

    if limit and limit > 0:
        golden_set = golden_set[:limit]

    print(f"[CONFIG] Dataset: {dataset_path} ({len(golden_set)} scenarios selected)")
    print(f"[CONFIG] Execution Mode: {mode.upper()} | Output: {output_path}")

    # Prepare shared corpus if in corpus mode
    shared_collection = None
    if mode == "corpus":
        shared_collection = index_eval_corpus(golden_set)

    # 1. Execute Pipeline Across Scenarios
    print(f"\n[PHASE 1] Executing ATLAS Pipeline across {len(golden_set)} golden scenarios...\n")
    samples = []
    t0_pipeline = time.perf_counter()

    for idx, item in enumerate(golden_set, start=1):
        qid = item["query_id"]
        q_text = item["query"]
        print(f"[{idx:02d}/{len(golden_set):02d}] Processing {qid:18s} | '{q_text[:60]}...'")

        if mode == "corpus":
            scenario_sample = run_corpus_scenario(item, shared_collection)
        else:
            scenario_sample = run_live_scenario(item)

        samples.append(scenario_sample)

        # Gentle pacing between queries to respect rate limits
        if idx < len(golden_set) and delay > 0:
            time.sleep(delay)

    t1_pipeline = time.perf_counter()
    pipeline_duration_s = round(t1_pipeline - t0_pipeline, 2)
    print(f"\n[PHASE 1 COMPLETE] Pipeline execution finished in {pipeline_duration_s}s ({pipeline_duration_s/len(samples):.2f}s/query)")

    # 2. Build Ragas Dataset
    data = {
        "question": [s["question"] for s in samples],
        "contexts": [s["contexts"] for s in samples],
        "answer": [s["answer"] for s in samples],
        "ground_truth": [s["ground_truth"] for s in samples],
    }
    dataset = Dataset.from_dict(data)

    # 3. Initialize RAGAS Judge & Metrics
    embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    if judge == "groq":
        active_model = groq_model or os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing in .env!")
        print(f"\n[PHASE 2] Running RAGAS Evaluation on Golden Set (Judge: Groq / {active_model})...")
        print("Evaluating metrics: Faithfulness, Context Precision, Context Recall, Answer Relevancy (strictness=1)\n")
        judge_llm = ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_api_key,
            model=active_model,
            temperature=0.0,
            max_tokens=350,
            timeout=120,
            max_retries=15,
        )
        custom_ar = AnswerRelevancy(strictness=1)
        eval_metrics = [faithfulness, context_precision, context_recall, custom_ar]
        run_config = RunConfig(timeout=180, max_retries=15, max_workers=1)
    else:
        active_model = "gemini-3.5-flash-lite"
        print(f"\n[PHASE 2] Running RAGAS Evaluation on Golden Set (Judge: Google Gemini / {active_model})...")
        print("Evaluating metrics: Faithfulness, Context Precision, Context Recall, Answer Relevancy (strictness=1)\n")
        judge_llm = ChatGoogleGenerativeAI(
            model=active_model,
            timeout=120,
            max_retries=10,
        )
        custom_ar = AnswerRelevancy(strictness=1)
        eval_metrics = [faithfulness, context_precision, context_recall, custom_ar]
        # Single worker to guarantee free-tier rate limits (15 RPM) are strictly respected
        run_config = RunConfig(timeout=300, max_retries=10, max_workers=1)

    t0_eval = time.perf_counter()
    eval_result = evaluate(
        dataset=dataset,
        metrics=eval_metrics,
        llm=judge_llm,
        embeddings=embedder,
        run_config=run_config,
    )
    t1_eval = time.perf_counter()
    eval_duration_s = round(t1_eval - t0_eval, 2)

    # 4. Extract Results
    df = eval_result.to_pandas()
    avg_faithfulness = float(df["faithfulness"].mean()) if "faithfulness" in df.columns else 0.0
    avg_context_precision = float(df["context_precision"].mean()) if "context_precision" in df.columns else 0.0
    avg_context_recall = float(df["context_recall"].mean()) if "context_recall" in df.columns else 0.0
    has_relevancy = "answer_relevancy" in df.columns and not df["answer_relevancy"].dropna().empty
    avg_answer_relevancy = float(df["answer_relevancy"].dropna().mean()) if has_relevancy else None

    # Extract per-scenario scores from pandas DataFrame
    per_scenario_results = []
    for i, sample in enumerate(samples):
        row = df.iloc[i]
        f_score = float(row.get("faithfulness", 0.0)) if not pd_isna(row.get("faithfulness")) else 0.0
        p_score = float(row.get("context_precision", 0.0)) if not pd_isna(row.get("context_precision")) else 0.0
        r_score = float(row.get("context_recall", 0.0)) if not pd_isna(row.get("context_recall")) else 0.0
        
        scenario_dict = {
            "query_id": sample["query_id"],
            "category": sample["category"],
            "query": sample["question"],
            "faithfulness": round(f_score, 4),
            "context_precision": round(p_score, 4),
            "context_recall": round(r_score, 4),
        }
        if has_relevancy:
            ar_score = float(row.get("answer_relevancy", 0.0)) if not pd_isna(row.get("answer_relevancy")) else 0.0
            scenario_dict["answer_relevancy"] = round(ar_score, 4)

        per_scenario_results.append(scenario_dict)

    # 5. Format & Print Report
    table_width = 110 if has_relevancy else 95
    print("\n" + "=" * table_width)
    print("                       RAGAS GOLDEN SET EVALUATION BREAKDOWN                         ")
    print("=" * table_width)
    if has_relevancy:
        print(f"{'Query ID':18s} | {'Category':24s} | {'Faithfulness':12s} | {'Context Prec':12s} | {'Context Rec':12s} | {'Ans Relevancy':13s}")
    else:
        print(f"{'Query ID':20s} | {'Category':26s} | {'Faithfulness':12s} | {'Context Prec':12s} | {'Context Rec':12s}")
    print("-" * table_width)
    for res in per_scenario_results:
        if has_relevancy:
            print(
                f"{res['query_id']:18s} | "
                f"{res['category']:24s} | "
                f"{res['faithfulness']:12.2f} | "
                f"{res['context_precision']:12.2f} | "
                f"{res['context_recall']:12.2f} | "
                f"{res.get('answer_relevancy', 0.0):13.2f}"
            )
        else:
            print(
                f"{res['query_id']:20s} | "
                f"{res['category']:26s} | "
                f"{res['faithfulness']:12.2f} | "
                f"{res['context_precision']:12.2f} | "
                f"{res['context_recall']:12.2f}"
            )
    print("-" * table_width)
    if has_relevancy:
        print(
            f"{'MACRO AVERAGE (' + str(len(samples)) + ')':18s} | "
            f"{'ALL CATEGORIES':24s} | "
            f"{avg_faithfulness:12.2f} | "
            f"{avg_context_precision:12.2f} | "
            f"{avg_context_recall:12.2f} | "
            f"{avg_answer_relevancy:13.2f}"
        )
    else:
        print(
            f"{'MACRO AVERAGE (' + str(len(samples)) + ')':20s} | "
            f"{'ALL CATEGORIES':26s} | "
            f"{avg_faithfulness:12.2f} | "
            f"{avg_context_precision:12.2f} | "
            f"{avg_context_recall:12.2f}"
        )
    print("=" * table_width)

    # 6. Resume Bullet Points
    if has_relevancy:
        resume_bullet = (
            f"Evaluated {len(samples)} golden travel-planning scenarios with RAGAS, achieving "
            f"{int(round(avg_faithfulness * 100))}% faithfulness, "
            f"{int(round(avg_context_precision * 100))}% context precision, "
            f"{int(round(avg_context_recall * 100))}% context recall, and "
            f"{int(round(avg_answer_relevancy * 100))}% answer relevancy."
        )
        latex_bullet = (
            f"\\item {{Evaluated \\textbf{{{len(samples)} golden travel-planning scenarios}} with \\textbf{{RAGAS}}, "
            f"achieving \\textbf{{{int(round(avg_faithfulness * 100))}\\% faithfulness}}, "
            f"\\textbf{{{int(round(avg_context_precision * 100))}\\% context precision}}, "
            f"\\textbf{{{int(round(avg_context_recall * 100))}\\% context recall}}, and "
            f"\\textbf{{{int(round(avg_answer_relevancy * 100))}\\% answer relevancy}} across multi-constraint itineraries.}}"
        )
    else:
        resume_bullet = (
            f"Evaluated {len(samples)} golden travel-planning scenarios with RAGAS, achieving "
            f"{int(round(avg_faithfulness * 100))}% faithfulness, "
            f"{int(round(avg_context_precision * 100))}% context precision, and "
            f"{int(round(avg_context_recall * 100))}% context recall."
        )
        latex_bullet = (
            f"\\item {{Evaluated \\textbf{{{len(samples)} golden travel-planning scenarios}} with \\textbf{{RAGAS}}, "
            f"achieving \\textbf{{{int(round(avg_faithfulness * 100))}\\% faithfulness}}, "
            f"\\textbf{{{int(round(avg_context_precision * 100))}\\% context precision}}, and "
            f"\\textbf{{{int(round(avg_context_recall * 100))}\\% context recall}} across multi-constraint itineraries.}}"
        )

    print("\n" + "=" * table_width)
    print("                     VERIFIED RESUME-READY BULLET POINTS                             ")
    print("=" * table_width)
    print("\n[PLAINTEXT]:")
    print(f"  {resume_bullet}\n")
    print("[LATEX]:")
    print(f"  {latex_bullet}\n")
    print("=" * table_width)

    # 7. Save JSON Artifact
    output_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_scenarios_evaluated": len(samples),
        "execution_mode": mode,
        "judge": {
            "provider": judge,
            "model": active_model,
        },
        "timing": {
            "pipeline_generation_seconds": pipeline_duration_s,
            "ragas_evaluation_seconds": eval_duration_s,
            "total_seconds": round(pipeline_duration_s + eval_duration_s, 2),
        },
        "ragas_macro_averages": {
            "faithfulness": round(avg_faithfulness, 4),
            "context_precision": round(avg_context_precision, 4),
            "context_recall": round(avg_context_recall, 4),
            "faithfulness_pct": f"{int(round(avg_faithfulness * 100))}%",
            "context_precision_pct": f"{int(round(avg_context_precision * 100))}%",
            "context_recall_pct": f"{int(round(avg_context_recall * 100))}%",
        },
        "resume_ready_bullet": resume_bullet,
        "latex_bullet": latex_bullet,
        "per_scenario_breakdown": per_scenario_results,
    }
    if has_relevancy:
        output_data["ragas_macro_averages"]["answer_relevancy"] = round(avg_answer_relevancy, 4)
        output_data["ragas_macro_averages"]["answer_relevancy_pct"] = f"{int(round(avg_answer_relevancy * 100))}%"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n[SUCCESS] Comprehensive RAGAS report saved to: {output_path}\n")
    return output_data


def pd_isna(val: Any) -> bool:
    """Helper to check if a value is NaN or None without requiring explicit pandas import."""
    if val is None:
        return True
    try:
        import math
        return math.isnan(float(val))
    except (ValueError, TypeError):
        return False


def main():
    parser = argparse.ArgumentParser(description="Airbnb ATLAS RAGAS Automated Evaluation Suite")
    parser.add_argument("--limit", type=int, default=None, help="Optional scenario limit (default: None, runs complete evaluation across all scenarios)")
    parser.add_argument("--mode", choices=["corpus", "live"], default="corpus", help="Execution mode: 'corpus' (fast & deterministic) or 'live' (real web scraping)")
    parser.add_argument("--judge", choices=["gemini", "groq"], default="gemini", help="LLM Judge for RAGAS evaluation (default: gemini)")
    parser.add_argument("--groq-model", default=None, help="Groq model to use when --judge groq is set (defaults to GROQ_MODEL in .env or qwen/qwen3.8-27b)")
    parser.add_argument("--dataset", default=DEFAULT_DATASET_PATH, help="Path to golden evaluation JSON dataset")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH, help="Path to save evaluation results JSON")
    parser.add_argument("--query-id", default=None, help="Evaluate a specific query ID only")
    parser.add_argument("--delay", type=float, default=1.0, help="Inter-query delay in seconds to respect rate limits")

    args = parser.parse_args()

    run_evaluation(
        dataset_path=args.dataset,
        output_path=args.output,
        limit=args.limit,
        mode=args.mode,
        judge=args.judge,
        groq_model=args.groq_model,
        query_id=args.query_id,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()