import operator
import os
import sqlite3
import time
from typing import Annotated, Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.rag_engine import (
    dynamic_research_and_index,
    format_retrieved_context,
    query_and_rerank,
)

load_dotenv()


# =====================================================================
# 1. Pydantic Schemas for Structured LLM Outputs
# =====================================================================

class TripParameters(BaseModel):
    destination: str | None = Field(None, description="The specific destination if mentioned. None if undecided.")
    current_location: str | None = Field(None, description="The user's starting location, needed if destination is undecided.")
    vibe_or_interests: str | None = Field(None, description="The kind of vibe or activity the user wants. Defaults to popular sights if unspecified.")
    budget: str | None = Field(
        None, 
        description="The user's budget for the trip (e.g. '$500', 'under $300', 'budget-friendly', 'luxury', 'moderate standard budget'). If the user asks for recommendations or doesn't know, provide a reasonable standard budget like 'moderate standard budget'."
    )
    number_of_days: int | None = Field(None, description="The number of days for the trip.")
    missing_critical_fields: list[str] = Field(default_factory=list, description="Missing fields required for the scenario.")
    is_ready_for_execution: bool = Field(False, description="True ONLY if we have enough parameters to plan a trip or suggest destinations.")
    clarification_question: str | None = Field(None, description="A natural question to ask if fields are missing.")
    requires_new_research: bool = Field(
        True,
        description="Set to False ONLY if the user is asking to revise an existing itinerary (e.g. cheaper hotels, swap days) without fundamentally changing the destination."
    )


class ItineraryCard(BaseModel):
    title: str = Field(description="The heading for this card (e.g., 'Trip Overview' or 'Day 1: Arrival').")
    details: list[str] = Field(
        description=(
            "A highly detailed list of bullet points for this card. "
            "Specific factual claims (hotel names, prices, activities, travel times) MUST cite source tags like [Src-1], [Src-2]. "
            "If a price or amenity cannot be confirmed from context, state that it could not be confirmed."
        )
    )


class ItineraryOutput(BaseModel):
    chat_message: str = Field(description="A short, conversational 1-sentence message to the user acknowledging their request.")
    itinerary_cards: list[ItineraryCard] = Field(description="The itinerary broken down into separate sections/cards. The first should always be an Overview.")


class ClaimCheckItem(BaseModel):
    claim: str = Field(description="The factual claim extracted from the draft itinerary.")
    cited_source: str | None = Field(description="The cited tag e.g. [Src-1] or None if unreferenced.")
    status: Literal["SUPPORTED", "UNSUPPORTED", "UNCERTAIN"] = Field(
        description="SUPPORTED if clearly substantiated by cited chunk; UNSUPPORTED if not backed; UNCERTAIN if ambiguous."
    )
    explanation: str = Field(description="Brief 1-sentence rationale comparing claim to cited chunk text.")


class VerificationResult(BaseModel):
    verified_cards: list[ItineraryCard] = Field(
        description="The final cleaned itinerary cards. Any unsupported or fabricated claims must be removed or rephrased with explicit caveats."
    )
    claims: list[ClaimCheckItem] = Field(default_factory=list, description="Itemized verification of key claims.")
    faithfulness_score: float = Field(description="Calculated score between 0.0 and 1.0 (supported claims / total verified claims).")
    review_summary: str = Field(description="Brief summary of verification changes made.")


# =====================================================================
# 2. Central Agent State
# =====================================================================

class AgentState(TypedDict):
    session_id: str
    messages: Annotated[list, operator.add]
    trip_params: dict
    research_status: dict
    retrieved_context: str
    reranked_chunks: list[dict]
    draft_itinerary: list[dict]
    final_itinerary: list[dict]
    citations: list[dict]
    verification_report: dict
    timings: dict


# =====================================================================
# 3. Model Initialization
# =====================================================================

# Primary LLM for supervisor and generation (gemini-3.5-flash-lite offers high speed & reliability)
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0.1)

supervisor_evaluator = llm.with_structured_output(TripParameters)
generator_evaluator = llm.with_structured_output(ItineraryOutput)
verifier_evaluator = llm.with_structured_output(VerificationResult)


