
import json
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.database import save_session
from app.graph import app_graph

# Initialize the FastAPI application
app = FastAPI(title="Airbnb Atlas API", description="Semantic Orchestration Engine")

# Allow Cross-Origin Requests so your Claude/Vercel frontend can talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your Vercel URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the data structure expected from the frontend
class ChatRequest(BaseModel):
    session_id: str | None = None
    messages: list[Any] = []

class ChatResponse(BaseModel):
    session_id: str
    response: list | str
    is_clarification: bool
    destination: str | None = None
    chat_message: str | None = None
    citations: list[dict] = []
    timings: dict = {}
    verification_report: dict = {}

@app.post("/plan_trip", response_model=ChatResponse)
def plan_trip_endpoint(request: ChatRequest):
    print("\n--- 🌐 RECEIVED API REQUEST ---")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    # Normalize messages to clean strings regardless of whether frontend sent string or card object
    clean_messages: list[str] = []
    for m in (request.messages or []):
        if isinstance(m, str):
            clean_messages.append(m)
        elif isinstance(m, dict):
            clean_messages.append(m.get("text") or m.get("content") or json.dumps(m))
        elif isinstance(m, list):
            clean_messages.append(json.dumps(m))
        else:
            clean_messages.append(str(m))

    latest_message = clean_messages[-1] if clean_messages else ""
    initial_state = {
        "messages": [latest_message],
        "session_id": session_id,
    }
    
    # Pass the session_id as the thread_id so LangGraph loads the correct checkpoint memory
    config = {"configurable": {"thread_id": session_id}}
    
    # Execute the 5-Stage LangGraph workflow
    result = app_graph.invoke(initial_state, config=config)
    
    final_itinerary = result.get("final_itinerary")
    citations = result.get("citations", [])
    timings = result.get("timings", {})
    verification_report = result.get("verification_report", {})
    
    # Save session to the SQLite database
    save_session(
        session_id=session_id,
        messages=result.get("messages", []),
        parameters=result.get("trip_params", {}),
        final_itinerary=json.dumps(final_itinerary) if isinstance(final_itinerary, list) else final_itinerary
    )
    
    # Route the output based on whether the graph finished or paused for clarification
    trip_params = result.get("trip_params", {})
    dest = trip_params.get("destination")
    is_ready = trip_params.get("is_ready_for_execution", False)

    # If the supervisor is asking a clarification question, NEVER leak old itineraries or set the destination title
    if not is_ready:
        last_msg = result["messages"][-1] if result.get("messages") else "Could you provide more details?"
        clean_msg = last_msg.replace("Atlas: ", "") if isinstance(last_msg, str) else last_msg
        return ChatResponse(
            session_id=session_id,
            response=clean_msg,
            is_clarification=True,
            destination=None,
            chat_message=clean_msg,
            timings=timings,
        )

    if final_itinerary:
        # The trip was successfully generated
        raw_msg = result["messages"][-1] if result.get("messages") else "Here is your verified itinerary."
        clean_msg = raw_msg.replace("Atlas: ", "") if isinstance(raw_msg, str) else raw_msg
        
        return ChatResponse(
            session_id=session_id,
            response=final_itinerary,
            is_clarification=False,
            destination=dest,
            chat_message=clean_msg,
            citations=citations,
            timings=timings,
            verification_report=verification_report,
        )
    else:
        # Fallback clarification response
        last_msg = result["messages"][-1] if result.get("messages") else "Could you provide more details?"
        clean_msg = last_msg.replace("Atlas: ", "") if isinstance(last_msg, str) else last_msg
        return ChatResponse(
            session_id=session_id,
            response=clean_msg, 
            is_clarification=True,
            destination=None,
            chat_message=clean_msg,
            timings=timings,
        )

# Health check endpoint for Render deployment
@app.get("/")
def health_check():
    return {"status": "Atlas Engine is Online"}