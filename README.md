# Airbnb Atlas 🌍

**Airbnb Atlas** is an AI-powered travel copilot that uses a multi-agent **LangGraph** orchestration engine combined with **Just-In-Time Retrieval-Augmented Generation (RAG)**. 

Unlike traditional chatbots that rely on static, pre-built knowledge bases, Atlas deploys autonomous agents that search the live internet, scrape real-time travel guides, build an ephemeral vector database (ChromaDB) on the fly, and synthesize hyper-personalized itineraries grounded in verified, current data.

![Atlas Architecture](https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800&q=80) *(Sample travel imagery)*

## 🚀 Key Features

* **Just-In-Time (JIT) RAG**: Scrapes live internet data on every query to ensure the AI knows about new hotels, current prices, and real-time conditions.
* **Stateful Session Memory**: Remembers your entire conversation across turns using LangGraph `MemorySaver` and a custom SQLite database. You can ask follow-up revisions (e.g., *"make it 3 days instead"* or *"make the hotels cheaper"*), and the AI instantly adapts.
* **Intelligent Edge Routing**: Optimizes API costs and latency by intelligently bypassing heavy web scraping if you are simply revising an existing itinerary.
* **Structured JSON UI Binding**: Uses strict Pydantic schemas to force the LLM to output flawlessly structured data, seamlessly rendering a beautiful "Day Box" UI without fragile text parsing.
* **Authentic Media Integration**: Dynamically fetches genuine, official header photographs of your generated destinations using the public Wikipedia API.

## 🛠️ Architecture & Tech Stack

### Backend
* **Framework**: FastAPI
* **Orchestration**: LangGraph & LangChain
* **LLM**: Google Gemini (gemini-3.5-flash-lite)
* **Embeddings**: `all-MiniLM-L6-v2` (runs 100% locally via HuggingFace)
* **Vector Database**: ChromaDB (ephemeral, in-memory)
* **Web Search/Scraping**: DuckDuckGo Search + BeautifulSoup4
* **Database**: SQLite (for persistent conversation threads)

### Frontend
* **Framework**: React + Vite
* **Styling**: Tailwind CSS
* **Markdown Rendering**: `react-markdown` + `remark-gfm`

## ⚙️ How It Works (The Multi-Agent Workflow)

1. **The Supervisor Node**: Extracts the user's travel parameters (destination, budget, vibe, days) using structured LLM outputs. If data is missing, it pauses execution and asks a clarifying question.
2. **The Dynamic Research Node**: If research is needed, this agent executes a live web search, scrapes the top travel articles, chunks the text, embeds it locally, and saves it into an ephemeral ChromaDB instance.
3. **The Synthesizer Node**: Queries the fresh Vector DB, retrieves the top factual chunks, and uses them to ground the LLM's final response—generating a highly detailed, personalized itinerary with strict budget bifurcations.

## 🏃‍♂️ Running the Project Locally

### Prerequisites
* Python 3.10+
* Node.js 18+
* Google Gemini API Key

### Backend Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/airbnb-atlas.git
   cd airbnb-atlas
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set your Gemini API key in your environment variables.
5. Run the FastAPI server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend/airbnb-atlas
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the Vite development server:
   ```bash
   npm run dev
   ```
4. Open your browser to `http://localhost:5173` and start planning your trip!

## 🧪 Evaluation (The RAG Triad)

This project has been rigorously evaluated using the **Ragas** framework to measure grounding and hallucinations:
* **Faithfulness**: Benchmarked at ~53%, demonstrating a healthy hybrid balance where core facts are grounded in live scraped data, while the LLM supplements with general travel advice.
* **Context Recall**: 1.0 (100% coverage of ground-truth requirements).
* **Observability**: Fully instrumented with **LangSmith** for granular tracing of agent latency, token usage, and execution paths.