def extract_session_id(state: AgentState, config: RunnableConfig | None = None) -> str:
    """Helper to extract a consistent session identifier."""
    if state.get("session_id"):
        return state["session_id"]
    if config and "configurable" in config and "thread_id" in config["configurable"]:
        return str(config["configurable"]["thread_id"])
    return "default_session"


# =====================================================================
# STAGE 1: Supervisor / Router Agent (LLM)
# =====================================================================

def supervisor_node(state: AgentState, config: RunnableConfig | None = None):
    print("\n--- [STAGE 1] SUPERVISOR / ROUTER AGENT ---")
    t0 = time.perf_counter()
    session_id = extract_session_id(state, config)

    chat_history = "\n".join([str(m) for m in state.get("messages", [])])

    prompt = f"""
    You are the Airbnb Atlas Supervisor & Intent Router.
    Analyze the full conversation history:
    {chat_history}

    Your goal is to parse constraints and route appropriately:

    SCENARIO 1: User specifies destination.
    Required: 'destination', 'vibe_or_interests', 'budget', 'number_of_days'.

    BUDGET & VIBE HANDLING (PREVENT REPETITIVE CLARIFICATION LOOPS):
    - If the user explicitly mentions a budget (e.g. "$500", "15000 INR", "cheap", "luxury"), ALWAYS extract it into 'budget'.
    - If the user says they do NOT know the budget, asks "what is an ideal one?", says "reasonable / standard / moderate / flexible / any / recommended / whatever", or asks you to suggest:
      DO NOT keep asking for budget repeatedly!
      Assign a sensible, standard mid-range travel budget for that destination (e.g. "moderate standard budget" or "standard mid-range") into 'budget', and proceed!
    - If vibe is unspecified or user says "tourist places", "famous places", "sightseeing", "anything is fine", "popular", assign "popular sights and attractions" to 'vibe_or_interests' and proceed!
    - If destination and duration/days are known, and budget is either specified or the user asked for a recommendation / standard budget, set is_ready_for_execution = True so research and generation can proceed immediately!

    SCENARIO 2: User is undecided about destination.
    Required: 'current_location', 'vibe_or_interests', 'budget', 'number_of_days'.

    REVISIONS: If the user is modifying or revising an already-planned trip (e.g. "make hotels cheaper", "less days", "swap day 2")
    without asking for a completely different destination, set requires_new_research = False so prior evidence is reused.
    If the destination has changed or this is an initial trip, set requires_new_research = True.

    If required fields are truly missing and the user hasn't asked for recommendations, set is_ready_for_execution = False and provide ONE concise clarification_question.
    If all required data for the scenario is present, set is_ready_for_execution = True.
    """

    result = supervisor_evaluator.invoke(prompt)
    t1 = time.perf_counter()
    elapsed_ms = round((t1 - t0) * 1000, 1)

    timings = dict(state.get("timings", {}))
    timings["supervisor_ms"] = elapsed_ms

    if not result.is_ready_for_execution:
        print(f"Supervisor Decision: Clarification needed -> {result.clarification_question} ({elapsed_ms}ms)")
        return {
            "session_id": session_id,
            "trip_params": result.model_dump(),
            "messages": [f"Atlas: {result.clarification_question}"],
            "timings": timings,
        }

    dest_str = result.destination or "undecided destination"
    print(f"Supervisor Decision: Ready for {dest_str}! (new_research={result.requires_new_research}, {elapsed_ms}ms)")
    return {
        "session_id": session_id,
        "trip_params": result.model_dump(),
        "timings": timings,
    }


# =====================================================================
# STAGE 2: Dynamic Research Node (Deterministic Tool Node - NO LLM)
# =====================================================================

