import sys
import types

# --- QUICK FIX FOR RAGAS BUG ---
# Ragas crashes looking for a deprecated VertexAI module. 
# This injects a fake empty module so it successfully loads.
dummy_chat = types.ModuleType("langchain_community.chat_models.vertexai")
dummy_chat.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = dummy_chat
# -------------------------------

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Initialize the LLM-as-a-judge and embedder
judge_llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def run_evaluation():
    # 1. Define your ground truth test set
    data = {
        "question": ["I want a quiet riverside stay in Tirthan Valley under ₹5000."],
        "contexts": [["Tirthan Riverside Stay costs ₹4500. It is located directly on the riverbank offering quiet digital detox vibes."]],
        "answer": ["I recommend the Tirthan Riverside Stay for ₹4500, which offers a quiet digital detox on the riverbank."],
        "ground_truth": ["Tirthan Riverside Stay is a quiet option on the river for ₹4500."]
    }
    
    dataset = Dataset.from_dict(data)

    # 2. Run the Ragas evaluation metrics
    print("Running RAGAS Evaluation...")
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=judge_llm,
        embeddings=embedder
    )
    
    print("\n--- 📊 Evaluation Results ---")
    print(result)

if __name__ == "__main__":
    run_evaluation()