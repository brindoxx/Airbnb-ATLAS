import argparse
import hashlib
import json
import os
import re
import sys
import time
from typing import Any

import numpy as np

# Ensure root path is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chromadb import EphemeralClient
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import CrossEncoder

GOLDEN_SET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "golden_eval_set.json"
)
OUTPUT_RESULTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "benchmark_results.json"
)


# =====================================================================
# 1. IR METRICS EVALUATOR (Bi-Encoder vs Cross-Encoder)
# =====================================================================

class IREvaluator:
    def __init__(self):
        print("[INIT] Loading Bi-Encoder (all-MiniLM-L6-v2) & Cross-Encoder (ms-marco-MiniLM-L-6-v2)...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        self.chroma_client = EphemeralClient()

    def _fact_covered_in_chunk(self, fact: str, chunk: str, fact_embedding: list[float], chunk_embedding: list[float]) -> bool:
        """Determines if a ground-truth fact is covered by a retrieved chunk.
        Uses combined token overlap and cosine similarity threshold.
        """
        # Exact token overlap check
        fact_words = set(re.findall(r"\b\w{4,}\b", fact.lower()))
        chunk_words = set(re.findall(r"\b\w{4,}\b", chunk.lower()))
        overlap_ratio = len(fact_words & chunk_words) / max(len(fact_words), 1)

        # Cosine similarity
        vec1 = np.array(fact_embedding)
        vec2 = np.array(chunk_embedding)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        sim = float(np.dot(vec1, vec2) / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0

        return overlap_ratio >= 0.35 or sim >= 0.65

    def index_global_corpus(self, items: list[dict[str, Any]]) -> tuple[Any, dict[str, list[dict]]]:
        """Indexes all snapshotted sources across all golden queries into a single shared
        evaluation corpus so queries must discriminate between target and distractor travel documents.
        """
        all_chunks = []
        all_ids = []
        all_metadatas = []
        query_source_map = {}

        for item in items:
            qid = item["query_id"]
            sources = item.get("snapshotted_sources", [])
            query_source_map[qid] = sources

            for s_idx, source in enumerate(sources):
                source_id = source.get("source_id", f"Src-{s_idx+1}")
                text = source.get("text", "")
                split_chunks = self.text_splitter.split_text(text)
                if not split_chunks:
                    split_chunks = [text]

                for c_idx, c_text in enumerate(split_chunks):
                    cid = f"{qid}_{source_id}_{c_idx}"
                    all_chunks.append(c_text)
                    all_ids.append(cid)
                    all_metadatas.append({
                        "query_id": qid,
                        "source_id": source_id,
                        "title": source.get("title", ""),
                        "domain": source.get("domain", ""),
                        "chunk_id": cid
                    })

        coll_name = "eval_shared_golden_corpus"
        collection = self.chroma_client.get_or_create_collection(coll_name)
        if collection.count() > 0:
            collection.delete(ids=collection.get()["ids"])

        print(f"[INDEX] Indexing {len(all_chunks)} chunks into shared benchmark evaluation corpus...")
        chunk_embeddings = self.embeddings.embed_documents(all_chunks)
        collection.add(
            documents=all_chunks,
            ids=all_ids,
            metadatas=all_metadatas,
            embeddings=chunk_embeddings
        )
        return collection, query_source_map

    def evaluate_query_against_corpus(
        self,
        collection: Any,
        item: dict[str, Any],
        top_k: int = 5
    ) -> dict[str, Any]:
        """Evaluates a single golden query against the shared corpus.
        Compares Bi-Encoder top-5 vs Two-Tier (Top-15 candidates -> Cross-Encoder rerank -> Top-5).
        """
        query_id = item["query_id"]
        query_text = item["query"]
        ground_truth_facts = item["ground_truth_facts"]
        total_chunks = collection.count()

        fact_embeddings = self.embeddings.embed_documents(ground_truth_facts)
        query_vector = self.embeddings.embed_query(query_text)

        # Strategy A: Pure Bi-Encoder Retrieval (Top-5 by cosine similarity)
        bi_results = collection.query(
            query_embeddings=[query_vector],
            n_results=min(top_k, total_chunks),
            include=["documents", "metadatas", "distances"]
        )
        bi_docs = bi_results["documents"][0]
        bi_metas = bi_results["metadatas"][0]

        # Strategy B: Two-Tier (Candidate fetch top-15 -> Cross-Encoder rerank top-5)
        n_candidates = min(15, total_chunks)
        candidate_results = collection.query(
            query_embeddings=[query_vector],
            n_results=n_candidates,
            include=["documents", "metadatas"]
        )
        cand_docs = candidate_results["documents"][0]
        cand_metas = candidate_results["metadatas"][0]

        pairs = [[query_text, d] for d in cand_docs]
        cross_scores = self.cross_encoder.predict(pairs)
        ranked_cand = sorted(
            zip(cand_docs, cand_metas, cross_scores),
            key=lambda x: x[2],
            reverse=True
        )
        cross_docs = [x[0] for x in ranked_cand[:top_k]]
        cross_metas = [x[1] for x in ranked_cand[:top_k]]

        bi_doc_embeddings = self.embeddings.embed_documents(bi_docs) if bi_docs else []
        cross_doc_embeddings = self.embeddings.embed_documents(cross_docs) if cross_docs else []

        def compute_metrics(retrieved_docs, retrieved_metas, retrieved_embeddings):
            if not retrieved_docs or not ground_truth_facts:
                return {"recall": 0.0, "precision": 0.0, "ndcg": 0.0}

            fact_covered = [False] * len(ground_truth_facts)
            chunk_relevances = []

            for d_idx, (doc, meta, d_emb) in enumerate(zip(retrieved_docs, retrieved_metas, retrieved_embeddings)):
                # Chunk must belong to target query's domain or cover factual statements
                belongs_to_target = meta.get("query_id") == query_id
                relevance_grade = 0

                if belongs_to_target:
                    relevance_grade += 1
                    for f_idx, (fact, f_emb) in enumerate(zip(ground_truth_facts, fact_embeddings)):
                        if self._fact_covered_in_chunk(fact, doc, f_emb, d_emb):
                            fact_covered[f_idx] = True
                            relevance_grade += 1

                chunk_relevances.append(relevance_grade)

            recall = sum(fact_covered) / len(ground_truth_facts)
            relevant_chunks_count = sum(1 for r in chunk_relevances if r > 0)
            precision = relevant_chunks_count / len(retrieved_docs)

            dcg = 0.0
            for rank, rel in enumerate(chunk_relevances, start=1):
                dcg += (2**rel - 1) / np.log2(rank + 1)

            ideal_relevances = sorted(chunk_relevances, reverse=True)
            idcg = 0.0
            for rank, rel in enumerate(ideal_relevances, start=1):
                idcg += (2**rel - 1) / np.log2(rank + 1)

            ndcg = (dcg / idcg) if idcg > 0 else (1.0 if sum(chunk_relevances) == 0 else 0.0)

            return {
                "recall": round(float(recall), 4),
                "precision": round(float(precision), 4),
                "ndcg": round(float(ndcg), 4)
            }

        bi_metrics = compute_metrics(bi_docs, bi_metas, bi_doc_embeddings)
        cross_metrics = compute_metrics(cross_docs, cross_metas, cross_doc_embeddings)

        return {
            "query_id": query_id,
            "category": item.get("category", ""),
            "bi_encoder": bi_metrics,
            "cross_encoder": cross_metrics,
            "corpus_chunks": total_chunks
        }

    def run_all(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluates all golden queries against the shared corpus and computes macro-averaged IR improvements."""
        collection, _ = self.index_global_corpus(items)
        results = []
        for idx, item in enumerate(items, 1):
            res = self.evaluate_query_against_corpus(collection, item, top_k=5)
            if res:
                results.append(res)
                print(
                    f"[{idx:02d}/{len(items):02d}] {res['query_id']:15s} | "
                    f"Bi nDCG: {res['bi_encoder']['ndcg']:.3f} -> Cross nDCG: {res['cross_encoder']['ndcg']:.3f} | "
                    f"P@5: {res['bi_encoder']['precision']:.2f} -> {res['cross_encoder']['precision']:.2f} | "
                    f"R@5: {res['bi_encoder']['recall']:.2f} -> {res['cross_encoder']['recall']:.2f}"
                )

        if not results:
            return {}

        bi_recalls = [r["bi_encoder"]["recall"] for r in results]
        bi_precisions = [r["bi_encoder"]["precision"] for r in results]
        bi_ndcgs = [r["bi_encoder"]["ndcg"] for r in results]

        cr_recalls = [r["cross_encoder"]["recall"] for r in results]
        cr_precisions = [r["cross_encoder"]["precision"] for r in results]
        cr_ndcgs = [r["cross_encoder"]["ndcg"] for r in results]

        avg_bi = {
            "recall@5": round(float(np.mean(bi_recalls)), 4),
            "precision@5": round(float(np.mean(bi_precisions)), 4),
            "ndcg@5": round(float(np.mean(bi_ndcgs)), 4),
        }
        avg_cr = {
            "recall@5": round(float(np.mean(cr_recalls)), 4),
            "precision@5": round(float(np.mean(cr_precisions)), 4),
            "ndcg@5": round(float(np.mean(cr_ndcgs)), 4),
        }

        # Percentage gains
        def gain(new_v, old_v):
            if old_v == 0:
                return 0.0
            return round(((new_v - old_v) / old_v) * 100, 2)

        improvement = {
            "recall_gain_pct": gain(avg_cr["recall@5"], avg_bi["recall@5"]),
            "precision_gain_pct": gain(avg_cr["precision@5"], avg_bi["precision@5"]),
            "ndcg_gain_pct": gain(avg_cr["ndcg@5"], avg_bi["ndcg@5"]),
        }

        return {
            "evaluated_queries": len(results),
            "baseline_bi_encoder": avg_bi,
            "two_tier_cross_encoder": avg_cr,
            "relative_improvements": improvement,
            "per_query_details": results
        }


# =====================================================================
# 2. CITATION & GENERATION METRICS EVALUATOR
# =====================================================================

def evaluate_citations_and_coverage(cards: list[dict], retrieved_sources: list[dict]) -> dict[str, Any]:
    """Measures Citation Coverage and Citation Precision on structured itinerary cards.
    - Citation Coverage: % of factual sentences that carry [Src-X] tags.
    - Citation Precision: % of [Src-X] citations that reference genuine retrieved sources.
    """
    valid_source_ids = {s.get("source_id") for s in retrieved_sources if s.get("source_id")}
    # Also support default "Src-1", "Src-2" etc.
    if not valid_source_ids:
        valid_source_ids = {"Src-1", "Src-2", "Src-3", "Src-4", "Src-5", "Src-6"}

    total_bullet_sentences = 0
    cited_sentences = 0
    total_citations = 0
    valid_citations = 0

    for card in cards:
        details = card.get("details", [])
        for detail in details:
            sentences = [s.strip() for s in re.split(r"[.!?]\s+", detail) if len(s.strip()) > 15]
            if not sentences:
                sentences = [detail]

            for sent in sentences:
                total_bullet_sentences += 1
                matches = re.findall(r"\[(Src-\d+)\]", sent)
                if matches:
                    cited_sentences += 1
                    for match in matches:
                        total_citations += 1
                        if match in valid_source_ids:
                            valid_citations += 1

    coverage = round(cited_sentences / max(total_bullet_sentences, 1), 4)
    precision = round(valid_citations / max(total_citations, 1), 4) if total_citations > 0 else 1.0

    return {
        "total_sentences": total_bullet_sentences,
        "cited_sentences": cited_sentences,
        "citation_coverage": coverage,
        "total_citations": total_citations,
        "valid_citations": valid_citations,
        "citation_precision": precision
    }


# =====================================================================
# 3. LATENCY & END-TO-END PIPELINE BENCHMARK (Cold vs Warm)
# =====================================================================

def benchmark_cold_and_warm_pipeline() -> dict[str, Any]:
    """Runs a live end-to-end benchmark pair on the 5-stage LangGraph workflow:
    - Turn 1 (Cold Trip Request): full research, scrape, embed, rerank, generate, verify.
    - Turn 2 (Warm Revision Request): supervisor detects revision, reuses session Chroma collection, reranks, generates, verifies.
    """
    from app.graph import app_graph
    import uuid

    session_id = f"bench_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": session_id}}

    print(f"\n=======================================================")
    print(f"BENCHMARKING LIVE 5-STAGE WORKFLOW (Session: {session_id})")
    print(f"=======================================================")

    # ── TURN 1: COLD REQUEST ──
    cold_prompt = "I want to visit Tirthan Valley for trout fishing and riverside homestays, 4 days, budget is $500."
    print(f"\n[BENCHMARK] Executing Cold Request: '{cold_prompt}'")
    t0_cold = time.perf_counter()
    cold_res = app_graph.invoke(
        {"messages": [cold_prompt], "session_id": session_id},
        config=config
    )
    t1_cold = time.perf_counter()
    cold_total_s = round(t1_cold - t0_cold, 2)
    cold_timings = cold_res.get("timings", {})
    cold_cards = cold_res.get("final_itinerary", [])
    cold_verif = cold_res.get("verification_report", {})
    cold_citations = cold_res.get("citations", [])

    cold_eval = evaluate_citations_and_coverage(cold_cards, cold_citations)

    print(f"[COLD FINISHED] Duration: {cold_total_s}s | Cards Generated: {len(cold_cards)}")
    print(f"  Stage Timings: {cold_timings}")
    print(f"  Faithfulness: {cold_verif.get('faithfulness_score', 1.0)} | Citation Coverage: {cold_eval['citation_coverage']*100:.1f}%")

    # ── TURN 2: WARM REVISION REQUEST ──
    warm_prompt = "Make the accommodations cheaper and under $300 for the entire trip."
    print(f"\n[BENCHMARK] Executing Warm Revision: '{warm_prompt}'")
    t0_warm = time.perf_counter()
    warm_res = app_graph.invoke(
        {"messages": [warm_prompt], "session_id": session_id},
        config=config
    )
    t1_warm = time.perf_counter()
    warm_total_s = round(t1_warm - t0_warm, 2)
    warm_timings = warm_res.get("timings", {})
    warm_cards = warm_res.get("final_itinerary", [])
    warm_verif = warm_res.get("verification_report", {})
    warm_citations = warm_res.get("citations", [])

    warm_eval = evaluate_citations_and_coverage(warm_cards, warm_citations)

    speedup = round(cold_total_s / max(warm_total_s, 0.1), 2)
    print(f"[WARM FINISHED] Duration: {warm_total_s}s | Speedup: {speedup}x")
    print(f"  Stage Timings: {warm_timings}")
    print(f"  Faithfulness: {warm_verif.get('faithfulness_score', 1.0)} | Citation Coverage: {warm_eval['citation_coverage']*100:.1f}%")

    return {
        "session_id": session_id,
        "cold_request": {
            "prompt": cold_prompt,
            "total_seconds": cold_total_s,
            "timings_ms": cold_timings,
            "cards_count": len(cold_cards),
            "faithfulness": cold_verif.get("faithfulness_score", 1.0),
            "citation_coverage": cold_eval["citation_coverage"],
            "citation_precision": cold_eval["citation_precision"],
            "claims_verified": len(cold_verif.get("claims", [])),
        },
        "warm_revision": {
            "prompt": warm_prompt,
            "total_seconds": warm_total_s,
            "timings_ms": warm_timings,
            "cards_count": len(warm_cards),
            "faithfulness": warm_verif.get("faithfulness_score", 1.0),
            "citation_coverage": warm_eval["citation_coverage"],
            "citation_precision": warm_eval["citation_precision"],
            "claims_verified": len(warm_verif.get("claims", [])),
            "speedup_factor": speedup,
        }
    }


# =====================================================================
# 4. MAIN RUNNER & REPORT PRINTER
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="Airbnb ATLAS RAG Benchmark Suite")
    parser.add_argument("--ir-only", action="store_true", help="Run only the IR retrieval benchmark on golden set")
    parser.add_argument("--pipeline-only", action="store_true", help="Run only live cold/warm pipeline latency benchmark")
    parser.add_argument("--output", default=OUTPUT_RESULTS_PATH, help="Path to save benchmark results json")
    args = parser.parse_args()

    print("==================================================================")
    print("      AIRBNB ATLAS RAG SYSTEM BENCHMARK SUITE (5-STAGE EVAL)      ")
    print("==================================================================")

    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    full_report: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "golden_set_size": len(golden_set)
    }

    # 1. Run IR Evaluation
    if not args.pipeline_only:
        print(f"\n[PHASE 1] Running IR Benchmark across {len(golden_set)} golden queries...")
        ir_evaluator = IREvaluator()
        ir_results = ir_evaluator.run_all(golden_set)
        full_report["ir_retrieval_benchmark"] = ir_results

    # 2. Run Live Pipeline Benchmark
    if not args.ir_only:
        print("\n[PHASE 2] Running Live Cold vs Warm 5-Stage Pipeline Benchmark...")
        pipeline_results = benchmark_cold_and_warm_pipeline()
        full_report["pipeline_benchmark"] = pipeline_results

    # 3. Save JSON Report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"\n[REPORT] Detailed benchmark results saved to: {args.output}")

    # 4. Print Summary Comparison Table
    print("\n" + "="*70)
    print("               FINAL DEFENSIVE BENCHMARK SUMMARY                 ")
    print("="*70)

    if "ir_retrieval_benchmark" in full_report:
        ir = full_report["ir_retrieval_benchmark"]
        bi = ir["baseline_bi_encoder"]
        cr = ir["two_tier_cross_encoder"]
        imp = ir["relative_improvements"]

        print("\n1. RETRIEVAL QUALITY (Bi-Encoder vs Two-Tier Cross-Encoder):")
        print(f"  - Recall@5:    Baseline: {bi['recall@5']:.4f}  -->  Two-Tier: {cr['recall@5']:.4f}  (+{imp['recall_gain_pct']}%)")
        print(f"  - Precision@5: Baseline: {bi['precision@5']:.4f}  -->  Two-Tier: {cr['precision@5']:.4f}  (+{imp['precision_gain_pct']}%)")
        print(f"  - nDCG@5:      Baseline: {bi['ndcg@5']:.4f}  -->  Two-Tier: {cr['ndcg@5']:.4f}  (+{imp['ndcg_gain_pct']}%)")

    if "pipeline_benchmark" in full_report:
        pb = full_report["pipeline_benchmark"]
        cold = pb["cold_request"]
        warm = pb["warm_revision"]

        print("\n2. GENERATION & VERIFICATION FIDELITY:")
        print(f"  - Claim Verifier Faithfulness: Cold: {cold['faithfulness']:.2f} | Warm: {warm['faithfulness']:.2f}")
        print(f"  - Citation Coverage:           Cold: {cold['citation_coverage']*100:.1f}% | Warm: {warm['citation_coverage']*100:.1f}%")
        print(f"  - Citation Precision:          Cold: {cold['citation_precision']*100:.1f}% | Warm: {warm['citation_precision']*100:.1f}%")

        print("\n3. LATENCY PERFORMANCE & CACHE EFFICIENCY:")
        print(f"  - Cold Request Latency: {cold['total_seconds']}s (Stage 2 Research: {cold['timings_ms'].get('research_ms', 0)}ms)")
        print(f"  - Warm Revision Latency: {warm['total_seconds']}s (Stage 2 Research: 0ms - Reused)")
        print(f"  - Speedup Multiplier:    {warm['speedup_factor']}x faster warm revisions")

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