def dynamic_research_node(state: AgentState, config: RunnableConfig | None = None):
    print("\n--- [STAGE 2] DYNAMIC RESEARCH NODE ---")
    t0 = time.perf_counter()
    session_id = extract_session_id(state, config)

    params = state.get("trip_params", {})
    dest = params.get("destination")
    start_loc = params.get("current_location", "")
    vibe = params.get("vibe_or_interests", "")
    budget = params.get("budget", "")
    days = params.get("number_of_days", "")

    # Clean filler expressions from vibe so search engines don't receive conversational noise
    filler_vibes = {"anything is fine", "any", "anything", "fine", "none", "whatever", "flexible", "normal", "no preference"}
    vibe_clean = "" if vibe.lower().strip() in filler_vibes else vibe.strip()

    if dest:
        parts = [dest]
        if vibe_clean:
            parts.append(vibe_clean)
        parts.append("travel guide")
        search_query = " ".join(parts)
    else:
        parts = ["best"]
        if vibe_clean:
            parts.append(vibe_clean)
        parts.append("travel destinations")
        if start_loc:
            parts.append(f"from {start_loc}")
        search_query = " ".join(parts)

    # Execute search, scrape, chunk, metadata attachment, and Chroma indexing
    research_result = dynamic_research_and_index(session_id=session_id, destination_query=search_query)

    t1 = time.perf_counter()
    elapsed_ms = round((t1 - t0) * 1000, 1)

    timings = dict(state.get("timings", {}))
    timings["research_ms"] = elapsed_ms

    # If research failed/halted, reset context & citations to prevent cross-destination bleed
    if not research_result.get("success", True):
        return {
            "research_status": research_result,
            "retrieved_context": "",
            "citations": [],
            "reranked_chunks": [],
            "draft_itinerary": [],
            "final_itinerary": [],
            "timings": timings,
        }

    return {
        "research_status": research_result,
        "draft_itinerary": [],
        "final_itinerary": [],
        "timings": timings,
    }


# =====================================================================
# STAGE 3: Cross-Encoder Reranker Node (Deterministic Local ML - NO LLM)
# =====================================================================

def reranker_node(state: AgentState, config: RunnableConfig | None = None):
    print("\n--- [STAGE 3] CROSS-ENCODER RERANKER NODE ---")
    t0 = time.perf_counter()
    session_id = extract_session_id(state, config)

    params = state.get("trip_params", {})
    vibe = params.get("vibe_or_interests", "")
    budget = params.get("budget", "")
    days = params.get("number_of_days", "")
    dest = params.get("destination", "")

    query = f"{dest} options for vibe: {vibe}, budget: {budget}, duration: {days} days."

    # Retrieve top 20 candidates, then rerank with local ms-marco Cross-Encoder to top 6
    reranked = query_and_rerank(session_id=session_id, query=query, top_k_candidates=20, final_top_k=6)
    formatted_context = format_retrieved_context(reranked)

    # Compile source manifest for frontend
    source_manifest = []
    seen_sources = set()
    for item in reranked:
        src_id = item["source_id"]
        if src_id not in seen_sources:
            seen_sources.add(src_id)
            source_manifest.append({
                "source_id": src_id,
                "title": item["title"],
                "domain": item["domain"],
                "url": item["url"],
            })

    t1 = time.perf_counter()
    elapsed_ms = round((t1 - t0) * 1000, 1)

    timings = dict(state.get("timings", {}))
    timings["rerank_ms"] = elapsed_ms

    print(f"Reranker: Selected top {len(reranked)} chunks ({elapsed_ms}ms)")
    return {
        "reranked_chunks": reranked,
        "retrieved_context": formatted_context,
        "citations": source_manifest,
        "timings": timings,
    }


# =====================================================================
# STAGE 4: Citation-Aware Generator Agent (LLM)
# =====================================================================

