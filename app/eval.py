import sys
import os
import types
import warnings

# ──────────────────────────────────────────────────
# 1. Suppress all known harmless warnings up front
# ──────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

# Ensure the parent directory is in the path so 'python app\eval.py' works
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- QUICK FIX FOR RAGAS BUG ---
# Ragas 0.4.x crashes looking for a deprecated VertexAI module.
# This injects a fake empty module so Ragas loads without errors.
dummy_chat = types.ModuleType("langchain_community.chat_models.vertexai")
dummy_chat.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = dummy_chat
# ─────────────────────────────────

from datasets import Dataset
from ragas import evaluate
from ragas.run_config import RunConfig

from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

# Import our LangGraph orchestration
from app.graph import app_graph

load_dotenv()

# Using gemini-3.5-flash-lite for the judge (active, supported, and generous free-tier rate limits)
judge_llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", timeout=120, max_retries=5)
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# RunConfig limits concurrency to 2 parallel workers to avoid overloading the API
run_config = RunConfig(timeout=300, max_retries=5, max_workers=2)


def run_evaluation():
    # ── Test Question ──
    question = (
        "I want to go to Tirthan Valley, looking for riverside stays "
        "and trout fishing. My budget is $500 and I want to stay for 4 days."
    )
    ground_truth = (
        "The user is looking for riverside stays in Tirthan Valley "
        "with a budget of $500 for 4 days."
    )

    # ── Run the actual LangGraph RAG pipeline ──
    print(f"Executing LangGraph pipeline for question: {question}")
    state = {"messages": [question]}
    result = app_graph.invoke(state)

    generated_answer = result.get("final_itinerary", result["messages"][-1])
    retrieved_context = result.get("retrieved_context", "")

    print("\nPipeline executed successfully! Starting Evaluation...")

    # ── Build the evaluation dataset ──
    # Split context into individual retrieved chunks for precision calculation
    context_chunks = [c.strip() for c in retrieved_context.split("\n\n") if c.strip()]
    if not context_chunks:
        context_chunks = [retrieved_context]

    data = {
        "question": [question],
        "contexts": [context_chunks],
        "answer": [generated_answer],
        "ground_truth": [ground_truth],
    }
    dataset = Dataset.from_dict(data)

    # ── Run the RAGAS evaluation ──
    print("Running RAGAS Evaluation on Live Output...\n")

    eval_result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge_llm,
        embeddings=embedder,
        run_config=run_config,
    )

    print("\n--- Evaluation Results ---")
    print(eval_result)


if __name__ == "__main__":
    run_evaluation()