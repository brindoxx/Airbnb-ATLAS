import os
import sys
import types
import warnings
import json
import time

warnings.filterwarnings("ignore")
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

dummy_chat = types.ModuleType("langchain_community.chat_models.vertexai")
dummy_chat.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = dummy_chat

from dotenv import load_dotenv
load_dotenv()

from app.rag_engine import (
    chroma_client,
    embeddings,
    cross_encoder,
    text_splitter,
    format_retrieved_context,
)
from app.graph import generator_evaluator, verifier_evaluator
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, context_precision, context_recall
from ragas.run_config import RunConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

with open("data/golden_eval_set.json", "r", encoding="utf-8") as f:
    golden_set = json.load(f)

test_items = golden_set[:2]

coll = chroma_client.get_or_create_collection("test_ragas_eval_2")
if coll.count() > 0:
    coll.delete(ids=coll.get()["ids"])

all_chunks = []
all_ids = []
all_metas = []

for item in test_items:
    qid = item["query_id"]
    for s_idx, src in enumerate(item.get("snapshotted_sources", [])):
        chunks = text_splitter.split_text(src["text"])
        for c_idx, chk in enumerate(chunks):
            cid = f"{qid}_{s_idx}_{c_idx}"
            all_chunks.append(chk)
            all_ids.append(cid)
            all_metas.append({
                "query_id": qid,
                "source_id": src.get("source_id", f"Src-{s_idx+1}"),
                "title": src.get("title", ""),
                "domain": src.get("domain", ""),
                "url": f"https://{src.get('domain', 'web')}",
                "chunk_id": cid,
            })

coll.add(
    documents=all_chunks,
    ids=all_ids,
    metadatas=all_metas,
    embeddings=embeddings.embed_documents(all_chunks)
)
print(f"Indexed {len(all_chunks)} chunks.")

questions = []
answers = []
contexts_list = []
ground_truths = []

for item in test_items:
    q = item["query"]
    q_vec = embeddings.embed_query(q)
    res = coll.query(query_embeddings=[q_vec], n_results=min(10, coll.count()), include=["documents", "metadatas"])
    cand_docs = res["documents"][0]
    cand_metas = res["metadatas"][0]

    pairs = [[q, d] for d in cand_docs]
    scores = cross_encoder.predict(pairs)
    ranked = sorted(zip(cand_docs, cand_metas, scores), key=lambda x: x[2], reverse=True)[:3]

    reranked_chunks = []
    for doc, meta, score in ranked:
        reranked_chunks.append({
            "source_id": meta["source_id"],
            "chunk_id": meta["chunk_id"],
            "title": meta["title"],
            "domain": meta["domain"],
            "url": meta["url"],
            "text": doc,
            "rerank_score": float(score),
        })

    formatted_ctx = format_retrieved_context(reranked_chunks)

    gen_prompt = f"""
    Create a travel itinerary for the query based STRICTLY on retrieved context:
    USER REQUEST: "{q}"
    RETRIEVED CONTEXT:
    {formatted_ctx}
    Cite [Src-X] tags on claims.
    """
    gen_out = generator_evaluator.invoke(gen_prompt)

    cards_text = ""
    for card in gen_out.itinerary_cards:
        cards_text += f"\n### {card.title}\n"
        for d in card.details:
            cards_text += f"- {d}\n"

    verif_prompt = f"""
    Cross-examine factual claims against retrieved evidence chunks:
    RETRIEVED EVIDENCE:
    {formatted_ctx}
    DRAFT ITINERARY:
    {cards_text}
    """
    verif_out = verifier_evaluator.invoke(verif_prompt)
    final_cards = verif_out.verified_cards if verif_out.verified_cards else gen_out.itinerary_cards

    answer_text = ""
    for c in final_cards:
        answer_text += f"### {c.title}\n"
        for d in c.details:
            answer_text += f"- {d}\n"
        answer_text += "\n"

    questions.append(q)
    answers.append(answer_text.strip())
    contexts_list.append([c["text"] for c in reranked_chunks])
    ground_truths.append("\n".join(item["ground_truth_facts"]))
    time.sleep(2)  # Avoid rate limits during generation

print("Generated answers for 2 items. Starting Ragas evaluate...")

data = {
    "question": questions,
    "contexts": contexts_list,
    "answer": answers,
    "ground_truth": ground_truths,
}
ds = Dataset.from_dict(data)

judge_llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", timeout=120, max_retries=10)
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
run_config = RunConfig(timeout=300, max_retries=10, max_workers=1)

eval_res = evaluate(
    dataset=ds,
    metrics=[faithfulness, context_precision, context_recall],
    llm=judge_llm,
    embeddings=embedder,
    run_config=run_config,
)

print("\n=== EVAL RESULT ===")
print(eval_res)
df = eval_res.to_pandas()
print("\n=== DATAFRAME ===")
print(df[["question", "faithfulness", "context_precision", "context_recall"]])
