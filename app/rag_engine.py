import requests
from bs4 import BeautifulSoup
from chromadb import EphemeralClient
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# We use an Ephemeral Client because the data is temporary. 
# It lives only in RAM for the duration of the user's session.
chroma_client = EphemeralClient()
collection = chroma_client.get_or_create_collection(name="dynamic_travel_context")
# Downloads a tiny, lightning-fast embedding model that runs locally
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
# embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-2",
#     output_dimensionality=768,)
search_tool = DuckDuckGoSearchResults(num_results=3)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

def scrape_webpage(url: str) -> str:
    """Visits a URL and extracts the readable text."""
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Extract text from paragraphs to avoid HTML clutter
        paragraphs = soup.find_all('p')
        return " ".join([p.get_text() for p in paragraphs])
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return ""

def dynamic_research_and_index(destination_query: str):
    """
    Agentic Action: 
    1. Searches the web for the destination & stays.
    2. Scrapes the live data.
    3. Embeds it into ChromaDB instantly.
    """
    print(f"🌍 Agent is researching: {destination_query}...")
    
    # 1. Search the web
    try:
        raw_search_results = search_tool.run(f"{destination_query} best places to visit and stay travel guide")
    except Exception as e:
        print(f"⚠️ Web search failed (likely rate-limited): {e}")
        raw_search_results = f"Web search failed. Rely on your internal knowledge to suggest an itinerary for: {destination_query}"
    
    # DuckDuckGo returns a string of snippets and links. We will extract the links.
    # (For production, you'd parse the URLs properly using regex or Tavily API)
    import re
    urls = re.findall(r'(https?://[^\s]+)', raw_search_results)
    urls = [url.strip("],") for url in urls][:3] # Grab top 3 links
    
    all_live_text = ""
    for url in urls:
        print(f"📖 Agent reading: {url}")
        all_live_text += scrape_webpage(url) + "\n\n"
        
    if not all_live_text.strip():
        print("⚠️ Could not scrape enough data. Falling back to search snippets.")
        all_live_text = raw_search_results

    # 2. Chunk the live data
    chunks = text_splitter.split_text(all_live_text)
    
    # 3. Embed into ChromaDB on the fly
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    print(f"🧠 Embedding {len(chunks)} chunks into live Vector DB...")
    
    # Clear previous session data to prevent cross-contamination of trips
    if collection.count() > 0:
        existing_ids = collection.get()["ids"]
        collection.delete(ids=existing_ids)
        
    collection.add(
        documents=chunks,
        ids=ids,
        embeddings=embeddings.embed_documents(chunks)
    )
    print("✅ Real-time Knowledge Base built!")

def query_live_database(vibe_query: str):
    """Queries the newly built live database for specific constraints."""
    query_vector = embeddings.embed_query(vibe_query)
    
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=5
    )
    return results['documents'][0]

if __name__ == "__main__":
    # Test the Agentic Workflow
    user_request = "Nainital Uttarakhand"
    
    # 1. Agent researches and builds the DB
    dynamic_research_and_index(user_request)
    
    # 2. Agent queries its own generated DB for exact user vibes
    vibe_request = "riverside stays, quiet nature, and trout fishing"
    answers = query_live_database(vibe_request)
    
    print("\n--- 🎯 AI Synthesized Findings ---")
    for idx, ans in enumerate(answers):
        print(f"Match {idx+1}: {ans[:300]}...\n")