def citation_generator_node(state: AgentState):
    print("\n--- [STAGE 4] CITATION-AWARE GENERATOR AGENT ---")
    t0 = time.perf_counter()

    research_status = state.get("research_status", {})
    # Check if scraping gate halted execution
    if research_status and not research_status.get("success", True):
        msg = research_status.get(
            "message",
            "Insufficient live web sources could be verified for this request. Live research was halted to prevent hallucinations."
        )
        t1 = time.perf_counter()
        timings = dict(state.get("timings", {}))
        timings["generation_ms"] = round((t1 - t0) * 1000, 1)

        fallback_cards = [
            ItineraryCard(
                title="Live Research Gate Notice",
                details=[
                    msg,
                    "Atlas requires verified live internet sources to generate an itinerary. Please refine your destination or try again shortly."
                ]
            )
        ]
        return {
            "draft_itinerary": [c.model_dump() for c in fallback_cards],
            "messages": [f"Atlas: {msg}"],
            "retrieved_context": "",
            "citations": [],
            "reranked_chunks": [],
            "timings": timings,
        }

    context = state.get("retrieved_context", "")
    params = state.get("trip_params", {})
    dest = params.get("destination")
    start_loc = params.get("current_location", "")
    latest_user_msg = state["messages"][-1] if state.get("messages") else "Create the itinerary."

    prompt = f"""
    You are the Airbnb Atlas Itinerary Synthesizer.
    Create a highly specific, engaging itinerary for {dest or ('destinations from ' + start_loc)}
    based STRICTLY on the retrieved context below.

    USER REQUEST: "{latest_user_msg}"

    RETRIEVED LIVE CONTEXT (With source tags):
    {context}

    CRITICAL CITATION & FACTUALITY RULES:
    1. Every specific factual statement (hotel name, pricing, activity, neighborhood, transit duration) MUST cite one or more source tags, e.g. "Stay at Tirthan Riverside Homestay for ₹4,500/night [Src-1]".
    2. DO NOT fabricate prices or amenities. If the exact cost or amenity is not confirmed in the context, explicitly state "Price/amenity unconfirmed in live sources".
    3. Include a comprehensive budget breakdown (stays, food, transport, activities) in the Overview and daily cards using the cited facts.
    4. Format your cards with rich, descriptive paragraphs per bullet.
    """

    response = generator_evaluator.invoke(prompt)
    t1 = time.perf_counter()
    elapsed_ms = round((t1 - t0) * 1000, 1)

    timings = dict(state.get("timings", {}))
    timings["generation_ms"] = elapsed_ms

    print(f"Generator: Synthesized {len(response.itinerary_cards)} cards ({elapsed_ms}ms)")
    return {
        "draft_itinerary": [c.model_dump() for c in response.itinerary_cards],
        "messages": [f"Atlas: {response.chat_message}"],
        "timings": timings,
    }


# =====================================================================
# STAGE 5: Claim Verification Agent / Critic (LLM Judge)
# =====================================================================

def claim_verification_node(state: AgentState):
    print("\n--- [STAGE 5] CLAIM VERIFICATION AGENT (CRITIC) ---")
    t0 = time.perf_counter()

    draft_cards = state.get("draft_itinerary", [])
    context = state.get("retrieved_context", "")
    research_status = state.get("research_status", {})

    # If this was a scraping gate notice or empty context, safely bypass critic verification
    is_gate_halt = (
        (research_status and not research_status.get("success", True))
        or any("Gate Notice" in card.get("title", "") for card in draft_cards)
        or not draft_cards
        or not context
        or context == "No relevant context retrieved."
    )

    if is_gate_halt:
        t1 = time.perf_counter()
        timings = dict(state.get("timings", {}))
        timings["verification_ms"] = 0.0
        timings["total_ms"] = round(sum(v for k, v in timings.items() if k.endswith("_ms")), 1)
        return {
            "final_itinerary": draft_cards,
            "verification_report": {
                "faithfulness_score": None,
                "status": "GATE_HALTED",
                "review_summary": "Scraping Gate halted execution to avoid ungrounded hallucinations. Claim verification safely bypassed.",
                "claims": [],
            },
            "citations": [],
            "timings": timings,
        }

    cards_text = ""
    for card in draft_cards:
        cards_text += f"\n### {card.get('title')}\n"
        for detail in card.get("details", []):
            cards_text += f"- {detail}\n"

    prompt = f"""
    You are the Airbnb Atlas Claim Verification Judge (Critic).
    Review the draft itinerary below and cross-examine all factual claims against the retrieved evidence chunks.

    RETRIEVED EVIDENCE CHUNKS:
    {context}

    DRAFT ITINERARY TO VERIFY:
    {cards_text}

    YOUR TASKS:
    1. Extract the key factual claims (stays, prices, activities, travel times, logistics).
    2. Label each claim as:
       - SUPPORTED: Clearly verified by the cited source chunk text.
       - UNSUPPORTED: Not in the source chunk or hallucinated.
       - UNCERTAIN: Mentioned but details are ambiguous.
    3. Calculate faithfulness_score = (supported claims / total claims).
    4. Return the cleaned verified_cards:
       - Keep supported facts intact with their citations [Src-X].
       - If an unsupported claim is found, either excise it or replace with "could not be independently verified from live sources".
    """

    verification_res = verifier_evaluator.invoke(prompt)

    t1 = time.perf_counter()
    elapsed_ms = round((t1 - t0) * 1000, 1)

    timings = dict(state.get("timings", {}))
    timings["verification_ms"] = elapsed_ms
    timings["total_ms"] = round(sum(v for k, v in timings.items() if k.endswith("_ms")), 1)

    print(
        f"Verification Critic: Faithfulness Score = {verification_res.faithfulness_score:.2f} "
        f"({len(verification_res.claims)} claims checked, {elapsed_ms}ms, Total: {timings['total_ms']}ms)"
    )

    final_cards = [c.model_dump() for c in verification_res.verified_cards] if verification_res.verified_cards else draft_cards

    return {
        "final_itinerary": final_cards,
        "verification_report": verification_res.model_dump(),
        "timings": timings,
    }


