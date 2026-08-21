import operator
from typing import Annotated, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.rag_engine import dynamic_research_and_index, query_live_database


# 1. Define the Expected Output Schema for the Supervisor
class TripParameters(BaseModel):
    destination: str | None = Field(None, description="The specific destination if mentioned. Leave None if user is undecided.")
    current_location: str | None = Field(None, description="The user's starting location, needed if destination is undecided.")
    vibe_or_interests: str | None = Field(None, description="The kind of vibe or activity the user wants.")
    budget: str | None = Field(None, description="The user's budget for the trip.")
    number_of_days: int | None = Field(None, description="The number of days for the trip.")
    missing_critical_fields: list[str] = Field(default_factory=list, description="Missing fields required for the scenario.")
    is_ready_for_execution: bool = Field(False, description="True ONLY if we have enough parameters to plan a trip or suggest destinations.")
    clarification_question: str | None = Field(None, description="A natural question to ask if fields are missing.")

# 2. Define the Central Graph State
class AgentState(TypedDict):
    # 'operator.add' ensures messages are appended, not overwritten
    messages: Annotated[list, operator.add] 
    trip_params: dict
    retrieved_context: str
    final_itinerary: str

# Initialize the LLM (Gemini 1.5 Flash is perfect for speed here)
llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", temperature=0.2)
structured_evaluator = llm.with_structured_output(TripParameters)

# --- NODE 1: The Supervisor ---
def supervisor_node(state: AgentState):
    print("\n--- 🧠 SUPERVISOR NODE ---")
    chat_history = "\n".join(state["messages"])
    
    prompt = f"""
    You are the Airbnb Atlas Supervisor.
    Analyze the user's request: {chat_history}
    
    Your goal is to collect enough information to plan a trip.
    
    SCENARIO 1: User knows their destination.
    We need: 'destination', 'vibe_or_interests', 'budget', and 'number_of_days'.
    
    SCENARIO 2: User DOES NOT know where to go.
    We need: 'current_location', 'vibe_or_interests', 'budget', and 'number_of_days'.
    
    If anything is missing for the applicable scenario, set is_ready_for_execution to False and ask ONE friendly follow-up question to collect the missing data.
    If all required data is collected, set is_ready_for_execution to True.
    """
    
    result = structured_evaluator.invoke(prompt)
    
    if not result.is_ready_for_execution:
        print(f"Supervisor Decision: Asking for clarification -> {result.clarification_question}")
        return {
            "trip_params": result.model_dump(),
            "messages": [f"Atlas: {result.clarification_question}"]
        }
        
    dest_str = result.destination if result.destination else "undecided destination"
    print(f"Supervisor Decision: Ready to execute for {dest_str}!")
    return {"trip_params": result.model_dump()}

# --- NODE 2: The JIT RAG Execution ---
def dynamic_research_node(state: AgentState):
    print("\n--- 🌍 DYNAMIC RESEARCH NODE ---")
    dest = state["trip_params"].get("destination")
    start_loc = state["trip_params"].get("current_location", "")
    vibe = state["trip_params"].get("vibe_or_interests", "")
    budget = state["trip_params"].get("budget", "")
    days = state["trip_params"].get("number_of_days", "")
    
    if dest:
        search_query = f"{dest} {vibe} travel guide {days} days budget {budget}"
    else:
        search_query = f"best {vibe} travel destinations from {start_loc} budget {budget} for {days} days"
    
    # Trigger your real-time scraping engine!
    dynamic_research_and_index(search_query)
    
    # Query the newly built live DB
    query = f"Provide options matching vibe: {vibe}, budget: {budget}, duration: {days} days."
    raw_context = query_live_database(query)
    
    return {"retrieved_context": "\n\n".join(raw_context) if isinstance(raw_context, list) else raw_context}

# --- NODE 3: The Synthesizer ---
def synthesizer_node(state: AgentState):
    print("\n--- ✍️ SYNTHESIZER NODE ---")
    context = state.get("retrieved_context", "")
    dest = state["trip_params"].get("destination")
    start_loc = state["trip_params"].get("current_location", "")
    
    if dest:
        system_task = f"Create a highly specific, engaging itinerary for {dest} based ONLY on this verified live internet data."
    else:
        system_task = f"Propose 2-3 great destination options from {start_loc} with high-level plans based ONLY on this verified live internet data."
        
    prompt = f"""
    You are the Airbnb Atlas Copilot.
    {system_task}
    
    Context:
    {context}
    
    Ensure you highlight how the places match the user's vibe and budget. Do not hallucinate amenities or prices.
    """
    
    response = llm.invoke(prompt)
    itinerary_text = extract_text(response.content)  # <-- normalize here
    
    return {
        "final_itinerary": itinerary_text,
        "messages": [f"Atlas: {itinerary_text}"]
    }

def extract_text(content) -> str:
    """Gemini/LangChain sometimes returns .content as a plain string,
    sometimes as a list of content blocks. Normalize to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "".join(parts)
    return str(content)

# --- EDGE ROUTING LOGIC ---
def route_after_supervisor(state: AgentState):
    params = state.get("trip_params", {})
    if params.get("is_ready_for_execution"):
        return "dynamic_research_node"
    return END # Stop the graph and wait for the user's reply

# --- COMPILE THE GRAPH ---
workflow = StateGraph(AgentState)

# Add all nodes
workflow.add_node("supervisor_node", supervisor_node)
workflow.add_node("dynamic_research_node", dynamic_research_node)
workflow.add_node("synthesizer_node", synthesizer_node)

# Define the flow
workflow.add_edge(START, "supervisor_node")
workflow.add_conditional_edges(
    "supervisor_node",
    route_after_supervisor,
    {
        "dynamic_research_node": "dynamic_research_node",
        END: END
    }
)
workflow.add_edge("dynamic_research_node", "synthesizer_node")
workflow.add_edge("synthesizer_node", END)

# Compile into an executable application
app_graph = workflow.compile()

# --- QUICK TEST RUNNER ---
if __name__ == "__main__":
    print("Test 1: Vague Prompt (Should ask for clarification)")
    test_state_1 = {"messages": ["I want to go on a trip to the mountains."]}
    result_1 = app_graph.invoke(test_state_1)
    
    print("\n" + "="*50 + "\n")
    
    print("Test 2: Complete Prompt (Should execute full pipeline)")
    test_state_2 = {"messages": ["I want to go to Tirthan Valley, looking for riverside stays and trout fishing. My budget is $500 and I want to stay for 4 days."]}
    result_2 = app_graph.invoke(test_state_2)
    print("\nFinal Output:\n", result_2.get("final_itinerary", result_2["messages"][-1]))