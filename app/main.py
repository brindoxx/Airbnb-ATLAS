
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import uuid

from app.graph import app_graph
from app.database import save_session

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
    messages: list[str]

class ChatResponse(BaseModel):
    session_id: str
    response: list | str
    is_clarification: bool
    destination: str | None = None
    chat_message: str | None = None

@app.post("/plan_trip", response_model=ChatResponse)
def plan_trip_endpoint(request: ChatRequest):
    print("\n--- 🌐 RECEIVED API REQUEST ---")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    # LangGraph's Checkpointer Remembers everything. We only need to pass the LATEST message.
    latest_message = request.messages[-1] if request.messages else ""
    initial_state = {"messages": [latest_message]}
    
    # Pass the session_id as the thread_id so LangGraph loads the correct memory
    config = {"configurable": {"thread_id": session_id}}
    
    # Execute the LangGraph workflow
    result = app_graph.invoke(initial_state, config=config)
    
    final_itinerary = result.get("final_itinerary")
    
    # Save session to the SQLite database
    import json
    save_session(
        session_id=session_id,
        messages=result["messages"],
        parameters=result.get("trip_params", {}),
        final_itinerary=json.dumps(final_itinerary) if isinstance(final_itinerary, list) else final_itinerary
    )
    
    # Route the output based on whether the graph finished or paused for clarification
    trip_params = result.get("trip_params", {})
    dest = trip_params.get("destination")
    
    if final_itinerary:
        # The trip was successfully generated
        # Clean the "Atlas: " prefix from the chat message if it exists
        raw_msg = result["messages"][-1]
        clean_msg = raw_msg.replace("Atlas: ", "") if isinstance(raw_msg, str) else raw_msg
        
        return ChatResponse(
            session_id=session_id,
            response=final_itinerary,
            is_clarification=False,
            destination=dest,
            chat_message=clean_msg
        )
    else:
        # The Supervisor halted execution to ask for missing parameters
        # Grab the last message added by the Supervisor
        return ChatResponse(
            session_id=session_id,
            response=result["messages"][-1], 
            is_clarification=True
        )

# Health check endpoint for Render deployment
@app.get("/")
def health_check():
    return {"status": "Atlas Engine is Online"}