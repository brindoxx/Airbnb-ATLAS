import hashlib
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup
from chromadb import EphemeralClient
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import CrossEncoder

load_dotenv()

# We use an Ephemeral Client because data is ephemeral and session-scoped.
chroma_client = EphemeralClient()

# Local Bi-Encoder for vector search
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Local Cross-Encoder for high-precision reranking
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

search_tool = DuckDuckGoSearchResults(num_results=10)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def sanitize_session_id(session_id: str) -> str:
    """Ensures session_id is a valid ChromaDB collection name (3-63 chars, [a-zA-Z0-9_-])."""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
    if not clean:
        clean = "default_session"
    return f"session_{clean}"[:63]


def get_session_collection(session_id: str):
    """Retrieves or creates a private vector collection for a specific session."""
    coll_name = sanitize_session_id(session_id)
    return chroma_client.get_or_create_collection(name=coll_name)


def scrape_webpage(url: str) -> dict[str, Any]:
    """Visits a URL and extracts clean readable text along with page metadata."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc or "web"

        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=8)
        if response.status_code != 200:
            return {"url": url, "domain": domain, "title": domain, "text": "", "success": False}

        soup = BeautifulSoup(response.content, "html.parser")

        # Strip scripts, styles, and navigational junk
        for element in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            element.decompose()

        # Extract title
        page_title = domain
        if soup.title and soup.title.string:
            page_title = soup.title.string.strip()

        # Extract readable content from paragraphs and headings
        blocks = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            txt = tag.get_text(strip=True)
            if len(txt) > 25:
                blocks.append(txt)

        full_text = " ".join(blocks)
        is_success = len(full_text) >= 200

        return {
            "url": url,
            "domain": domain,
            "title": page_title,
            "text": full_text,
            "success": is_success,
        }
    except Exception as e:
        print(f"[SCRAPE] Failed to scrape {url}: {e}")
        return {
            "url": url,
            "domain": urllib.parse.urlparse(url).netloc or "web",
            "title": "Unavailable Source",
            "text": "",
            "success": False,
        }


def sanitize_search_query(query: str) -> str:
    """Sanitize and focus search queries by removing conversational filler,
    redundant suffixes, and restrictive constraint tokens that break search engines."""
    q = str(query or "").strip()

    # Remove conversational filler phrases and user constraints that hinder web search
    filler_patterns = [
        r"\b(anything is fine|any vibe|whatever|no preference|i want to go to?|planning a trip to?|trip to|looking for|options? for|any|fine)\b",
        r"\b(budget\s*(?:of)?\s*[\d,]+\s*(?:rs|inr|usd|\$)?)\b",
        r"\b(under\s*[\d,]+|cheap|affordable)\b",
        r"\b(\d+\s*days?\s*trip|\d+\s*days?|\d+\s*nights?)\b",
    ]
    for pat in filler_patterns:
        q = re.sub(pat, " ", q, flags=re.IGNORECASE)

    # Remove duplicate words while preserving order
    words = q.split()
    seen = set()
    cleaned_words = []
    for w in words:
        wl = w.lower()
        if wl not in seen or wl in ["and", "to", "in"]:
            seen.add(wl)
            cleaned_words.append(w)

    result = " ".join(cleaned_words).strip()
    return result if len(result) > 2 else query


def dynamic_research_and_index(session_id: str, destination_query: str) -> dict[str, Any]:
    """Agentic Action:

    1. Searches the live web for the destination & stays.
    2. Scrapes the live data with rich metadata.
    3. Enforces a strict scraping gate (no hallucinating if live data is missing).
    4. Chunks, hashes, and embeds into an isolated session ChromaDB collection.
    """
    print(f"\n[RESEARCH] Agent researching for session '{session_id}': {destination_query}...")

    clean_q = sanitize_search_query(destination_query)
    print(f"[RESEARCH] Sanitized query: '{clean_q}'")

    # 1. Search the web (with fallback if primary search fails or yields < 3 URLs)
    raw_search_results = ""
    primary_query = f"{clean_q} places to visit hotels travel guide" if "travel guide" not in clean_q.lower() else f"{clean_q} places to visit hotels"
    try:
        raw_search_results = search_tool.run(primary_query)
    except Exception as e:
        print(f"[SEARCH] Primary search failed: {e}")

    # Extract clean HTTP URLs from DuckDuckGo response
    found_urls = re.findall(r"(https?://[^\s\]\)\,\<\>]+)", raw_search_results)

    # If primary search produced < 3 URLs, trigger simplified fallback search
    if len(found_urls) < 3:
        core_dest = clean_q.split()[0] if clean_q else destination_query
        fallback_query = f"{core_dest} tourism attractions places to stay travel guide"
        print(f"[SEARCH] Primary search returned {len(found_urls)} URLs. Running fallback: '{fallback_query}'")
        try:
            fallback_res = search_tool.run(fallback_query)
            more_urls = re.findall(r"(https?://[^\s\]\)\,\<\>]+)", fallback_res)
            found_urls.extend(more_urls)
        except Exception as e2:
            print(f"[SEARCH] Fallback search failed: {e2}")

    # Deduplicate while preserving order and limit to top 8 links
    unique_urls = []
    seen = set()
    for u in found_urls:
        clean_u = u.strip("],\"'")
        if clean_u not in seen and not any(ext in clean_u for ext in [".pdf", ".jpg", ".png"]):
            seen.add(clean_u)
            unique_urls.append(clean_u)
        if len(unique_urls) >= 8:
            break

    # 2. Scrape each URL
    successful_docs: list[dict[str, Any]] = []
    for url in unique_urls:
        print(f"[SCRAPE] Reading: {url}")
        doc = scrape_webpage(url)
        if doc["success"]:
            successful_docs.append(doc)

    total_scraped_chars = sum(len(d["text"]) for d in successful_docs)

    # 3. SCRAPING GATE: Guardrail against deceptive grounding
    if len(successful_docs) < 2 or total_scraped_chars < 500:
        print(f"[GATE] Scraping Gate Failed: Only {len(successful_docs)} sources and {total_scraped_chars} chars obtained.")
        return {
            "success": False,
            "status": "INSUFFICIENT_LIVE_SOURCES",
            "message": (
                f"Live web search could not retrieve sufficient verified sources for '{destination_query}'. "
                "Execution halted by the Scraping Gate to avoid ungrounded hallucinations."
            ),
            "sources": [],
            "chunk_count": 0,
        }

    # 4. Chunk each document with full provenance metadata
    all_chunks: list[str] = []
    all_ids: list[str] = []
    all_metadatas: list[dict[str, Any]] = []

    timestamp_iso = datetime.now(timezone.utc).isoformat()

    for doc_idx, doc in enumerate(successful_docs):
        source_id = f"Src-{doc_idx + 1}"
        doc_chunks = text_splitter.split_text(doc["text"])

        for chk_idx, chunk_text in enumerate(doc_chunks):
            chunk_id = f"src_{doc_idx + 1}_chk_{chk_idx + 1}"
            content_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:12]

            all_chunks.append(chunk_text)
            all_ids.append(chunk_id)
            all_metadatas.append({
                "source_id": source_id,
                "chunk_id": chunk_id,
                "source_url": doc["url"],
                "page_title": doc["title"][:100],
                "domain": doc["domain"],
                "retrieval_timestamp": timestamp_iso,
                "content_hash": content_hash,
            })

    # 5. Embed into the session's private Chroma collection
    collection = get_session_collection(session_id)

    # Clear prior data in THIS session collection only (preserves other users & turns)
    if collection.count() > 0:
        existing_ids = collection.get()["ids"]
        collection.delete(ids=existing_ids)

    print(f"[INDEX] Embedding {len(all_chunks)} chunks with metadata into session collection '{sanitize_session_id(session_id)}'...")
    chunk_embeddings = embeddings.embed_documents(all_chunks)

    collection.add(
        documents=all_chunks,
        ids=all_ids,
        metadatas=all_metadatas,
        embeddings=chunk_embeddings,
    )
    print("[INDEX] Session Knowledge Base successfully indexed!")

    source_manifest = [
        {
            "source_id": f"Src-{idx + 1}",
            "title": d["title"],
            "domain": d["domain"],
            "url": d["url"],
        }
        for idx, d in enumerate(successful_docs)
    ]

    return {
        "success": True,
        "status": "INDEXED",
        "chunk_count": len(all_chunks),
        "sources": source_manifest,
    }


def query_and_rerank(
    session_id: str,
    query: str,
    top_k_candidates: int = 20,
    final_top_k: int = 6,
) -> list[dict[str, Any]]:
    """Two-tier retrieval:

    Tier 1 (Bi-Encoder): Retrieves top 15-20 candidates from session ChromaDB.
    Tier 2 (Cross-Encoder): Re-scores (query, chunk) with ms-marco-MiniLM-L-6-v2,
                           returning the top 5-6 highest-signal chunks.
    """
    collection = get_session_collection(session_id)
    doc_count = collection.count()
    if doc_count == 0:
        return []

    n_fetch = min(top_k_candidates, doc_count)
    query_vector = embeddings.embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_fetch,
        include=["documents", "metadatas", "distances"],
    )

    candidate_docs = results["documents"][0]
    candidate_metas = results["metadatas"][0]

    if not candidate_docs:
        return []

    # Run Cross-Encoder scoring over (query, document) pairs
    pairs = [[query, doc] for doc in candidate_docs]
    cross_scores = cross_encoder.predict(pairs)

    ranked_results: list[dict[str, Any]] = []
    for doc, meta, score in zip(candidate_docs, candidate_metas, cross_scores):
        ranked_results.append({
            "source_id": meta.get("source_id", "Src-Unknown"),
            "chunk_id": meta.get("chunk_id", ""),
            "title": meta.get("page_title", ""),
            "domain": meta.get("domain", ""),
            "url": meta.get("source_url", ""),
            "text": doc,
            "rerank_score": float(score),
            "timestamp": meta.get("retrieval_timestamp", ""),
        })

    # Sort descending by Cross-Encoder score
    ranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return ranked_results[:final_top_k]


def format_retrieved_context(reranked_chunks: list[dict[str, Any]]) -> str:
    """Formats reranked chunks with clean citation identifiers for the LLM generator."""
    if not reranked_chunks:
        return "No relevant context retrieved."

    formatted_parts = []
    for c in reranked_chunks:
        header = f"[{c['source_id']}] Source: {c['title']} ({c['domain']}) | Chunk: {c['chunk_id']}"
        body = f"{header}\nURL: {c['url']}\nContent: {c['text']}\n"
        formatted_parts.append(body)

    return "\n---\n".join(formatted_parts)


# Backwards compatibility helper
def query_live_database(vibe_query: str, session_id: str = "default_session") -> list[str]:
    chunks = query_and_rerank(session_id, vibe_query, top_k_candidates=15, final_top_k=5)
    return [c["text"] for c in chunks]


if __name__ == "__main__":
    test_session = "test_tirthan_session"
    res = dynamic_research_and_index(test_session, "Tirthan Valley Himachal Pradesh")
    print("\nIndexing Result:", res)

    if res["success"]:
        ranked = query_and_rerank(test_session, "riverside homestays trout fishing budget", final_top_k=3)
        print("\n--- Top Reranked Chunks ---")
        for r in ranked:
            print(f"[{r['source_id']}] Score: {r['rerank_score']:.4f} | {r['title']} ({r['domain']})")
            print(f"{r['text'][:200]}...\n")