from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from app.graph import app_graph
from fastapi.middleware.cors import CORSMiddleware

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
    messages: List[str]

class ChatResponse(BaseModel):
    response: str
    is_clarification: bool

@app.post("/plan_trip", response_model=ChatResponse)
def plan_trip_endpoint(request: ChatRequest):
    print("\n--- 🌐 RECEIVED API REQUEST ---")
    
    # Initialize the graph state with the chat history provided by the frontend
    initial_state = {"messages": request.messages}
    
    # Execute the LangGraph workflow
    result = app_graph.invoke(initial_state)
    
    # Route the output based on whether the graph finished or paused for clarification
    if "final_itinerary" in result and result["final_itinerary"]:
        # The trip was successfully generated
        return ChatResponse(
            response=result["final_itinerary"],
            is_clarification=False
        )
    else:
        # The Supervisor halted execution to ask for missing parameters
        # Grab the last message added by the Supervisor
        return ChatResponse(
            response=result["messages"][-1], 
            is_clarification=True
        )

# Health check endpoint for Render deployment
@app.get("/")
def health_check():
    return {"status": "Atlas Engine is Online"}