
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
    response: str
    is_clarification: bool

@app.post("/plan_trip", response_model=ChatResponse)
def plan_trip_endpoint(request: ChatRequest):
    print("\n--- 🌐 RECEIVED API REQUEST ---")
    
    session_id = request.session_id or str(uuid.uuid4())
    
    # Initialize the graph state with the chat history provided by the frontend
    initial_state = {"messages": request.messages}
    
    # Execute the LangGraph workflow
    result = app_graph.invoke(initial_state)
    
    final_itinerary = result.get("final_itinerary")
    
    # Save session to the SQLite database
    save_session(
        session_id=session_id,
        messages=result["messages"],
        parameters=result.get("trip_params", {}),
        final_itinerary=final_itinerary
    )
    
    # Route the output based on whether the graph finished or paused for clarification
    if final_itinerary:
        # The trip was successfully generated
        return ChatResponse(
            session_id=session_id,
            response=final_itinerary,
            is_clarification=False
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