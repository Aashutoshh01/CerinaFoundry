import sqlite3
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt
from langgraph.checkpoint.sqlite import SqliteSaver 

from state import CerinaState
from nodes import drafter_node, safety_node, clinical_node, crisis_node 

# --- Routing Logic ---

def route_safety(state: CerinaState) -> Literal["crisis_manager", "drafter", "clinical_critic"]:
    """
    Determines the next step based on safety critique results.

    Analyzes the latest critique to classify the safety risk. If the draft fails 
    safety checks, it determines whether to route to the crisis manager (for 
    severe risks/harm) or back to the drafter for a standard rewrite.

    Args:
        state (CerinaState): The current state of the workflow.

    Returns:
        Literal["crisis_manager", "drafter", "clinical_critic"]: The next node to visit.
    """
    latest_critique = state["critique_history"][-1]
    
    if latest_critique["status"] == "FAIL":
        feedback_lower = latest_critique["feedback"].lower()
        
        # Expanded keyword list to catch variations of dangerous content
        crisis_keywords = ["harm", "suicid", "kill", "death", "emergency", "danger", "hurt"]
        
        # If any keyword is found, trigger the Crisis Manager immediately
        if any(word in feedback_lower for word in crisis_keywords):
            print(f"!!! CRITICAL SAFETY FLAGGED: {feedback_lower} -> ROUTING TO CRISIS MANAGER !!!")
            return "crisis_manager"
            
        print("!!! SAFETY VIOLATION (Standard) - LOOPING BACK !!!")
        return "drafter"
    
    return "clinical_critic"


def route_clinical(state: CerinaState) -> Literal["drafter", "human_approval"]:
    """
    Evaluates clinical critique results and manages iteration limits.

    Routes the workflow back to the drafter if the clinical critique fails,
    provided the maximum iteration count has not been exceeded. Otherwise,
    proceeds to human approval to avoid infinite loops.

    Args:
        state (CerinaState): The current state of the workflow.

    Returns:
        Literal["drafter", "human_approval"]: The next node to visit.
    """
    latest_critique = state["critique_history"][-1]
    iter_count = state["iteration_count"]
    
    # Circuit Breaker: Prevent infinite loops by enforcing a max iteration limit
    if iter_count > 3:
        print("!!! MAX ITERATIONS REACHED - FORCING HUMAN REVIEW !!!")
        return "human_approval"

    if latest_critique["status"] == "FAIL":
        print(f"--- Rejection: {latest_critique['feedback']} ---")
        return "drafter"
        
    return "human_approval"

# --- Human Node ---

def human_approval_node(state: CerinaState):
    """
    Manages the human-in-the-loop approval process.

    Pauses the graph execution using the `interrupt` mechanism to await external
    user input via the API. Upon resumption, processes the user's decision
    (approve or reject).

    Args:
        state (CerinaState): The current state of the workflow.

    Returns:
        Command: A LangGraph Command object directing the flow to END or back to drafter.
    """
    print("\n--- 👤 HUMAN APPROVAL REQUIRED ---")
    
    # Interrupt execution to wait for API input
    user_feedback = interrupt({
        "draft": state["current_draft"],
        "critiques": state["critique_history"]
    })
    
    # Resume logic based on user action
    action = user_feedback.get("action")
    
    if action == "approve":
        print("--- ✅ HUMAN APPROVED ---")
        return Command(goto=END, update={"final_status": "approved"})
    
    elif action == "reject":
        print("--- ❌ HUMAN REJECTED ---")
        # Loop back to Drafter with the human's specific feedback
        return Command(goto="drafter", update={
            "critique_history": [{
                "agent_name": "Human", 
                "score": 0, 
                "feedback": user_feedback.get("feedback", "Human rejected"), 
                "status": "FAIL"
            }]
        })

# --- Building the Graph ---

# Initialize the StateGraph
builder = StateGraph(CerinaState)

# Add Nodes
builder.add_node("drafter", drafter_node)
builder.add_node("safety_guardian", safety_node)
builder.add_node("clinical_critic", clinical_node)
builder.add_node("human_approval", human_approval_node)
builder.add_node("crisis_manager", crisis_node) 

# Define Standard Flow
builder.add_edge(START, "drafter")
builder.add_edge("drafter", "safety_guardian")

# Define Conditional Logic (Routing)
builder.add_conditional_edges("safety_guardian", route_safety)
builder.add_conditional_edges("clinical_critic", route_clinical)

# Wiring for Crisis Manager
# If a crisis occurs, route to human approval for final oversight
builder.add_edge("crisis_manager", "human_approval") 

# --- Persistence ---
# Initialize SQLite checkpointing for state persistence across interactions
conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(conn)

# Compile the graph
graph = builder.compile(checkpointer=checkpointer)