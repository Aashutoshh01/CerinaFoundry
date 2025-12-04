"""
Cerina Protocol Foundry API Server.

This module implements a FastAPI server that acts as the interface between the
frontend dashboard (or external clients) and the LangGraph-based clinical workflow.
It handles session management, workflow execution, and human-in-the-loop interventions.
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from langgraph.types import Command
from graph import graph

# Initialize FastAPI application
app = FastAPI(title="Cerina Protocol Foundry API")

# Configure CORS to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Data Models ---

class RunRequest(BaseModel):
    """Payload for initiating a new workflow session."""
    thread_id: str
    user_query: str

class ReviewRequest(BaseModel):
    """Payload for submitting a human review decision."""
    thread_id: str
    action: str  # Expected values: "approve" or "reject"
    feedback: Optional[str] = None

# --- Helper Functions ---

def process_graph_result(result: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """
    Analyzes the graph state to determine the current workflow status.

    Checks if the workflow has paused at an interrupt (waiting for human review)
    or if it has completed execution.

    Args:
        result (Dict[str, Any]): The output from the last graph invocation.
        config (Dict): The configuration dictionary containing the thread_id.

    Returns:
        Dict[str, Any]: A dictionary containing status, draft content, and critiques.
    """
    snapshot = graph.get_state(config)
    
    # Check if the workflow is paused at the 'human_approval' node
    if snapshot.next and snapshot.next[0] == 'human_approval':
        interrupt_value = snapshot.tasks[0].interrupts[0].value
        return {
            "status": "PAUSED",
            "node": "human_approval",
            "draft": interrupt_value["draft"],
            "critiques": interrupt_value["critiques"]
        }
    
    # Otherwise, the workflow has completed
    return {
        "status": "COMPLETED",
        "final_status": result.get("final_status", "unknown"),
        "final_draft": result.get("current_draft", "")
    }

# --- API Endpoints ---

@app.get("/")
def health_check():
    """Simple health check endpoint to verify server status."""
    return {"status": "Cerina Foundry is Online"}

@app.post("/run")
async def run_workflow(request: RunRequest):
    """
    Starts a new generation session based on the user's query.

    Initializes the graph state with the user's input and executes the workflow
    until it either finishes or hits a human approval interrupt.

    Args:
        request (RunRequest): Contains the thread ID and the clinical query.
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # Initialize state with the user's query formatted for the Drafter node
    initial_state = {
        "messages": [("user", request.user_query)], 
        "iteration_count": 0, 
        "critique_history": [],
        "current_draft": "" 
    }
    
    try:
        # invoke() blocks until the graph pauses (interrupt) or finishes
        result = graph.invoke(initial_state, config=config)
        return process_graph_result(result, config)
    except Exception as e:
        print(f"SERVER ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/human-review")
async def human_review(request: ReviewRequest):
    """
    Submits human feedback to a paused workflow.

    Resumes execution from the 'human_approval' node with the user's decision
    (approve/reject) and any accompanying feedback.

    Args:
        request (ReviewRequest): Contains the decision action and feedback.
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    resume_payload = {
        "action": request.action,
        "feedback": request.feedback
    }
    
    try:
        # Resume the graph using the Command object
        result = graph.invoke(Command(resume=resume_payload), config=config)
        return process_graph_result(result, config)
    except Exception as e:
        print(f"SERVER ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    """
    Retrieves the current state of a specific session.

    Useful for polling the status of a long-running generation or restoring
    a session after a page reload.

    Args:
        thread_id (str): The unique identifier for the session.
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Pass an empty dict as the first arg because process_graph_result 
        # relies on graph.get_state(), not the direct result object.
        return process_graph_result({}, config)
    except Exception as e:
         # Return IDLE status if the state does not exist or cannot be retrieved
         return {"status": "IDLE"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)