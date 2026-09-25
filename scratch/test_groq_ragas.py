import os
import sys
import types
from dotenv import load_dotenv

load_dotenv()

# Patch for Ragas VertexAI bug
dummy_chat = types.ModuleType("langchain_community.chat_models.vertexai")
dummy_chat.ChatVertexAI = type("ChatVertexAI", (object,), {})
sys.modules["langchain_community.chat_models.vertexai"] = dummy_chat

from datasets import Dataset
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate
from ragas.metrics import faithfulness, context_precision, context_recall
from ragas.metrics._answer_relevance import AnswerRelevancy
from ragas.run_config import RunConfig

groq_api_key = os.getenv("GROQ_API_KEY")
model_name = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

print(f"Testing Groq with model: {model_name}")

judge_llm = ChatOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=groq_api_key,
    model=model_name,
    temperature=0.0,
    timeout=60,
    max_retries=5,
)

embedder = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

sample_data = {
    "question": ["Plan a 3-day budget trip to Tirthan Valley under INR 12,000 for 2 people."],
    "contexts": [
        [
            "Budget homestays in Jibhi and Gushaini range from INR 1,200 to 2,000 per night.",
            "Local HRTC buses run daily from Aut tunnel to Banjar and Gushaini costing INR 50-80.",
            "Entry permit for Great Himalayan National Park (GHNP) costs INR 100 per Indian national."
        ]
    ],
    "answer": [
        "Day 1: Arrive via Aut and take HRTC bus (INR 60) to Jibhi. Stay in a budget homestay (INR 1,500/night). "
        "Day 2: Trek to Great Himalayan National Park (entry INR 100/person). "
        "Day 3: Visit Chhoie waterfall and return. Total accommodation for 2 nights is INR 3,000, leaving plenty of buffer under INR 12,000."
    ],
    "ground_truth": [
        "Tirthan Valley budget stays in Gushaini/Jibhi cost INR 1,200-2,000/night. Aut to Banjar HRTC bus costs INR 50-80. GHNP permit is INR 100/person."
    ]
}

dataset = Dataset.from_dict(sample_data)
run_config = RunConfig(timeout=60, max_retries=5, max_workers=2)

custom_relevancy = AnswerRelevancy(strictness=1)

print("Evaluating with faithfulness, context_precision, context_recall, custom_relevancy (strictness=1)...")
res = evaluate(
    dataset=dataset,
    metrics=[faithfulness, context_precision, context_recall, custom_relevancy],
    llm=judge_llm,
    embeddings=embedder,
    run_config=run_config,
)
print("SUCCESS with custom_relevancy!")
print(res.to_pandas()[["faithfulness", "context_precision", "context_recall", "answer_relevancy"]])