# =====================================================================
# 4. Conditional Edge Routing Logic
# =====================================================================

def route_after_supervisor(state: AgentState, config: RunnableConfig | None = None):
    params = state.get("trip_params", {})
    if not params.get("is_ready_for_execution"):
        return END

    from app.rag_engine import get_session_collection
    session_id = extract_session_id(state, config)
    collection = get_session_collection(session_id)
    has_existing_evidence = collection.count() > 0

    if not params.get("requires_new_research", True) and has_existing_evidence:
        print("[ROUTER] Warm Revision detected: Bypassing research and reusing session evidence!")
        return "reranker_node"
    else:
        return "dynamic_research_node"


def route_after_research(state: AgentState):
    research_status = state.get("research_status", {})
    if not research_status.get("success", True):
        # Scraping gate failed; skip reranking and route directly to generator for transparent notice
        return "citation_generator_node"
    return "reranker_node"


# =====================================================================
# 5. Compile the 5-Stage Graph with SQLite Checkpointer
# =====================================================================

workflow = StateGraph(AgentState)

# Add all 5 stages
workflow.add_node("supervisor_node", supervisor_node)
workflow.add_node("dynamic_research_node", dynamic_research_node)
workflow.add_node("reranker_node", reranker_node)
workflow.add_node("citation_generator_node", citation_generator_node)
workflow.add_node("claim_verification_node", claim_verification_node)

# Connect edges
workflow.add_edge(START, "supervisor_node")

workflow.add_conditional_edges(
    "supervisor_node",
    route_after_supervisor,
    {
        "dynamic_research_node": "dynamic_research_node",
        "reranker_node": "reranker_node",
        END: END,
    },
)

workflow.add_conditional_edges(
    "dynamic_research_node",
    route_after_research,
    {
        "reranker_node": "reranker_node",
        "citation_generator_node": "citation_generator_node",
    },
)

workflow.add_edge("reranker_node", "citation_generator_node")
workflow.add_edge("citation_generator_node", "claim_verification_node")
workflow.add_edge("claim_verification_node", END)

# Persistent SQLite checkpointer so sessions survive server restarts
CHECKPOINT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
CHECKPOINT_DB_PATH = os.path.join(CHECKPOINT_DIR, "langgraph_checkpoints.db")

conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
checkpointer = SqliteSaver(conn)
checkpointer.setup()

app_graph = workflow.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    print("Testing 5-stage pipeline locally...")
    config = {"configurable": {"thread_id": "test_run_tirthan_1"}}
    initial_input = {
        "session_id": "test_run_tirthan_1",
        "messages": ["I want to go to Tirthan Valley for trout fishing and riverside stays for 4 days with a budget of $500."]
    }
    res = app_graph.invoke(initial_input, config=config)
    print("\nFinal Itinerary:", res.get("final_itinerary"))
    print("\nTimings:", res.get("timings"))
    print("\nVerification:", res.get("verification_report"))